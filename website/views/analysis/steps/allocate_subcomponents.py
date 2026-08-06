from decimal import Decimal, DecimalException
from urllib.parse import quote

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect
from django.utils.translation import gettext as _, gettext_lazy as _l
from django.views.generic.detail import SingleObjectMixin
from django_filters.views import FilterView

from ombucore.admin import panel_commands
from ombucore.admin.buttons import CancelButton, SubmitButton
from ombucore.admin.views import FilterMixin
from ombucore.admin.views.base import FormView as PanelsFormView
from website.filterset import AllocateCostTypeGrantSiteFilterSet
from website.forms.analysis import AllocateSubcomponentsBulkForm
from website.models import Analysis, CostLineItem, CostLineItemConfig, InterventionInstance
from website.models.cost_type import ProgramCost
from website.models.subcomponent import SubcomponentCostAllocation
from website.views.mixins import (
    AnalysisPermissionRequiredMixin,
    AnalysisStepDetailMixin,
    AnalysisStepFiltersetMixin,
)
from website.workflows import AnalysisWorkflow


def _allocation_str(value: Decimal) -> str:
    """JSON-friendly string without trailing zeros (Decimal("60.0000") -> "60")."""
    text = f"{value:f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


class AllocateSubcomponents(AnalysisPermissionRequiredMixin, AnalysisStepDetailMixin):
    """
    Redirects to the first intervention/grant to allocate sub-components for.
    """

    step_name = "allocate-subcomponents"
    permission_required = "website.change_analysis"
    title = ""
    help_text = _("")

    def get(self, request, *args, **kwargs):
        if len(self.step.steps):
            return redirect(self.step.steps[0].get_href())
        else:
            return redirect(self.workflow.get_next(self.step).get_href())


