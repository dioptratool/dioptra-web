from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import reverse
from django.utils.functional import cached_property

from website.models import InterventionInstance
from website.models.cost_type import ProgramCost
from website.models.subcomponent import subcomponent_allocation_complete
from website.workflows._steps_base import SubStep
from website.workflows._workflow_base import Workflow

if TYPE_CHECKING:
    from website.workflows.analysis.steps.allocate_subcomponents import AllocateSubcomponents


class AllocateSubcomponentsInterventionGrant(SubStep):
    name = "allocate-subcomponents-intervention-grant"

    def __init__(
        self,
        parent: AllocateSubcomponents,
        workflow: Workflow,
        intervention_instance: InterventionInstance,
        grant: str,
    ):
        super().__init__(workflow)
        self.parent = parent
        self.intervention_instance = intervention_instance
        self.grant = grant

    @property
    def subcomponent_analysis(self):
        return self.intervention_instance.subcomponent_cost_analysis

    @cached_property
    def dependencies_met(self) -> bool:
        return self.parent.dependencies_met

    @cached_property
    def is_complete(self) -> bool:
        """
        Complete when every program-cost line item in this grant with a positive
        allocation to this intervention instance has a subcomponent allocation
        that is skipped or totals 100%.
        """
        cost_line_items = (
            self.analysis.cost_line_items.cost_type_category_items()
            .filter(
                grant_code=self.grant,
                config__cost_type__type=ProgramCost.id,
            )
            .select_related("config")
            .prefetch_related(
                "config__allocations",
                "config__subcomponent_cost_allocations",
            )
        )
        for cost_line_item in cost_line_items:
            allocation = next(
                (
                    a
                    for a in cost_line_item.config.allocations.all()
                    if a.intervention_instance_id == self.intervention_instance.id
                ),
                None,
            )
            if allocation is None or not allocation.allocation:
                continue
            if not subcomponent_allocation_complete(cost_line_item, self.subcomponent_analysis):
                return False
        return True

    def get_nav_title(self) -> str:
        if len(self.analysis.grants_list()) > 1:
            return f"{self.intervention_instance.display_name()}: {self.grant}"
        return self.intervention_instance.display_name()

    def get_href(self) -> str:
        return reverse(
            "analysis-allocate-subcomponents-intervention-grant",
            kwargs={
                "pk": self.analysis.pk,
                "intervention_instance_pk": self.intervention_instance.pk,
                "grant": self.grant,
            },
        )
