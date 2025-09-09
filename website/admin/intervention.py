import django_filters
from django.utils.translation import gettext_lazy as _

from ombucore.admin.filterset import FilterSet
from ombucore.admin.modeladmin.base import ModelAdmin
from ombucore.admin.sites import site
from website.forms.intervention import InterventionForm
from website.models import Intervention, InterventionGroup


class InterventionFilterSet(FilterSet):
    search = django_filters.CharFilter(
        field_name="name",
        lookup_expr="icontains",
    )

    class Meta:
        fields = [
            "search",
        ]


class InterventionAdmin(ModelAdmin):
    filterset_class = InterventionFilterSet
    form_class = InterventionForm
    list_display = (("name", _("Name")),)


site.register(Intervention, InterventionAdmin)


class InterventionGroupFilterSet(FilterSet):
    search = django_filters.CharFilter(
        field_name="name",
        lookup_expr="icontains",
    )

    class Meta:
        fields = [
            "search",
        ]


class InterventionGroupAdmin(ModelAdmin):
    filterset_class = InterventionGroupFilterSet
    list_display = (("name", _("Name")),)


site.register(InterventionGroup, InterventionGroupAdmin)
