import os

from django.conf import settings
from django.core.validators import get_available_image_extensions
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch.dispatcher import receiver
from django.utils import timezone
from django.utils.html import format_html
from imagekit.cachefiles import ImageCacheFile
from imagekit.registry import generator_registry
from mptt.models import MPTTModel, TreeForeignKey
from polymorphic.models import PolymorphicModel
from taggit_autosuggest.managers import TaggableManager

from .renderers import DocumentRenderer, ImageRenderer, render_label
from .validators import FileExtensionValidator


class AssetFolder(MPTTModel):
    title = models.CharField(max_length=200)
    created = models.DateTimeField("created", editable=False, default=timezone.now)
    parent = TreeForeignKey(
        "self",
        null=True,
        blank=True,
        verbose_name="Parent Folder",
        related_name="children",
        help_text="The parent folder to put this folder under.",
        on_delete=models.SET_NULL,
    )

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Folder"


class Asset(PolymorphicModel):
    """
    Base polymorphic for all asset classes.
    """

    title = models.CharField(max_length=200)
    created = models.DateTimeField("created", editable=False, default=timezone.now)
    tags = TaggableManager(blank=True, help_text="Find tags by name or create new ones.")
    folder = TreeForeignKey(
        "assetfolder",
        null=True,
        blank=True,
        verbose_name="Asset Folder",
        related_name="folder",
        help_text="The folder to put this asset into.",
        on_delete=models.SET_NULL,
    )
    caption = models.CharField(max_length=255, blank=True)
    hide_caption = models.BooleanField(default=False)

    def __str__(self):
        return self.title

    def render_embedded(self, local_settings=None, render_fn=render_label):
        return render_fn(self, local_settings)

    class Meta:
        verbose_name = "Asset"
        verbose_name_plural = "Assets"
        ordering = ["-created"]


class ImageAsset(Asset):
    image = models.ImageField(
        upload_to="img",
        width_field="width",
        height_field="height",
        help_text=getattr(settings, "OMBUASSETS_IMAGE_HELP_TEXT", None),
        validators=[
            FileExtensionValidator(
                whitelist=getattr(
                    settings,
                    "OMBUASSETS_IMAGE_WHITELIST",
                    get_available_image_extensions(),
                ),
            )
        ],
    )
    width = models.CharField(max_length=20, blank=True)
    height = models.CharField(max_length=20, blank=True)

    @property
    def url(self):
        return self.image.url

    def resized_image(self, generator_name="assets:preview_thumbnail"):
        generator = generator_registry.get(generator_name, source=self.image)
        return ImageCacheFile(generator)

    def render_embedded(self, local_settings=None, render_fn=ImageRenderer()):
        return render_fn(self, local_settings)

    def render_preview(self):
        url = self.resized_image().url
        title = self.title
        return format_html('<img src="{url}" title="{title}" />', url=url, title=title)

    render_preview.allow_tags = True
    render_preview.short_description = "Image"

    @classmethod
    def folder_filter_choices(cls):
        return [("", "All")] + cls.FOLDERS

    class Meta:
        verbose_name = "Image"
        verbose_name_plural = "Images"


DOCUMENT_TYPES_WHITELIST = getattr(
    settings,
    "DOCUMENT_TYPES_WHITELIST",
    (
        "ppt",
        "pptx",
        "pdf",
        "doc",
        "docx",
        "xls",
        "xlt",
        "txt",
        "ZIP",
    ),
)

DOCUMENT_TYPE_NAME_MAP = getattr(
    settings,
    "DOCUMENT_TYPE_NAME_MAP",
    {
        "ppt": "Microsoft PowerPoint Document",
        "pptx": "Microsoft PowerPoint Document",
        "pdf": "PDF Document",
        "doc": "Microsoft Word Document",
        "docx": "Microsoft Word Document",
        "xls": "Microsoft Excel Document",
        "xlsx": "Microsoft Excel Document",
        "xlt": "Microsoft Excel Document",
        "txt": "Text Document",
        "zip": "ZIP Archive",
    },
)


class DocumentAsset(Asset):
    document = models.FileField(
        upload_to="doc", validators=[FileExtensionValidator(DOCUMENT_TYPES_WHITELIST)]
    )
    file_type = models.CharField(max_length=100)

    def clean(self):
        self.populate_file_type()

    def populate_file_type(self):
        filename = self.document.name
        ext = os.path.splitext(filename)[1].split(".")[-1].lower()
        self.file_type = ext

    def render_preview(self):
        return format_html("{title} ({file_type})", title=self.title, file_type=self.file_type)

    def render_embedded(self, local_settings=None, render_fn=DocumentRenderer()):
        return render_fn(self, local_settings)

    def human_file_type(self):
        return DOCUMENT_TYPE_NAME_MAP.get(self.file_type, self.file_type)

    @classmethod
    def file_type_filter_choices(cls):
        return [("", "All")] + [
            (t, DOCUMENT_TYPE_NAME_MAP[t])
            for t in DocumentAsset.objects.values_list("file_type", flat=True).distinct()
        ]

    @property
    def url(self):
        return self.document.url

    class Meta:
        verbose_name = "Document"
        verbose_name_plural = "Documents"


@receiver(pre_save, sender=DocumentAsset)
def document_pre_save(sender, instance, **kwargs):
    document = instance
    document.populate_file_type()


def wrap_in_aspect_box(html, nativeWidth, nativeHeight):
    template = "<div class='aspect-ratio-box'><span class='aspect-prop' style='padding-top: {ratioPercentage}%;'></span>{html}</div>"
    ratioPercentage = (float(nativeHeight) / float(nativeWidth)) * 100
    return template.format(ratioPercentage=ratioPercentage, html=html)
