import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from website.models import CostLineItem
from website.tests.factories import (
    CostLineItemConfigFactory,
    CostLineItemInterventionAllocationFactory,
    InterventionInstanceFactory,
)
from website.tests.test_corrections.helpers import group, make_analysis, tx


@pytest.mark.django_db
class TestGetSoleAllocatorName:
    def test_returns_empty_string_without_any_allocation(self, defaults):
        config = CostLineItemConfigFactory()

        assert config.get_sole_allocator_name == ""

    def test_returns_empty_string_without_a_full_allocation(self, defaults):
        config = CostLineItemConfigFactory()
        instance = InterventionInstanceFactory(analysis=config.cost_line_item.analysis)
        CostLineItemInterventionAllocationFactory(
            cli_config=config,
            intervention_instance=instance,
            allocation=50,
        )

        assert config.get_sole_allocator_name == ""

    def test_returns_display_name_for_full_allocation(self, defaults):
        config = CostLineItemConfigFactory()
        instance = InterventionInstanceFactory(analysis=config.cost_line_item.analysis)
        CostLineItemInterventionAllocationFactory(
            cli_config=config,
            intervention_instance=instance,
            allocation=100,
        )

        assert config.get_sole_allocator_name == instance.display_name()


@pytest.mark.django_db
class TestTransactionsCount:
    """Step pages read each row's transaction count from the row query, not one query per row."""

    def test_annotated_rows_answer_without_a_query(self, defaults):
        analysis = make_analysis()
        tx(analysis, "100")
        tx(analysis, "200")
        tx(analysis, "300", site_code="S2")
        group(analysis)

        rows = list(analysis.cost_line_items.with_transactions_count().order_by("site_code"))

        with CaptureQueriesContext(connection) as queries:
            counts = [row.transactions_count for row in rows]
        assert counts == [2, 1]
        assert len(queries) == 0

    def test_a_row_without_transactions_counts_zero(self, defaults):
        cost_line_item = CostLineItemConfigFactory().cost_line_item

        row = CostLineItem.objects.with_transactions_count().get(pk=cost_line_item.pk)

        assert row.transactions_count == 0

    def test_an_unannotated_row_falls_back_to_one_count(self, defaults):
        analysis = make_analysis()
        tx(analysis, "100")
        group(analysis)
        row = CostLineItem.objects.get(analysis=analysis)

        with CaptureQueriesContext(connection) as queries:
            assert row.transactions_count == 1
        assert len(queries) == 1
