from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _l

from website import betterdb
from website.models import SubcomponentCostAllocation
from website.models.cost_line_item import CostLineItemConfig
from website.models.cost_type import ProgramCost
from website.utils import list_dedupe
from website.workflows._steps_base import MultiStep
from website.workflows._workflow_base import Workflow
from .substeps import AllocateSubcomponentsInterventionGrant


class AllocateSubcomponents(MultiStep):
    name = "allocate-subcomponents"
    nav_title = _l("Allocate Sub-Component Costs")

    def __init__(self, workflow: Workflow):
        super().__init__(workflow)
        if not self.analysis or not self.analysis.id:
            return

        program_cost_grants = list_dedupe(
            self.analysis.cost_type_category_grants.filter(
                cost_type_category__cost_type__type=ProgramCost.id,
            ).values_list("grant", flat=True)
        )

        for intervention_instance in self.analysis.interventioninstance_set.all():
            if not hasattr(intervention_instance, "subcomponent_cost_analysis"):
                continue
            for grant in program_cost_grants:
                self.steps.append(
                    AllocateSubcomponentsInterventionGrant(
                        self,
                        self.workflow,
                        intervention_instance,
                        grant,
                    )
                )

    @cached_property
    def is_enabled(self) -> bool:
        if not getattr(self.analysis, "pk", None):
            return False
        return bool(self.analysis.subcomponent_cost_analyses())

    @cached_property
    def dependencies_met(self) -> bool:
        return self.workflow.get_step("allocate").is_complete

    def get_href(self) -> str:
        return reverse("analysis-allocate-subcomponents", kwargs={"pk": self.analysis.pk})

    def invalidate(self) -> None:
        self.workflow.invalidate_step("insights")
        cost_line_item_configs = CostLineItemConfig.objects.filter(
            cost_line_item__in=self.analysis.cost_line_items.all()
        )

        subcomponent_allocations = SubcomponentCostAllocation.objects.filter(
            cli_config__in=cost_line_item_configs
        )
        SubcomponentCostAllocation.objects.filter(cloned_from__in=subcomponent_allocations).update(
            cloned_from=None
        )
        betterdb.delete(subcomponent_allocations)
