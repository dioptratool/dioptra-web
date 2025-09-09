import dataclasses
import datetime
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


@dataclasses.dataclass
class TransactionLike:
    """When we bulk-import, we have all the transaction dicts. There's no need to re-query them.
    But sometimes we don't bulk-import, and may not have them. This is similar enough
    to a Transaction that we can use it in many places.
    """

    id: int
    date: datetime.date
    country_code: str
    grant_code: str
    budget_line_code: str
    account_code: str
    site_code: str
    sector_code: str
    transaction_code: str
    transaction_description: str
    currency_code: str
    budget_line_description: str
    amount_in_instance_currency: Decimal
    amount_in_source_currency: Decimal
    dummy_field_1: str
    dummy_field_2: str
    dummy_field_3: str
    dummy_field_4: str
    dummy_field_5: str
    analysis_id: int
    cost_line_item_id: int | None = None


class Transaction(models.Model):
    analysis = models.ForeignKey(
        "website.Analysis",
        verbose_name=_("Analysis"),
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    cost_line_item = models.ForeignKey(
        "website.CostLineItem",
        verbose_name=_("Cost Line Item"),
        null=True,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    date = models.DateField(
        verbose_name=_("Date"),
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
    transaction_code = models.CharField(
        verbose_name=_("Transaction code"),
        max_length=255,
        null=False,
        blank=True,
        default="",
    )
    transaction_description = models.TextField(
        verbose_name=_("Transaction description"),
        null=False,
        blank=True,
        default="",
    )
    currency_code = models.CharField(
        verbose_name=_("Currency code"),
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
    amount_in_instance_currency = models.DecimalField(
        verbose_name=_("Amount, in instance currency"),
        max_digits=14,
        decimal_places=settings.DECIMAL_PLACES,
    )
    amount_in_source_currency = models.DecimalField(
        verbose_name=_("Amount, in source currency"),
        max_digits=14,
        decimal_places=settings.DECIMAL_PLACES,
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
    dummy_field_3 = models.CharField(
        verbose_name=_("Dummy field 3"),
        max_length=255,
        null=False,
        blank=True,
        default="",
    )
    dummy_field_4 = models.CharField(
        verbose_name=_("Dummy field 4"),
        max_length=255,
        null=False,
        blank=True,
        default="",
    )
    dummy_field_5 = models.CharField(
        verbose_name=_("Dummy field 5"),
        max_length=255,
        null=False,
        blank=True,
        default="",
    )
    cloned_from = models.ForeignKey(
        "website.Transaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = _("Transaction")
        verbose_name_plural = _("Transaction")
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
