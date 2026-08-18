import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from website.models import Analysis, FieldLabelOverrides
from website.tests.factories import AnalysisFactory, CostLineItemFactory, TransactionFactory


@pytest.mark.django_db
class TestCostItemCustomFields:
    def test_no_custom_fields_when_nothing_is_populated(self):
        analysis = AnalysisFactory()
        CostLineItemFactory(analysis=analysis)

        assert analysis.cost_item_custom_fields == []

    def test_no_custom_fields_when_the_analysis_has_no_cost_items(self):
        assert AnalysisFactory().cost_item_custom_fields == []

    def test_only_populated_custom_fields_are_returned(self):
        analysis = AnalysisFactory()
        CostLineItemFactory(analysis=analysis, dummy_field_2="Donor")

        assert analysis.cost_item_custom_fields == [
            {
                "field": "dummy_field_2",
                "label_key": "ci_dummy_field_2",
                "default_label": "Budget Custom Field 2",
            }
        ]

    def test_a_value_on_any_row_shows_the_column_for_the_whole_analysis(self):
        analysis = AnalysisFactory()
        CostLineItemFactory(analysis=analysis, dummy_field_1="")
        CostLineItemFactory(analysis=analysis, dummy_field_1="CC-100")

        assert [column["field"] for column in analysis.cost_item_custom_fields] == ["dummy_field_1"]

    def test_all_five_custom_fields_are_returned_in_order(self):
        analysis = AnalysisFactory()
        CostLineItemFactory(
            analysis=analysis,
            dummy_field_1="a",
            dummy_field_2="b",
            dummy_field_3="c",
            dummy_field_4="d",
            dummy_field_5="e",
        )

        assert [column["field"] for column in analysis.cost_item_custom_fields] == [
            f"dummy_field_{n}" for n in range(1, 6)
        ]

    def test_another_analysis_values_do_not_leak(self):
        analysis = AnalysisFactory()
        CostLineItemFactory(analysis=analysis)
        CostLineItemFactory(analysis=AnalysisFactory(), dummy_field_1="CC-100")

        assert analysis.cost_item_custom_fields == []

    def test_result_is_cached_and_costs_one_query(self):
        analysis = AnalysisFactory()
        CostLineItemFactory(analysis=analysis, dummy_field_1="CC-100")
        analysis = Analysis.objects.get(pk=analysis.pk)

        with CaptureQueriesContext(connection) as queries:
            analysis.cost_item_custom_fields
            analysis.cost_item_custom_fields

        assert len(queries) == 1


@pytest.mark.django_db
class TestTransactionCustomFields:
    def test_no_custom_fields_when_nothing_is_populated(self):
        analysis = AnalysisFactory()
        TransactionFactory(analysis=analysis)

        assert analysis.transaction_custom_fields == []

    def test_only_populated_custom_fields_are_returned(self):
        analysis = AnalysisFactory()
        TransactionFactory(analysis=analysis, dummy_field_4="PRJ-7")

        assert analysis.transaction_custom_fields == [
            {
                "field": "dummy_field_4",
                "label_key": "tr_dummy_field_4",
                "default_label": "Transaction Custom Field 4",
            }
        ]

    def test_cost_item_and_transaction_custom_fields_are_independent(self):
        analysis = AnalysisFactory()
        CostLineItemFactory(analysis=analysis, dummy_field_1="CC-100")
        TransactionFactory(analysis=analysis, dummy_field_2="DFID")

        assert [column["field"] for column in analysis.cost_item_custom_fields] == ["dummy_field_1"]
        assert [column["field"] for column in analysis.transaction_custom_fields] == ["dummy_field_2"]


@pytest.mark.django_db
def test_label_key_and_default_resolve_through_field_label_overrides():
    from website.models.utils import load_field_label_override

    overrides = FieldLabelOverrides.get()
    overrides.ci_dummy_field_1 = "Cost Centre"
    overrides.ci_dummy_field_1_overridden = True
    overrides.save()

    analysis = AnalysisFactory()
    CostLineItemFactory(analysis=analysis, dummy_field_1="CC-100", dummy_field_2="DFID")

    labels = [
        load_field_label_override(column["label_key"], column["default_label"])
        for column in analysis.cost_item_custom_fields
    ]
    assert labels == ["Cost Centre", "Budget Custom Field 2"]
