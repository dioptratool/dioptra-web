"""
Feature 98 -- the analysis step filtersets (website/filterset.py).

The filtersets are exercised directly, built the way AnalysisStepFiltersetMixin builds them: the
GET data plus the analysis. Page rendering is covered in test_views/test_step_filters.py.
"""

import re
from datetime import date
from decimal import Decimal
from urllib.parse import urlencode

import pytest
from django.db import connection
from django.http import QueryDict
from django.test.utils import CaptureQueriesContext

from website.filterset import (
    AllocateCostTypeGrantFilterSet,
    AllocateSubcomponentsFilterSet,
    CategorizeCostTypeFilterSet,
    keyword_q,
)
from website.models import FieldLabelOverrides
from website.tests.factories import AccountCodeDescriptionFactory, AnalysisFactory, CostLineItemFactory
from website.tests.test_corrections.helpers import group, item_for, make_analysis, tx

ALL_STEP_FILTERSETS = (
    CategorizeCostTypeFilterSet,
    AllocateCostTypeGrantFilterSet,
    AllocateSubcomponentsFilterSet,
)


def build(filterset_class, analysis, **params):
    """A filterset over the analysis' cost items, built from a query string like the step views do."""
    data = QueryDict(urlencode(params, doseq=True))
    return filterset_class(data, queryset=analysis.cost_line_items.all(), analysis=analysis)


def pks(filterset):
    return set(filterset.qs.values_list("pk", flat=True))


@pytest.fixture
def analysis(defaults):
    return AnalysisFactory()


@pytest.fixture
def sites(analysis):
    """One cost item per site code, keyed by site code."""
    return {code: CostLineItemFactory(analysis=analysis, site_code=code) for code in ("S1", "S2", "S3")}


@pytest.mark.django_db
class TestChoiceFilters:
    """98.3 -- a choice filter is multi-select and a row matches any selected option."""

    def test_any_of_the_selected_sites(self, analysis, sites):
        fs = build(CategorizeCostTypeFilterSet, analysis, site_code=["S1", "S2"])

        assert pks(fs) == {sites["S1"].pk, sites["S2"].pk}

    def test_empty_value_is_no_selection(self, analysis, sites):
        fs = build(CategorizeCostTypeFilterSet, analysis, site_code=[""])

        assert pks(fs) == {cli.pk for cli in sites.values()}
        assert not fs.form.errors

    def test_choices_are_the_analysis_sites(self, analysis, sites):
        CostLineItemFactory(site_code="ELSEWHERE")  # another analysis

        fs = build(CategorizeCostTypeFilterSet, analysis)

        assert [value for value, _label in fs.form.fields["site_code"].choices] == ["S1", "S2", "S3"]

    def test_filtering_does_not_add_distinct(self, analysis, sites):
        fs = build(CategorizeCostTypeFilterSet, analysis, site_code=["S1"])

        assert "DISTINCT" not in str(fs.qs.query)


@pytest.mark.django_db
class TestInventory:
    """98.8-98.10 -- which facets each step offers."""

    def test_grant_only_on_confirm_categories(self, analysis):
        assert "grant_code" in build(CategorizeCostTypeFilterSet, analysis).form.fields
        assert "grant_code" not in build(AllocateCostTypeGrantFilterSet, analysis).form.fields
        assert "grant_code" not in build(AllocateSubcomponentsFilterSet, analysis).form.fields

    @pytest.mark.parametrize("filterset_class", ALL_STEP_FILTERSETS)
    def test_site_and_sector_on_every_step(self, analysis, filterset_class):
        fields = build(filterset_class, analysis).form.fields

        assert {"site_code", "sector_code", "search"} <= set(fields)


@pytest.mark.django_db
class TestLabels:
    """98.12 -- filter names follow the field label overrides, like the column headers."""

    def test_defaults_match_the_column_headers(self, analysis):
        fields = build(CategorizeCostTypeFilterSet, analysis).form.fields

        assert fields["grant_code"].label == "Grant"
        assert fields["site_code"].label == "Site"
        assert fields["sector_code"].label == "Sector Code"

    def test_override_renames_the_filter(self, analysis):
        overrides = FieldLabelOverrides.get()
        overrides.ci_site_code = "Programme Site"
        overrides.ci_site_code_overridden = True
        overrides.save()

        fields = build(AllocateCostTypeGrantFilterSet, analysis).form.fields

        assert fields["site_code"].label == "Programme Site"
        assert fields["sector_code"].label == "Sector Code"

    def test_labels_are_resolved_with_one_query(self, analysis):
        FieldLabelOverrides.get()  # the singleton row exists before we count

        with CaptureQueriesContext(connection) as queries:
            _form = build(CategorizeCostTypeFilterSet, analysis).form

        label_queries = [q["sql"] for q in queries if "website_fieldlabeloverrides" in q["sql"]]
        assert len(label_queries) == 1, label_queries


