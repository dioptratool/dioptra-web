import django_filters
from django.utils.translation import gettext_lazy as _

from ombucore.admin.filterset import FilterSet
from ombucore.admin.modeladmin.base import ModelAdmin
from ombucore.admin.sites import site
from website import models as website_models


class CostTypeFilterSet(FilterSet):
    search = django_filters.CharFilter(
        field_name="name",
        lookup_expr="icontains",
    )

    class Meta:
        fields = [
            "search",
        ]


class CostTypeAdmin(ModelAdmin):
    filterset_class = CostTypeFilterSet
    form_config = {
        "fields": [
            "name",
        ],
    }
    add_view = False
    reorder_view = False
    delete_view = False

    list_display = (
        ("name", _("Label")),
        ("display_type", _("Type")),
    )

    def display_type(self, obj):
        return dict(obj.TYPE_CHOICES).get(obj.type)


site.register(website_models.CostType, CostTypeAdmin)
