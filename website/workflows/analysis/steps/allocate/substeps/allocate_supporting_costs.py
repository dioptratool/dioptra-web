from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import reverse
from django.utils.functional import cached_property

from website.workflows._steps_base import SubStep
from website.workflows._workflow_base import Workflow

if TYPE_CHECKING:
    from website.workflows.analysis.steps.allocate import Allocate


class AllocateSupportingCosts(SubStep):
    name = "allocate-supporting-costs"

    def __init__(
        self,
        parent: Allocate,
        workflow: Workflow,
        grant_code: str,
    ):
        super().__init__(workflow)
        self.parent = parent
        self.grant_code = grant_code

    @cached_property
    def dependencies_met(self) -> bool:
        """
        Categorization Step must be complete and all previous Cost Type Grant Allocation sub-steps within the parent
        Allocate step must be complete before work can be started on AllocateSupportingCosts
        """
        if not self.workflow.get_step("categorize").is_complete:
            return False
        incomplete_cost_type_grant_steps = []
        for step in self.workflow.get_step("allocate").steps:
            if step.name == "allocate-cost_type-grant" and not step.is_complete:
                incomplete_cost_type_grant_steps.append(step)

        if incomplete_cost_type_grant_steps:
            return False

        return True

    @cached_property
    def is_complete(self) -> bool:
        return self.analysis.special_country_allocation_complete(grant_code=self.grant_code)

    def get_nav_title(self) -> str:
        """
        Only display the Grant Code in the title if more than one grant code is present on the Analysis:
        """
        title = "Other Supporting Costs"

        analysis_grants = self.analysis.query_grants()
        if len(analysis_grants) > 1:
            title = f"{title}: {self.grant_code}"

        return title

    def get_href(self) -> str:
        return reverse(
            "analysis-allocate-supporting-costs",
            kwargs={
                "pk": self.analysis.pk,
                "grant": self.grant_code,
            },
        )
