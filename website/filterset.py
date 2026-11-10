"""
Filtersets for the pages that list cost items.

The analysis step pages (Confirm Categories, Allocate Intervention Costs, Allocate Sub-Component
Costs) share ``CostLineItemStepFilterSet`` (Feature 98: Analysis Filters). The facets are rendered by
``features/_filters.html`` and driven by ``js/filters.js``, which dispatches on each facet's ``kind``.
"""

from collections import namedtuple

import django_filters
from django import forms
from django.conf import settings
from django.db.models import Exists, OuterRef, Q
from django.utils.translation import gettext_lazy as _l
from django_filters.fields import RangeField
from django_filters.widgets import SuffixedMultiWidget

from ombucore.admin.widgets import FlatpickrDateWidget
from website.currency import currency_symbol
from website.models import AccountCodeDescription, CostLineItem, FieldLabelOverrides, Transaction
from website.models.utils import load_field_label_override

# One entry of the "Add filter" menu: the bound form field, and the kind the chip script dispatches on.
Facet = namedtuple("Facet", ["field", "kind"])

# Form fields that are not facets of the "Add filter" menu.
NON_FACET_FIELDS = ("search", "order_by")


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

    def facet_groups(self):
        """
        The "Add filter" menu as ``[(heading, [Facet, ...]), ...]``: one unnamed group of every
        field but the search box and the ordering, in form order. Subclasses group and order them.
        """
        return [("", self.facets(name for name in self.form.fields if name not in NON_FACET_FIELDS))]

    def facets(self, names):
        return [Facet(self.form[name], getattr(self.filters[name], "kind", "")) for name in names]


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


def keyword_q(field_name, text):
    """98.1 / 98.2: every whitespace-separated word must appear in the field, ignoring case."""
    q = Q()
    for word in text.split():
        q &= Q(**{f"{field_name}__icontains": word})
    return q


def range_is_set(value):
    """Whether a cleaned From/To value carries at least one bound (a slice object is always truthy)."""
    return value is not None and (value.start is not None or value.stop is not None)


class QFilterMixin:
    """
    A filter that states its condition as a Q, so the same condition can narrow the cost item rows
    or be folded into one EXISTS over the transactions.
    """

    def filter(self, qs, value):
        q = self.q(value)
        return qs.filter(q) if q else qs


class KeywordFilter(QFilterMixin, django_filters.CharFilter):
    kind = "text"

    def q(self, value):
        return keyword_q(self.field_name, value) if value else Q()


class FromToWidget(SuffixedMultiWidget):
    """Two inputs side by side, submitted as ``<name>_min`` and ``<name>_max``."""

    template_name = "widgets/from-to-range.html"
    suffixes = ["min", "max"]

    def decompress(self, value):
        if value:
            return [value.start, value.stop]
        return [None, None]


