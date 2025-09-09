from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _l

from website.models.cost_type import CostType, CostTypeType, ProgramCost
from website.utils import list_dedupe
from website.workflows._steps_base import MultiStep
from website.workflows._workflow_base import Workflow
from .substeps.subcomponent_analysis_allocate_cost_type_grant import (
    SubcomponentsAllocateCostTypeGrant,
)
from .substeps.subcomponent_analysis_allocate_supporting_costs import (
    SubcomponentsAllocateSupportingCosts,
)


class SubcomponentsAllocate(MultiStep):
    name = "allocate-subcomponent-costs"
    nav_title = _l("Allocate Costs")

    def __init__(self, workflow: Workflow):
        super().__init__(workflow)
        if not self.analysis or not self.analysis.id:
            return

        cost_type_ids_and_grants = list_dedupe(
            self.analysis.cost_type_category_grants.all().values_list(
                "cost_type_category__cost_type_id",
                "grant",
            )
        )
        cost_type_lookup = CostType.objects.in_bulk({ct for ct, _ in cost_type_ids_and_grants})

        for cost_type_id, grant in cost_type_ids_and_grants:
            if not cost_type_id:
                # TODO: In what case should this Sector be None?  Is this an error?
                continue

            step = SubcomponentsAllocateCostTypeGrant(
                self,
                self.workflow,
                cost_type_lookup[cost_type_id],
                grant,
            )
            if step.has_clis_to_allocate():
                self.steps.append(step)

        # We must include a final step if any Special Country Cost Line Items exist on the Analysis
        unique_grant_codes = sorted(
            {item.grant_code for item in self.analysis.special_country_cost_line_items}
        )
        unique_grant_codes.sort()
        for grant_code in unique_grant_codes:
            self.steps.append(SubcomponentsAllocateSupportingCosts(self, self.workflow, grant_code))

    @cached_property
    def dependencies_met(self) -> bool:
        if self.analysis and self.analysis.interventioninstance_set.count() != 1:
            return False
        return self.workflow.get_step("confirm-subcomponents").is_complete

    def get_href(self) -> str:
        return reverse(
            "subcomponent-cost-analysis-allocate",
            kwargs={
                "pk": self.analysis.pk,
                "subcomponent_pk": self.analysis.subcomponent_cost_analysis.pk,
            },
        )

    def cost_types_of_type_complete(self, cost_type_type: CostTypeType) -> bool:
        cost_type_steps = [step for step in self.steps if hasattr(step, "cost_type")]
        return all([step.is_complete for step in cost_type_steps if step.cost_type.type == cost_type_type.id])

    def cost_type_types_complete_through(self, cost_type_type: CostTypeType) -> bool:
        if not cost_type_type:
            return True
        for st in CostType.TYPES:
            if st == cost_type_type:
                return self.cost_types_of_type_complete(st)
            if not self.cost_types_of_type_complete(st):
                return False
        return False

    @property
    def is_complete(self) -> bool:
        if not self.dependencies_met:
            return False
        if not (self.analysis and getattr(self.analysis, "pk", None)):
            return False

        complete = all(
            [substep.is_complete for substep in self.steps if substep.cost_type.type == ProgramCost().id]
        )
        if complete:
            self.analysis.subcomponent_cost_analysis.calculate_and_apply_allocations_to_shared_costs_and_skipped_items()
        return complete
