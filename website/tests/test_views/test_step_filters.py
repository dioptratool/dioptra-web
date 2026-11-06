"""
Feature 98 -- the filter bar on the Confirm Categories, Allocate Intervention Costs and
Allocate Sub-Component Costs pages.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from website.models import SubcomponentCostAllocation
from website.tests.factories import (
    AccountCodeDescriptionFactory,
    CostLineItemConfigFactory,
    CostLineItemFactory,
    SubcomponentCostAnalysisFactory,
)
from website.tests.test_corrections.helpers import group, item_for, make_analysis, tx
from website.tests.utils import facet


def categorize_url(analysis):
    return reverse(
        "analysis-categorize-cost_type",
        kwargs={"pk": analysis.pk, "cost_type_pk": analysis.cost_line_items.first().config.cost_type.pk},
    )


def allocate_url(analysis):
    return reverse(
        "analysis-allocate-cost_type-grant",
        kwargs={
            "pk": analysis.pk,
            "cost_type_pk": analysis.cost_line_items.first().config.cost_type.pk,
            "grant": analysis.grants.split(",")[0],
        },
    )


def subcomponents_url(analysis):
    return reverse(
        "analysis-allocate-subcomponents-intervention-grant",
        kwargs={
            "pk": analysis.pk,
            "intervention_instance_pk": analysis.interventioninstance_set.first().pk,
            "grant": analysis.grants.split(",")[0],
        },
    )


def two_items(analysis):
    """The fixture's two cost items, given distinct sites and names."""
    first, second = analysis.cost_line_items.order_by("pk")[:2]
    first.site_code, first.budget_line_description = "S1", "Payroll"
    second.site_code, second.budget_line_description = "S2", "Vehicles"
    first.save()
    second.save()
    return first, second


@pytest.mark.django_db
class TestChoiceFacets:
    @pytest.mark.parametrize("page_url", [categorize_url, allocate_url], ids=["categorize", "allocate"])
    def test_site_facet_is_a_checkbox_group_with_apply(
        self, analysis_workflow_with_confirmed_categories_cost_line_item, client_with_admin, page_url
    ):
        analysis = analysis_workflow_with_confirmed_categories_cost_line_item.analysis
        two_items(analysis)

        response = client_with_admin.get(page_url(analysis))

        assert response.status_code == 200
        site_facet = facet(response.content.decode(), "site_code")
        assert 'type="checkbox"' in site_facet
        assert 'value="S1"' in site_facet and 'value="S2"' in site_facet
        assert "Apply" in site_facet

    def test_site_facet_on_the_subcomponents_page(
        self, analysis_workflow_with_subcomponent_labels, client_with_admin
    ):
        analysis = analysis_workflow_with_subcomponent_labels.analysis
        two_items(analysis)

        response = client_with_admin.get(subcomponents_url(analysis))

        assert response.status_code == 200
        site_facet = facet(response.content.decode(), "site_code")
        assert 'type="checkbox"' in site_facet
        assert 'data-filter="grant_code"' not in response.content.decode()

    def test_grant_facet_only_on_confirm_categories(
        self, analysis_workflow_with_confirmed_categories_cost_line_item, client_with_admin
    ):
        analysis = analysis_workflow_with_confirmed_categories_cost_line_item.analysis

        assert 'data-filter="grant_code"' in client_with_admin.get(categorize_url(analysis)).content.decode()
        assert (
            'data-filter="grant_code"' not in client_with_admin.get(allocate_url(analysis)).content.decode()
        )

    def test_selected_sites_narrow_the_rows(
        self, analysis_workflow_with_confirmed_categories_cost_line_item, client_with_admin
    ):
        analysis = analysis_workflow_with_confirmed_categories_cost_line_item.analysis
        first, second = two_items(analysis)

        response = client_with_admin.get(categorize_url(analysis), {"site_code": ["S1"]})

        assert response.status_code == 200
        assert [cli.pk for cli in response.context["object_list"]] == [first.pk]

    def test_filter_label_follows_override_in_the_menu(
        self, analysis_workflow_with_confirmed_categories_cost_line_item, client_with_admin
    ):
        from website.models import FieldLabelOverrides

        analysis = analysis_workflow_with_confirmed_categories_cost_line_item.analysis
        overrides = FieldLabelOverrides.get()
        overrides.ci_site_code = "Programme Site"
        overrides.ci_site_code_overridden = True
        overrides.save()

        content = client_with_admin.get(categorize_url(analysis)).content.decode()

        assert 'data-filter-target="site_code">Programme Site</a>' in content


