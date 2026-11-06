"""
Query shape of the filtered step pages (Confirm Categories, Allocate Intervention Costs, Allocate
Sub-Component Costs): per-row work must come from the row query, not one query per row.
"""

import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from website.models import FieldLabelOverrides
from website.tests.factories import SubcomponentCostAnalysisFactory, TransactionFactory
from website.tests.test_corrections.helpers import group, make_analysis, tx
from website.tests.test_views.test_allocate_supporting_costs import (
    add_special_cost_line_item,
    supporting_costs_url,
)
from website.tests.test_views.test_step_filters import (
    allocate_everything,
    allocate_url,
    categorize_url,
    subcomponents_url,
)

PAGES = [categorize_url, allocate_url, subcomponents_url]
PAGE_IDS = ["categorize", "allocate", "subcomponents"]


def analysis_with_rows(row_count, **transaction_values):
    """``row_count`` cost items on one grant, each grouped from two transactions, reachable on all three pages."""
    analysis = make_analysis()
    for n in range(row_count):
        tx(analysis, "100", site_code=f"S{n}", transaction_description="Payroll", **transaction_values)
        tx(analysis, "50", site_code=f"S{n}", transaction_description="Fuel", **transaction_values)
    group(analysis)
    analysis.cost_type_categories.update(confirmed=True)
    allocate_everything(analysis)
    SubcomponentCostAnalysisFactory(analysis=analysis)
    return analysis


def transaction_only_queries(queries):
    """Queries on the transactions alone: the per-row COUNTs and the transaction-row prefetch."""
    return [
        q["sql"]
        for q in queries
        if '"website_transaction"' in q["sql"] and '"website_costlineitem"' not in q["sql"]
    ]


def get_page(client, page_url, analysis):
    with CaptureQueriesContext(connection) as queries:
        response = client.get(page_url(analysis))
    assert response.status_code == 200
    return response, queries


@pytest.mark.django_db
class TestTransactionCounts:
    @pytest.mark.parametrize("page_url", PAGES, ids=PAGE_IDS)
    def test_transaction_queries_do_not_grow_with_the_rows(self, defaults, client_with_admin, page_url):
        _small, small_queries = get_page(client_with_admin, page_url, analysis_with_rows(2))
        _large, large_queries = get_page(client_with_admin, page_url, analysis_with_rows(4))

        assert len(transaction_only_queries(large_queries)) == len(transaction_only_queries(small_queries))

    @pytest.mark.parametrize("page_url", PAGES, ids=PAGE_IDS)
    def test_transaction_rows_are_not_loaded(self, defaults, client_with_admin, page_url):
        _response, queries = get_page(client_with_admin, page_url, analysis_with_rows(2))

        assert not [q["sql"] for q in queries if q["sql"].startswith('SELECT "website_transaction"."id"')]

    @pytest.mark.parametrize("page_url", PAGES, ids=PAGE_IDS)
    def test_each_row_still_shows_its_transaction_count(self, defaults, client_with_admin, page_url):
        response, _queries = get_page(client_with_admin, page_url, analysis_with_rows(2))

        summaries = re.findall(
            r'analysis-table__cost-item-transactions-summary">\s*(\d+)\s+transactions',
            response.content.decode(),
        )
        assert summaries == ["2", "2"]


@pytest.mark.django_db
class TestAnalysisFetchedOnce:
    @pytest.mark.parametrize("page_url", PAGES, ids=PAGE_IDS)
    def test_a_get_loads_the_analysis_once(self, defaults, client_with_admin, page_url):
        """setup_step() loads the analysis with the workflow prefetches; the GET must not repeat it."""
        analysis = analysis_with_rows(2)

        _response, queries = get_page(client_with_admin, page_url, analysis)

        by_pk = f'FROM "website_analysis" WHERE "website_analysis"."id" = {analysis.pk}'
        analysis_queries = [q["sql"] for q in queries if by_pk in q["sql"]]
        assert len(analysis_queries) == 1, analysis_queries


def override_labels(**labels):
    overrides = FieldLabelOverrides.get()
    for key, label in labels.items():
        setattr(overrides, key, label)
        setattr(overrides, f"{key}_overridden", True)
    overrides.save()


def label_queries(queries):
    return [q["sql"] for q in queries if 'FROM "website_fieldlabeloverrides"' in q["sql"]]


@pytest.mark.django_db
class TestTransactionHeaderLabels:
    """Each row's transaction table header is labelled from one read of the overrides per page."""

    @pytest.mark.parametrize("page_url", PAGES, ids=PAGE_IDS)
    def test_label_lookups_do_not_grow_with_the_rows(self, defaults, client_with_admin, page_url):
        _small, small_queries = get_page(client_with_admin, page_url, analysis_with_rows(2))
        _large, large_queries = get_page(client_with_admin, page_url, analysis_with_rows(4))

        assert len(label_queries(large_queries)) == len(label_queries(small_queries))

    @pytest.mark.parametrize("page_url", PAGES, ids=PAGE_IDS)
    def test_each_rows_transaction_header_uses_the_overrides(self, defaults, client_with_admin, page_url):
        override_labels(tr_site_code="Location", tr_date="Posted On", tr_amount="Value")

        response, _queries = get_page(client_with_admin, page_url, analysis_with_rows(2))

        content = response.content.decode()
        assert content.count("<th>Location</th>") == 2
        assert content.count("<th>Posted On</th>") == 2
        assert content.count('<th class="analysis-table__amount-cell">Value</th>') == 2

    @pytest.mark.parametrize("page_url", [categorize_url, allocate_url], ids=["categorize", "allocate"])
    def test_each_rows_header_labels_the_populated_custom_columns(
        self, defaults, client_with_admin, page_url
    ):
        override_labels(tr_dummy_field_1="Project Code")

        response, _queries = get_page(
            client_with_admin, page_url, analysis_with_rows(2, dummy_field_1="PRJ-1")
        )

        assert (
            response.content.decode().count('<th class="analysis-table__custom-field-cell">Project Code</th>')
            == 2
        )

    def test_supporting_costs_rows_use_the_overrides(
        self, client_with_admin, analysis_workflow_with_allocations
    ):
        """Other Supporting Costs renders the same row partial for its special-country items."""
        analysis = analysis_workflow_with_allocations.analysis
        special = add_special_cost_line_item(analysis)
        TransactionFactory(analysis=analysis, cost_line_item=special, grant_code=special.grant_code)
        override_labels(tr_site_code="Location")

        response = client_with_admin.get(supporting_costs_url(analysis))

        assert response.status_code == 200
        assert response.content.decode().count("<th>Location</th>") == 1