def test_keyword_q_is_empty_for_blank_text():
    assert not keyword_q("budget_line_description", "")
    assert not keyword_q("budget_line_description", "   ")


@pytest.mark.django_db
class TestKeywordFilters:
    """98.1 / 98.2 -- case-insensitive, and every word must be present somewhere in the value."""

    @pytest.fixture
    def items(self, analysis):
        names = ("Staff Salaries - Nairobi", "Nairobi Vehicle Hire", "Staff Training")
        return {name: CostLineItemFactory(analysis=analysis, budget_line_description=name) for name in names}

    def test_matches_ignoring_case(self, analysis, items):
        fs = build(CategorizeCostTypeFilterSet, analysis, budget_line_description="SALARIES")

        assert pks(fs) == {items["Staff Salaries - Nairobi"].pk}

    def test_every_word_must_match_in_any_order(self, analysis, items):
        fs = build(CategorizeCostTypeFilterSet, analysis, budget_line_description="nairobi staff")

        assert pks(fs) == {items["Staff Salaries - Nairobi"].pk}

    def test_blank_text_is_no_filter(self, analysis, items):
        fs = build(CategorizeCostTypeFilterSet, analysis, budget_line_description="   ")

        assert pks(fs) == {cli.pk for cli in items.values()}
        assert not fs.form.errors


@pytest.mark.django_db
class TestAmountFilter:
    """98.4, 98.6, 98.7 -- From and To inputs, each optional, both inclusive."""

    @pytest.fixture
    def amounts(self, analysis):
        return {
            amount: CostLineItemFactory(analysis=analysis, total_cost=Decimal(amount))
            for amount in ("50", "100", "150")
        }

    def test_from_only(self, analysis, amounts):
        fs = build(CategorizeCostTypeFilterSet, analysis, total_cost_min="100")

        assert pks(fs) == {amounts["100"].pk, amounts["150"].pk}

    def test_to_only(self, analysis, amounts):
        fs = build(CategorizeCostTypeFilterSet, analysis, total_cost_max="100")

        assert pks(fs) == {amounts["50"].pk, amounts["100"].pk}

    def test_both_bounds_are_inclusive(self, analysis, amounts):
        fs = build(CategorizeCostTypeFilterSet, analysis, total_cost_min="100", total_cost_max="100")

        assert pks(fs) == {amounts["100"].pk}

    def test_invalid_number_is_ignored(self, analysis, amounts):
        fs = build(CategorizeCostTypeFilterSet, analysis, total_cost_min="abc")

        assert pks(fs) == {cli.pk for cli in amounts.values()}
        assert "total_cost" in fs.form.errors

    def test_sensitive_accounts_never_match_an_amount_range(self, analysis, amounts):
        AccountCodeDescriptionFactory(account_code="4100", sensitive_data=True)
        hidden = amounts["100"]
        hidden.account_code = "4100"
        hidden.budget_line_description = "Payroll"
        hidden.save()

        by_amount = build(CategorizeCostTypeFilterSet, analysis, total_cost_min="0")
        by_name = build(CategorizeCostTypeFilterSet, analysis, budget_line_description="payroll")

        assert pks(by_amount) == {amounts["50"].pk, amounts["150"].pk}
        assert pks(by_name) == {hidden.pk}


@pytest.mark.django_db
class TestAccountDescriptionFilter:
    """The Account Code Description column: options are the texts the table shows."""

    @pytest.fixture
    def accounts(self, analysis):
        AccountCodeDescriptionFactory(account_code="4100", account_description="Salaries")
        AccountCodeDescriptionFactory(account_code="4200", account_description="Salaries")
        AccountCodeDescriptionFactory(account_code="5000", account_description="Travel")
        codes = ("4100", "4200", "5000", "9999")
        return {code: CostLineItemFactory(analysis=analysis, account_code=code) for code in codes}

    def test_options_are_the_displayed_texts(self, analysis, accounts):
        fs = build(CategorizeCostTypeFilterSet, analysis)

        choices = [value for value, _label in fs.form.fields["account_description"].choices]
        assert choices == ["9999", "Salaries", "Travel"]

    def test_a_description_matches_every_code_behind_it(self, analysis, accounts):
        fs = build(CategorizeCostTypeFilterSet, analysis, account_description=["Salaries"])

        assert pks(fs) == {accounts["4100"].pk, accounts["4200"].pk}

    def test_a_code_without_description_is_matched_by_the_code(self, analysis, accounts):
        fs = build(AllocateCostTypeGrantFilterSet, analysis, account_description=["9999", "Travel"])

        assert pks(fs) == {accounts["9999"].pk, accounts["5000"].pk}


