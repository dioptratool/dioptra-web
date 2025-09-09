from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import reverse
from django.utils.functional import cached_property

from website.workflows._steps_base import SubStep
from website.workflows._workflow_base import Workflow

if TYPE_CHECKING:
    from ..subcomponent_analysis_allocate import SubcomponentsAllocate


class SubcomponentsAllocateSupportingCosts(SubStep):
    name = "subcomponent-analysis-allocate-supporting-costs"

    def __init__(
        self,
        parent: SubcomponentsAllocate,
        workflow: Workflow,
        grant_code: str,
    ):
        super().__init__(workflow)
        self.parent = parent
        self.grant_code = grant_code

    @cached_property
    def dependencies_met(self) -> bool:
        if not self.workflow.get_step("confirm-subcomponents").is_complete:
            return False

        incomplete_cost_type_grant_steps = []
        for step in self.workflow.get_step("allocate-subcomponent-costs").steps:
            if step.name == "subcomponent-analysis-allocate-cost_type-grant" and not step.is_complete:
                incomplete_cost_type_grant_steps.append(step)

        if incomplete_cost_type_grant_steps:
            return False
        if self.analysis and self.analysis.interventioninstance_set.count() != 1:
            return False
        return True

    @cached_property
    def is_complete(self) -> bool:
        return self.analysis.subcomponent_cost_analysis.special_country_allocation_complete(
            grant_code=self.grant_code
        )

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
            "subcomponent-cost-analysis-allocate-supporting-costs",
            kwargs={
                "pk": self.analysis.pk,
                "grant": self.grant_code,
            },
        )
