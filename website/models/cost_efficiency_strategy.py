from ckeditor.fields import RichTextField
from django.db import models
from django.utils.translation import gettext_lazy as _

from ombucore.admin.fields import ManyToManyField


class CostEfficiencyStrategy(models.Model):
    app_log_entry_link_name = "ombucore.admin:website_costefficiencystrategy_change"
    title = models.CharField(
        verbose_name=_("Title"),
        max_length=255,
    )
    interventions = ManyToManyField(
        "website.Intervention",
        verbose_name=_("Intervention Being Analyzed"),
    )
    efficiency_driver_description = RichTextField(
        verbose_name=_("Efficiency Driver description"),
        blank=True,
        null=True,
    )
    strategy_to_improve_description = RichTextField(
        verbose_name=_("Strategy to Improve Cost-Efficiency description"),
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = _("Cost Efficiency Strategy")
        verbose_name_plural = _("Cost Efficiency Strategies")
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title