@pytest.mark.django_db
class TestCustomFieldFacets:
    """Facets exist for exactly the custom columns the tables show (populated ones)."""

    def test_facet_exists_only_for_populated_columns(self, analysis):
        CostLineItemFactory(analysis=analysis, dummy_field_2="CC-100")
        CostLineItemFactory(analysis=analysis)

        fields = build(CategorizeCostTypeFilterSet, analysis).form.fields

        assert "ci_dummy_field_2" in fields
        assert "ci_dummy_field_1" not in fields
        assert "ci_dummy_field_3" not in fields

    def test_filters_the_column(self, analysis):
        hit = CostLineItemFactory(analysis=analysis, dummy_field_2="CC-100")
        CostLineItemFactory(analysis=analysis, dummy_field_2="CC-200")

        fs = build(AllocateCostTypeGrantFilterSet, analysis, ci_dummy_field_2="cc-1")

        assert pks(fs) == {hit.pk}

    def test_subcomponents_step_has_no_custom_field_facets(self, analysis):
        CostLineItemFactory(analysis=analysis, dummy_field_2="CC-100")

        assert "ci_dummy_field_2" not in build(AllocateSubcomponentsFilterSet, analysis).form.fields

    def test_label_is_the_column_header(self, analysis):
        CostLineItemFactory(analysis=analysis, dummy_field_2="CC-100")

        assert build(CategorizeCostTypeFilterSet, analysis).form.fields["ci_dummy_field_2"].label == (
            "Budget Custom Field 2"
        )

        overrides = FieldLabelOverrides.get()
        overrides.ci_dummy_field_2 = "Cost Centre"
        overrides.ci_dummy_field_2_overridden = True
        overrides.save()

        assert (
            build(CategorizeCostTypeFilterSet, analysis).form.fields["ci_dummy_field_2"].label
            == "Cost Centre"
        )


@pytest.mark.django_db
class TestFacetMenu:
    def test_cost_item_facets_in_display_order_with_their_kinds(self, analysis):
        CostLineItemFactory(analysis=analysis, dummy_field_3="x")

        groups = build(CategorizeCostTypeFilterSet, analysis).facet_groups()

        assert [heading for heading, _facets in groups] == [""]
        facets = groups[0][1]
        assert [facet.field.name for facet in facets] == [
            "budget_line_description",
            "grant_code",
            "site_code",
            "sector_code",
            "account_description",
            "total_cost",
            "ci_dummy_field_3",
        ]
        assert {facet.field.name: facet.kind for facet in facets} == {
            "budget_line_description": "text",
            "grant_code": "choices",
            "site_code": "choices",
            "sector_code": "choices",
            "account_description": "choices",
            "total_cost": "range",
            "ci_dummy_field_3": "text",
        }


TRANSACTION_FACETS = {"transaction_description", "transaction_date", "transaction_amount"}


@pytest.fixture
def transaction_analysis(defaults):
    """
    Item A (site S1): t1 "Payroll January" 100 on 1 Jan 2024 with custom field 1 "PRJ-7", and
    t2 "Fuel" 300 on 15 Feb 2024. Item B (site S2): t3 "Payroll March" 300 on 31 Mar 2024.
    """
    analysis = make_analysis()
    tx(
        analysis,
        "100",
        transaction_description="Payroll January",
        date=date(2024, 1, 1),
        dummy_field_1="PRJ-7",
    )
    tx(analysis, "300", transaction_description="Fuel", date=date(2024, 2, 15))
    tx(analysis, "300", site_code="S2", transaction_description="Payroll March", date=date(2024, 3, 31))
    group(analysis)
    return analysis


def items_a_b(analysis):
    return item_for(analysis, site_code="S1").pk, item_for(analysis, site_code="S2").pk


