from django.core.validators import validate_image_file_extension
from django.db import models
from django.utils.translation import gettext_lazy as _

from website.data_loading.transaction_templates.registry import (
    DEFAULT_TRANSACTION_TEMPLATE_ID,
    get_transaction_template_choices,
)
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
        help_text=_(
            "Optional override. Leave blank -- or tick Clear -- to offer a template generated "
            "from the columns the budget importer actually reads, including any custom "
            "fields. Upload a file only if this instance needs a bespoke template."
        ),
        null=True,
        blank=True,
    )

    transaction_data_template = models.CharField(
        verbose_name=_("Transaction Import Template"),
        help_text=_("The transaction upload template available on the Load Data step."),
        max_length=100,
        choices=get_transaction_template_choices,
        default=DEFAULT_TRANSACTION_TEMPLATE_ID,
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
