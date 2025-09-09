from __future__ import annotations

from collections.abc import Iterable

from django.db import models
from django.utils.translation import gettext_lazy as _

from ombucore.admin.fields import ForeignKey
from website import betterdb, stopwatch
from .category import Category
from .cost_line_item import CostLineItem, CostLineItemConfig
from .cost_type import CostType


class CostTypeCategoryMapping(models.Model):
    app_log_entry_link_name = "ombucore.admin:website_costtypecategorymapping_change"

    country_code = models.CharField(
        verbose_name=_("Country code"),
        max_length=255,
        null=True,
        blank=True,
    )
    grant_code = models.CharField(
        verbose_name=_("Grant code"),
        max_length=255,
        null=True,
        blank=True,
    )
    budget_line_code = models.CharField(
        verbose_name=_("Budget line code"),
        max_length=255,
        null=True,
        blank=True,
    )
    account_code = models.CharField(
        verbose_name=_("Account code"),
        max_length=255,
        null=True,
        blank=True,
    )
    site_code = models.CharField(
        verbose_name=_("Site code"),
        max_length=255,
        null=True,
        blank=True,
    )
    sector_code = models.CharField(
        verbose_name=_("Sector code"),
        max_length=255,
        null=True,
        blank=True,
    )
    budget_line_description = models.CharField(
        verbose_name=_("Budget line description"),
        max_length=255,
        null=True,
        blank=True,
    )
    cost_type = ForeignKey(
        CostType,
        verbose_name=_("Cost Type"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    category = ForeignKey(
        Category,
        verbose_name=_("Category"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    criteria_fields = [
        "country_code",
        "grant_code",
        "budget_line_code",
        "account_code",
        "site_code",
        "sector_code",
        "budget_line_description",
    ]

    class Meta:
        verbose_name = _("Cost Type / Category Mapping")
        verbose_name_plural = _("Cost Type / Category Mappings")

    def __str__(self):
        return str(self._meta.verbose_name)

    @classmethod
    @stopwatch.trace()
    def auto_categorize_cost_line_items(cls, cost_line_items: Iterable[CostLineItem]):
        default_category = Category.get_default()
        default_cost_type = CostType.get_default()
        mappings = cls.generate_mappings()
        to_insert = []
        to_update = []
        for cost_line_item in cost_line_items:
            # All dicts must have the same keys for insert or update
            if hasattr(cost_line_item, "config"):
                config = {
                    "id": cost_line_item.config.id,
                    "cost_type_id": cost_line_item.config.cost_type_id,
                    "category_id": cost_line_item.config.category_id,
                    "subcomponent_analysis_allocations_skipped": cost_line_item.config.subcomponent_analysis_allocations_skipped,
                }
                is_new = False
            else:
                config = {
                    "cost_line_item_id": cost_line_item.id,
                    "cost_type_id": None,
                    "category_id": None,
                    "subcomponent_analysis_allocations_skipped": False,
                }
                is_new = True
            # We can have a LOT of line items.
            # We want to make sure we only update the ones that have changed.
            cost_type_set = False
            category_set = False
            for mapping in mappings:
                if cls.cost_line_item_matches(mapping, cost_line_item):
                    mapped_cost_type = mapping["result"]["cost_type"]
                    if mapped_cost_type and config["cost_type_id"] != mapped_cost_type.id:
                        config["cost_type_id"] = mapped_cost_type.id
                        cost_type_set = True

                    mapped_category = mapping["result"]["category"]
                    if mapped_category and config["category_id"] != mapped_category.id:
                        config["category_id"] = mapped_category.id
                        category_set = True

            if not config["category_id"]:
                config["category_id"] = default_category.id
                category_set = True

            if not config["cost_type_id"]:
                config["cost_type_id"] = default_cost_type.id
                cost_type_set = True
            if is_new:
                to_insert.append(config)
            elif category_set or cost_type_set:
                to_update.append(config)
        betterdb.bulk_insert(CostLineItemConfig, to_insert)
        betterdb.bulk_update_dicts(CostLineItemConfig, to_update)

    @classmethod
    def cost_line_item_matches(cls, mapping, cost_line_item):
        for field, value in mapping["criteria"].items():
            if not getattr(cost_line_item, field) == value:
                return False
        return True

    @classmethod
    def generate_mappings(cls) -> list[dict]:
        mappings = []
        for mapping in cls.objects.prefetch_related("cost_type", "category").all():
            m = {
                "criteria": {},
                "result": {
                    "cost_type": getattr(mapping, "cost_type", None),
                    "category": getattr(mapping, "category", None),
                },
            }
            for field in cls.criteria_fields:
                value = getattr(mapping, field, None)
                if value:
                    m["criteria"][field] = value

            mappings.append(m)
        mappings.sort(key=lambda m: len(m["criteria"].keys()))
        return mappings
