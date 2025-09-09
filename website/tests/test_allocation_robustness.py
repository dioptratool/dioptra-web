import pytest

from website.tests.factories import (
    AnalysisFactory,
    CategoryFactory,
    CostLineItemConfigFactory,
    CostLineItemFactory,
    InterventionFactory,
)
from website.workflows import AnalysisWorkflow


@pytest.fixture
def simple_confirmed_analysis(defaults):
    category_1 = CategoryFactory(name="My Test Category 1")
    category_2 = CategoryFactory(name="My Test Category 2")

    intervention1 = InterventionFactory(
        name="First Intervention",
        output_metrics=[
            "NumberOfTeacherDaysOfTraining",
        ],
    )
    intervention2 = InterventionFactory(
        name="Second Intervention",
        output_metrics=[
            "NumberOfTeacherDaysOfTraining",
        ],
    )

    analysis = AnalysisFactory()
    analysis.grants = "DF119"
    analysis.save()
    analysis.add_intervention(
        intervention1,
        parameters={
            "number_of_teachers": 40,
            "number_of_days_of_training": 80,
        },
    )
    analysis.add_intervention(
        intervention2,
        parameters={
            "number_of_teachers": 40,
            "number_of_days_of_training": 80,
        },
    )

    line_item_1 = CostLineItemFactory(
        analysis=analysis,
        budget_line_description="My Budget Line Description 1",
        country_code="USA",
        grant_code="DF119",
        sector_code="HEAL",
        total_cost=50000.00,
    )
    line_item_2 = CostLineItemFactory(
        analysis=analysis,
        budget_line_description="My Budget Line Description 2",
        country_code="USA",
        grant_code="DF119",
        sector_code="HEAL",
        total_cost=25000.00,
    )
    # set allocation, category, and cost type for the line items
    config1 = CostLineItemConfigFactory(
        cost_line_item=line_item_1,
    )

    config2 = CostLineItemConfigFactory(
        cost_line_item=line_item_2,
    )

    config1.category = category_1
    config2.category = category_2
    config1.save()
    config2.save()

    analysis.ensure_cost_type_category_objects()

    for each in analysis.cost_type_categories.all():
        each.confirmed = True
        each.save()

    analysis.calculate_output_costs()
    return analysis


@pytest.mark.django_db
def test_fixture(simple_confirmed_analysis):
    wf = AnalysisWorkflow(simple_confirmed_analysis)
    assert wf.get_last_incomplete().name == "allocate-cost_type-grant"
    assert wf.get_last_complete().name == "categorize-cost_type"
