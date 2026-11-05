from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _l

from website.models import AnalysisCostType
from website.models.subcomponent import subcomponent_allocation_complete
from website.workflows._workflow_base import Workflow
from ._base import AddOtherCostsSubStep

if TYPE_CHECKING:
    from website.workflows.analysis.steps.add_other_costs import AddOtherCosts


class AddInKindContributionsCosts(AddOtherCostsSubStep):
    nav_title: str = _l("In-Kind Contributions")
    page_title: str = _l("Add In-Kind Contributions")
    subtitle: str = _l("Cost Item")

    cost_type: int = AnalysisCostType.IN_KIND
    name: str = "add-in-kind-contributor-costs"

    def __init__(self, parent: AddOtherCosts, workflow: Workflow):
        super().__init__(workflow)
        self.cost_line_items = self.analysis.in_kind_contributions_cost_line_items
        self.parent = parent

    def items_needing_subcomponent_split(self) -> list:
        """
        In-kind items with a non-zero allocation to an intervention that has sub-component
        labels, whose split is missing, partial, or not 100% (86.6). Component edits after
        the item was saved are what usually put an item here.
        """
        labelled = {
            instance.id: instance.subcomponent_cost_analysis
            for instance in self.analysis.interventioninstance_set.all()
            if hasattr(instance, "subcomponent_cost_analysis")
            and instance.subcomponent_cost_analysis.subcomponent_labels
        }
        if not labelled:
            return []
        items = self.cost_line_items.select_related("config").prefetch_related(
            "config__allocations", "config__subcomponent_cost_allocations"
        )
        needing = []
        for item in items:
            for allocation in item.config.allocations.all():
                subcomponent_analysis = labelled.get(allocation.intervention_instance_id)
                if subcomponent_analysis is None or not allocation.allocation:
                    continue
                if not subcomponent_allocation_complete(item, subcomponent_analysis):
                    needing.append(item)
                    break
        return needing

    @cached_property
    def is_complete(self) -> bool:
        return self.cost_line_items.exists() and not self.items_needing_subcomponent_split()

    @cached_property
    def dependencies_met(self) -> bool:
        if self.analysis.other_hq_costs:
            # If another sub-step exists ahead of this one, return True
            return True

        return super().dependencies_met

    def get_help_text(self) -> str:
        return format_html(
            "<span> "
            "In this step you may add the value of goods and/or services donated by "
            "other actors. If you do not want to include this in the analysis, please change the "
            'settings in the <a href="{}"> Define Analysis</a> step. '
            "</span>",
            self.get_define_href(),
        )
