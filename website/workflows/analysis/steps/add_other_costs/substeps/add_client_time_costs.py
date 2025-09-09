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


class AddClientTimeCosts(AddOtherCostsSubStep):
    nav_title: str = _l("Client Time")
    page_title: str = _l("Add Client Time")
    subtitle: str = _l("Client Time Cost")

    cost_type: int = AnalysisCostType.CLIENT_TIME
    name: str = "add-client-time-costs"

    def __init__(self, parent: AddOtherCosts, workflow: Workflow):
        super().__init__(workflow)
        self.cost_line_items = self.analysis.client_time_cost_line_items
        self.parent = parent

    @cached_property
    def dependencies_met(self) -> bool:
        if self.analysis.in_kind_contributions or self.analysis.other_hq_costs:
            # If another sub-step exists ahead of this one, return True
            return True

        return super().dependencies_met

    def get_help_text(self) -> str:
        return format_html(
            """
            <span>
                In this step you may add the value of time spent by people participating in the program. For each group
                entered you will need to know the number of people and how much time each individual spent participating 
                in the program. If you do not want to include this in the analysis, change the settings in the 
                <a href="{}">Define Analysis</a> step.
            </span>
        """,
            self.get_define_href(),
        )
