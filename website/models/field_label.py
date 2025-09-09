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

    ci_grant_code = models.CharField(_("Grant Code"), max_length=40, null=True, blank=True)
    ci_grant_code_overridden = models.BooleanField(_("Overridden"), default=False)

    ci_site_code = models.CharField(_("Site Code"), max_length=40, null=True, blank=True)
    ci_site_code_overridden = models.BooleanField(_("Overridden"), default=False)

    ci_cost_type = models.CharField(_("Cost Type"), max_length=40, null=True, blank=True)
    ci_cost_type_overridden = models.BooleanField(_("Overridden"), default=False)

    ci_total_cost = models.CharField(_("Total Cost"), max_length=40, null=True, blank=True)
    ci_total_cost_overridden = models.BooleanField(_("Overridden"), default=False)

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
