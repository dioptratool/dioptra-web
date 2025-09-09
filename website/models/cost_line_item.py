from __future__ import annotations

from decimal import Decimal
from enum import IntEnum

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models import Value
from django.db.models.functions import Coalesce, Length, NullIf, StrIndex, Substr
from django.utils.translation import gettext_lazy as _

from website.models.intervention_instance import InterventionInstance
from website.models.field_types import SubcomponentAnalysisValuesType
from website.models.fields import TypedJsonField
from website.models.query_utils import require_prefetch


class CostLineItemQuerySet(models.QuerySet):
    def cost_type_category_items(self):
        """
        Returns a queryset excluding non-categorized Line Items
        """
        return self.exclude(Q(is_special_lump_sum=True) | Q(config__analysis_cost_type__isnull=False))

    def order_by(self, *field_names):
        """
        https://stackoverflow.com/questions/50689359/django-natural-sort-queryset/59220344

        Override of builtin order_by so that we can order CostLineItem budget_line_description
        with a `Natural Sort` pattern, i.e.
        1.2.1 Budget Line Description
        1.2.2 Budget Line Description
        1.3 Budget Line Description
        1.3.1 Budget Line Description
        """
        if "budget_line_description" not in field_names:
            return super().order_by(*field_names)

        new_field_names = []
        for field_name in field_names:
            if field_name == "budget_line_description":
                new_field_names.extend(
                    [
                        Coalesce(
                            Substr(
                                "budget_line_description",
                                Value(0),
                                NullIf(
                                    StrIndex("budget_line_description", Value(" ")),
                                    Value(0),
                                ),
                            ),
                            "budget_line_description",
                        ),
                        Length("budget_line_description"),
                        "budget_line_description",
                    ]
                )
            else:
                new_field_names.append(field_name)

        converted_field_names = tuple(new_field_names)
        return super().order_by(*converted_field_names)


CostLineItemManager = models.Manager.from_queryset(CostLineItemQuerySet)


class CostLineItem(models.Model):
    objects = CostLineItemManager()

    analysis = models.ForeignKey(
        "website.Analysis",
        verbose_name=_("Analysis"),
        on_delete=models.CASCADE,
        related_name="unfiltered_cost_line_items",
        # This related is unused but permits the access to ALL the cost line items for an analysis.
        # Code should use `Analysis.cost_line_items` which filters out some corrupted line items.
    )
    country_code = models.CharField(
        verbose_name=_("Country code"),
        max_length=10,
        null=False,
        blank=True,
        default="",
    )
    grant_code = models.CharField(
        verbose_name=_("Grant code"),
        max_length=255,
        null=False,
        blank=True,
        default="",
    )
    budget_line_code = models.CharField(
        verbose_name=_("Budget line code"),
        max_length=255,
        null=False,
        blank=True,
        default="",
    )
    account_code = models.CharField(
        verbose_name=_("Account code"),
        max_length=255,
        null=False,
        blank=True,
        default="",
    )
    site_code = models.CharField(
        verbose_name=_("Site code"),
        max_length=255,
        null=False,
        blank=True,
        default="",
    )
    sector_code = models.CharField(
        verbose_name=_("Sector code"),
        max_length=255,
        null=False,
        blank=True,
        default="",
    )
    budget_line_description = models.CharField(
        verbose_name=_("Budget line description"),
        max_length=1000,
        null=False,
        blank=True,
        default="",
    )
    total_cost = models.DecimalField(
        verbose_name=_("Total cost"),
        max_digits=14,
        decimal_places=settings.DECIMAL_PLACES,
    )
    loe_or_unit = models.DecimalField(
        verbose_name=_("LOE or Unit"),
        max_digits=14,
        decimal_places=settings.DECIMAL_PLACES,
        null=True,
        blank=True,
    )
    months_or_unit = models.DecimalField(
        verbose_name=_("Months or Unit"),
        max_digits=14,
        decimal_places=settings.DECIMAL_PLACES,
        null=True,
        blank=True,
    )
    unit_cost = models.DecimalField(
        verbose_name=_("Unit cost"),
        max_digits=14,
        decimal_places=settings.DECIMAL_PLACES,
        null=True,
        blank=True,
    )
    quantity = models.DecimalField(
        verbose_name=_("Quantity"),
        max_digits=14,
        decimal_places=settings.DECIMAL_PLACES,
        null=True,
        blank=True,
    )
    dummy_field_1 = models.CharField(
        verbose_name=_("Dummy field 1"),
        max_length=255,
        null=False,
        blank=True,
        default="",
    )
    dummy_field_2 = models.CharField(
        verbose_name=_("Dummy field 2"),
        max_length=255,
        null=False,
        blank=True,
        default="",
    )
    note = models.CharField(
        verbose_name=_("Note"),
        max_length=2048,
        null=False,
        blank=True,
        default="",
    )
    cloned_from = models.ForeignKey(
        "website.CostLineItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    is_special_lump_sum = models.BooleanField(
        verbose_name=_("Special Country Lump Sum Cost Item"),
        default=False,
    )

    class Meta:
        verbose_name = _("Cost Line Item")
        verbose_name_plural = _("Cost Line Items")
        indexes = [
            models.Index(
                fields=[
                    "country_code",
                    "grant_code",
                    "budget_line_code",
                    "account_code",
                    "site_code",
                    "sector_code",
                ]
            )
        ]

    def __str__(self) -> str:
        if self.budget_line_description:
            return self.budget_line_description
        else:
            return f"{self.analysis}, (Item {self.id})"

    @classmethod
    def site_code_filter_choices(cls, filter_kwargs=None):
        filter_kwargs = filter_kwargs or {}
        return [
            (p, p)
            for p in cls.objects.filter(**filter_kwargs)
            .order_by("site_code")
            .values_list("site_code", flat=True)
            .distinct()
            if p
        ]

    @classmethod
    def grant_code_filter_choices(cls, filter_kwargs=None):
        filter_kwargs = filter_kwargs or {}
        return [
            (p, p)
            for p in cls.objects.filter(**filter_kwargs)
            .order_by("grant_code")
            .values_list("grant_code", flat=True)
            .distinct()
            if p
        ]

    @classmethod
    def sector_code_filter_choices(cls, filter_kwargs=None):
        filter_kwargs = filter_kwargs or {}
        return [
            (p, p)
            for p in cls.objects.filter(**filter_kwargs)
            .order_by("sector_code")
            .values_list("sector_code", flat=True)
            .distinct()
            if p
        ]

    @property
    def allocated_cost_on_model(self) -> Decimal:
        """
        This is here to replace the Query annotations that I'm seeing in the code that look like this:
        def _get_cost_line_items(an_analysis: Analysis):
            return an_analysis.cost_line_items.annotate(
                allocated_cost=F("total_cost") * (F("config__allocation") / Value(100))
                ).order_by("-allocated_cost")

        At the moment I don't know why those were done that way.  Is it a style choice?  An optimization?
        I need/want it here, so I'll set it and possibly refactor in the future.

        ~RJ 09/15/2023
        """
        if hasattr(self, "config"):
            return self.total_cost * Decimal(sum(a.allocation for a in self.config.allocations.all()) / 100)
        else:
            return Decimal("0")

    def set_allocation_for_intervention(
        self,
        intervention_instance: InterventionInstance,
        allocation: Decimal,
    ) -> None:
        try:
            item = self.config.allocations.get(intervention_instance=intervention_instance)
        except CostLineItemInterventionAllocation.DoesNotExist:
            item = self.config.allocations.create(intervention_instance=intervention_instance)
        item.allocation = allocation
        item.save()

    def labeled_subcomponent_analysis_allocations(self) -> list[tuple[str, Decimal]]:
        """
        Zip the Labels in the subcomponent_cost_analysis with the values in the CostLineItemConfig

        This is done to populate the initial values on the form without including things that don't have labels.
        """
        labeled_values = []
        if not self.config.subcomponent_analysis_allocations:
            self.config.subcomponent_analysis_allocations = {}
        for i, label in enumerate(self.analysis.subcomponent_cost_analysis.subcomponent_labels):
            value = self.config.subcomponent_analysis_allocations.get(str(i), Decimal(0))
            labeled_values.append((label, value))
        return labeled_values


