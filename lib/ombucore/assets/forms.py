import django_filters
from mptt.forms import TreeNodeChoiceField

from ombucore.admin.forms.base import ModelFormBase
from ombucore.imagewidget.fields import PreviewableImageInput
from .models import AssetFolder, DocumentAsset, ImageAsset


class TreeNodeChoiceFilter(django_filters.Filter):
    """
    django-filters ModelChoiceFilter uses the ModelChoiceField class from django.forms.
    We were using ModelChoiceFilter to filter our AssetFolders. Since we don't want to
    display folders as a flat select, but instead as a hierarchically sorted select, we subclass
    django-filters Filter and set the field_class to TreeNodeChoiceField, which is used
    by mptt, the base for our AssetFolder class.
    """

    field_class = TreeNodeChoiceField


class ImageForm(ModelFormBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tags"].widget.attrs = {"placeholder": "Begin typing"}

    class Meta:
        model = ImageAsset
        widgets = {
            "image": PreviewableImageInput(),
        }
        fields = (
            "title",
            "image",
            "tags",
            "folder",
            "caption",
            "hide_caption",
        )
        fieldsets = (
            (
                "Basic",
                {
                    "fields": (
                        "title",
                        "image",
                        "tags",
                        "folder",
                        "caption",
                        "hide_caption",
                    ),
                },
            ),
        )


class DocumentForm(ModelFormBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tags"].widget.attrs = {"placeholder": "Begin typing"}

    class Meta:
        model = DocumentAsset
        fields = ("title", "document", "tags", "folder")
        fieldsets = (
            (
                "Basic",
                {
                    "fields": ("title", "document", "tags", "folder"),
                },
            ),
        )


class FolderForm(ModelFormBase):
    class Meta:
        model = AssetFolder
        fields = (
            "title",
            "parent",
        )
        fieldsets = (
            (
                "Basic",
                {
                    "fields": ("title",),
                },
            ),
            (
                "Position",
                {
                    "fields": ("parent",),
                },
            ),
        )
