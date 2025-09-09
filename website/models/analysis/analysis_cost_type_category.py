from django.db import models
from django.utils.translation import gettext_lazy as _


class AnalysisCostTypeCategory(models.Model):
    analysis = models.ForeignKey(
        "website.Analysis",
        verbose_name=_("Analysis"),
        on_delete=models.CASCADE,
        related_name="cost_type_categories",
    )
    cost_type = models.ForeignKey(
        "website.CostType",
        verbose_name=_("CostType"),
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
    )
    category = models.ForeignKey(
        "website.Category",
        verbose_name=_("Category"),
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
    )
    confirmed = models.BooleanField(
        verbose_name=_("Confirmed?"),
        default=False,
    )
    cloned_from = models.ForeignKey(
        "website.AnalysisCostTypeCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["cost_type__order", "category__order"]

    def __repr__(self):
        return f"<AnalysisCostTypeCategory: {self.cost_type} :: {self.category} for: {self.analysis.title} >"

    def get_cost_line_items(self):
        return (
            self.analysis.cost_line_items.filter(
                config__cost_type=self.cost_type,
                config__category=self.category,
            )
            .select_related("config")
            .prefetch_related("transactions")
            .order_by(
                "grant_code",
                "budget_line_description",
                "site_code",
                "sector_code",
                "account_code",
            )
        )
