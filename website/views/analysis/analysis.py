from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic import DetailView
from django.views.generic.base import TemplateView

from ombucore.admin.panel_commands import Resolve
from ombucore.admin.views.base import FormView as PanelsFormView
from website.forms.analysis import (
    AnalysisLessonsEditorForm,
    SaveSuggestedToAllConfirmForm,
)
from website.forms.cost_line_item import (
    AddCostLineItemForm,
    ClientTimeCostLineItemForm,
    InKindCostLineItemForm,
    OtherHQCostLineItemForm,
)
from website.models import (
    Analysis,
    AnalysisCostType,
    AnalysisCostTypeCategoryGrant,
    CostLineItem,
)
from website.models.cost_line_item import CostLineItemInterventionAllocation
from website.views.mixins import AnalysisObjectMixin, AnalysisPermissionRequiredMixin
from website.workflows import AnalysisWorkflow


class AnalysisDetailView(AnalysisObjectMixin, LoginRequiredMixin, DetailView):
    """
    Serves as the main entrypoint for linking to an analysis.

    Redirects to the latest-incomplete step in the analysis workflow.
    """

    model = Analysis

    def get(self, request, *args, **kwargs):
        self.analysis = self.get_object()
        workflow = AnalysisWorkflow(self.analysis)
        step = workflow.get_last_incomplete_or_last()
        return redirect(step.get_href())


class AnalysisLessonsEditorView(AnalysisPermissionRequiredMixin, AnalysisObjectMixin, PanelsFormView):
    success_message = "Lesson was successfully updated for <strong>%(title)s</strong>"

    permission_required = "website.change_analysis"
    form_class = AnalysisLessonsEditorForm
    title = "Edit"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.analysis = self.get_object()
        self.lesson_field = kwargs.pop("lesson_field", None)
        if not self.lesson_field:
            raise Http404(_("Lesson field type not found"))

    def get_supertitle(self):
        if self.lesson_field == "breakdown_lesson":
            return "Takeaways from the cost breakdown"
        else:
            return "Lessons and takeaways from the analysis results"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["analysis"] = self.analysis
        kwargs["lesson_field"] = self.lesson_field

        return kwargs

    def form_valid(self, form):
        lesson_value = form.cleaned_data["lesson"]
        try:
            setattr(self.analysis, self.lesson_field, lesson_value)
            self.analysis.save(update_fields=[self.lesson_field])
        except ValidationError as err:
            messages.error(self.request, err.message)

        form.cleaned_data["title"] = self.analysis.title
        return super().form_valid(form)

    def get_success_commands(self):
        return [
            Resolve(
                {
                    "operation": "saved",
                }
            )
        ]


class SaveSuggestedToAllConfirmView(AnalysisPermissionRequiredMixin, AnalysisObjectMixin, PanelsFormView):
    title = None
    supertitle = "Save Suggested % to All Items"
    template_name = "panel-form-save-suggested.html"
    success_message = "Suggested &#37; updated successfully."
    permission_required = "website.change_analysis"
    form_class = SaveSuggestedToAllConfirmForm

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.analysis = self.get_object()
        self.workflow = AnalysisWorkflow(self.analysis)
        self.parent_step = self.workflow.get_step("allocate")
        self.step = None
        for substep in self.parent_step.steps:
            if substep.get_href() == reverse("analysis-allocate-cost_type-grant", kwargs=self.kwargs):
                self.step = substep
                break

        self.cost_type_category_grants = self.analysis.cost_type_category_grants.filter(
            cost_type_category__cost_type=self.step.cost_type,
            grant=self.step.grant,
        ).select_related("cost_type_category")

    def form_valid(self, form):
        response = super().form_valid(form)
        self._apply_suggested_value_to_all_cost_line_items()
        self.workflow.invalidate_step("insights")
        self.workflow.calculate_if_possible()
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["analysis"] = self.analysis
        ctx["workflow"] = self.workflow
        ctx["step"] = self.step
        return ctx

    def get_success_commands(self):
        return [
            Resolve(
                {
                    "operation": "saved",
                }
            )
        ]

    def _apply_suggested_value_to_all_cost_line_items(self):
        suggested_allocations = self.analysis.get_suggested_allocations()

        data = {}
        for cost_type_category_grant in self.cost_type_category_grants:
            for cost_line_item in cost_type_category_grant.get_cost_line_items():
                data[cost_line_item.id] = {}
                for intervention_instance in self.analysis.interventioninstance_set.all():
                    this_suggested_allocation = (
                        suggested_allocations.get(self.step.cost_type.id, {})
                        .get(self.step.grant, {})
                        .get(intervention_instance)
                    )
                    percentage = str(this_suggested_allocation[2])

                    data[cost_line_item.id][intervention_instance] = percentage

        # Due to the number of cost line items that need to be updated here we do them in bulk at the cost of memory.
        #  If memory is a concern you should be be able to chunk the first cost_line_items query
        #  and everything else should be fine.

        # Retrieve all the relevant cost line items at once
        cost_line_item_ids = data.keys()
        cost_line_items = self.analysis.cost_line_items.filter(pk__in=cost_line_item_ids).values(
            "id", "config"
        )
        cost_line_item_map = {cli["id"]: cli for cli in cost_line_items}

        # Retrieve existing allocations
        existing_allocations = CostLineItemInterventionAllocation.objects.filter(
            cli_config_id__in=[cli["config"] for cli in cost_line_items],
            intervention_instance__in=self.analysis.interventioninstance_set.all(),
        )
        existing_allocation_map = {
            (a.cli_config_id, a.intervention_instance): a for a in existing_allocations
        }

        # Prepare new and updated allocations
        new_allocations = []
        updated_allocations = []

        for cost_line_item_id, allocations in data.items():
            cost_line_item = cost_line_item_map[cost_line_item_id]
            for intervention_instance, allocation in allocations.items():
                allocation_key = (cost_line_item["config"], intervention_instance)
                if allocation_key in existing_allocation_map:
                    allocation_obj = existing_allocation_map[allocation_key]
                    allocation_obj.allocation = allocation
                    updated_allocations.append(allocation_obj)
                else:
                    new_allocations.append(
                        CostLineItemInterventionAllocation(
                            cli_config_id=cost_line_item["config"],
                            intervention_instance=intervention_instance,
                            allocation=allocation,
                        )
                    )

        # Use bulk create and update
        with transaction.atomic():
            if new_allocations:
                CostLineItemInterventionAllocation.objects.bulk_create(new_allocations)
            if updated_allocations:
                CostLineItemInterventionAllocation.objects.bulk_update(updated_allocations, ["allocation"])


