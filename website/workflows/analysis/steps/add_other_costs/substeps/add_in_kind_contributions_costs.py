from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _l

from website.models import AnalysisCostType
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
