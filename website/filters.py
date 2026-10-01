import django_filters
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Case, IntegerField, Q, Value, When
from django.http import QueryDict
from django_filters.constants import EMPTY_VALUES

from website.filterset import FilterSet
from .models import Analysis, AnalysisStatus, Country, Intervention

User = get_user_model()

# Lifecycle order for sorting: a rank rather than the alphabetical order of the stored values.
STATUS_RANK = Case(
    When(analysis_status=AnalysisStatus.IN_PROGRESS, then=Value(0)),
    When(analysis_status=AnalysisStatus.COMPLETE, then=Value(1)),
    When(analysis_status=AnalysisStatus.VALIDATED, then=Value(2)),
    default=Value(3),
    output_field=IntegerField(),
)

ARCHIVED_CHOICES = (("no", "No"), ("yes", "Yes"))


class StableOrderingFilter(django_filters.OrderingFilter):
    """Orders as asked, then by primary key, so paging over equal values is stable."""

    def filter(self, qs, value):
        if value in EMPTY_VALUES:
            return qs
        ordering = [self.get_ordering_value(param) for param in value]
        return qs.order_by(*ordering, "pk")


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

    # Any of the selected statuses; nothing selected adds no condition.
    analysis_status = django_filters.MultipleChoiceFilter(
        label="Status",
        choices=AnalysisStatus.choices,
        widget=forms.CheckboxSelectMultiple,
    )

    # No: unarchived only (the default). Yes: archived only. Any: both.
    archived = django_filters.ChoiceFilter(
        label="Archived",
        choices=ARCHIVED_CHOICES,
        empty_label="Any",
        method="filter_archived",
    )

    order_by = StableOrderingFilter(
        fields=(
            ("title", "title"),
            ("updated", "updated"),
            ("grants", "grants"),
            ("country", "country"),
            ("interventions", "interventions"),
            ("owner", "owner"),
            ("output_costs", "output_costs"),
            ("status_rank", "analysis_status"),
        )
    )

    def __init__(self, data=None, queryset=None, **kwargs):
        # No `archived` parameter at all is the default view: unarchived analyses. A present but
        # empty parameter is the cleared filter, which shows everything. Defaulting here keeps the
        # results and the displayed controls consistent however the filterset is built.
        data = data.copy() if data is not None else QueryDict(mutable=True)
        if "archived" not in data:
            data["archived"] = "no"
        if hasattr(data, "setlist"):
            # An empty status value is no selection, not an invalid choice that blanks the page.
            data.setlist("analysis_status", [value for value in data.getlist("analysis_status") if value])
        super().__init__(data, queryset=queryset, **kwargs)
        if "status_rank" not in self.queryset.query.annotations:
            self.queryset = self.queryset.annotate(status_rank=STATUS_RANK)

    def keyword_search(self, queryset, name, value):
        return queryset.filter(Q(title__icontains=value) | Q(grants__icontains=value))

    def filter_archived(self, queryset, name, value):
        if value == "yes":
            return queryset.filter(is_archived=True)
        if value == "no":
            return queryset.filter(is_archived=False)
        return queryset
