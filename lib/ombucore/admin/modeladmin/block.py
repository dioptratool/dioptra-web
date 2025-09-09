from ombucore.admin.modeladmin.base import ModelAdmin


class BlockAdmin(ModelAdmin):
    delete_view = False
    app_log = False


class AssetBlockAdmin(BlockAdmin):
    form_config = {
        "fields": ("title", "hide_title", "width", "offset", "asset"),
        "fieldsets": (
            ("Basic", {"fields": ("title", "hide_title", "asset")}),
            ("Style", {"fields": ("width", "offset")}),
        ),
    }
    changelist_view = False

    def modify_related_info(self, info, obj):
        info["base_class"] = "Block"
        return info


class RichTextBlockAdmin(BlockAdmin):
    form_config = {
        "fields": ("title", "hide_title", "width", "offset", "body"),
        "fieldsets": (
            (
                "Basic",
                {"fields": ("title", "hide_title", "body")},
            ),
            ("Style", {"fields": ("width", "offset")}),
        ),
    }
    changelist_view = False

    def modify_related_info(self, info, obj):
        info["base_class"] = "Block"
        return info
