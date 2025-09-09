from decimal import Decimal

from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from website.models.query_utils import require_prefetch


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
            qs.select_related("config")
            .prefetch_related("transactions")
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

    def subcomponent_allocation_complete(self):
        relevant_cost_line_items = self.get_cost_line_items()
        relevant_cost_line_items = relevant_cost_line_items.exclude(
            Q(config__allocations__allocation=0) | Q(config__allocations__allocation__isnull=True)
        )

        return (
            relevant_cost_line_items.filter(
                (
                    Q(config__subcomponent_analysis_allocations_skipped=False)
                    & (
                        Q(config__subcomponent_analysis_allocations__isnull=True)
                        | Q(config__subcomponent_analysis_allocations={})
                    )
                ),
            ).count()
            == 0
        )

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
