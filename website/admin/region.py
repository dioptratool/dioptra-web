import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from ombucore.admin.filterset import FilterSet
from ombucore.admin.modeladmin.base import ModelAdmin
from ombucore.admin.sites import site
from website import models as website_models


class RegionFilterSet(FilterSet):
    search = django_filters.CharFilter(field_name="search", method="filter_search")
    order_by = django_filters.OrderingFilter(
        choices=(
            ("name", _("Name (A-Z)")),
            ("-name", _("Name (Z-A)")),
            ("region_code", _("Code (A-Z)")),
            ("-region_code", _("Code (Z-A)")),
        ),
        empty_label=None,
    )

    class Meta:
        fields = ["search", "order_by"]

    def filter_search(self, queryset, name, value):
        return queryset.filter(Q(name__icontains=value) | Q(region_code__icontains=value))


class RegionAdmin(ModelAdmin):
    filterset_class = RegionFilterSet
    form_config = {
        "fields": ["name", "region_code"],
    }

    list_display = (
        ("name", _("Name")),
        ("region_code", _("Code")),
    )


site.register(website_models.Region, RegionAdmin)
