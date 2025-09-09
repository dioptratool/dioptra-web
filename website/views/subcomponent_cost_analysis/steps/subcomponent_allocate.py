from decimal import Decimal
from decimal import DecimalException
from urllib.parse import quote

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _, gettext_lazy as _l
from django.views.generic import UpdateView
from django.views.generic.detail import SingleObjectMixin
from django_filters.views import FilterView

from ombucore.admin import panel_commands
from ombucore.admin.buttons import CancelButton, SubmitButton
from ombucore.admin.views import FilterMixin
from ombucore.admin.views.base import FormView as PanelsFormView
from website.filterset import AllocateCostTypeGrantSiteFilterSet
from website.forms.subcomponent import BulkSubcomponentAnalysisAllocationForm
from website.models import (
    Analysis,
    AnalysisCostTypeCategoryGrant,
    CostLineItemConfig,
    Settings,
)
from website.models import CostLineItem
from website.views.mixins import (
    AllocateMixin,
    AnalysisStepMixin,
)
from website.views.mixins import (
    AnalysisPermissionRequiredMixin,
    AnalysisStepFiltersetMixin,
)
from website.workflows import AnalysisWorkflow


class SubcomponentsAllocate(
    AnalysisPermissionRequiredMixin,
    AnalysisStepMixin,
    UpdateView,
):
    step_name = "allocate-subcomponent-costs"
    permission_required = "website.change_analysis"
    title = None
    help_text = None
    template_name = "subcomponent-cost-analysis/allocate-subcomponents.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.analysis = self.get_object()
        self.dioptra_settings = Settings.objects.first()
        self.setup_step()

    def setup_step(self):
        super().setup_step()
        self.workflow = AnalysisWorkflow(analysis=self.analysis)

    def dispatch(self, request, *args, **kwargs):
        if (
            not self.analysis.subcomponent_cost_analysis
            or self.analysis.interventioninstance_set.count() != 1
        ):
            return redirect(
                reverse(
                    "analysis-insights",
                    kwargs={
                        "pk": self.analysis.pk,
                    },
                )
            )
        if not self.step or not self.step.dependencies_met:
            return redirect(
                reverse(
                    "subcomponent-cost-analysis",
                    kwargs={
                        "analysis_pk": self.analysis.pk,
                        "pk": self.analysis.subcomponent_cost_analysis.pk,
                    },
                )
            )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = {}
        if self.title:
            context["title"] = self.title
        if self.help_text:
            context["help_text"] = self.help_text

        context["dioptra_settings"] = self.dioptra_settings
        context["analysis"] = self.analysis
        context["subcomponent_cost_analysis"] = self.analysis.subcomponent_cost_analysis
        context["workflow"] = self.workflow
        context["step"] = self.step

        return context

    def get(self, request, *args, **kwargs):
        """
        Return redirect to first CostType to allocate costs by subcomponent.
        """
        if len(self.step.steps):
            return redirect(self.step.steps[0].get_href())
        else:
            return redirect(self.workflow.get_next(self.step).get_href())