class CurrencyInput(forms.NumberInput):
    """
    A number input with the analysis' currency symbol in front of it. The symbol is also left on the
    input as ``data-currency-symbol`` so filters.js can format the facet's result chip.
    """

    template_name = "widgets/currency-input.html"

    def __init__(self, attrs=None, currency_symbol=None):
        self.currency_symbol = currency_symbol
        super().__init__(attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["currency_symbol"] = self.currency_symbol or ""
        if self.currency_symbol:
            context["widget"]["attrs"]["data-currency-symbol"] = self.currency_symbol
        return context


class AmountFromToWidget(FromToWidget):
    def __init__(self, attrs=None, currency_symbol=None):
        widgets = tuple(
            CurrencyInput(
                attrs={"placeholder": placeholder, "step": "0.01"},
                currency_symbol=currency_symbol,
            )
            for placeholder in (_l("From"), _l("To"))
        )
        super().__init__(widgets, attrs)


class AmountRangeField(RangeField):
    widget = AmountFromToWidget

    def compress(self, data_list):
        """A To below the From is taken as the range entered backwards: the bounds are swapped."""
        if data_list:
            start, stop = data_list
            if start is not None and stop is not None and stop < start:
                data_list = [stop, start]
        return super().compress(data_list)


class FromToFilter(QFilterMixin, django_filters.Filter):
    """98.4-98.7: optional From and To bounds, both inclusive."""

    field_class = AmountRangeField
    kind = "range"

    def q(self, value):
        q = Q()
        if value is not None:
            if value.start is not None:
                q &= Q(**{f"{self.field_name}__gte": value.start})
            if value.stop is not None:
                q &= Q(**{f"{self.field_name}__lte": value.stop})
        return q


class DateFromToWidget(FromToWidget):
    """Two date pickers, submitted as ``<name>_after`` and ``<name>_before``."""

    suffixes = ["after", "before"]

    def __init__(self, attrs=None):
        widgets = tuple(
            FlatpickrDateWidget(
                # Dioptra's display format. `static` keeps the calendar inside the facet: the
                # "Add filter" dropdown closes on any click outside its menu. Pick-only, like the
                # Define page: flatpickr's typed-input parser is case-sensitive on the month.
                options={"dateFormat": settings.DATE_FORMAT, "static": True},
                format="%d-%b-%Y",
                attrs={"placeholder": placeholder},
            )
            for placeholder in (_l("From"), _l("To"))
        )
        super().__init__(widgets, attrs)


class DateFromToField(RangeField):
    """Two optional dates in the site's input formats, cleaned to a ``slice(date, date)``."""

    widget = DateFromToWidget

    def __init__(self, *args, **kwargs):
        fields = (
            forms.DateField(input_formats=settings.DATE_INPUT_FORMATS),
            forms.DateField(input_formats=settings.DATE_INPUT_FORMATS),
        )
        super().__init__(fields, *args, **kwargs)


class DateFromToFilter(FromToFilter):
    field_class = DateFromToField
    kind = "date-range"


class AnyOfFilter(django_filters.MultipleChoiceFilter):
    """
    A multi-select choice facet: a row matches when its value equals any selected option (98.3).

    django-filter defaults multi-choice filters to ``distinct=True``, which would put SELECT DISTINCT
    on every filtered step page for nothing: the filtered column is on the row itself.
    """

    kind = "choices"

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", forms.CheckboxSelectMultiple)
        kwargs.setdefault("distinct", False)
        super().__init__(*args, **kwargs)


class AccountDescriptionFilter(AnyOfFilter):
    """
    The Account Code Description column. The options are the texts the table shows (the description,
    or the raw account code when there is none); selecting one matches every code behind it.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.code_map = {}

    def set_choices(self, analysis):
        descriptions = AccountCodeDescription.as_map()
        codes = (
            CostLineItem.objects.filter(analysis=analysis)
            .exclude(account_code="")
            .order_by("account_code")
            .values_list("account_code", flat=True)
            .distinct()
        )
        self.code_map = {}
        for code in codes:
            description = descriptions.get(code)
            display = (
                description.account_description if description and description.account_description else code
            )
            self.code_map.setdefault(display, []).append(code)
        self.extra["choices"] = [(display, display) for display in sorted(self.code_map, key=str.casefold)]

    def filter(self, qs, value):
        if not value:
            return qs
        codes = [code for display in value for code in self.code_map.get(display, ())]
        return qs.filter(account_code__in=codes)


class CostLineItemStepFilterSet(AnalysisStepFilterSet):
    """
    The filters shared by the Confirm Categories, Allocate Intervention Costs and Allocate
    Sub-Component Costs pages (Feature 98).

    Subclasses switch facets on and off through the class attributes. Everything that depends on
    the analysis (choices, labels, which facets exist) is settled in ``__init__``, before the form
    is built: django-filter caches each filter's form field and the form itself on first access.
    """

    include_grant = True
    include_custom_fields = True

    # Facets whose query-string values repeat; a blank value is "no selection", not an invalid choice.
    MULTI_FILTERS = ("grant_code", "site_code", "sector_code", "account_description")
    # Facet name -> FieldLabelOverrides key, so an override renames the facet as it does the header (98.12).
    LABEL_KEYS = {
        "budget_line_description": "ci_budget_line_description",
        "grant_code": "ci_grant_code",
        "site_code": "ci_site_code",
        "sector_code": "ci_sector_code",
        "total_cost": "ci_total_cost",
        "transaction_date": "tr_date",
        "transaction_amount": "tr_amount",
    }
    # Menu order of the cost item facets (98.8); a facet the form does not have is skipped.
    COST_ITEM_FACETS = (
        "budget_line_description",
        "grant_code",
        "site_code",
        "sector_code",
        "account_description",
        "total_cost",
        "ci_dummy_field_1",
        "ci_dummy_field_2",
        "ci_dummy_field_3",
        "ci_dummy_field_4",
        "ci_dummy_field_5",
    )
    # Menu order of the transaction facets (98.8); they exist only when the analysis has transactions.
    TRANSACTION_FACETS = (
        "transaction_description",
        "transaction_date",
        "transaction_amount",
        "tr_dummy_field_1",
        "tr_dummy_field_2",
        "tr_dummy_field_3",
        "tr_dummy_field_4",
        "tr_dummy_field_5",
    )
    # From/To facets on amounts. The tables hide the amounts of sensitive accounts, and a range
    # could otherwise reveal them, so those rows never match while one of these is set.
    AMOUNT_FILTERS = ("total_cost", "transaction_amount")

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

    budget_line_description = KeywordFilter(label=_l("Cost Item Name"))
    grant_code = AnyOfFilter(label=_l("Grant"))
    site_code = AnyOfFilter(label=_l("Site"))
    sector_code = AnyOfFilter(label=_l("Sector Code"))
    account_description = AccountDescriptionFilter(label=_l("Account Code Description"))
    total_cost = FromToFilter(label=_l("Cost Item Amount"))

    # Conditions on the Transaction rows; see filter_queryset().
    transaction_description = KeywordFilter(label=_l("Transaction Description"))
    transaction_date = DateFromToFilter(field_name="date", label=_l("Transaction Date"))
    transaction_amount = FromToFilter(
        field_name="amount_in_instance_currency", label=_l("Transaction Amount")
    )

    class Meta:
        model = CostLineItem
        fields = []

    def __init__(self, data=None, queryset=None, *, analysis, **kwargs):
        self.analysis = analysis
        super().__init__(self._normalised(data), queryset, analysis=analysis, **kwargs)
        if not self.include_grant:
            del self.filters["grant_code"]
        self.filters["account_description"].set_choices(analysis)
        symbol = currency_symbol(analysis)
        for name in self.AMOUNT_FILTERS:
            self.filters[name].extra["widget"] = AmountFromToWidget(currency_symbol=symbol)
        overrides = FieldLabelOverrides.get()
        if self.include_custom_fields:
            self._add_custom_field_filters("ci", analysis.cost_item_custom_fields, overrides)
        if not analysis.has_transactions():
            for name in self.TRANSACTION_FACETS:
                self.filters.pop(name, None)
        elif self.include_custom_fields:
            self._add_custom_field_filters("tr", analysis.transaction_custom_fields, overrides)
        for name, key in self.LABEL_KEYS.items():
            if name in self.filters:
                facet = self.filters[name]
                facet.label = load_field_label_override(key, facet.label, overrides=overrides)

    def _normalised(self, data):
        """Drop blank values from the repeatable facets; a blank is no selection."""
        if data is None or not hasattr(data, "setlist"):
            return data
        data = data.copy()
        for name in self.MULTI_FILTERS:
            if name in data:
                data.setlist(name, [value for value in data.getlist(name) if value])
        return data

    def _add_custom_field_filters(self, prefix, columns, overrides):
        """
        One keyword facet per custom column the tables show (``Analysis.cost_item_custom_fields``
        and friends list only the populated ones), named after its override key: ``ci_dummy_field_2``.
        """
        for column in columns:
            facet = KeywordFilter(
                field_name=column["field"],
                label=load_field_label_override(
                    column["label_key"], column["default_label"], overrides=overrides
                ),
            )
            facet.model = self._meta.model
            facet.parent = self
            self.filters[f"{prefix}_{column['field']}"] = facet

    def filter_queryset(self, queryset):
        """
        Cost item facets narrow the rows one by one. Transaction facets are ANDed into a single
        condition applied as one EXISTS over the analysis' transactions, so a row is kept when at
        least one of its transactions satisfies every transaction facet together (98.11). The
        subquery is scoped by analysis_id as well as by row: without it the planner scans the whole
        transaction table (measured 100-305 ms against 11-40 ms at the configured limits).
        """
        cleaned = self.form.cleaned_data
        transaction_q = Q()
        for name, value in cleaned.items():
            if name in self.TRANSACTION_FACETS:
                transaction_q &= self.filters[name].q(value)
            else:
                queryset = self.filters[name].filter(queryset, value)
        if transaction_q:
            matching = Transaction.objects.filter(
                analysis_id=self.analysis.pk, cost_line_item_id=OuterRef("pk")
            ).filter(transaction_q)
            queryset = queryset.filter(Exists(matching))
        if any(range_is_set(cleaned.get(name)) for name in self.AMOUNT_FILTERS):
            sensitive = AccountCodeDescription.objects.filter(sensitive_data=True).values("account_code")
            queryset = queryset.exclude(account_code__in=sensitive)
        return queryset

    def facet_groups(self):
        cost_item = self.facets(name for name in self.COST_ITEM_FACETS if name in self.form.fields)
        transaction = self.facets(name for name in self.TRANSACTION_FACETS if name in self.form.fields)
        if not transaction:
            return [("", cost_item)]
        return [(_l("Cost item"), cost_item), (_l("Transaction"), transaction)]

    def keyword_search(self, queryset, name, value):
        return queryset.filter(
            Q(site_code__icontains=value)
            | Q(sector_code__icontains=value)
            | Q(grant_code__icontains=value)
            | Q(account_code__icontains=value)
            | Q(budget_line_description__icontains=value)
        )


class CategorizeCostTypeFilterSet(CostLineItemStepFilterSet):
    """Confirm Categories: every facet, Grant included (98.8)."""


class AllocateCostTypeGrantFilterSet(CostLineItemStepFilterSet):
    """Allocate Intervention Costs: the page already shows one grant, so no Grant facet (98.9)."""

    include_grant = False


class AllocateSubcomponentsFilterSet(AllocateCostTypeGrantFilterSet):
    """Allocate Sub-Component Costs: no Grant and no custom-field facets (98.10)."""

    include_custom_fields = False