@pytest.mark.django_db
class TestFiltersSurviveSaves:
    def test_subcomponents_post_with_filter_in_url_saves_and_keeps_it(
        self, analysis_workflow_with_subcomponent_labels, client_with_admin
    ):
        analysis = analysis_workflow_with_subcomponent_labels.analysis
        first, _second = two_items(analysis)
        subcomponent_analysis = analysis.interventioninstance_set.first().subcomponent_cost_analysis
        prefix = f"cost_line_item_subcomponent_allocation_{first.id}_{subcomponent_analysis.id}"

        response = client_with_admin.post(
            subcomponents_url(analysis) + "?site_code=S1",
            data={f"{prefix}_0": "60", f"{prefix}_1": "40"},
        )

        assert response.status_code == 302
        assert "site_code=S1" in response.url
        assert SubcomponentCostAllocation.objects.filter(
            subcomponent_analysis=subcomponent_analysis, cli_config=first.config, skipped=False
        ).exists()


@pytest.mark.django_db
class TestCostItemFacets:
    def test_name_keyword_narrows_the_rows(
        self, analysis_workflow_with_confirmed_categories_cost_line_item, client_with_admin
    ):
        analysis = analysis_workflow_with_confirmed_categories_cost_line_item.analysis
        first, _second = two_items(analysis)

        response = client_with_admin.get(categorize_url(analysis), {"budget_line_description": "PAY"})

        assert response.status_code == 200
        assert [cli.pk for cli in response.context["object_list"]] == [first.pk]

    def test_amount_facet_has_from_and_to_number_inputs(
        self, analysis_workflow_with_confirmed_categories_cost_line_item, client_with_admin
    ):
        analysis = analysis_workflow_with_confirmed_categories_cost_line_item.analysis

        content = client_with_admin.get(allocate_url(analysis)).content.decode()

        amount_facet = facet(content, "total_cost")
        assert 'data-filter-kind="range"' in amount_facet
        assert 'name="total_cost_min"' in amount_facet
        assert 'name="total_cost_max"' in amount_facet
        assert 'type="number"' in amount_facet
        assert "Apply" in amount_facet

    def test_custom_field_facet_everywhere_but_the_subcomponents_page(
        self, analysis_workflow_with_subcomponent_labels, client_with_admin
    ):
        analysis = analysis_workflow_with_subcomponent_labels.analysis
        cost_line_item = analysis.cost_line_items.first()
        cost_line_item.dummy_field_2 = "CC-100"
        cost_line_item.save()

        for url in (categorize_url(analysis), allocate_url(analysis)):
            assert 'data-filter="ci_dummy_field_2"' in client_with_admin.get(url).content.decode()
        assert (
            'data-filter="ci_dummy_field_2"'
            not in client_with_admin.get(subcomponents_url(analysis)).content.decode()
        )


@pytest.fixture
def transaction_analysis(defaults):
    """Item A (S1): Payroll 100 on 1 Jan 2024 and Fuel 300 on 15 Feb 2024; item B (S2): Payroll 300 on 31 Mar 2024."""
    analysis = make_analysis()
    tx(analysis, "100", transaction_description="Payroll January", date=date(2024, 1, 1))
    tx(analysis, "300", transaction_description="Fuel", date=date(2024, 2, 15))
    tx(analysis, "300", site_code="S2", transaction_description="Payroll March", date=date(2024, 3, 31))
    group(analysis)
    analysis.cost_type_categories.update(confirmed=True)
    return analysis


def allocate_everything(analysis):
    for cost_line_item in analysis.cost_line_items.cost_type_category_items():
        for instance in analysis.interventioninstance_set.all():
            cost_line_item.set_allocation_for_intervention(instance, Decimal("100"))


