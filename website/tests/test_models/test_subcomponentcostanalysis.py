from decimal import Decimal

import pytest

from website.models import AnalysisCostType, SubcomponentCostAnalysis
from website.tests.factories import (
    CostLineItemConfigFactory,
    CostLineItemFactory,
    CostLineItemInterventionAllocationFactory,
    SubcomponentCostAllocationFactory,
    SubcomponentCostAnalysisFactory,
)


@pytest.mark.django_db
class TestSubcomponentCostAnalysis:
    def test_analysis_has_subcomponent_labels(self):
        subcomponent_cost_analysis = SubcomponentCostAnalysisFactory(
            subcomponent_labels=["Setup", "Delivery"]
        )

        assert subcomponent_cost_analysis.analysis.has_subcomponent_labels()

    def test_cost_line_item_average_minimal(
        self, analysis_workflow_with_all_cost_lines_allocated_to_subcomponents
    ):
        subcomponent_cost_analysis = SubcomponentCostAnalysis.objects.first()
        assert subcomponent_cost_analysis.cost_line_item_average() == [
            20,
            20,
            20,
            20,
            20,
        ]

    def test_cost_line_item_average_minimal_with_intervention_cost_types(
        self, analysis_workflow_with_all_cost_lines_allocated_to_subcomponents
    ):
        """The cost line average excludes items with an analysis_cost_type set"""
        subcomponent_cost_analysis = SubcomponentCostAnalysis.objects.first()
        new_cli = CostLineItemFactory(
            analysis=subcomponent_cost_analysis.analysis,
        )
        CostLineItemConfigFactory(
            cost_line_item=new_cli,
            analysis_cost_type=AnalysisCostType.CLIENT_TIME,
        )
        assert subcomponent_cost_analysis.cost_line_item_average() == [
            20,
            20,
            20,
            20,
            20,
        ]

    def test_cost_line_item_average_more_line_items(
        self, analysis_workflow_with_all_cost_lines_allocated_to_subcomponents
    ):
        analysis = analysis_workflow_with_all_cost_lines_allocated_to_subcomponents.analysis
        subcomponent_cost_analysis = SubcomponentCostAnalysis.objects.first()

        for _ in range(100):
            cli_config = CostLineItemConfigFactory(
                cost_line_item=CostLineItemFactory(analysis=subcomponent_cost_analysis.analysis),
            )
            SubcomponentCostAllocationFactory(
                subcomponent_analysis=subcomponent_cost_analysis,
                cli_config=cli_config,
                allocations={
                    "0": "10",
                    "1": "10",
                    "2": "10",
                    "3": "10",
                    "4": "60",
                },
            )
            CostLineItemInterventionAllocationFactory(
                cli_config=cli_config,
                intervention_instance=analysis.interventioninstance_set.first(),
                allocation=Decimal("0.5"),
            )

        # This is not great test code, but the values here will change based on the seeded number of interventions.
        #  It is correct but if you end up here chasing down a value you may want to refactor the fixtures
        assert subcomponent_cost_analysis.cost_line_item_average() == [
            Decimal("10.04"),
            Decimal("10.04"),
            Decimal("10.04"),
            Decimal("10.04"),
            Decimal("59.84"),
        ]

    def test_cost_line_item_average_with_skipped_items(
        self, analysis_workflow_with_all_cost_lines_allocated_to_subcomponents
    ):
        subcomponent_cost_analysis = SubcomponentCostAnalysis.objects.first()
        for _ in range(10):
            cli_config = CostLineItemConfigFactory(
                cost_line_item=CostLineItemFactory(analysis=subcomponent_cost_analysis.analysis),
            )
            SubcomponentCostAllocationFactory(
                subcomponent_analysis=subcomponent_cost_analysis,
                cli_config=cli_config,
                allocations={},
                skipped=True,
            )

        assert subcomponent_cost_analysis.cost_line_item_average() == [
            20,
            20,
            20,
            20,
            20,
        ]

    def test_cost_line_item_average_heavily_weighted_on_one_cost_line_item(
        self, analysis_workflow_with_all_cost_lines_allocated_to_subcomponents
    ):
        subcomponent_cost_analysis = SubcomponentCostAnalysis.objects.first()

        config1 = CostLineItemConfigFactory(
            cost_line_item=CostLineItemFactory(
                total_cost=Decimal("1000"),
                analysis=subcomponent_cost_analysis.analysis,
            ),
        )
        SubcomponentCostAllocationFactory(
            subcomponent_analysis=subcomponent_cost_analysis,
            cli_config=config1,
            allocations={
                "0": "100",
                "1": "0",
                "2": "0",
                "3": "0",
                "4": "0",
            },
        )

        for each_intervention_instance in subcomponent_cost_analysis.analysis.interventioninstance_set.all():
            CostLineItemInterventionAllocationFactory(
                cli_config=config1,
                intervention_instance=each_intervention_instance,
                allocation=Decimal("0.5"),
            )

        assert subcomponent_cost_analysis.cost_line_item_average() == [
            Decimal("96.92"),
            Decimal("0.77"),
            Decimal("0.77"),
            Decimal("0.77"),
            Decimal("0.77"),
        ]