class SubcomponentsAllocatebyCostTypeGrant(
    FilterMixin,
    AnalysisPermissionRequiredMixin,
    AnalysisStepFiltersetMixin,
    AllocateMixin,
    FilterView,
):
    step_name = "allocate-subcomponent-costs"
    permission_required = "website.change_analysis"
    template_name = "subcomponent-cost-analysis/subcomponent-analysis-allocate-cost_type-grant.html"
    model = CostLineItem
    filterset_class = AllocateCostTypeGrantSiteFilterSet

    title = ""
    help_text = _("")

    def setup_step(self):
        self.object = self.get_object()
        self.analysis = self.object
        self.workflow = AnalysisWorkflow(self.analysis)
        self.parent_step = self.workflow.get_step(self.step_name)

        self.step = None
        for substep in self.parent_step.steps:
            encoded_request_path = quote(self.request.path)
            if substep.get_href() == encoded_request_path:
                self.step = substep
                break
        if self.step is None:
            self.cost_type_category_grants = AnalysisCostTypeCategoryGrant.objects.none()
        else:
            self.cost_type_category_grants = (
                self.analysis.cost_type_category_grants.filter(
                    cost_type_category__cost_type=self.step.cost_type,
                    grant=self.step.grant,
                )
                .select_related("cost_type_category", "cost_type_category__category")
                .prefetch_related(
                    "cost_type_category__analysis__unfiltered_cost_line_items",
                    "cost_type_category__analysis__unfiltered_cost_line_items__config__allocations",
                )
                .distinct()
            )

    def modify_queryset(self, queryset):
        return (
            queryset.filter(
                analysis_id=self.object.id,
                config__cost_type=self.step.cost_type,
                grant_code=self.step.grant,
            )
            .select_related("config", "config__cost_type")
            .prefetch_related(
                "transactions",
                "config",
                "config__allocations",
                "config__category",
                "config__allocations__intervention_instance",
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

        context["subcomponent_analysis_averages"] = self._get_cost_line_averages_by_cost_type_grant()
        context["subcomponent_analysis_average_all"] = self._get_cost_line_average_all()

        cost_line_items_count = 0
        cost_type_category_grant: AnalysisCostTypeCategoryGrant
        for cost_type_category_grant in self.cost_type_category_grants:
            cost_line_items_count += cost_type_category_grant.get_cost_line_items().count()

        context.update(
            {
                "cost_line_items_count": cost_line_items_count,
                "cost_type_category_grants": self.cost_type_category_grants,
                "title": "How is each cost item allocated between sub-components?",
                "help_text": "Set the percentage of each cost item across each sub-component. All percentages for each "
                "sub-component must equal 100% in order to complete this analysis. If you are not able "
                "to allocate sub-component percentages for any cost item, you may click “Skip”, and "
                "Dioptra will automatically calculate and apply suggested percentages for that cost item.",
            }
        )

        self.filterset.form.fields["site_code"].choices = (
            self.object.site_codes_choices_from_cost_line_items()
        )

        return context

    def _get_cost_line_averages_by_cost_type_grant(self) -> dict:
        cost_line_averages = {}
        for cost_type_category_grant in self.cost_type_category_grants:
            cost_type = cost_type_category_grant.cost_type_category.cost_type
            category = cost_type_category_grant.cost_type_category.category
            grant = cost_type_category_grant.grant

            if cost_type.name not in cost_line_averages:
                cost_line_averages[cost_type.name] = {}
            if category.name not in cost_line_averages[cost_type.name]:
                cost_line_averages[cost_type.name][category.name] = {}
            if grant not in cost_line_averages[cost_type.name][category.name]:
                cost_line_averages[cost_type.name][category.name][grant] = (
                    self.analysis.subcomponent_cost_analysis.cost_line_item_average(
                        cost_type=cost_type, category=category, grant=grant
                    )
                )
        return cost_line_averages

    def _get_cost_line_average_all(self) -> list:
        return list(
            zip(
                self.analysis.subcomponent_cost_analysis.subcomponent_labels,
                self.analysis.subcomponent_cost_analysis.cost_line_item_average(),
            )
        )

    def _get_cost_line_item_ids_and_allocations_from_post(self, request):
        data = {}
        for input_name, allocation in request.POST.items():
            if input_name.startswith("cost_line_item_") and "subcomponent_allocation" in input_name:
                name_pieces = input_name.split("_")
                cost_line_item_id = int(name_pieces[3])

                # If we are skipping things we clear the data we saved.
                if name_pieces[-1] == "skip":
                    data[cost_line_item_id] = {}
                    data[cost_line_item_id]["skipped"] = True
                    continue
                # Otherwise we should save things.
                if cost_line_item_id not in data:
                    data[cost_line_item_id] = {}
                data[cost_line_item_id]["skipped"] = False

                subcomponent_allocation_idx = str(name_pieces[-1])
                if allocation != "":
                    data[cost_line_item_id][subcomponent_allocation_idx] = allocation
                elif allocation == "":
                    data[cost_line_item_id][subcomponent_allocation_idx] = 0
        return data

    def _validate_data(self, data):
        errors = {}
        valid_data = {}
        for cost_line_item_id, allocations in data.items():
            allocation_sum = 0
            valid_data[cost_line_item_id] = {}
            valid_data[cost_line_item_id]["allocations"] = {}

            if allocations.get("skipped"):
                # IF we are skipping we bypass and all the rest of the data
                valid_data[cost_line_item_id]["skipped"] = True
                continue
            valid_data[cost_line_item_id]["skipped"] = False
            for k, v in allocations.items():
                if k == "skipped":
                    continue
                allocation = str(v).strip().replace("%", "")
                try:
                    allocation = Decimal(allocation)
                except DecimalException:
                    errors[cost_line_item_id] = _("Not a number")

                if allocation < 0 or allocation > 100:
                    errors[cost_line_item_id] = _("Invalid allocation (0-100)")
                allocation_sum += allocation
                # We round trip the value into a Decimal and back into a string to store it in the db
                valid_data[cost_line_item_id]["allocations"][k] = str(allocation)
            if allocation_sum != Decimal(100):
                errors[cost_line_item_id] = _("Allocations must total 100%")

        return valid_data, errors

    def post(self, request, *args, **kwargs):
        filterset_class = self.get_filterset_class()
        self.filterset = self.get_filterset(filterset_class)
        self.object_list = self.modify_queryset(self.filterset.qs)
        submitted_data = self._get_cost_line_item_ids_and_allocations_from_post(request)
        data, errors = self._validate_data(submitted_data)
        if errors:
            context = self.get_context_data(errors=errors)
            # We should attempt to save the items that were not in error
            good_data = {key: data[key] for key in data if key not in errors}
            if good_data:
                self._save_data(good_data)
            context["previous_data"] = submitted_data
            return self.render_to_response(context)
        else:
            self._save_data(data)

        query = f"?{request.GET.urlencode()}" if request.GET else ""
        return redirect(self.request.path + query)

    def _save_data(self, data):
        for cost_line_item_id, allocation in data.items():
            cost_line_item = self.analysis.cost_line_items.get(pk=cost_line_item_id)
            if allocation.get("skipped"):
                cost_line_item.config.subcomponent_analysis_allocations_skipped = True
                cost_line_item.config.subcomponent_analysis_allocations = {}
            else:
                cost_line_item.config.subcomponent_analysis_allocations_skipped = False
                cost_line_item.config.subcomponent_analysis_allocations = allocation["allocations"]
            cost_line_item.config.save()


class SubcomponentsAllocateBulk(
    AnalysisPermissionRequiredMixin,
    LoginRequiredMixin,
    PanelsFormView,
    SingleObjectMixin,
):
    model = Analysis
    form_class = BulkSubcomponentAnalysisAllocationForm
    template_name = "panel-form-bulk-subcomponent-allocate.html"

    supertitle = _l("Selected Cost Items")
    title = _l("Set Sub-component Allocation Percentage")
    permission_required = "website.change_analysis"
    buttons = [
        SubmitButton(text=_("Save")),
        CancelButton(),
    ]
    help_text = _("")

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.object = self.get_object()
        self.analysis = self.object
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
        kwargs["extra_label_fields"] = self.analysis.subcomponent_cost_analysis.subcomponent_labels

        return kwargs

    def form_valid(self, form):
        config_ids = form.cleaned_data["config_ids"]
        allocations = {}
        for field_name, value in form.cleaned_data.items():
            if field_name.startswith("subcomponent_allocation_"):
                allocations[str(int(field_name.split("_")[-1]))] = value

        self._assign_allocations(config_ids, allocations)
        return super().form_valid(form)

    def _assign_allocations(self, config_ids, allocations):
        update_kwargs = {}
        update_kwargs["subcomponent_analysis_allocations"] = allocations
        update_kwargs["subcomponent_analysis_allocations_skipped"] = False

        CostLineItemConfig.objects.filter(cost_line_item__analysis_id=self.analysis.id).filter(
            id__in=config_ids
        ).update(**update_kwargs)

    def get_success_message(self, cleaned_data):
        return _("%(count)s cost items updated") % {"count": len(self.config_ids)}

    def get_success_commands(self):
        return [panel_commands.Resolve()]
