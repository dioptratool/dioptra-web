import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from ombucore.admin.filterset import FilterSet
from ombucore.admin.modeladmin.base import ModelAdmin
from ombucore.admin.sites import site
from website.models import CostEfficiencyStrategy, Intervention


class CostEfficiencyStrategyFilterSet(FilterSet):
    search = django_filters.CharFilter(method="keyword_search")

    intervention = django_filters.ModelChoiceFilter(
        label=_("Intervention"),
        field_name="interventions",
        queryset=Intervention.objects.all(),
    )

    order_by = django_filters.OrderingFilter(
        choices=(
            ("title", _("Title (A-Z)")),
            ("-title", _("Title (Z-A)")),
        ),
        empty_label=None,
    )

    def keyword_search(self, queryset, name, value):
        return queryset.filter(
            Q(title__icontains=value)
            | Q(efficiency_driver_description__icontains=value)
            | Q(strategy_to_improve_description__icontains=value)
        )

    class Meta:
        fields = [
            "search",
        ]


class CostEfficiencyStrategyAdmin(ModelAdmin):
    filterset_class = CostEfficiencyStrategyFilterSet
    list_display = (
        ("title", _("Title")),
        ("display_interventions", _("Intervention being analyzed")),
    )

    def display_interventions(self, strategy):
        return ", ".join([intervention.name for intervention in strategy.interventions.all()])


site.register(CostEfficiencyStrategy, CostEfficiencyStrategyAdmin)
