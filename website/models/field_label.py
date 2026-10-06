from django.db import models
from django.utils.translation import gettext_lazy as _


class FieldLabelOverrides(models.Model):
    app_log_entry_link_name = "ombucore.admin:website_fieldlabeloverrides_change"

    tr_date = models.CharField(_("Date"), max_length=40, null=True, blank=True)
    tr_date_overridden = models.BooleanField(_("Overridden"), default=False)

    tr_site_code = models.CharField(_("Site Code"), max_length=40, null=True, blank=True)
    tr_site_code_overridden = models.BooleanField(_("Overridden"), default=False)

    tr_amount = models.CharField(_("Amount"), max_length=40, null=True, blank=True)
    tr_amount_overridden = models.BooleanField(_("Overridden"), default=False)

    tr_dummy_field_1 = models.CharField(_("Transaction Custom Field 1"), max_length=40, null=True, blank=True)
    tr_dummy_field_1_overridden = models.BooleanField(_("Overridden"), default=False)

    tr_dummy_field_2 = models.CharField(_("Transaction Custom Field 2"), max_length=40, null=True, blank=True)
    tr_dummy_field_2_overridden = models.BooleanField(_("Overridden"), default=False)

    tr_dummy_field_3 = models.CharField(_("Transaction Custom Field 3"), max_length=40, null=True, blank=True)
    tr_dummy_field_3_overridden = models.BooleanField(_("Overridden"), default=False)

    tr_dummy_field_4 = models.CharField(_("Transaction Custom Field 4"), max_length=40, null=True, blank=True)
    tr_dummy_field_4_overridden = models.BooleanField(_("Overridden"), default=False)

    tr_dummy_field_5 = models.CharField(_("Transaction Custom Field 5"), max_length=40, null=True, blank=True)
    tr_dummy_field_5_overridden = models.BooleanField(_("Overridden"), default=False)

    ci_grant_code = models.CharField(_("Grant Code"), max_length=40, null=True, blank=True)
    ci_grant_code_overridden = models.BooleanField(_("Overridden"), default=False)

    ci_site_code = models.CharField(_("Site Code"), max_length=40, null=True, blank=True)
    ci_site_code_overridden = models.BooleanField(_("Overridden"), default=False)

    ci_account_code = models.CharField(_("Account Code"), max_length=40, null=True, blank=True)
    ci_account_code_overridden = models.BooleanField(_("Overridden"), default=False)

    ci_sector_code = models.CharField(_("Sector Code"), max_length=40, null=True, blank=True)
    ci_sector_code_overridden = models.BooleanField(_("Overridden"), default=False)

    ci_budget_line_description = models.CharField(
        _("Budget Line Description"), max_length=40, null=True, blank=True
    )
    ci_budget_line_description_overridden = models.BooleanField(_("Overridden"), default=False)

    ci_cost_type = models.CharField(_("Cost Type"), max_length=40, null=True, blank=True)
    ci_cost_type_overridden = models.BooleanField(_("Overridden"), default=False)

    ci_total_cost = models.CharField(_("Total Cost"), max_length=40, null=True, blank=True)
    ci_total_cost_overridden = models.BooleanField(_("Overridden"), default=False)

    ci_dummy_field_1 = models.CharField(_("Budget Custom Field 1"), max_length=40, null=True, blank=True)
    ci_dummy_field_1_overridden = models.BooleanField(_("Overridden"), default=False)

    ci_dummy_field_2 = models.CharField(_("Budget Custom Field 2"), max_length=40, null=True, blank=True)
    ci_dummy_field_2_overridden = models.BooleanField(_("Overridden"), default=False)

    ci_dummy_field_3 = models.CharField(_("Budget Custom Field 3"), max_length=40, null=True, blank=True)
    ci_dummy_field_3_overridden = models.BooleanField(_("Overridden"), default=False)

    ci_dummy_field_4 = models.CharField(_("Budget Custom Field 4"), max_length=40, null=True, blank=True)
    ci_dummy_field_4_overridden = models.BooleanField(_("Overridden"), default=False)

    ci_dummy_field_5 = models.CharField(_("Budget Custom Field 5"), max_length=40, null=True, blank=True)
    ci_dummy_field_5_overridden = models.BooleanField(_("Overridden"), default=False)

    @classmethod
    def label_for(cls, field_name, default=None):
        obj = cls.get()
        if hasattr(obj, field_name) and getattr(obj, f"{field_name}_overridden", False):
            return getattr(obj, field_name)
        return default

    def __str__(self):
        return "Field Label Overrides"

    @classmethod
    def get(cls):
        try:
            return cls.objects.get()
        except cls.DoesNotExist:
            return cls.objects.create()

    class Meta:
        verbose_name = _("Field Label Overrides")
        verbose_name_plural = _("Field Label Overrides")
