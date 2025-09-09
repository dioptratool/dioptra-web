from taggit.models import Tag

from ombucore.admin.modeladmin import ModelAdmin
from ombucore.admin.sites import site


class TagAdmin(ModelAdmin):
    reorder_view = False
    form_config = {
        "fields": ("name",),
        "fieldsets": (("Basic", {"fields": ("name",)}),),
    }

    list_display = [
        ("name", "Title"),
    ]

    def tag_title(self, obj):
        return obj.title[:20] + "..."


site.register(Tag, TagAdmin)
