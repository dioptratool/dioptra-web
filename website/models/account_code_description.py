from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _


class AccountCodeDescription(models.Model):
    app_log_entry_link_name = "ombucore.admin:website_accountcodedescription_change"
    account_code = models.CharField(
        verbose_name=_("Account Code"),
        max_length=255,
    )
    account_description = models.CharField(
        verbose_name=_("Account Description"),
        max_length=255,
    )
    sensitive_data = models.BooleanField(
        verbose_name=_("Contains sensitive data"),
        help_text=_("When checked, costs and transactions will not be shown for this account code."),
        default=False,
    )

    class Meta:
        verbose_name = _("Account Code Description")
        verbose_name_plural = _("Account Code Description")

    def __str__(self) -> str:
        return self.account_code

    @classmethod
    def as_map(cls) -> dict[str, AccountCodeDescription]:
        return {acd.account_code: acd for acd in AccountCodeDescription.objects.all()}