class AllocateSubcomponentsInterventionGrant(
    FilterMixin,
    AnalysisPermissionRequiredMixin,
    AnalysisStepFiltersetMixin,
    FilterView,
):
    step_name = "allocate-subcomponents"
    template_name = "analysis/allocate-subcomponents-intervention-grant.html"
    permission_required = "website.change_analysis"
    model = CostLineItem
    filterset_class = AllocateCostTypeGrantSiteFilterSet
    title = _l("How is each cost item allocated between sub-components?")
    help_text = _l(
        "Set the percentage of each cost item toward its sub-components. If the percentage "
        'allocation is not known, select "Skip" to exclude that cost item from the allocation.'
    )

    def setup_step(self):
        super().setup_step()
        self.step = None
        if self.parent_step is None:
            return
        for substep in self.parent_step.steps:
            encoded_request_path = quote(self.request.path)
            if substep.get_href() == encoded_request_path:
                self.step = substep
                break

    def modify_queryset(self, queryset):
        return (
            queryset.cost_type_category_items()
            .filter(
                analysis_id=self.object.id,
                grant_code=self.step.grant,
                config__cost_type__type=ProgramCost.id,
                config__allocations__intervention_instance=self.step.intervention_instance,
                config__allocations__allocation__gt=0,
            )
            .select_related("config", "config__cost_type", "config__category")
            .prefetch_related(
                "transactions",
                "config__allocations",
                "config__allocations__intervention_instance",
                "config__subcomponent_cost_allocations",
            )
            .order_by(
                "grant_code",
                "budget_line_description",
                "site_code",
                "sector_code",
                "account_code",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        cost_line_items = list(self.object_list)
        cost_type_category_grants = (
            self.analysis.cost_type_category_grants.filter(
                grant=self.step.grant,
                cost_type_category__cost_type__type=ProgramCost.id,
            )
            .select_related("cost_type_category", "cost_type_category__category")
            .prefetch_related(
                # Needed by subcomponent_allocation_complete_for(); without these
                # each category badge would re-query the whole analysis.
                "cost_type_category__analysis__unfiltered_cost_line_items",
                "cost_type_category__analysis__unfiltered_cost_line_items__config__allocations",
                "cost_type_category__analysis__unfiltered_cost_line_items__config__subcomponent_cost_allocations",
            )
            .distinct()
        )

        category_items = []
        categories_complete = {}
        for cost_type_category_grant in cost_type_category_grants:
            items = [
                cli
                for cli in cost_line_items
                if cli.config.cost_type_id == cost_type_category_grant.cost_type_category.cost_type_id
                and cli.config.category_id == cost_type_category_grant.cost_type_category.category_id
            ]
            if not items:
                continue
            category_items.append((cost_type_category_grant, items))
            categories_complete[cost_type_category_grant.id] = (
                cost_type_category_grant.subcomponent_allocation_complete_for(self.step.intervention_instance)
            )

        context.update(
            {
                "cost_line_items_count": len(cost_line_items),
                "category_items": category_items,
                "categories_complete": categories_complete,
            }
        )

        self.filterset.form.fields["site_code"].choices = (
            self.object.site_codes_choices_from_cost_line_items()
        )

        next_step = self.step.get_next()
        if next_step and not next_step.dependencies_met:
            context["next_message"] = _(
                "You must finish setting the allocation for all cost items before moving on."
            )

        return context

    def post(self, request, *args, **kwargs):
        filterset_class = self.get_filterset_class()
        self.filterset = self.get_filterset(filterset_class)
        self.object_list = self.modify_queryset(self.filterset.qs)
        data = self._get_subcomponent_allocations_from_post(request)
        data, errors = self._validate_subcomponent_data(data)
        if errors:
            context = self.get_context_data(errors=errors)

            # We should attempt to save the items that were not in error
            good_data = {key: data[key] for key in data if key not in errors}
            if good_data:
                self._save_subcomponent_data(good_data)
                self.workflow.invalidate_step("insights")
                self.workflow.calculate_if_possible()

            return self.render_to_response(context)
        else:
            self._save_subcomponent_data(data)
            self.workflow.invalidate_step("insights")
            self.workflow.calculate_if_possible()
        query = f"?{request.GET.urlencode()}" if request.GET else ""
        return redirect(self.request.path + query)

    def _get_subcomponent_allocations_from_post(self, request):
        data = {}
        prefix = "cost_line_item_subcomponent_allocation_"
        subcomponent_analysis_id = self.step.subcomponent_analysis.id
        for input_name, allocation in request.POST.items():
            if not input_name.startswith(prefix):
                continue

            parts = input_name[len(prefix) :].split("_")
            if len(parts) != 3:
                continue
            cost_line_item_id, input_analysis_id, subcomponent_idx = parts
            try:
                cost_line_item_id = int(cost_line_item_id)
                input_analysis_id = int(input_analysis_id)
            except ValueError:
                continue
            if input_analysis_id != subcomponent_analysis_id:
                continue

            row = data.setdefault(cost_line_item_id, {"allocations": {}, "skipped": False})
            if subcomponent_idx == "skip":
                row["allocations"] = {}
                row["skipped"] = True
                continue
            if row["skipped"]:
                continue
            row["allocations"][subcomponent_idx] = allocation
        return data

    def _validate_subcomponent_data(self, data):
        """
        Partial rows are valid and saved (completeness still requires every
        label present and a total of exactly 100 — see
        subcomponent_allocation_complete); only over-allocation is rejected.
        Blank inputs are not stored, so an all-blank row saves as
        allocations={} and clears previously saved values.
        """
        valid_data = {}
        errors = {}
        allowed_ids = {cli.id for cli in self.object_list}

        for cost_line_item_id, submitted in data.items():
            if cost_line_item_id not in allowed_ids:
                continue
            if submitted["skipped"]:
                valid_data[cost_line_item_id] = {"allocations": {}, "skipped": True}
                continue

            allocation_sum = Decimal(0)
            allocations = {}
            row_error = None
            for idx, allocation in submitted["allocations"].items():
                allocation = str(allocation).strip().replace("%", "")
                if allocation == "":
                    continue
                try:
                    allocation = Decimal(allocation)
                except DecimalException:
                    row_error = _("Not a number")
                    continue
                if allocation < 0 or allocation > 100:
                    row_error = _("Invalid allocation (0-100)")
                allocation_sum += allocation
                allocations[str(idx)] = str(allocation)

            if row_error is None and allocation_sum > Decimal(100):
                row_error = _("Allocations cannot total more than 100%")
            if row_error:
                errors[cost_line_item_id] = row_error

            valid_data[cost_line_item_id] = {"allocations": allocations, "skipped": False}

        return valid_data, errors

    def _save_subcomponent_data(self, data):
        if not data:
            return

        subcomponent_analysis = self.step.subcomponent_analysis
        cost_line_items = self.analysis.cost_line_items.filter(pk__in=data.keys()).select_related("config")
        SubcomponentCostAllocation.objects.bulk_create(
            [
                SubcomponentCostAllocation(
                    subcomponent_analysis=subcomponent_analysis,
                    cli_config=cost_line_item.config,
                    allocations=data[cost_line_item.id]["allocations"],
                    skipped=data[cost_line_item.id]["skipped"],
                )
                for cost_line_item in cost_line_items
            ],
            update_conflicts=True,
            unique_fields=["subcomponent_analysis", "cli_config"],
            update_fields=["allocations", "skipped"],
        )


class AllocateSubcomponentsBulk(
    AnalysisPermissionRequiredMixin,
    LoginRequiredMixin,
    PanelsFormView,
    SingleObjectMixin,
):
    model = Analysis
    form_class = AllocateSubcomponentsBulkForm
    template_name = "panel-form-bulk-subcomponent-allocate.html"
    supertitle = _l("Selected Cost Items")
    title = _l("Set Allocation Percentage")
    permission_required = "website.change_analysis"
    buttons = [
        SubmitButton(text=_l("Save")),
        CancelButton(),
    ]
    help_text = _l("What is the percent allocation of the selected cost items to the sub-components?")

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.object = self.get_object()
        self.analysis = self.object
        try:
            self.intervention_instance = self.analysis.interventioninstance_set.select_related(
                "subcomponent_cost_analysis"
            ).get(pk=kwargs["intervention_instance_pk"])
        except InterventionInstance.DoesNotExist:
            raise Http404(_("No intervention instance found matching the query"))
        if not hasattr(self.intervention_instance, "subcomponent_cost_analysis"):
            raise Http404(_("Intervention instance has no subcomponent cost analysis"))
        self.subcomponent_analysis = self.intervention_instance.subcomponent_cost_analysis
        self.config_ids = self._get_config_ids(request)

    def _get_config_ids(self, request):
        if request.method == "POST":
            return request.POST.getlist("config_ids")
        else:
            # config_ids are a comma-separated string (e.g. `12,44,2,34`).
            return request.GET.get("config_ids", "").split(",")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["initial"]["config_ids"] = self.config_ids
        kwargs["subcomponent_labels"] = self.subcomponent_analysis.subcomponent_labels or []
        return kwargs

    def form_valid(self, form):
        config_ids = form.cleaned_data["config_ids"]
        prefix = "subcomponent_allocation_"
        allocations = {
            name[len(prefix) :]: _allocation_str(value)
            for name, value in form.cleaned_data.items()
            if name.startswith(prefix)
        }
        # Restrict to the rows this step actually shows (program costs in this
        # grant with a positive allocation to this intervention instance) so
        # forged config_ids can't reach rows outside the step.
        configs = list(
            CostLineItemConfig.objects.filter(
                cost_line_item__in=self.analysis.cost_line_items.cost_type_category_items(),
                cost_line_item__grant_code=self.kwargs["grant"],
                cost_type__type=ProgramCost.id,
                allocations__intervention_instance=self.intervention_instance,
                allocations__allocation__gt=0,
                id__in=config_ids,
            )
        )
        SubcomponentCostAllocation.objects.bulk_create(
            [
                SubcomponentCostAllocation(
                    subcomponent_analysis=self.subcomponent_analysis,
                    cli_config=config,
                    allocations=dict(allocations),
                    skipped=False,
                )
                for config in configs
            ],
            update_conflicts=True,
            unique_fields=["subcomponent_analysis", "cli_config"],
            update_fields=["allocations", "skipped"],
        )
        workflow = AnalysisWorkflow(self.analysis)
        workflow.invalidate_step("insights")
        workflow.calculate_if_possible()
        return super().form_valid(form)

    def get_success_message(self, cleaned_data):
        return _("{count} cost items updated").format(count=len(self.config_ids))

    def get_success_commands(self):
        return [panel_commands.Resolve()]
