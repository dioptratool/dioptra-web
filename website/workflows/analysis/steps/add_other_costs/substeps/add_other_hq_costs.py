from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _l

from website.models import AnalysisCostType
from website.workflows._workflow_base import Workflow
from ._base import AddOtherCostsSubStep

if TYPE_CHECKING:
    from website.workflows.analysis.steps.add_other_costs import AddOtherCosts


class AddOtherHQCosts(AddOtherCostsSubStep):
    nav_title: str = _l("Other HQ Costs")
    page_title: str = _l("Add Other HQ Costs")
    subtitle: str = _l("Cost Item")

    cost_type: int = AnalysisCostType.OTHER_HQ
    name: str = "add-other-hq-costs"

    def __init__(self, parent: AddOtherCosts, workflow: Workflow):
        super().__init__(workflow)
        self.cost_line_items = self.analysis.other_hq_costs_cost_line_items
        self.parent = parent

    def get_help_text(self) -> str:
        return format_html(
            "<span>"
            "In this step you may add one or more HQ cost items that "
            "were not captured in the previous steps. If you do not "
            "want to include this in the analysis, please change the "
            'settings in the <a href="{}">Define Analysis</a> step.'
            "</span>",
            self.get_define_href(),
        )
