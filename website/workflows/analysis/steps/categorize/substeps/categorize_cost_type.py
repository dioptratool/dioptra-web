from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import reverse
from django.utils.functional import cached_property

from website.models import CostType
from website.workflows._steps_base import SubStep
from website.workflows._workflow_base import Workflow

if TYPE_CHECKING:
    from website.workflows.analysis.steps.categorize import Categorize


class CategorizeCostType(SubStep):
    name = "categorize-cost_type"

    def __init__(self, parent: Categorize, workflow: Workflow, cost_type: CostType):
        super().__init__(workflow)
        self.parent = parent
        self.cost_type = cost_type

    @cached_property
    def dependencies_met(self) -> bool:
        return self.workflow.get_step("load-data").is_complete

    @cached_property
    def is_complete(self) -> bool:
        if not self.dependencies_met:
            return False
        if self.analysis and getattr(self.analysis, "pk", None):
            confirmed_cost_type_categories = self.analysis.cost_type_categories.filter(
                cost_type=self.cost_type
            ).values_list("confirmed", flat=True)
            return len(confirmed_cost_type_categories) and all(confirmed_cost_type_categories)
        return False

    def get_nav_title(self) -> str:
        return self.cost_type.name

    def get_href(self) -> str:
        return reverse(
            "analysis-categorize-cost_type",
            kwargs={"pk": self.analysis.pk, "cost_type_pk": self.cost_type.pk},
        )
