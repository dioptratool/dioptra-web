from urllib.parse import quote

from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic import DetailView

from website.models import AnalysisCostType
from website.views.mixins import AnalysisPermissionRequiredMixin, AnalysisStepMixin


class AddOtherCosts(AnalysisPermissionRequiredMixin, AnalysisStepMixin, DetailView):
    """
    Redirects to the first cost_type to confirm categories.
    """

    step_name = "add-other-costs"
    permission_required = "website.change_analysis"
    title = ""
    help_text = _("")

    def get(self, request, *args, **kwargs):
        """
        Return redirect to first Other Cost to add.
        """
        if not self.step.steps:
            return redirect(reverse("analysis", kwargs={"pk": self.analysis.pk}))

        url = self.step.steps[0].get_href()
        for step in self.step.steps:
            if not step.is_complete:
                url = step.get_href()
                break
        return redirect(url)


class AddOtherCostsDetail(AnalysisPermissionRequiredMixin, AnalysisStepMixin, DetailView):
    step_name = "add-other-costs"
    template_name = "analysis/add-other-costs.html"
    permission_required = "website.change_analysis"
    title = ""
    help_text = _("")

    def setup_step(self):
        super().setup_step()

        self.step = None
        for substep in self.parent_step.steps:
            encoded_request_path = quote(self.request.path)
            if substep.get_href() == encoded_request_path:
                self.step = substep
                break

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.step:
            return context
        if self.step.cost_type not in (
            AnalysisCostType.CLIENT_TIME,
            AnalysisCostType.IN_KIND,
            AnalysisCostType.OTHER_HQ,
        ):
            return context

        show_allocation = True
        additional_fields = {}
        if self.step.cost_type == AnalysisCostType.CLIENT_TIME:
            show_allocation = False
            additional_fields = {
                "loe_or_unit": "Number of Clients",
                "quantity": "Hours per Client",
                "unit_cost": "Hourly Cost",
                "config.get_sole_allocator_name": "Intervention",
            }
        elif self.step.cost_type == AnalysisCostType.IN_KIND:
            additional_fields = {
                "quantity": "Quantity",
                "unit_cost": "Unit Cost",
            }
        elif self.step.cost_type == AnalysisCostType.OTHER_HQ:
            pass

        intervention_links_in_order = []
        allocations_order = {}
        if show_allocation:
            for intervention_instance in self.analysis.interventioninstance_set.all():
                intervention_links_in_order.append(intervention_instance)
                allocations_order[intervention_instance.intervention.id] = intervention_instance.order

        context.update(
            {
                "intervention_links_in_order": intervention_links_in_order,
                "additional_fields": additional_fields,
                "allocation_order": allocations_order,
                "analysis": self.analysis,
                "cost_line_items": self.step.cost_line_items,
                "cost_line_item_count": self.step.cost_line_items.count(),
                "cost_type": int(self.step.cost_type),
                "show_allocation": show_allocation,
                "title": self.step.page_title,
                "total_cost": sum([line_item.total_cost for line_item in self.step.cost_line_items]),
                "show_cost_type_column": self.step.cost_type == AnalysisCostType.OTHER_HQ,
            }
        )
        return context
