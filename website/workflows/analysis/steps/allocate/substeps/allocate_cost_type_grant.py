from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import reverse
from django.utils.functional import cached_property

from website.models import CostType
from website.models.query_utils import require_prefetch
from website.workflows._steps_base import SubStep
from website.workflows._workflow_base import Workflow

if TYPE_CHECKING:
    from website.workflows.analysis.steps.allocate import Allocate


class AllocateCostTypeGrant(SubStep):
    name = "allocate-cost_type-grant"

    def __init__(
        self,
        parent: Allocate,
        workflow: Workflow,
        cost_type: CostType,
        grant: str,
    ):
        super().__init__(workflow)
        self.parent = parent
        self.cost_type = cost_type
        self.grant = grant

    @cached_property
    def dependencies_met(self) -> bool:
        if not self.workflow.get_step("categorize").is_complete:
            return False

        # Require cost_types of each type to be completed in order.
        previous_type = self.cost_type.get_previous_type()
        if previous_type and not self.parent.cost_type_types_complete_through(previous_type):
            return False

        return True

    @cached_property
    def is_complete(self) -> bool:
        """
        To determine if this step is complete we find out
         which interventions are present and make sure there
         are allocations for those interventions on each cost line item.
        """

        cost_type_categories = require_prefetch(self.analysis, "cost_type_categories")
        cost_type_categories = [c for c in cost_type_categories if c.cost_type_id == self.cost_type.id]
        cost_line_items = self.analysis.cost_line_items.prefetch_related(
            "config",
            "config__allocations",
        ).all()
        intervention_instances = require_prefetch(self.analysis, "interventioninstance_set")

        for each_ctc in cost_type_categories:
            items = []

            for cli in cost_line_items:
                if (
                    cli.grant_code == self.grant
                    and cli.config.category_id == each_ctc.category_id
                    and cli.config.cost_type_id == self.cost_type.id
                ):

                    items.append(cli)

            if not items:
                continue

            # For every intervention make sure at least one allocation is non-null
            for each_intervention_instance in intervention_instances:
                ok = False
                for cli in items:
                    allocs = require_prefetch(cli.config, "allocations")
                    for a in allocs:
                        if a.intervention_instance_id == each_intervention_instance.id:
                            if a.allocation is None:
                                return False
                            ok = True
                if not ok:
                    return False
        return True

    def get_nav_title(self) -> str:
        if len(self.analysis.grants_list()) > 1:
            return f"{self.cost_type.name}: {self.grant}"
        return self.cost_type.name

    def get_href(self) -> str:
        return reverse(
            "analysis-allocate-cost_type-grant",
            kwargs={
                "pk": self.analysis.pk,
                "cost_type_pk": self.cost_type.pk,
                "grant": self.grant,
            },
        )