@pytest.mark.django_db
class TestTransactionFacets:
    def test_absent_on_an_analysis_without_transactions(self, analysis):
        CostLineItemFactory(analysis=analysis)

        fs = build(CategorizeCostTypeFilterSet, analysis)

        assert not TRANSACTION_FACETS & set(fs.form.fields)
        assert not TRANSACTION_FACETS & set(fs.filters)
        assert [heading for heading, _facets in fs.facet_groups()] == [""]

    def test_description_keyword_needs_every_word(self, transaction_analysis):
        a, b = items_a_b(transaction_analysis)

        assert pks(
            build(CategorizeCostTypeFilterSet, transaction_analysis, transaction_description="PAYROLL")
        ) == {a, b}
        assert pks(
            build(CategorizeCostTypeFilterSet, transaction_analysis, transaction_description="march payroll")
        ) == {b}

    def test_date_bounds_are_inclusive_in_either_format(self, transaction_analysis):
        a, b = items_a_b(transaction_analysis)

        after = build(CategorizeCostTypeFilterSet, transaction_analysis, transaction_date_after="15-Feb-2024")
        before = build(
            CategorizeCostTypeFilterSet, transaction_analysis, transaction_date_before="2024-01-01"
        )
        between = build(
            CategorizeCostTypeFilterSet,
            transaction_analysis,
            transaction_date_after="02-Jan-2024",
            transaction_date_before="2024-03-30",
        )

        assert pks(after) == {a, b}
        assert pks(before) == {a}
        assert pks(between) == {a}
        bounds = between.form.cleaned_data["transaction_date"]
        assert (bounds.start, bounds.stop) == (date(2024, 1, 2), date(2024, 3, 30))

    def test_amount_bounds(self, transaction_analysis):
        a, b = items_a_b(transaction_analysis)

        assert pks(
            build(CategorizeCostTypeFilterSet, transaction_analysis, transaction_amount_min="300")
        ) == {a, b}
        assert pks(
            build(CategorizeCostTypeFilterSet, transaction_analysis, transaction_amount_max="100")
        ) == {a}

    def test_one_transaction_must_satisfy_every_transaction_facet(self, transaction_analysis):
        """98.11: item A has a Payroll transaction and a 300 transaction, but not one that is both."""
        _a, b = items_a_b(transaction_analysis)

        fs = build(
            CategorizeCostTypeFilterSet,
            transaction_analysis,
            transaction_description="payroll",
            transaction_amount_min="300",
        )

        assert pks(fs) == {b}

    def test_transaction_facets_become_one_analysis_scoped_exists(self, transaction_analysis):
        fs = build(
            CategorizeCostTypeFilterSet,
            transaction_analysis,
            transaction_description="payroll",
            transaction_amount_min="1",
            transaction_date_after="2024-01-01",
        )

        sql = str(fs.qs.query)
        assert sql.count("EXISTS") == 1
        assert re.search(r'FROM "website_transaction" U0 WHERE \(U0\."analysis_id" = \d+ AND', sql), sql

    def test_custom_field_facets_follow_the_populated_transaction_columns(self, transaction_analysis):
        a, _b = items_a_b(transaction_analysis)

        fields = build(AllocateCostTypeGrantFilterSet, transaction_analysis).form.fields

        assert "tr_dummy_field_1" in fields
        assert "tr_dummy_field_2" not in fields
        assert "ci_dummy_field_1" not in fields  # the cost items of a transaction analysis carry none
        assert pks(build(AllocateCostTypeGrantFilterSet, transaction_analysis, tr_dummy_field_1="prj")) == {a}
        assert (
            "tr_dummy_field_1" not in build(AllocateSubcomponentsFilterSet, transaction_analysis).form.fields
        )

    def test_labels_follow_the_transaction_column_headers(self, transaction_analysis):
        fields = build(CategorizeCostTypeFilterSet, transaction_analysis).form.fields
        assert fields["transaction_description"].label == "Transaction Description"
        assert fields["transaction_date"].label == "Transaction Date"
        assert fields["transaction_amount"].label == "Transaction Amount"
        assert fields["tr_dummy_field_1"].label == "Transaction Custom Field 1"

        overrides = FieldLabelOverrides.get()
        overrides.tr_date = "Posting Date"
        overrides.tr_date_overridden = True
        overrides.save()

        assert build(CategorizeCostTypeFilterSet, transaction_analysis).form.fields[
            "transaction_date"
        ].label == ("Posting Date")

    def test_sensitive_accounts_never_match_a_transaction_amount_range(self, transaction_analysis):
        a, b = items_a_b(transaction_analysis)
        AccountCodeDescriptionFactory(account_code="4100", sensitive_data=True)  # every item's account

        assert (
            pks(build(CategorizeCostTypeFilterSet, transaction_analysis, transaction_amount_min="0")) == set()
        )
        assert pks(
            build(CategorizeCostTypeFilterSet, transaction_analysis, transaction_description="payroll")
        ) == {a, b}

    def test_menu_groups_cost_item_and_transaction_facets(self, transaction_analysis):
        groups = build(CategorizeCostTypeFilterSet, transaction_analysis).facet_groups()

        assert [heading for heading, _facets in groups] == ["Cost item", "Transaction"]
        transaction_facets = groups[1][1]
        assert [facet.field.name for facet in transaction_facets] == [
            "transaction_description",
            "transaction_date",
            "transaction_amount",
            "tr_dummy_field_1",
        ]
        assert {facet.field.name: facet.kind for facet in transaction_facets}[
            "transaction_date"
        ] == "date-range"
