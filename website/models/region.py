from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from ombucore.admin.fields import ForeignKey


class Region(models.Model):
    app_log_entry_link_name = "ombucore.admin:website_region_change"
    name = models.CharField(
        verbose_name=_("Name"),
        max_length=255,
    )
    region_code = models.CharField(
        verbose_name=_("Region Code"),
        max_length=255,
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Region")
        verbose_name_plural = _("Regions")
        ordering = ["name"]


class Country(models.Model):
    app_log_entry_link_name = "ombucore.admin:website_country_change"

    name = models.CharField(verbose_name=_("Name"), max_length=255, unique=True)
    code = models.CharField(
        verbose_name=_("Code"),
        max_length=10,
    )
    region = ForeignKey(
        Region,
        verbose_name=_("Region"),
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    is_default = models.BooleanField(
        default=False,
        help_text="If selected, new user accounts will be assigned this country as the account's primary country.",
        verbose_name="Default country for new users",
    )
    always_include_costs = models.BooleanField(
        default=False,
        help_text="If selected, cost items from this country will always be imported, regardless of the country "
        "filters configured for the analysis or the instance",
        verbose_name="Always include costs from this country into analyses",
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Country")
        verbose_name_plural = _("Countries")
        ordering = ["name"]

    @classmethod
    def get_default_country(cls):
        return cls.objects.filter(is_default=True).first()

    @classmethod
    def get_always_include_countries(cls):
        return cls.objects.filter(always_include_costs=True)
