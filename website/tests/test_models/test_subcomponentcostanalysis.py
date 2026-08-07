from decimal import Decimal

import pytest

from website.models import AnalysisCostType, CostType, SubcomponentCostAnalysis
from website.models.cost_type import Indirect, Support
from website.tests.factories import (
    AnalysisFactory,
    CostLineItemConfigFactory,
    CostLineItemFactory,
    CostLineItemInterventionAllocationFactory,
    InterventionInstanceFactory,
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

    def test_allocated_totals_ignores_short_partial_rows(self, defaults):
        subcomponent_cost_analysis = SubcomponentCostAnalysisFactory(
            subcomponent_labels=["Treatment", "Outreach"]
        )
        intervention_instance = subcomponent_cost_analysis.intervention_instance
        analysis = intervention_instance.analysis

        full_config = CostLineItemConfigFactory(
            cost_line_item=CostLineItemFactory(analysis=analysis, total_cost=Decimal("1000")),
        )
        CostLineItemInterventionAllocationFactory(
            cli_config=full_config,
            intervention_instance=intervention_instance,
            allocation=Decimal("50"),
        )
        SubcomponentCostAllocationFactory(
            subcomponent_analysis=subcomponent_cost_analysis,
            cli_config=full_config,
            allocations={"0": "60", "1": "40"},
        )

        partial_config = CostLineItemConfigFactory(
            cost_line_item=CostLineItemFactory(analysis=analysis, total_cost=Decimal("1000")),
        )
        CostLineItemInterventionAllocationFactory(
            cli_config=partial_config,
            intervention_instance=intervention_instance,
            allocation=Decimal("50"),
        )
        SubcomponentCostAllocationFactory(
            subcomponent_analysis=subcomponent_cost_analysis,
            cli_config=partial_config,
            allocations={"0": "50"},
        )

        # The partial row must not truncate the totals to one column via
        # zip(*...); its missing label contributes zero.
        assert subcomponent_cost_analysis.allocated_totals() == [550.0, 200.0]

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


@pytest.mark.django_db
class TestFullCostPercentages:
    """
    The full-cost sub-component split (applied to Program + Support + Indirect
    Costs) derives shared costs from the weighted Program Cost allocation, so
    it must equal the Program Cost weighted average no matter what allocation
    rows are stored on shared, skipped, or in-kind items.
    """

    def _subcomponent_analysis(self):
        subcomponent_analysis = SubcomponentCostAnalysisFactory(subcomponent_labels=["Treatment", "Outreach"])
        return subcomponent_analysis, subcomponent_analysis.intervention_instance

    def _add_row(
        self,
        subcomponent_analysis,
        intervention_instance,
        *,
        total_cost,
        intervention_allocation,
        allocations=None,
        skipped=False,
        cost_type_type=None,
        analysis_cost_type=None,
    ):
        config_kwargs = {
            "cost_line_item": CostLineItemFactory(
                analysis=intervention_instance.analysis,
                total_cost=Decimal(total_cost),
            ),
        }
        if cost_type_type is not None:
            config_kwargs["cost_type"] = CostType.objects.get(type=cost_type_type)
        if analysis_cost_type is not None:
            config_kwargs["cost_type"] = None
            config_kwargs["analysis_cost_type"] = analysis_cost_type
        config = CostLineItemConfigFactory(**config_kwargs)
        CostLineItemInterventionAllocationFactory(
            cli_config=config,
            intervention_instance=intervention_instance,
            allocation=Decimal(intervention_allocation),
        )
        if allocations is not None or skipped:
            SubcomponentCostAllocationFactory(
                subcomponent_analysis=subcomponent_analysis,
                cli_config=config,
                allocations=allocations or {},
                skipped=skipped,
            )
        return config

    def test_equals_the_program_cost_weighted_average(self, defaults):
        subcomponent_analysis, intervention_instance = self._subcomponent_analysis()
        self._add_row(
            subcomponent_analysis,
            intervention_instance,
            total_cost="1000",
            intervention_allocation="50",
            allocations={"0": "60", "1": "40"},
        )
        self._add_row(
            subcomponent_analysis,
            intervention_instance,
            total_cost="3000",
            intervention_allocation="50",
            allocations={"0": "20", "1": "80"},
        )

        # (500 * 60% + 1500 * 20%) / 2000 = 30%
        assert subcomponent_analysis.full_cost_percentages() == [30, 70]

    def test_ignores_stored_allocations_on_support_rows(self, defaults):
        subcomponent_analysis, intervention_instance = self._subcomponent_analysis()
        self._add_row(
            subcomponent_analysis,
            intervention_instance,
            total_cost="1000",
            intervention_allocation="50",
            allocations={"0": "60", "1": "40"},
        )
        # A stored allocation on a Support row (e.g. derived rows migrated
        # from 2.1) must not shift the split.
        self._add_row(
            subcomponent_analysis,
            intervention_instance,
            total_cost="9000",
            intervention_allocation="100",
            allocations={"0": "0", "1": "100"},
            cost_type_type=Support.id,
        )

        assert subcomponent_analysis.full_cost_percentages() == [60, 40]

    def test_ignores_stored_allocations_on_indirect_rows(self, defaults):
        subcomponent_analysis, intervention_instance = self._subcomponent_analysis()
        self._add_row(
            subcomponent_analysis,
            intervention_instance,
            total_cost="1000",
            intervention_allocation="50",
            allocations={"0": "60", "1": "40"},
        )
        self._add_row(
            subcomponent_analysis,
            intervention_instance,
            total_cost="5000",
            intervention_allocation="100",
            allocations={"0": "100", "1": "0"},
            cost_type_type=Indirect.id,
        )

        assert subcomponent_analysis.full_cost_percentages() == [60, 40]

    def test_all_cost_types_with_skipped_and_in_kind_rows(self, defaults):
        subcomponent_analysis, intervention_instance = self._subcomponent_analysis()
        self._add_row(
            subcomponent_analysis,
            intervention_instance,
            total_cost="1000",
            intervention_allocation="50",
            allocations={"0": "60", "1": "40"},
        )
        self._add_row(
            subcomponent_analysis,
            intervention_instance,
            total_cost="9000",
            intervention_allocation="100",
            allocations={"0": "0", "1": "100"},
            cost_type_type=Support.id,
        )
        self._add_row(
            subcomponent_analysis,
            intervention_instance,
            total_cost="5000",
            intervention_allocation="100",
            allocations={"0": "100", "1": "0"},
            cost_type_type=Indirect.id,
        )
        # A skipped Program row keeps whatever values it had before skipping.
        self._add_row(
            subcomponent_analysis,
            intervention_instance,
            total_cost="2000",
            intervention_allocation="100",
            allocations={"0": "100", "1": "0"},
            skipped=True,
        )
        self._add_row(
            subcomponent_analysis,
            intervention_instance,
            total_cost="4000",
            intervention_allocation="100",
            allocations={"0": "25", "1": "75"},
            analysis_cost_type=AnalysisCostType.IN_KIND,
        )

        assert subcomponent_analysis.full_cost_percentages() == [60, 40]

    def test_empty_without_allocated_program_rows(self, defaults):
        subcomponent_analysis, intervention_instance = self._subcomponent_analysis()
        self._add_row(
            subcomponent_analysis,
            intervention_instance,
            total_cost="2000",
            intervention_allocation="100",
            allocations={"0": "100", "1": "0"},
            skipped=True,
        )
        self._add_row(
            subcomponent_analysis,
            intervention_instance,
            total_cost="9000",
            intervention_allocation="100",
            allocations={"0": "0", "1": "100"},
            cost_type_type=Support.id,
        )

        assert subcomponent_analysis.full_cost_percentages() == []

    def test_split_is_independent_per_intervention(self, defaults):
        analysis = AnalysisFactory()
        instance_1 = InterventionInstanceFactory(analysis=analysis)
        instance_2 = InterventionInstanceFactory(analysis=analysis)
        subcomponent_analysis_1 = SubcomponentCostAnalysisFactory(
            intervention_instance=instance_1,
            subcomponent_labels=["Treatment", "Outreach"],
        )
        subcomponent_analysis_2 = SubcomponentCostAnalysisFactory(
            intervention_instance=instance_2,
            subcomponent_labels=["Treatment", "Outreach"],
        )

        config = CostLineItemConfigFactory(
            cost_line_item=CostLineItemFactory(analysis=analysis, total_cost=Decimal("1000")),
        )
        for instance in (instance_1, instance_2):
            CostLineItemInterventionAllocationFactory(
                cli_config=config,
                intervention_instance=instance,
                allocation=Decimal("50"),
            )
        SubcomponentCostAllocationFactory(
            subcomponent_analysis=subcomponent_analysis_1,
            cli_config=config,
            allocations={"0": "100", "1": "0"},
        )
        SubcomponentCostAllocationFactory(
            subcomponent_analysis=subcomponent_analysis_2,
            cli_config=config,
            allocations={"0": "0", "1": "100"},
        )

        assert subcomponent_analysis_1.full_cost_percentages() == [100, 0]
        assert subcomponent_analysis_2.full_cost_percentages() == [0, 100]
