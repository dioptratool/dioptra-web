from django.core.validators import validate_image_file_extension
from django.db import models
from django.utils.translation import gettext_lazy as _

from website.validators import FileSizeValidator


class Settings(models.Model):
    google_analytics_code = models.CharField(
        verbose_name=_("Google Analytics tracking ID"),
        help_text=_('E.g. "UA-10304692-04"'),
        null=True,
        blank=True,
        max_length=100,
    )

    show_transactions = models.BooleanField(
        verbose_name=_("Show Transaction Data"),
        help_text=_(
            "If enabled, the underlying transactions for all cost line items will be displayed, if available."
        ),
        default=True,
    )

    budget_upload_template = models.FileField(
        verbose_name=_("Budget Upload Template"),
        null=True,
        blank=True,
    )

    instance_logo = models.ImageField(
        verbose_name=_("Instance Logo"),
        null=True,
        blank=True,
        validators=[FileSizeValidator(), validate_image_file_extension],
    )

    paginate_by = models.IntegerField(
        verbose_name=_("Paginate by"),
        choices=(
            (10, "10"),
            (25, "25"),
            (50, "50"),
            (100, "100"),
        ),
        default=25,
    )

    transaction_country_filter = models.BooleanField(
        verbose_name=_("Transaction Country Filter"),
        default=False,
        help_text="If enabled, transactions loaded from the transaction data store "
        "for each analysis will be limited to the country selected.",
    )

    class Meta:
        verbose_name = _("Settings")
        verbose_name_plural = _("Settings")

    def __str__(self) -> str:
        return str(self.__class__._meta.verbose_name)

    @classmethod
    def country_filtering_enabled(cls) -> bool:
        dioptra_settings = cls.objects.first()
        if not dioptra_settings:
            return False

        return dioptra_settings.transaction_country_filter