@pytest.mark.django_db
class TestTransactionFacets:
    def test_date_facet_is_a_flatpickr_pair_and_the_page_loads_its_script(
        self, transaction_analysis, client_with_admin
    ):
        content = client_with_admin.get(categorize_url(transaction_analysis)).content.decode()

        date_facet = facet(content, "transaction_date")
        assert 'data-filter-kind="date-range"' in date_facet
        assert 'name="transaction_date_after"' in date_facet
        assert 'name="transaction_date_before"' in date_facet
        assert "data-flatpickr" in date_facet
        # Pick-only, like the Define page: flatpickr's typed-input parser is case-sensitive on the
        # month and rewrites "01-jan-2024" to a date a year earlier.
        assert "allowInput" not in date_facet
        assert "flatpickr.min.js" in content
        assert 'class="filter__menu-heading">Transaction<' in content

    def test_budget_analysis_has_no_transaction_facets_or_script(
        self, analysis_workflow_with_confirmed_categories_cost_line_item, client_with_admin
    ):
        analysis = analysis_workflow_with_confirmed_categories_cost_line_item.analysis

        content = client_with_admin.get(categorize_url(analysis)).content.decode()

        assert 'data-filter="transaction_' not in content
        assert "flatpickr.min.js" not in content
        assert "filter__menu-heading" not in content

    def test_transaction_facets_narrow_the_rows_with_one_exists(
        self, transaction_analysis, client_with_admin
    ):
        b = item_for(transaction_analysis, site_code="S2")

        with CaptureQueriesContext(connection) as queries:
            response = client_with_admin.get(
                categorize_url(transaction_analysis),
                {"transaction_description": "payroll", "transaction_amount_min": "300"},
            )

        assert response.status_code == 200
        assert [cli.pk for cli in response.context["object_list"]] == [b.pk]
        exists_queries = [
            q["sql"] for q in queries if "EXISTS" in q["sql"] and "website_transaction" in q["sql"]
        ]
        assert len(exists_queries) == 1, exists_queries

    def test_subcomponents_post_with_a_transaction_facet_in_the_url_saves(
        self, transaction_analysis, client_with_admin
    ):
        allocate_everything(transaction_analysis)
        subcomponent_analysis = SubcomponentCostAnalysisFactory(analysis=transaction_analysis)
        a = item_for(transaction_analysis, site_code="S1")
        prefix = f"cost_line_item_subcomponent_allocation_{a.id}_{subcomponent_analysis.id}"

        response = client_with_admin.post(
            subcomponents_url(transaction_analysis) + "?transaction_description=fuel",
            data={f"{prefix}_0": "60", f"{prefix}_1": "40"},
        )

        assert response.status_code == 302
        assert "transaction_description=fuel" in response.url
        assert SubcomponentCostAllocation.objects.filter(
            subcomponent_analysis=subcomponent_analysis, cli_config=a.config, skipped=False
        ).exists()


@pytest.mark.django_db
class TestSensitiveAmountsStayHidden:
    def test_category_total_is_hidden_when_a_filter_isolates_a_sensitive_item(
        self, transaction_analysis, client_with_admin
    ):
        """Narrowing a category to one sensitive-account row must not reveal its amount in the header."""
        AccountCodeDescriptionFactory(account_code="7000", account_description="Rent", sensitive_data=True)
        template = item_for(transaction_analysis, site_code="S1").config
        rent = CostLineItemFactory(
            analysis=transaction_analysis,
            grant_code="G1",
            site_code="S3",
            account_code="7000",
            budget_line_description="Office Rent",
            total_cost=Decimal("1200"),
        )
        CostLineItemConfigFactory(
            cost_line_item=rent, cost_type=template.cost_type, category=template.category
        )

        response = client_with_admin.get(
            categorize_url(transaction_analysis), {"budget_line_description": "rent"}
        )

        assert response.status_code == 200
        assert [cli.pk for cli in response.context["object_list"]] == [rent.pk]
        assert "1,200" not in response.content.decode()


@pytest.mark.django_db
class TestAllocateHeaderCount:
    def test_cost_items_to_allocate_counts_the_filtered_rows(
        self, analysis_workflow_with_confirmed_categories_cost_line_item, client_with_admin
    ):
        analysis = analysis_workflow_with_confirmed_categories_cost_line_item.analysis
        first, _second = two_items(analysis)

        unfiltered = client_with_admin.get(allocate_url(analysis))
        filtered = client_with_admin.get(allocate_url(analysis), {"site_code": ["S1"]})

        shown = len(unfiltered.context["object_list"])
        assert shown >= 1
        assert f"{shown} Cost Items to allocate" in unfiltered.content.decode()
        assert [cli.pk for cli in filtered.context["object_list"]] == [first.pk]
        assert "1 Cost Items to allocate" in filtered.content.decode()

    def test_the_header_count_does_not_run_the_filtered_query_again(
        self, transaction_analysis, client_with_admin
    ):
        """The count comes from the rows the page loads: a transaction facet is not scanned twice."""
        with CaptureQueriesContext(connection) as queries:
            response = client_with_admin.get(
                allocate_url(transaction_analysis), {"transaction_description": "payroll"}
            )

        assert response.status_code == 200
        assert "2 Cost Items to allocate" in response.content.decode()
        filtered_queries = [
            q["sql"] for q in queries if "EXISTS" in q["sql"] and '"website_costlineitem"' in q["sql"]
        ]
        assert len(filtered_queries) == 1, filtered_queries
