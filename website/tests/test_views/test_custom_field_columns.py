import pytest
from django.urls import reverse

from website.models import FieldLabelOverrides
from website.tests.factories import TransactionFactory


def _categorize_url(analysis):
    return reverse(
        "analysis-categorize-cost_type",
        kwargs={
            "pk": analysis.pk,
            "cost_type_pk": analysis.cost_line_items.first().config.cost_type.pk,
        },
    )


def _allocate_url(analysis):
    return reverse(
        "analysis-allocate-cost_type-grant",
        kwargs={
            "pk": analysis.pk,
            "cost_type_pk": analysis.cost_line_items.first().config.cost_type.pk,
            "grant": analysis.grants.split(",")[0],
        },
    )


@pytest.mark.django_db
class TestCostItemCustomColumns:
    def test_no_columns_render_when_no_custom_data_exists(
        self, analysis_workflow_with_allocations, client_with_admin
    ):
        analysis = analysis_workflow_with_allocations.analysis

        for url in (_categorize_url(analysis), _allocate_url(analysis)):
            content = client_with_admin.get(url).content.decode()
            assert "analysis-table__custom-field-cell" not in content
            assert "Budget Custom Field" not in content

    def test_populated_column_renders_on_confirm_categories(
        self, analysis_workflow_with_allocations, client_with_admin
    ):
        analysis = analysis_workflow_with_allocations.analysis
        cost_line_item = analysis.cost_line_items.first()
        cost_line_item.dummy_field_2 = "CC-100"
        cost_line_item.save()

        content = client_with_admin.get(_categorize_url(analysis)).content.decode()

        assert "Budget Custom Field 2" in content
        assert "CC-100" in content
        # Only the populated column, not all five.
        assert "Budget Custom Field 1" not in content
        assert "Budget Custom Field 3" not in content

    def test_populated_column_renders_on_allocate_costs(
        self, analysis_workflow_with_allocations, client_with_admin
    ):
        analysis = analysis_workflow_with_allocations.analysis
        cost_line_item = analysis.cost_line_items.first()
        cost_line_item.dummy_field_1 = "CC-200"
        cost_line_item.save()

        content = client_with_admin.get(_allocate_url(analysis)).content.decode()

        assert "Budget Custom Field 1" in content
        assert "CC-200" in content

    def test_overridden_label_replaces_the_default_header(
        self, analysis_workflow_with_allocations, client_with_admin
    ):
        overrides = FieldLabelOverrides.get()
        overrides.ci_dummy_field_1 = "Cost Centre"
        overrides.ci_dummy_field_1_overridden = True
        overrides.save()

        analysis = analysis_workflow_with_allocations.analysis
        cost_line_item = analysis.cost_line_items.first()
        cost_line_item.dummy_field_1 = "CC-300"
        cost_line_item.save()

        content = client_with_admin.get(_categorize_url(analysis)).content.decode()

        assert "Cost Centre" in content
        assert "Budget Custom Field 1" not in content

    def test_column_shows_for_every_row_once_any_row_has_a_value(
        self, analysis_workflow_with_allocations, client_with_admin
    ):
        analysis = analysis_workflow_with_allocations.analysis
        cost_line_items = list(analysis.cost_line_items.all())
        cost_line_items[0].dummy_field_1 = "CC-400"
        cost_line_items[0].save()

        content = client_with_admin.get(_categorize_url(analysis)).content.decode()

        # Every cost line item gets a cell, including the ones whose value is blank --
        # visibility is decided analysis-wide, not row by row.
        assert content.count('<td class="analysis-table__custom-field-cell">') == len(cost_line_items)
        # Confirm Categories renders one table per category, so the header repeats per table.
        assert content.count('<th class="analysis-table__custom-field-cell">') == content.count(
            "Account Code Description"
        )


@pytest.mark.django_db
class TestTransactionCustomColumns:
    def test_drill_down_renders_populated_transaction_custom_field(
        self, analysis_workflow_with_allocations, client_with_admin
    ):
        analysis = analysis_workflow_with_allocations.analysis
        cost_line_item = analysis.cost_line_items.first()
        TransactionFactory(
            analysis=analysis,
            cost_line_item=cost_line_item,
            dummy_field_3="PRJ-7",
        )

        response = client_with_admin.get(
            reverse("cost-line-item-transactions", kwargs={"pk": cost_line_item.pk})
        )
        content = response.content.decode()

        assert response.status_code == 200
        assert "PRJ-7" in content
        assert content.count("analysis-table__custom-field-cell") == 1

    def test_drill_down_renders_nothing_when_no_custom_data_exists(
        self, analysis_workflow_with_allocations, client_with_admin
    ):
        analysis = analysis_workflow_with_allocations.analysis
        cost_line_item = analysis.cost_line_items.first()
        TransactionFactory(analysis=analysis, cost_line_item=cost_line_item)

        response = client_with_admin.get(
            reverse("cost-line-item-transactions", kwargs={"pk": cost_line_item.pk})
        )

        assert "analysis-table__custom-field-cell" not in response.content.decode()

    def test_parent_page_renders_the_matching_transaction_header(
        self, analysis_workflow_with_allocations, client_with_admin
    ):
        overrides = FieldLabelOverrides.get()
        overrides.tr_dummy_field_3 = "Project Code"
        overrides.tr_dummy_field_3_overridden = True
        overrides.save()

        analysis = analysis_workflow_with_allocations.analysis
        cost_line_item = analysis.cost_line_items.first()
        TransactionFactory(
            analysis=analysis,
            cost_line_item=cost_line_item,
            dummy_field_3="PRJ-7",
        )

        content = client_with_admin.get(_categorize_url(analysis)).content.decode()

        # Header lives in the parent page's skeleton; the values arrive over AJAX.
        assert "Project Code" in content

    def test_transaction_columns_do_not_appear_at_the_cost_item_level(
        self, analysis_workflow_with_allocations, client_with_admin
    ):
        """90.5's corollary: transaction custom fields never roll up into the cost item."""
        analysis = analysis_workflow_with_allocations.analysis
        cost_line_item = analysis.cost_line_items.first()
        TransactionFactory(
            analysis=analysis,
            cost_line_item=cost_line_item,
            dummy_field_1="TX-ONLY",
        )

        assert analysis.cost_item_custom_fields == []
        content = client_with_admin.get(_categorize_url(analysis)).content.decode()
        assert "Budget Custom Field" not in content
