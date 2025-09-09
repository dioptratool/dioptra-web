from decimal import Decimal

import pytest

from website.models import AnalysisCostType, SubcomponentCostAnalysis
from website.tests.factories import (
    CostLineItemConfigFactory,
    CostLineItemFactory,
    CostLineItemInterventionAllocationFactory,
)


@pytest.mark.django_db
class TestAnalysisSubcomponentAnalysisComplete:
    def test_starts_with_insights_complete(
        self,
        analysis_workflow_with_subcomponent_labels_and_client_time_added,
    ):
        analysis_wf = analysis_workflow_with_subcomponent_labels_and_client_time_added
        assert analysis_wf.get_step("insights").is_complete, (
            f"'insights' should be complete.  Instead "
            f"the last complete step is: '{analysis_wf.get_last_complete().name}'"
        )

    def test_starts_incomplete(self, analysis_workflow_with_subcomponent_labels_and_client_time_added):
        analysis = analysis_workflow_with_subcomponent_labels_and_client_time_added.analysis
        assert not all(scg.subcomponent_allocation_complete() for scg in analysis.cost_type_category_grants)

    def test_complete_if_skipped(self, analysis_workflow_with_subcomponent_labels_and_client_time_added):
        analysis = analysis_workflow_with_subcomponent_labels_and_client_time_added.analysis
        for scg in analysis.cost_type_category_grants.all():
            if not scg.subcomponent_allocation_complete():
                for cost_line_item in scg.get_cost_line_items():
                    cost_line_item.config.subcomponent_analysis_allocations_skipped = True
                    cost_line_item.config.save()
                assert scg.subcomponent_allocation_complete()

    def test_complete_if_allocated(self, analysis_workflow_with_subcomponent_labels_and_client_time_added):
        analysis = analysis_workflow_with_subcomponent_labels_and_client_time_added.analysis
        for scg in analysis.cost_type_category_grants.all():
            if not scg.subcomponent_allocation_complete():
                for cost_line_item in scg.get_cost_line_items():
                    cost_line_item.config.subcomponent_analysis_allocations = {"foo": "100"}
                    cost_line_item.config.save()
                assert scg.subcomponent_allocation_complete()

    def test_complete_if_mixed(self, analysis_workflow_with_subcomponent_labels_and_client_time_added):
        analysis = analysis_workflow_with_subcomponent_labels_and_client_time_added.analysis
        for scg in analysis.cost_type_category_grants.all():
            assert scg.get_cost_line_items().count() == 1

            if not scg.subcomponent_allocation_complete():
                for cost_line_item in scg.get_cost_line_items():
                    cost_line_item.config.subcomponent_analysis_allocations_skipped = True
                    cost_line_item.config.save()

                CostLineItemConfigFactory(
                    cost_line_item=CostLineItemFactory(
                        analysis=analysis,
                        grant_code=scg.grant,
                    ),
                    subcomponent_analysis_allocations={"foo": "100"},
                    cost_type=scg.cost_type_category.cost_type,
                    category=scg.cost_type_category.category,
                )

                assert scg.get_cost_line_items().count() == 2

                assert scg.subcomponent_allocation_complete()


@pytest.mark.django_db
class TestSubcomponentCostAnalysis:
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
            subcomponent_analysis_allocations={
                "0": "100",
                "1": "0",
                "2": "0",
                "3": "0",
                "4": "0",
            },
            cost_line_item=new_cli,
            analysis_cost_type=AnalysisCostType.CLIENT_TIME,
        ),
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
                subcomponent_analysis_allocations={
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
        if analysis.interventions.count() == 2:
            # The odd number is from the existing two from the fixture
            assert subcomponent_cost_analysis.cost_line_item_average() == [
                Decimal("10.08"),
                Decimal("10.08"),
                Decimal("10.08"),
                Decimal("10.08"),
                Decimal("59.68"),
            ]
        elif analysis.interventions.count() == 1:
            # The odd number is from the existing one from the fixture
            assert subcomponent_cost_analysis.cost_line_item_average() == [
                Decimal("10.04"),
                Decimal("10.04"),
                Decimal("10.04"),
                Decimal("10.04"),
                Decimal("59.84"),
            ]
        else:
            raise AssertionError("Unexpected number of interventions for this test")

    def test_cost_line_item_average_with_skipped_items(
        self, analysis_workflow_with_all_cost_lines_allocated_to_subcomponents
    ):
        subcomponent_cost_analysis = SubcomponentCostAnalysis.objects.first()
        for _ in range(10):
            CostLineItemConfigFactory(
                cost_line_item=CostLineItemFactory(analysis=subcomponent_cost_analysis.analysis),
                subcomponent_analysis_allocations_skipped=True,
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
            subcomponent_analysis_allocations={
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
