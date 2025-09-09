from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models, transaction
from django.db.models import F, Q, Sum, Value
from django.utils.translation import gettext_lazy as _

from website.models.intervention_instance import InterventionInstance
from website.models.mixins import OrderableMixin

if TYPE_CHECKING:
    from website.models import Analysis


class CostTypeType:
    pass


class ProgramCost(CostTypeType):
    id: int = 10
    name: str = _("Program Costs")
    shared: bool = False
    allocation_editable: bool = True


class Support(CostTypeType):
    id: int = 20
    name: str = _("Support Costs")
    shared: bool = True
    allocation_estimation_template: str = "analysis/allocation-estimation-support-costs.html"
    allocation_editable: bool = True

    def get_suggested_allocation(
        self,
        analysis: Analysis,
        intervention_instance: InterventionInstance,
        grant: str,
    ) -> tuple[Decimal, Decimal, Decimal]:
        # Get cost line items in the grant that are part of "Program Cost"
        # Cost Type
        numerator = (
            analysis.cost_line_items.filter(
                grant_code=grant,
                config__cost_type__type=ProgramCost.id,
                config__allocations__intervention_instance=intervention_instance,
            )
            .annotate(allocated_cost=F("total_cost") * (F("config__allocations__allocation") / Value(100)))
            .aggregate(Sum("allocated_cost"))["allocated_cost__sum"]
        )
        if numerator is None:
            numerator = 0

        # Sum all cost line items in the grant.
        denominator = analysis.cost_line_items.filter(
            grant_code=grant,
            config__cost_type__type=ProgramCost.id,
        ).aggregate(Sum("total_cost"))["total_cost__sum"]
        if denominator is None:
            denominator = 0

        if denominator == 0:
            percentage = 0
        else:
            percentage = ((numerator / denominator) * 100).quantize(
                settings.DECIMAL_PRECISION,
                rounding=ROUND_HALF_UP,
            )
        return numerator, denominator, percentage


class Indirect(CostTypeType):
    id: int = 30
    name: str = _("Indirect Costs")
    shared: bool = True
    allocation_estimation_template: str = "analysis/allocation-estimation-indirect.html"
    allocation_editable: bool = False

    def get_suggested_allocation(
        self,
        analysis: Analysis,
        intervention_instance: InterventionInstance,
        grant: str,
    ) -> tuple[Decimal, Decimal, Decimal]:
        # Get cost line items in the grant that are part of "Program Cost"
        # Cost Type
        numerator = (
            analysis.cost_line_items.filter(
                grant_code=grant,
            )
            .filter(
                (Q(config__cost_type__type=ProgramCost.id) | Q(config__cost_type__type=Support.id)),
                config__allocations__intervention_instance=intervention_instance,
            )
            .annotate(allocated_cost=F("total_cost") * (F("config__allocations__allocation") / Value(100)))
            .aggregate(Sum("allocated_cost"))["allocated_cost__sum"]
        )
        if numerator is None:
            numerator = 0

        # Sum all cost line items in the grant.
        denominator = (
            analysis.cost_line_items.filter(
                grant_code=grant,
            )
            .filter(Q(config__cost_type__type=ProgramCost.id) | Q(config__cost_type__type=Support.id))
            .aggregate(Sum("total_cost"))["total_cost__sum"]
        )
        if denominator is None:
            denominator = 0

        if denominator == 0:
            percentage = 0
        else:
            percentage = ((numerator / denominator) * 100).quantize(
                settings.DECIMAL_PRECISION,
                rounding=ROUND_HALF_UP,
            )
        return numerator, denominator, percentage


class CostType(OrderableMixin, models.Model):
    app_log_entry_link_name = "ombucore.admin:website_costtype_change"
    name = models.CharField(
        verbose_name=_("Label"),
        max_length=255,
    )
    TYPES = (
        ProgramCost(),
        Support(),
        Indirect(),
    )
    TYPE_CHOICES = [(cost_type_type.id, cost_type_type.name) for cost_type_type in TYPES]
    type = models.IntegerField(
        verbose_name=_("Type"),
        choices=TYPE_CHOICES,
        default=TYPES[0].id,
        unique=True,
    )
    order = models.PositiveIntegerField(
        verbose_name=_("Sort Order"),
    )
    default = models.BooleanField(default=False, verbose_name=_("Default"))

    class Meta:
        verbose_name = _("Cost Type")
        verbose_name_plural = _("Cost Types")
        ordering = ["type", "order"]

    def __str__(self):
        return self.name

    def type_obj(self):
        for cost_type_type in self.TYPES:
            if cost_type_type.id == self.type:
                return cost_type_type
        return None

    def save(self, *args, **kwargs):
        # This ensures only one instance is set to default
        if self.default:
            with transaction.atomic():
                CostType.objects.filter(default=True).update(default=False)
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

        # If we get into a state where nothing is the default we set it to the Instance's default to the default
        with transaction.atomic():
            if not CostType.objects.filter(default=True).exists():
                default_cat = CostType.objects.get(name=settings.DEFAULT_COST_TYPE)
                default_cat.default = True
                default_cat.save(update_fields=["default"])

    def get_previous_type(self):
        for i, cost_type_type in enumerate(self.TYPES):
            if cost_type_type.id == self.type:
                if i > 0:
                    return self.TYPES[i - 1]
        return None

    @classmethod
    def get_default(cls) -> CostType:
        return cls.objects.get(default=True)

    def is_program_cost(self):
        return self.type == ProgramCost.id
