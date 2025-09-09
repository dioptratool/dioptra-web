from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _l

from website.models import CostLineItemConfig
from website.workflows._steps_base import Step


class SubcomponentsConfirm(Step):
    """
    The subcomponents confirmation step in the subcomponent cost analysis
    workflow. Because this is the initial step, it covers create and update
    scenarios.
    """

    name = "confirm-subcomponents"
    nav_title = _l("Confirm Subcomponents")

    @cached_property
    def is_complete(self) -> bool:
        return (
            hasattr(self.analysis, "pk")
            and hasattr(self.analysis, "subcomponent_cost_analysis")
            and hasattr(self.analysis.subcomponent_cost_analysis, "pk")
            and self.analysis.subcomponent_cost_analysis.subcomponent_labels_confirmed
        )

    @cached_property
    def dependencies_met(self) -> bool:
        if self.analysis and self.analysis.interventioninstance_set.count() != 1:
            return False
        return self.workflow.get_step("insights").is_complete

    def get_href(self) -> str:
        return reverse(
            "subcomponent-cost-analysis-create",
            kwargs={"pk": self.analysis.pk},
        )

    def get_help_text(self):
        msg = (
            "This workflow allows you to determine how the cost of the"
            " interventions is divided between various sub-components."
            " In this step please confirm the list of labels that "
            "represent the sub-components to be analyzed. "
        )
        return format_html("<span>{}</span>", msg)

    def invalidate(self) -> None:
        self.analysis.subcomponent_cost_analysis.subcomponent_labels_confirmed = False
        self.analysis.subcomponent_cost_analysis.save()

        allocation_default = CostLineItemConfig._meta.get_field("subcomponent_analysis_allocations").default
        CostLineItemConfig.objects.filter(cost_line_item__analysis=self.analysis).update(
            subcomponent_analysis_allocations=allocation_default(),
            subcomponent_analysis_allocations_skipped=False,
        )
