import django_filters
from django import forms
from django.db.models import Q

from website.models import CostLineItem


class FilterSet(django_filters.FilterSet):
    """
    Subclassed to provide extra functionality to support the designs.
    """

    def applied_filters_count(self):
        """
        Returns the number of filters that were actually applied.

        Excludes the `search` and `order_by` fields if present on the filterset.
        """
        self.is_valid()  # Triggers form cleaning.
        exclude = ["search", "order_by"]
        applied_count = 0
        if hasattr(self.form, "cleaned_data"):
            for field_name, field_value in self.form.cleaned_data.items():
                if field_name not in exclude and field_value:
                    applied_count += 1
        return applied_count

    def filters_applied(self):
        """
        Returns True if the form was submitted and any filters (including
        `search` but excluding `order_by`) were applied.
        """
        self.is_valid()  # Triggers form cleaning.
        if hasattr(self.form, "cleaned_data"):
            for field_name, field_value in self.form.cleaned_data.items():
                if field_name != "order_by" and field_value:
                    return True
        return False


class AnalysisStepFilterSet(FilterSet):
    """
    Used to filter site and grant codes shown in the view's filter based on the Analysis of a CostLineItem
    """

    def __init__(self, *args, **kwargs):
        analysis = kwargs.pop("analysis")
        super().__init__(*args, **kwargs)
        if analysis:
            filter_kwargs = {"analysis": analysis}
            if self.filters.get("site_code"):
                self.filters["site_code"].extra["choices"] = list(
                    CostLineItem.site_code_filter_choices(filter_kwargs)
                )
            if self.filters.get("grant_code"):
                self.filters["grant_code"].extra["choices"] = list(
                    CostLineItem.grant_code_filter_choices(filter_kwargs)
                )
            if self.filters.get("sector_code"):
                self.filters["sector_code"].extra["choices"] = list(
                    CostLineItem.sector_code_filter_choices(filter_kwargs)
                )


class AllocateCostTypeGrantSiteFilterSet(AnalysisStepFilterSet):
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

    order_by = django_filters.OrderingFilter(
        fields=(
            ("grant_code", "grant_code"),
            ("budget_line_description", "budget_line_description"),
            ("site_code", "site_code"),
            ("account_code", "account_code"),
            ("total_cost", "total_cost"),
        )
    )

    def keyword_search(self, queryset, name, value):
        return queryset.filter(
            Q(site_code__icontains=value)
            | Q(sector_code__icontains=value)
            | Q(grant_code__icontains=value)
            | Q(account_code__icontains=value)
            | Q(budget_line_description__icontains=value)
        )

    site_code = django_filters.ChoiceFilter(
        label="Site Code",
        empty_label="Any",
        widget=forms.Select,
    )
    sector_code = django_filters.ChoiceFilter(
        label="Sector Code",
        empty_label="Any",
        widget=forms.Select,
    )

    class Meta:
        model = CostLineItem
        fields = [
            "search",
            "site_code",
        ]


class CategorizeCostTypeFilterSet(AnalysisStepFilterSet):
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

    order_by = django_filters.OrderingFilter(
        fields=(
            ("grant_code", "grant_code"),
            ("budget_line_description", "budget_line_description"),
            ("site_code", "site_code"),
            ("account_code", "account_code"),
            ("total_cost", "total_cost"),
        )
    )

    def keyword_search(self, queryset, name, value):
        return queryset.filter(
            Q(site_code__icontains=value)
            | Q(sector_code__icontains=value)
            | Q(grant_code__icontains=value)
            | Q(account_code__icontains=value)
            | Q(budget_line_description__icontains=value)
        )

    site_code = django_filters.ChoiceFilter(
        label="Site Code",
        empty_label="Any",
        widget=forms.Select,
    )

    grant_code = django_filters.ChoiceFilter(
        label="Grant Code",
        empty_label="Any",
        widget=forms.Select,
    )

    sector_code = django_filters.ChoiceFilter(
        label="Sector Code",
        empty_label="Any",
        widget=forms.Select,
    )

    class Meta:
        model = CostLineItem
        fields = [
            "search",
        ]