class CostLineItemTransactions(PermissionRequiredMixin, DetailView):
    template_name = "analysis/analysis-table/_analysis-table-transaction-rows-content.html"
    permission_required = "website.change_analysis"
    model = CostLineItem

    def has_permission(self):
        perms = self.get_permission_required()
        analysis = self.get_object().analysis
        return self.request.user.has_perms(perms, analysis)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["transactions"] = self.object.transactions.all()
        context["type"] = self.request.GET.get("type")
        return context


class CostLineItemUpsertView(AnalysisPermissionRequiredMixin, AnalysisObjectMixin, PanelsFormView):
    permission_required = "website.change_analysis"
    form_class = AddCostLineItemForm

    def __init__(self, **kwargs):
        self.analysis = None
        self.cost_line_item = None
        self.cost_type = None
        super().__init__(**kwargs)

    def setup(self, request, *args, **kwargs):
        cost_pk = kwargs.pop("cost_pk", None)
        super().setup(request, *args, **kwargs)

        self.analysis = self.get_object()
        self.cost_type = kwargs.get("cost_type", None)
        if cost_pk:
            self.cost_line_item = CostLineItem.objects.filter(pk=cost_pk).first()
            if not self.cost_line_item:
                raise Http404(_(f"No CostLineItem exists for Id={cost_pk}"))
            if self.cost_line_item.analysis_id != self.analysis.id:
                return HttpResponseBadRequest(
                    _(f"CostLineItem Id={cost_pk} does not match Analysis Id={self.analysis.pk}")
                )

        super().setup(request, *args, **kwargs)

    def _set_form_class(self):
        if self.cost_type == AnalysisCostType.CLIENT_TIME:
            self.form_class = ClientTimeCostLineItemForm
        elif self.cost_type == AnalysisCostType.IN_KIND:
            self.form_class = InKindCostLineItemForm
        elif self.cost_type == AnalysisCostType.OTHER_HQ:
            self.form_class = OtherHQCostLineItemForm

    def get_form(self, form_class=None):
        self._set_form_class()
        return super().get_form(form_class=self.form_class)

    def get_supertitle(self):
        return self.form_class.SUPER_TITLE

    def get_success_message(self, cleaned_data):
        return _(f"You have successfully saved a {self.form_class.SUB_TITLE}")

    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        if self.cost_line_item:
            form_kwargs.update({"instance": self.cost_line_item})
        else:
            form_kwargs["initial"].update({"analysis": self.analysis, "total_cost": 0})
        return form_kwargs

    def get_context_data(self, **kwargs):
        self._set_form_class()

        form_kwargs = self.get_form_kwargs()
        kwargs["form"] = self.form_class(**form_kwargs)

        context = super().get_context_data(**kwargs)
        context["title"] = self.form_class.SUB_TITLE
        return context

    def form_valid(self, form):
        self.cost_line_item = form.save()

        # Hack to make sure adding other CostLineItems correctly refreshes output costs
        workflow = AnalysisWorkflow(self.analysis)
        workflow.calculate_if_possible()

        return super().form_valid(form)

    def get_success_commands(self):
        return [
            Resolve(
                {
                    "operation": "saved",
                }
            )
        ]


class GrantCategoryHelp(PermissionRequiredMixin, TemplateView):
    template_name = "help/analysis-grant-help.html"
    permission_required = "website.change_analysis"
    model = AnalysisCostTypeCategoryGrant

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)

        cost_type_category_grant = self.model.objects.filter(pk=context["pk"]).first()
        if not cost_type_category_grant:
            raise Http404(_(f"No AnalysisCostTypeCategoryGrant exists for ID={context['pk']}"))

        context["help_text"] = cost_type_category_grant.cost_type_category.category.help_text
        return self.render_to_response(context)
