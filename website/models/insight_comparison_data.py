from django.db import models
from django.utils.translation import gettext_lazy as _


class InsightComparisonData(models.Model):
    app_log_entry_link_name = "ombucore.admin:website_insightcomparisondata_change"
    name = models.CharField(
        verbose_name=_("Name"),
        max_length=255,
    )
    country = models.ForeignKey(
        "website.Country",
        verbose_name=_("Country"),
        on_delete=models.PROTECT,
        related_name="+",
    )
    grants = models.CharField(max_length=255)
    intervention = models.ForeignKey(
        "website.Intervention",
        verbose_name=_("Intervention Being Analyzed"),
        on_delete=models.PROTECT,
    )
    parameters = models.JSONField(default=dict)
    output_costs = models.JSONField(default=dict)

    class Meta:
        verbose_name = _("Insight Comparison Data Point")
        verbose_name_plural = _("Insight Comparison Data")

    def __str__(self) -> str:
        return self.name

    def grants_list(self) -> list[str]:
        return [g.strip() for g in self.grants.split(",")]
