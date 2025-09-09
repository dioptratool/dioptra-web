import django_filters
from django.forms import widgets
from imagekit.cachefiles import ImageCacheFile
from imagekit.registry import generator_registry
from taggit.models import Tag

from ombucore.admin.filterset import FilterSet
from ombucore.admin.modeladmin import ModelAdmin
from ombucore.admin.sites import site as admin_site
from ombucore.admin.views import NestedReorderView, PreviewView
from .forms import DocumentForm, FolderForm, ImageForm, TreeNodeChoiceFilter
from .models import AssetFolder, DocumentAsset, ImageAsset


class ImageAssetFilterSet(FilterSet):
    search = django_filters.CharFilter(
        field_name="title",
        lookup_expr="icontains",
        help_text="",
    )
    folder = TreeNodeChoiceFilter(queryset=AssetFolder.objects.all())
    tags = django_filters.ModelChoiceFilter(
        queryset=Tag.objects.all().order_by("name"), widget=widgets.Select
    )
    order_by = django_filters.OrderingFilter(
        choices=(
            ("-created", "Created (newest first)"),
            ("created", "Created (oldest first)"),
        ),
        empty_label=None,
    )

    class Meta:
        model = ImageAsset
        fields = ["search", "folder"]


class ImagePreviewView(PreviewView):
    template_name = "assets/panel-preview-image.html"


class ImageAssetAdmin(ModelAdmin):
    form_class = ImageForm
    filterset_class = ImageAssetFilterSet
    preview_view = ImagePreviewView
    list_display_grid = True
    list_display = (("render_preview", "Preview"),)

    def modify_related_info(self, info, obj):
        generator = generator_registry.get("panels:widget:preview", source=obj.image)
        info["image_url"] = ImageCacheFile(generator).url
        return info


admin_site.register(ImageAsset, ImageAssetAdmin)


class DocumentAssetFilterSet(FilterSet):
    search = django_filters.CharFilter(
        field_name="title",
        lookup_expr="icontains",
        help_text="",
    )
    file_type = django_filters.ChoiceFilter(choices=DocumentAsset.file_type_filter_choices, help_text="")
    folder = TreeNodeChoiceFilter(queryset=AssetFolder.objects.all())
    tags = django_filters.ModelChoiceFilter(
        queryset=Tag.objects.all().order_by("name"), widget=widgets.Select
    )
    order_by = django_filters.OrderingFilter(
        choices=(
            ("-created", "Created (newest first)"),
            ("created", "Created (oldest first)"),
        ),
        empty_label=None,
    )

    class Meta:
        model = DocumentAsset
        fields = ["search", "folder"]


class DocumentPreviewView(PreviewView):
    template_name = "assets/panel-preview-document.html"


class DocumentAssetAdmin(ModelAdmin):
    form_class = DocumentForm
    filterset_class = DocumentAssetFilterSet
    preview_view = DocumentPreviewView
    list_display = (
        ("title", "Title"),
        ("human_file_type", "Type"),
    )


admin_site.register(DocumentAsset, DocumentAssetAdmin)


class AssetFolderAdmin(ModelAdmin):
    form_class = FolderForm
    changelist_view = NestedReorderView
    changelist_select_view = False


admin_site.register(AssetFolder, AssetFolderAdmin)