class AnalysisCostType(IntEnum):
    CLIENT_TIME = 1
    IN_KIND = 2
    OTHER_HQ = 3

    @classmethod
    def get_pretty_analysis_cost_type(cls, analysis_cost_type):
        pretty_map = {
            cls.CLIENT_TIME: "Client Time",
            cls.IN_KIND: "In-Kind Contributions",
            cls.OTHER_HQ: "Other HQ Costs",
        }
        return pretty_map[analysis_cost_type]


class CostLineItemConfig(models.Model):
    ANALYSIS_COST_TYPE_CHOICES = [(t.value, t.name) for t in AnalysisCostType]

    cost_line_item = models.OneToOneField(
        CostLineItem,
        verbose_name=_("Cost Line Item"),
        on_delete=models.CASCADE,
        related_name="config",
    )
    cost_type = models.ForeignKey(
        "website.CostType",
        verbose_name=_("Cost Type"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    category = models.ForeignKey(
        "website.Category",
        verbose_name=_("Category"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    analysis_cost_type = models.IntegerField(
        null=True,
        blank=True,
        choices=ANALYSIS_COST_TYPE_CHOICES,
    )
    cloned_from = models.ForeignKey(
        "website.CostLineItemConfig",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    subcomponent_analysis_allocations = TypedJsonField(
        typed_json=SubcomponentAnalysisValuesType,
        default=dict,
        null=True,
    )
    subcomponent_analysis_allocations_skipped = models.BooleanField(
        default=False,
    )

    @property
    def get_pretty_analysis_cost_type(self):
        return AnalysisCostType.get_pretty_analysis_cost_type(self.analysis_cost_type)

    def allocations_by_intervention_id(self) -> dict[int, CostLineItemInterventionAllocation]:
        return {a.intervention_instance.id: a.allocation for a in require_prefetch(self, "allocations")}

    def get_sole_allocator(self) -> InterventionInstance | None:
        if self.allocations.filter(allocation=100).exists():
            return self.allocations.filter(allocation=100).first().intervention_instance
        else:
            return None

    @property
    def get_sole_allocator_name(self) -> str:
        """
        This is a `@property` due to it being used in a very specific case in a django template
        where the value is being dynamically applied.
        At the time of the commit the relevant code is in:
            website.views.analysis.steps.add_other_costs.AddOtherCostsDetail.get_context_data
        """
        return self.get_sole_allocator().display_name()


class CostLineItemInterventionAllocation(models.Model):
    cli_config = models.ForeignKey(
        "website.CostLineItemConfig",
        on_delete=models.CASCADE,
        related_name="allocations",
    )

    intervention_instance = models.ForeignKey(
        "website.InterventionInstance",
        on_delete=models.CASCADE,
    )

    allocation = models.DecimalField(
        verbose_name=_("% allocation to intervention"),
        max_digits=7,
        decimal_places=settings.DECIMAL_PLACES,
        null=True,
        blank=True,
    )

    cloned_from = models.ForeignKey(
        "website.CostLineItemInterventionAllocation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    def __str__(self):
        return f"{self.cli_config.cost_line_item} - {self.intervention_instance.label}: {self.allocation}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cli_config", "intervention_instance"],
                name="unique_cli_config_intervention",
            )
        ]
