from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _l

from website.workflows._steps_base import MultiStep, Step
from website.workflows._workflow_base import Workflow
from website.workflows.analysis.steps.categorize.substeps.categorize_cost_type import (
    CategorizeCostType,
)


class Categorize(MultiStep):
    name = "categorize"
    nav_title = _l("Confirm Categories")

    def __init__(self, workflow: Workflow):
        super().__init__(workflow)
        if self.analysis and getattr(self.analysis, "pk", None):
            for cost_type in self.analysis.get_cost_types_used():
                self.steps.append(CategorizeCostType(self, self.workflow, cost_type))

    @cached_property
    def dependencies_met(self) -> bool:
        return self.workflow.get_step("load-data").is_complete

    @property
    def is_complete(self) -> bool:
        if not self.dependencies_met:
            return False
        if not self.steps:
            return False
        if self.analysis and getattr(self.analysis, "pk", None):
            return all([substep.is_complete for substep in self.steps])
        return False

    def get_href(self) -> str:
        return reverse("analysis-categorize", kwargs={"pk": self.analysis.pk})

    def get_step_by_cost_type(self, cost_type) -> Step:
        for step in self.steps:
            if step.cost_type == cost_type:
                return step
