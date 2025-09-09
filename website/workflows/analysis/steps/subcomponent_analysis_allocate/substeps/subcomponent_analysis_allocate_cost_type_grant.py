from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import reverse
from django.utils.functional import cached_property

from website.models import CostType
from website.workflows._steps_base import SubStep
from website.workflows._workflow_base import Workflow

if TYPE_CHECKING:
    from ..subcomponent_analysis_allocate import SubcomponentsAllocate


class SubcomponentsAllocateCostTypeGrant(SubStep):
    name = "subcomponent-analysis-allocate-cost_type-grant"

    def __init__(
        self,
        parent: SubcomponentsAllocate,
        workflow: Workflow,
        cost_type: CostType,
        grant: str,
    ):
        super().__init__(workflow)
        self.parent = parent
        self.cost_type = cost_type
        self.grant = grant

    def has_clis_to_allocate(self):
        return (
            self.analysis.cost_line_items.filter(config__cost_type=self.cost_type)
            .filter(config__allocations__allocation__gt=0)
            .count()
        )

    @cached_property
    def dependencies_met(self) -> bool:
        if not self.workflow.get_step("confirm-subcomponents").is_complete:
            return False

        # Require cost_types of each type to be completed in order.
        previous_type = self.cost_type.get_previous_type()
        if previous_type and not self.parent.cost_type_types_complete_through(previous_type):
            return False
        if self.analysis and self.analysis.interventioninstance_set.count() != 1:
            return False
        return True

    @cached_property
    def is_complete(self) -> bool:
        return (
            # Are there Cost Line Items?  They are required.
            self.analysis.cost_line_items.filter(config__cost_type=self.cost_type)
            .filter(config__allocations__allocation__gt=0)
            .count()
            # Are there Cost Line Items that are missing Allocations and not skipped? There shouldn't be.
            and not (
                self.analysis.cost_line_items_with_no_subcomponent_allocation(
                    self.cost_type,
                    self.grant,
                )
                .filter(config__allocations__allocation__gt=0)
                .filter(config__subcomponent_analysis_allocations_skipped=False)
                .count()
            )
        )

    def get_nav_title(self) -> str:
        if len(self.analysis.grants_list()) > 1:
            return f"{self.cost_type.name}: {self.grant}"
        return self.cost_type.name

    def get_href(self) -> str:
        return reverse(
            "subcomponent-cost-analysis-allocate-cost_type-grant",
            kwargs={
                "pk": self.analysis.pk,
                "subcomponent_pk": self.analysis.subcomponent_cost_analysis.pk,
                "cost_type_pk": self.cost_type.pk,
                "grant": self.grant,
            },
        )
