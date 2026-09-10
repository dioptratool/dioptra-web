from decimal import Decimal, ROUND_HALF_UP

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

    def cost_line_item_queryset(self):
        """Cost line items in this cost type, category and grant, unordered and without prefetches."""
        return self.cost_type_category.analysis.cost_line_items.filter(
            config__cost_type_id=self.cost_type_category.cost_type_id,
            config__category_id=self.cost_type_category.category_id,
            grant_code=self.grant,
        )

    def get_cost_line_items(self):
        return (
            self.cost_line_item_queryset()
            .select_related("config", "config__cost_type", "config__category")
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

    @staticmethod
    def _eligible_allocations(allocations, intervention_ids):
        """Map intervention id to the entered allocation of one cost item, or None if ineligible.

        Blank cells are dropped and a wholly blank row is ineligible. A row with
        any value outside 0-100, or totalling more than 100, is ineligible as a
        whole rather than cell by cell. Every writer validates saved allocations
        to those same bounds, so this only excludes rows edited outside the
        application. Cells for interventions outside the analysis cannot be
        created by the application and are ignored.
        """
        entered = {
            allocation.intervention_instance_id: allocation.allocation
            for allocation in allocations
            if allocation.allocation is not None and allocation.intervention_instance_id in intervention_ids
        }
        if not entered or any(not 0 <= value <= 100 for value in entered.values()):
            return None
        if sum(entered.values()) > 100:
            return None
        return entered

    def program_cost_suggestion(self, *, excluded_config_ids, intervention_ids=None):
        """Suggest per-intervention shares using saved peers in this grant/category.

        Count each eligible item's signed amount once, excluding all selected
        items and rows with wholly blank or invalid allocations. Missing/blank
        intervention allocations on an otherwise eligible row contribute zero.
        ``intervention_ids`` defaults to every intervention in the analysis;
        callers that already hold the list can pass it to save a query.
        """
        if not self.cost_type_category.cost_type.is_program_cost():
            raise ValueError("Program Cost suggestions require a Program Cost category")

        if intervention_ids is None:
            intervention_ids = self.cost_type_category.analysis.interventioninstance_set.values_list(
                "pk", flat=True
            )
        numerators = dict.fromkeys(intervention_ids, Decimal(0))
        denominator = Decimal(0)
        items = (
            self.cost_line_item_queryset()
            .exclude(config__pk__in=excluded_config_ids)
            .select_related("config")
            .prefetch_related("config__allocations")
        )
        for item in items:
            allocations = self._eligible_allocations(item.config.allocations.all(), numerators)
            if allocations is None:
                continue
            denominator += item.total_cost
            for intervention_id, value in allocations.items():
                numerators[intervention_id] += item.total_cost * value / 100

        result = {
            "numerators": numerators,
            "denominator": denominator,
            "allocations": None,
            "warning": None,
        }
        if not denominator:
            return result

        # Check before rounding so even a tiny negative share produces a warning.
        if any(numerator * denominator < 0 for numerator in numerators.values()):
            result["warning"] = _(
                "Due to the refund allocations the application was unable to produce a suggested allocation"
            )
            return result

        # Signed, partially allocated costs can exceed 100% before rounding.
        # Such an invalid result must not be treated as a rounding overflow.
        if abs(sum(numerators.values())) > abs(denominator):
            return result

        percentages = {}
        for intervention_id, numerator in numerators.items():
            share = (numerator / denominator * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            # A zero share of a negative denominator quantizes to -0.00; drop the sign.
            percentages[intervention_id] = share.copy_abs() if share == 0 else share
        if sum(percentages.values()) > 100:
            percentages = {
                intervention_id: value - Decimal("0.01") if value > 0 else value
                for intervention_id, value in percentages.items()
            }
        result["allocations"] = {
            intervention_id: str(value) for intervention_id, value in percentages.items()
        }
        return result

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
