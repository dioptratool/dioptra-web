from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _

from website.models.query_utils import require_prefetch
from website.models.subcomponent import requires_subcomponent_allocation, subcomponent_allocation_complete


class AnalysisCostTypeCategoryGrant(models.Model):
    cost_type_category = models.ForeignKey(
        "website.AnalysisCostTypeCategory",
        verbose_name=_("CostType Category"),
        on_delete=models.CASCADE,
        related_name="cost_type_category_grants",
    )
    grant = models.CharField(
        verbose_name=_("Grant"),
        max_length=255,
    )
    cloned_from = models.ForeignKey(
        "website.AnalysisCostTypeCategoryGrant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    def __repr__(self):
        return f"<AnalysisCostTypeCategoryGrant: {self.cost_type_category.cost_type} :: {self.cost_type_category.category} :: {self.grant} for: {self.analysis.title} >"

    def get_cost_line_items(self):
        qs = self.cost_type_category.analysis.cost_line_items.filter(
            config__cost_type=self.cost_type_category.cost_type,
            config__category=self.cost_type_category.category,
            grant_code=self.grant,
        )
        return (
            qs.select_related("config", "config__cost_type", "config__category")
            .prefetch_related("transactions", "config__allocations")
            .order_by(
                "grant_code",
                "budget_line_description",
                "site_code",
                "sector_code",
                "account_code",
            )
        )

    def allocation_complete(self) -> bool:
        analysis = self.cost_type_category.analysis
        for cli in require_prefetch(analysis, "unfiltered_cost_line_items"):
            if (
                cli.config.cost_type_id == self.cost_type_category.cost_type_id
                and cli.config.category_id == self.cost_type_category.category_id
                and cli.grant_code == self.grant
            ):
                allocations = require_prefetch(cli.config, "allocations")
                if not allocations:
                    return False
                if any(a.allocation is None for a in allocations):
                    return False

        # if we never found a bad one, allocation is complete
        return True

    def subcomponent_allocation_complete_for(self, intervention_instance) -> bool:
        """
        True when every cost line item in this cost_type/category/grant with a
        positive allocation to the given intervention instance has a complete
        (or skipped) subcomponent allocation.
        """
        if not hasattr(intervention_instance, "subcomponent_cost_analysis"):
            return True
        analysis = self.cost_type_category.analysis
        for cli in require_prefetch(analysis, "unfiltered_cost_line_items"):
            if (
                cli.config.cost_type_id == self.cost_type_category.cost_type_id
                and cli.config.category_id == self.cost_type_category.category_id
                and cli.grant_code == self.grant
                and requires_subcomponent_allocation(cli)
            ):
                allocations = require_prefetch(cli.config, "allocations")
                if not any(
                    allocation.intervention_instance_id == intervention_instance.id
                    and allocation.allocation
                    and allocation.allocation > 0
                    for allocation in allocations
                ):
                    continue
                if not subcomponent_allocation_complete(
                    cli,
                    intervention_instance.subcomponent_cost_analysis,
                ):
                    return False
        return True

    def assigned_items_total(self):
        """Sum of items that have allocations assigned."""
        total = 0
        for item in self.get_cost_line_items():
            for each_allocation in item.config.allocations.all():
                if each_allocation.allocation or each_allocation.allocation == 0:
                    total += item.total_cost
        return round(total, 4)

    def assigned_items_cost(self):
        """Sum of items that have allocations assigned, multiplied by the allocation."""
        cost = 0
        for item in self.get_cost_line_items():
            for each_allocation in item.config.allocations.all():
                if each_allocation.allocation is not None:
                    allocation_percent = each_allocation.allocation / Decimal(100)
                    cost += item.total_cost * allocation_percent
        return round(cost, 4)

    def suggested_allocation(self):
        if self.assigned_items_total() != 0:
            allocation = self.assigned_items_cost() / self.assigned_items_total()
            return f"{allocation:.2%}"

    def program_cost_suggestion(self):
        """Expose the legacy category calculation, including its grant-wide fallback.

        Retain the existing arithmetic, including counting explicit zeroes and
        counting an item's amount once per assigned intervention in the category.
        """
        numerator = self.assigned_items_cost()
        denominator = self.assigned_items_total()
        uses_fallback = denominator == 0
        if uses_fallback:
            numerator = 0
            denominator = 0
            categories = self.cost_type_category.analysis.cost_type_category_grants.filter(
                cost_type_category__cost_type=self.cost_type_category.cost_type,
                grant=self.grant,
            ).select_related("cost_type_category__analysis")
            for category in categories:
                for item in category.get_cost_line_items():
                    allocation_total = sum(
                        allocation.allocation
                        for allocation in item.config.allocations.all()
                        if allocation.allocation is not None
                    )
                    # Preserve calc_item_totals/calc_item_costs, including the
                    # fallback denominator's use of rows with a zero total.
                    if allocation_total == 0:
                        denominator += item.total_cost
                    numerator += item.total_cost * (allocation_total * Decimal(0.01))

        return {
            "numerator": numerator,
            "denominator": denominator,
            "allocation": (f"{numerator / denominator:.2%}".removesuffix("%") if denominator else None),
            "uses_fallback": uses_fallback,
        }

    def all_errors(self):
        if self.assigned_items_total() == 0:
            return True
        else:
            return False

    _show_allocation_calculator = False

    @property
    def show_allocation_calculator(self):
        return self._show_allocation_calculator

    @show_allocation_calculator.setter
    def show_allocation_calculator(self, value):
        self._show_allocation_calculator = value

    class Meta:
        ordering = [
            "cost_type_category__cost_type__type",
            "cost_type_category__cost_type__order",
            "grant",
            "cost_type_category__category__order",
        ]
