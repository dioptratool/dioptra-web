from __future__ import annotations

from ckeditor.fields import RichTextField
from django.conf import settings
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _

from website.models.mixins import OrderableMixin


class Category(OrderableMixin, models.Model):
    app_log_entry_link_name = "ombucore.admin:website_category_change"
    name = models.CharField(
        verbose_name=_("Name"),
        max_length=255,
    )
    description = models.TextField(
        verbose_name=_("Description"),
    )
    order = models.PositiveIntegerField(
        verbose_name=_("Sort Order"),
    )

    help_text = RichTextField(blank=True, verbose_name="Allocation Suggestion Help Text")
    default = models.BooleanField(default=False, verbose_name=_("Default"))

    class Meta:
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")
        ordering = ["order"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # This ensures only one instance is set to default
        if self.default:
            with transaction.atomic():
                Category.objects.filter(default=True).update(default=False)
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

        # If we get into a state where nothing is the default we set it to the Instance's default to the default
        with transaction.atomic():
            if not Category.objects.filter(default=True).exists():
                default_cat = Category.objects.get(name=settings.DEFAULT_CATEGORY)
                default_cat.default = True
                default_cat.save(update_fields=["default"])

    @classmethod
    def get_default(cls) -> Category:
        return cls.objects.get(default=True)
