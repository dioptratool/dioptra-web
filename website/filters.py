import django_filters
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from website.filterset import FilterSet
from .models import Analysis, Country, Intervention

User = get_user_model()


class AnalysisFilterSet(FilterSet):
    class Meta:
        model = Analysis
        fields = ["country", "interventions", "created_by"]

    search = django_filters.CharFilter(
        label="Search",
        method="keyword_search",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Enter keyword",
                "class": "filters__search-input",
            }
        ),
    )

    country = django_filters.ModelChoiceFilter(
        label="Country", empty_label="Any", queryset=Country.objects.all()
    )

    interventions = django_filters.ModelChoiceFilter(
        label="Intervention", empty_label="Any", queryset=Intervention.objects.all()
    )

    created_by = django_filters.ModelChoiceFilter(
        label="Owner",
        field_name="owner",
        empty_label="Any",
        queryset=User.objects.all(),
    )
    created_by.field.label_from_instance = lambda user: user.get_full_name()

    order_by = django_filters.OrderingFilter(
        fields=(
            ("title", "title"),
            ("updated", "updated"),
            ("grants", "grants"),
            ("country", "country"),
            ("interventions", "interventions"),
            ("owner", "owner"),
            ("output_costs", "output_costs"),
        )
    )

    def keyword_search(self, queryset, name, value):
        return queryset.filter(Q(title__icontains=value) | Q(grants__icontains=value))
