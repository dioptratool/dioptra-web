from django.db import models
from django.utils.translation import gettext_lazy as _


class AnalysisType(models.Model):
    title = models.CharField(
        verbose_name=_("Title"),
        max_length=255,
    )

    class Meta:
        ordering = ["title"]
        verbose_name = _("Analysis Type")
        verbose_name_plural = _("Analyses Types")

    def __str__(self) -> str:
        return self.title
