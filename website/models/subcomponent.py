from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _

from website.models.cost_line_item import CostLineItem, CostLineItemConfig
from website.models.field_types import SubcomponentAnalysisValuesType, SubcomponentLabelsType
from website.models.fields import TypedJsonField
from website.models.query_utils import require_prefetch
from .category import Category
from .cost_type import CostType, Indirect, Support


class SubcomponentCostAnalysis(models.Model):
    intervention_instance = models.OneToOneField(
        "website.InterventionInstance",
        verbose_name=_("Intervention"),
        on_delete=models.CASCADE,
        related_name="subcomponent_cost_analysis",
    )

    subcomponent_labels = TypedJsonField(
        typed_json=SubcomponentLabelsType,
        default=list,
        blank=True,
        null=True,
    )

    cloned_from = models.ForeignKey(
        "website.SubcomponentCostAnalysis",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = _("Subcomponent Cost Analysis")
        verbose_name_plural = _("Subcomponent Cost Analyses")

    def __str__(self):
        return f"Subcomponent Analysis for {self.intervention_instance.display_name()}"

    @property
    def analysis(self):
        return self.intervention_instance.analysis

    def save(self, *args, **kwargs):
        if not self.pk and not self.subcomponent_labels:
            self.subcomponent_labels = self.intervention_instance.intervention.subcomponent_labels
        super().save(*args, **kwargs)

    def _allocated_cost_for_intervention(self, cost_line_item: CostLineItem) -> Decimal:
        for allocation in cost_line_item.config.allocations.all():
            if allocation.intervention_instance_id == self.intervention_instance_id:
                return cost_line_item.total_cost * (Decimal(allocation.allocation) / Decimal(100))
        return Decimal("0")

    def _subcomponent_allocation_entries(self) -> list[tuple[CostLineItemConfig, dict, bool]]:
        return [
            (
                allocation_row.cli_config,
                allocation_row.allocations or {},
                allocation_row.skipped,
            )
            for allocation_row in self.allocations.select_related(
                "cli_config",
                "cli_config__cost_line_item",
                "cli_config__cost_type",
                "cli_config__category",
            )
            .prefetch_related("cli_config__allocations")
            .all()
        ]

    def allocated_totals(self):
        subcomponent_allocations = []
        for cli_config, allocations, skipped in self._subcomponent_allocation_entries():
            if not allocations:
                continue
            if skipped:
                continue
            each_cost_item = cli_config.cost_line_item

            # Get the value of each subcomponent allocation. Index by label so a
            # partial row cannot truncate every column via zip(*...) below.
            allocated_cost = self._allocated_cost_for_intervention(each_cost_item)
            subcomponent_allocations.append(
                [
                    Decimal(allocations.get(str(idx), "0")) / 100 * allocated_cost
                    for idx in range(len(self.subcomponent_labels or []))
                ]
            )

        # Add up all the subcomponents of the same type
        # This return a list of totals for Each Subcomponent Label
        return [round(float(sum(col)), 4) for col in zip(*subcomponent_allocations)]

    def cost_line_item_average(
        self,
        cost_type: CostType | None = None,
        category: Category | None = None,
        grant: str | None = None,
        analysis_cost_type: int | None = None,
        exclude_support_costs: bool = True,
    ) -> list[Decimal]:
        """
        This is not the average of the percentages of the Subcomponent analysis but instead the sum of costs
          for each subcomponent as a percentage of the whole subcomponent cost.

          This is a subtle and important distinction.

          There is also hard capped at 100.   Any remainder from rounding/floats/etc is add/subtracted from the last item.
        """
        subcomponent_allocations = []
        total_cost_for_clis_with_subcomponent_value = 0
        for each_config, allocations, skipped in self._subcomponent_allocation_entries():
            each_cost_item = each_config.cost_line_item
            if each_cost_item.is_special_lump_sum:
                continue
            if analysis_cost_type is None and each_config.analysis_cost_type:
                continue
            if analysis_cost_type is not None and each_config.analysis_cost_type != analysis_cost_type:
                continue
            if not allocations:
                continue
            if cost_type is not None and each_config.cost_type != cost_type:
                continue
            if category is not None and each_config.category != category:
                continue
            if grant is not None and each_cost_item.grant_code != grant:
                continue

            if skipped:
                continue

            if each_config.cost_type and each_config.cost_type.type == Indirect.id:
                continue

            if exclude_support_costs and each_config.cost_type and each_config.cost_type.type == Support.id:
                continue

            intervention_allocated_cost = self._allocated_cost_for_intervention(each_cost_item)
            # Index by label so a partial row cannot truncate every column via
            # zip(*...) below.
            subcomponent_allocations.append(
                [
                    (Decimal(allocations.get(str(idx), "0")) / 100) * intervention_allocated_cost
                    for idx in range(len(self.subcomponent_labels or []))
                ]
            )
            total_cost_for_clis_with_subcomponent_value += intervention_allocated_cost

        # Add up all the subcomponents of the same type and then divide them with the total of the Cost Line Items
        # This return a list of Average Percentages for Each Subcomponent Label
        # Percentages are returned as floats from 0-100 for display
        averages = []
        for col in zip(*subcomponent_allocations):
            if sum(col) > 0:
                averages.append(
                    round(
                        Decimal(sum(col) / total_cost_for_clis_with_subcomponent_value) * 100,
                        2,
                    )
                )
            else:
                averages.append(0)

        # This value cannot be over/under 100 so in the case where it might be we remove the extra from the last item
        if averages and sum(averages) != 100:
            averages[-1] += 100 - sum(averages)

        return averages

    def full_cost_percentages(self) -> list[Decimal]:
        """
        The sub-component split to apply against the intervention's full
        output cost (Program + Support + Indirect Costs).

        Users only enter sub-component allocations for Program Cost rows.
        Shared costs — Support, Indirect, and skipped rows — follow the
        weighted Program Cost split, so the full-cost split equals the
        Program Cost weighted average. The shared-cost derivation happens
        here at calculation time and is never persisted, so recalculation
        cannot leave stale derived rows (stored allocations on non-Program
        rows, e.g. migrated 2.1 data, are ignored). Insights, print, and the
        spreadsheet all read this method so their outputs cannot disagree.
        """
        return self.cost_line_item_average()

    def reset_cost_line_items(self):
        self.allocations.all().delete()


class SubcomponentCostAllocation(models.Model):
    subcomponent_analysis = models.ForeignKey(
        "website.SubcomponentCostAnalysis",
        verbose_name=_("Subcomponent Cost Analysis"),
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    cli_config = models.ForeignKey(
        "website.CostLineItemConfig",
        verbose_name=_("Cost Line Item Config"),
        on_delete=models.CASCADE,
        related_name="subcomponent_cost_allocations",
    )
    allocations = TypedJsonField(
        typed_json=SubcomponentAnalysisValuesType,
        default=dict,
        null=True,
    )
    skipped = models.BooleanField(default=False)
    cloned_from = models.ForeignKey(
        "website.SubcomponentCostAllocation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = _("Subcomponent Cost Allocation")
        verbose_name_plural = _("Subcomponent Cost Allocations")
        constraints = [
            models.UniqueConstraint(
                fields=["subcomponent_analysis", "cli_config"],
                name="unique_subcomponent_allocation_per_config",
            )
        ]


def requires_subcomponent_allocation(cost_line_item) -> bool:
    return not (cost_line_item.is_special_lump_sum or cost_line_item.config.analysis_cost_type)


def subcomponent_allocation_complete(cost_line_item, subcomponent_analysis) -> bool:
    """
    A cost line item's subcomponent allocation is complete when it is skipped or
    has a value for every subcomponent label and those values total exactly 100.
    """
    for allocation in require_prefetch(cost_line_item.config, "subcomponent_cost_allocations"):
        if allocation.subcomponent_analysis_id != subcomponent_analysis.id:
            continue
        if allocation.skipped:
            return True
        if not allocation.allocations:
            return False
        expected_indexes = {
            str(idx) for idx, _label in enumerate(subcomponent_analysis.subcomponent_labels or [])
        }
        if set((allocation.allocations or {}).keys()) != expected_indexes:
            return False
        return sum(Decimal(value) for value in allocation.allocations.values()) == Decimal(100)
    return False
