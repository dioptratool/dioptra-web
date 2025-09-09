from decimal import Decimal

import pytest

from website.models import CostType
from website.tests.factories import (
    AnalysisCostTypeCategoryFactory,
    AnalysisCostTypeCategoryGrantFactory,
    AnalysisFactory,
    CostLineItemConfigFactory,
    CostLineItemFactory,
    CostLineItemInterventionAllocationFactory,
    InterventionFactory,
    InterventionGroupFactory,
    SubcomponentCostAnalysisFactory,
)
from website.workflows import AnalysisWorkflow


@pytest.mark.django_db
def test_simplified_example_of_the_suggested_allocation_from_dioptra(defaults):
    """
    This example was provided to us from Dioptra.

    This is set up from scratch to be as specific as possible.

    This test makes sure that after allocating to some Cost Line Items
      the correct percentages are presented to the ones that were
      skipped or left blank on purpose

    """
    intervention_group = InterventionGroupFactory(name="Cash")
    unconditional_cash_transfer = InterventionFactory(
        name="Unconditional Cash Transfer",
        description="Provision of cash to individuals, households, "
        "or community recipients through electronic or "
        "direct cash, or via paper or evouchers, without "
        "conditions that must be met before receiving a "
        "transfer or restrictions on what a transfer can "
        "be spent on once received.",
        icon="cash",
        group=intervention_group,
        output_metrics=["ValueOfCashDistributed"],
        subcomponent_labels=["A", "B"],
    )
    intervention = unconditional_cash_transfer

    analysis = AnalysisFactory(
        grants="Unknown",
    )
    analysis.add_intervention(
        intervention,
        parameters={"value_of_cash_distributed": 1000.0},
    )
    analysis_wf = AnalysisWorkflow(analysis=analysis)

    item_1 = CostLineItemFactory(
        analysis=analysis_wf.analysis,
        grant_code="Unknown",
        total_cost=Decimal(100),
        budget_line_description="Item 1 - Support",
    )
    item_1_cost_line_item_config = CostLineItemConfigFactory(
        cost_line_item=item_1,
        cost_type=CostType.objects.get(name="Support Costs"),
    )

    CostLineItemInterventionAllocationFactory(
        cli_config=item_1_cost_line_item_config,
        intervention_instance=analysis.interventioninstance_set.first(),
        allocation=100,
    )

    item_1_cost_type_category = AnalysisCostTypeCategoryFactory(
        analysis=analysis_wf.analysis,
        category=item_1.config.category,
        confirmed=True,
        cost_type=item_1.config.cost_type,
    )
    AnalysisCostTypeCategoryGrantFactory(
        cost_type_category=item_1_cost_type_category,
        grant="Unknown",
    )

    item_2 = CostLineItemFactory(
        analysis=analysis_wf.analysis,
        grant_code="Unknown",
        total_cost=Decimal(200),
        budget_line_description="Item 2",
    )

    item_2_cost_line_item_config = CostLineItemConfigFactory(
        cost_line_item=item_2,
    )
    CostLineItemInterventionAllocationFactory(
        cli_config=item_2_cost_line_item_config,
        intervention_instance=analysis.interventioninstance_set.first(),
        allocation=40,
    )

    item_2_cost_type_category = AnalysisCostTypeCategoryFactory(
        analysis=analysis_wf.analysis,
        category=item_2.config.category,
        confirmed=True,
        cost_type=item_2.config.cost_type,
    )
    AnalysisCostTypeCategoryGrantFactory(
        cost_type_category=item_2_cost_type_category,
        grant="Unknown",
    )

    item_3 = CostLineItemFactory(
        analysis=analysis_wf.analysis,
        grant_code="Unknown",
        total_cost=Decimal(20),
        budget_line_description="Item 3",
    )

    item_3_cost_line_item_config = CostLineItemConfigFactory(
        cost_line_item=item_3,
    )
    CostLineItemInterventionAllocationFactory(
        cli_config=item_3_cost_line_item_config,
        intervention_instance=analysis.interventioninstance_set.first(),
        allocation=100,
    )

    item_3_cost_type_category = AnalysisCostTypeCategoryFactory(
        analysis=analysis_wf.analysis,
        category=item_3.config.category,
        confirmed=True,
        cost_type=item_3.config.cost_type,
    )
    AnalysisCostTypeCategoryGrantFactory(
        cost_type_category=item_3_cost_type_category,
        grant="Unknown",
    )

    item_4 = CostLineItemFactory(
        analysis=analysis_wf.analysis,
        grant_code="Unknown",
        total_cost=Decimal(1000),
        budget_line_description="Item 4 - Cash transfer",
    )

    item_4_cost_line_item_config = CostLineItemConfigFactory(
        cost_line_item=item_4,
    )
    CostLineItemInterventionAllocationFactory(
        cli_config=item_4_cost_line_item_config,
        intervention_instance=analysis.interventioninstance_set.first(),
        allocation=100,
    )

    item_4_cost_type_category = AnalysisCostTypeCategoryFactory(
        analysis=analysis_wf.analysis,
        category=item_4.config.category,
        confirmed=True,
        cost_type=item_4.config.cost_type,
    )
    AnalysisCostTypeCategoryGrantFactory(
        cost_type_category=item_4_cost_type_category,
        grant="Unknown",
    )

    # Now we do the Subcomponent and test our actual values
    subcomponent_cost_analysis = SubcomponentCostAnalysisFactory(
        analysis=analysis_wf.analysis,
        subcomponent_labels_confirmed=True,
    )

    item_2.config.subcomponent_analysis_allocations = {
        "0": "75",
        "1": "25",
    }
    item_2.config.save()

    item_3.config.subcomponent_analysis_allocations = {
        "0": "50",
        "1": "50",
    }
    item_3.config.save()

    assert subcomponent_cost_analysis.cost_line_item_average() == [70.0, 30.0]
