from any_urlfield.models import AnyUrlField
from ckeditor.fields import RichTextField
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from ombucore.admin.fields import UrlPathField
from website.help.fields import HelpItemType


def generate_path(obj, source_field):
    path = getattr(obj, "path", None)
    if not path:
        path = slugify(getattr(obj, source_field))
    i, exists = 0, True
    while exists:
        path = f"{path}{f'-{i}' if i > 0 else ''}"
        exists = obj._meta.default_manager.filter(path=path).exclude(pk=obj.id).exists()
        i += 1
    return path


class HelpTopic(models.Model):
    title = models.CharField(max_length=255)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Help Topic"
        verbose_name_plural = "Help Topics"
        ordering = ("title",)


class HelpItem(models.Model):
    app_log_entry_link_name = "ombucore.admin:help_helpitem_change"

    type = models.CharField(choices=HelpItemType.choices(), max_length=50)

    title = models.CharField(max_length=255)
    identifier = models.CharField(max_length=150)

    help_text = RichTextField(
        config_name="help_text",
        blank=True,
        help_text="If you leave this field blank, the contextual help item will not display in the application.",
    )
    link = AnyUrlField("More help", blank=True, null=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Contextual Help"
        verbose_name_plural = "Contextual Help"
        ordering = ("title",)


class HelpPage(models.Model):
    app_log_entry_link_name = "ombucore.admin:help_helppage_change"
    identifier = models.CharField(max_length=150, null=True, blank=True)
    title = models.CharField(max_length=255)
    body = RichTextField(blank=True)

    path = UrlPathField(
        "Path",
        max_length=200,
        blank=True,
        help_text="This is the desired URL path for this page. If you leave this field blank, a "
        "path will be created for you by hyphenating your page title. If you choose "
        "to manually create a path, it may include letters, numbers, hyphens, and "
        "forward slashes (e.g., ‘help/define-step’).",
    )

    topic = models.ForeignKey(
        "HelpTopic",
        verbose_name="Section",
        on_delete=models.PROTECT,
        help_text="This help page will appear alphabetically under this topic in the help menu when published.",
    )

    published = models.BooleanField(
        default=True,
        help_text="When published, this page will appear in the help menu.",
    )

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("help-page", kwargs={"path": self.path})

    def save(self, **kwargs):
        self.path = generate_path(self, "title")
        super().save(**kwargs)

    class Meta:
        verbose_name = "Help Page"
        verbose_name_plural = "Help Pages"
        ordering = ("title",)


AnyUrlField.register_model(HelpPage)
