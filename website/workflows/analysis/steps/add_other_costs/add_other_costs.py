from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _l

from website.workflows._steps_base import MultiStep
from website.workflows._workflow_base import Workflow
from .substeps import AddClientTimeCosts, AddInKindContributionsCosts, AddOtherHQCosts


class AddOtherCosts(MultiStep):
    name = "add-other-costs"
    nav_title = _l("Add Other Costs")

    def __init__(self, workflow: Workflow):
        super().__init__(workflow)

        if not self.analysis:
            return
        if not getattr(self.analysis, "pk", None):
            return

        if self.analysis.client_time:
            self.steps.append(AddClientTimeCosts(self, self.workflow))
        if self.analysis.in_kind_contributions:
            self.steps.append(AddInKindContributionsCosts(self, self.workflow))
        if self.analysis.other_hq_costs:
            self.steps.append(AddOtherHQCosts(self, self.workflow))

    @cached_property
    def is_complete(self) -> bool:
        if not self.dependencies_met:
            return False
        return all([step.is_complete for step in self.steps])

    @cached_property
    def dependencies_met(self) -> bool:
        return self.workflow.get_step("allocate").is_complete

    @cached_property
    def is_enabled(self) -> bool:
        if not getattr(self.analysis, "pk", None):
            return False
        return self.analysis.allows_other_costs

    def get_nav_title(self) -> str:
        title = "Add Other Costs"
        return title

    def get_href(self) -> str:
        return reverse(
            "analysis-add-other-costs",
            kwargs={
                "pk": self.analysis.pk,
            },
        )
