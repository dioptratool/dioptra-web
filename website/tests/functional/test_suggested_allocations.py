from decimal import Decimal

import pytest

from website.models.cost_type import CostType
from website.tests.factories import (
    AnalysisFactory,
    CostLineItemConfigFactory,
    CostLineItemInterventionAllocationFactory,
    InterventionFactory,
)


class TestSupportCostSuggestedAllocations:
    @pytest.fixture
    def simple_analysis(self, defaults):
        grant = "DF119"
        analysis = AnalysisFactory()
        analysis.grants = grant
        analysis.save()
        analysis.add_intervention(InterventionFactory(name="First Intervention"))

        cli1 = CostLineItemConfigFactory().cost_line_item
        cli2 = CostLineItemConfigFactory(
            cost_type=CostType.objects.get(name="Support Costs"),
            category=cli1.config.category,
        ).cost_line_item

        cli1.total_cost = Decimal(100)
        cli2.total_cost = Decimal(100)
        cli1.grant_code = grant
        cli2.grant_code = grant
        cli1.analysis = analysis
        cli2.analysis = analysis
        cli1.save()
        cli2.save()

        analysis.ensure_cost_type_category_objects()
        for each in analysis.cost_type_categories.all():
            each.confirmed = True
            each.save()
        return analysis

    @pytest.mark.django_db
    def test_get_suggested_allocations_single_intervention_support_project_cost(self, simple_analysis):
        """
        Single Intervention
        Simple test with 2 line items, one with an allocation and one not.
        The suggestion should be the same value as the allocated one.
        """

        analysis = simple_analysis
        cli1 = analysis.cost_line_items.filter(config__cost_type__type=CostType.TYPES[0].id).first()
        cli2 = analysis.cost_line_items.filter(config__cost_type__type=CostType.TYPES[1].id).first()

        CostLineItemInterventionAllocationFactory(
            allocation=Decimal("10"),
            cli_config=cli1.config,
            intervention_instance=analysis.interventioninstance_set.filter(
                intervention__name="First Intervention"
            ).first(),
        )

        (
            numerator,
            denominator,
            percentage,
        ) = cli2.config.cost_type.type_obj().get_suggested_allocation(
            analysis,
            analysis.interventioninstance_set.filter(intervention__name="First Intervention").first(),
            "DF119",
        )
        assert numerator == 10
        assert denominator == 100
        assert percentage == 10

    @pytest.mark.django_db
    def test_get_suggested_allocations_multiple_intervention_support_project_cost(self, simple_analysis):
        """
        Single Intervention
        Simple test with 2 line items, one with an allocation and one not.
        The suggestion should be the same value as the allocated one.
        """

        analysis = simple_analysis
        analysis.add_intervention(InterventionFactory(name="Second Intervention"))

        cli1 = analysis.cost_line_items.filter(config__cost_type__type=CostType.TYPES[0].id).first()
        cli2 = analysis.cost_line_items.filter(config__cost_type__type=CostType.TYPES[1].id).first()

        CostLineItemInterventionAllocationFactory(
            allocation=Decimal("10"),
            cli_config=cli1.config,
            intervention_instance=analysis.interventioninstance_set.filter(
                intervention__name="First Intervention"
            ).first(),
        )

        (
            numerator,
            denominator,
            percentage,
        ) = cli2.config.cost_type.type_obj().get_suggested_allocation(
            analysis,
            analysis.interventioninstance_set.filter(intervention__name="First Intervention").first(),
            "DF119",
        )
        assert numerator == 10
        assert denominator == 100
        assert percentage == 10

        (
            numerator,
            denominator,
            percentage,
        ) = cli2.config.cost_type.type_obj().get_suggested_allocation(
            analysis,
            analysis.interventioninstance_set.filter(intervention__name="Second Intervention").first(),
            "DF119",
        )

        assert numerator == 0
        assert denominator == 100
        assert percentage == 0
