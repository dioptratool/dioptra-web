import random
from datetime import date
from decimal import Decimal

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model

from website.workflows import AnalysisWorkflow
from .factories import (
    AnalysisCostTypeCategoryFactory,
    AnalysisCostTypeCategoryGrantFactory,
    AnalysisFactory,
    CategoryFactory,
    CostLineItemConfigFactory,
    CostLineItemFactory,
    CostLineItemInterventionAllocationFactory,
    CostTypeFactory,
    CountryFactory,
    InterventionFactory,
    SubcomponentCostAnalysisFactory,
    UserFactory,
)
from ..models import (
    Analysis,
    AnalysisCostType,
    AnalysisType,
    CostLineItem,
    Settings,
)
from ..models.cost_type import CostType

User = get_user_model()


@pytest.fixture
def defaults():
    Settings.objects.create()
    CategoryFactory(name=settings.DEFAULT_CATEGORY)
    CostTypeFactory(
        name="Program Costs",
        type=10,
        order=1,
        default=True,
    )
    CostTypeFactory(
        name="Support Costs",
        type=20,
        order=2,
    )
    CostTypeFactory(
        name="Indirect Costs",
        type=30,
        order=3,
    )


@pytest.fixture
def a_user():
    return UserFactory()


@pytest.fixture
def client_with_admin(client):
    admin = UserFactory(role=User.ADMIN)
    client.force_login(admin)
    return client


@pytest.fixture
def transaction_data_row():
    dummy_rows = [
        "Record general other when.",
        "Alone court figure role level.",
        "Off return present defense thank.",
        "",
        "Sell difference forget decade food off.",
    ]

    def _row_with_data(dummies=None):
        d = random.randint(0, 5) if dummies is None else dummies
        return [
            "1993-10-02",
            "LB",
            "9116",
            "317363",
            "5501",
            "",
            "",
            "",
            "",
            "SBD",
            "Pharmacist community",
            "-19243.9",
        ] + dummy_rows[:d]

    return _row_with_data


@pytest.fixture
def empty_analysis_workflow():
    """Starting point for all Workflows"""
    return AnalysisWorkflow(analysis=None)


@pytest.fixture
def analysis_workflow_with_analysis(defaults):
    """Starting point for all Workflows with an Analysis"""
    analysis: Analysis = AnalysisFactory()
    intervention = InterventionFactory(
        name="My Test Intervention",
        output_metrics=[
            "NumberOfTeacherDaysOfTraining",
        ],
    )
    analysis.add_intervention(
        intervention,
        parameters={
            "number_of_teachers": 1,
            "number_of_days_of_training": 1,
        },
    )

    return AnalysisWorkflow(analysis=analysis)


@pytest.fixture
def analysis_workflow_with_analysis_conditional_cash_transfer(defaults):
    """Starting point for all Workflows with an Analysis"""
    analysis: Analysis = AnalysisFactory()
    intervention = InterventionFactory(
        name="My Test Intervention",
        output_metrics=[
            "ValueOfCashDistributed",
        ],
    )
    analysis.add_intervention(
        intervention,
        parameters={
            "value_of_cash_distributed": 1000.0,
        },
    )

    return AnalysisWorkflow(analysis=analysis)


@pytest.fixture
def analysis_workflow_with_analysis_multiintervention(defaults):
    """Starting point for all Workflows with an Analysis and Multi-interventions"""
    analysis: Analysis = AnalysisFactory()
    intervention1 = InterventionFactory(
        name="My Test Intervention",
        output_metrics=[
            "NumberOfTeacherDaysOfTraining",
        ],
    )
    intervention2 = InterventionFactory(
        name="My 2nd Test Intervention",
        output_metrics=[
            "NumberOfTeacherYearsOfSupport",
        ],
    )

    analysis.add_intervention(
        intervention1,
        parameters={
            "number_of_days_of_training": 1,
            "number_of_teachers": 1,
        },
    )
    analysis.add_intervention(
        intervention2,
        parameters={
            "number_of_years_of_support": 1,
            "number_of_teachers": 1,
        },
    )

    return AnalysisWorkflow(analysis=analysis)


@pytest.fixture
def analysis_workflow_with_analysis_multiintervention_conditional_cash_transfer(defaults):
    """
    Starting point for all Workflows with an Analysis and Multi-Interventions.
    One of these Interventions is a Conditional Cash Transfer
    """
    analysis: Analysis = AnalysisFactory()
    intervention1 = InterventionFactory(
        name="My Test Intervention",
        output_metrics=[
            "ValueOfCashDistributed",
        ],
    )
    intervention2 = InterventionFactory(
        name="My 2nd Test Intervention",
        output_metrics=[
            "NumberOfTeacherYearsOfSupport",
        ],
    )

    analysis.add_intervention(
        intervention1,
        parameters={
            "value_of_cash_distributed": 1000.0,
        },
    )
    analysis.add_intervention(
        intervention2,
        parameters={
            "number_of_years_of_support": 1,
            "number_of_teachers": 1,
        },
    )

    return AnalysisWorkflow(analysis=analysis)


@pytest.fixture
def analysis_workflow_with_analysis_multiintervention_duplicates(defaults):
    """
    Starting point for all Workflows with an Analysis and Multi-interventions.
    This includes interventions that appear more than once on the Analysis
    """
    analysis: Analysis = AnalysisFactory()
    intervention1 = InterventionFactory(
        name="My Test Intervention",
        output_metrics=[
            "NumberOfTeacherDaysOfTraining",
        ],
    )

    analysis.add_intervention(
        intervention1,
        label="1st one",
        parameters={
            "number_of_days_of_training": 1,
            "number_of_teachers": 1,
        },
    )
    analysis.add_intervention(
        intervention1,
        label="2nd one",
        parameters={
            "number_of_days_of_training": 1,
            "number_of_teachers": 1,
        },
    )

    return AnalysisWorkflow(analysis=analysis)


@pytest.fixture(
    params=[
        "analysis_workflow_with_analysis",
        "analysis_workflow_with_analysis_conditional_cash_transfer",
        "analysis_workflow_with_analysis_multiintervention",
        "analysis_workflow_with_analysis_multiintervention_conditional_cash_transfer",
        "analysis_workflow_with_analysis_multiintervention_duplicates",
    ]
)
def analysis_workflow_with_loaddata_complete(
    request,
):
    analysis_wf = request.getfixturevalue(request.param)
    analysis = analysis_wf.analysis

    analysis.grants = "DF119"
    analysis.save()

    cli1 = CostLineItemFactory(analysis=analysis, grant_code="DF119")
    cli2 = CostLineItemFactory(analysis=analysis, grant_code="DF119")

    analysis.auto_categorize_cost_line_items()

    # By default they will both get the same category.  For some variety we change one.
    cli2.config.category = CategoryFactory()
    cli2.config.save()
    analysis.ensure_cost_type_category_objects()

    return AnalysisWorkflow(analysis)


@pytest.fixture
def analysis_workflow_with_confirmed_categories_cost_line_item(
    analysis_workflow_with_loaddata_complete,
):
    analysis_wf = analysis_workflow_with_loaddata_complete
    analysis = analysis_wf.analysis

    for each in analysis.cost_type_categories.all():
        each.confirmed = True
        each.save()

    return AnalysisWorkflow(analysis)


@pytest.fixture
def analysis_workflow_with_allocations(
    analysis_workflow_with_confirmed_categories_cost_line_item,
):
    analysis_wf = analysis_workflow_with_confirmed_categories_cost_line_item
    analysis = analysis_wf.analysis

    for each in analysis.cost_line_items.all():
        cost_line_item_config = each.config
        for each_intervention_instance in analysis.interventioninstance_set.all():
            CostLineItemInterventionAllocationFactory(
                allocation=Decimal("0.1"),
                cli_config=cost_line_item_config,
                intervention_instance=each_intervention_instance,
            )

    analysis.calculate_output_costs()

    # Included so that Add Other Costs has a substep.
    # TODO: Add Other Costs is optional we need to split here and have one branch that has these and another that doesn't
    analysis.client_time = True
    analysis.save()

    return AnalysisWorkflow(analysis)


@pytest.fixture
def analysis_workflow_with_client_time_added(
    analysis_workflow_with_allocations,
):
    analysis_wf = analysis_workflow_with_allocations
    analysis = analysis_wf.analysis

    for each in analysis.cost_line_items.all():
        cost_line_item_config = each.config
        cost_line_item_config.analysis_cost_type = AnalysisCostType.CLIENT_TIME
        cost_line_item_config.save()

    return AnalysisWorkflow(analysis)


@pytest.fixture
def analysis_workflow_with_subcomponent_labels(
    analysis_workflow_with_allocations,
):
    analysis_wf = analysis_workflow_with_allocations
    analysis = analysis_wf.analysis

    SubcomponentCostAnalysisFactory(
        analysis=analysis,
        subcomponent_labels_confirmed=True,
    )

    return AnalysisWorkflow(analysis)


@pytest.fixture
def analysis_workflow_with_subcomponent_labels_and_client_time_added(
    analysis_workflow_with_client_time_added,
):
    analysis_wf = analysis_workflow_with_client_time_added
    analysis = analysis_wf.analysis

    SubcomponentCostAnalysisFactory(
        analysis=analysis,
        subcomponent_labels_confirmed=True,
    )

    return AnalysisWorkflow(analysis)


@pytest.fixture
def analysis_workflow_with_all_cost_lines_allocated_to_subcomponents(
    analysis_workflow_with_subcomponent_labels_and_client_time_added,
):
    analysis_wf = analysis_workflow_with_subcomponent_labels_and_client_time_added
    analysis = analysis_wf.analysis

    # Remove the client_time piece to avoid the add-client-time-costs step that competes with the
    #   one line item on this analysis
    analysis.client_time = False
    analysis.save()

    each_line_item: CostLineItem

    for cost_line_item in analysis.cost_line_items.all():
        cost_line_item.config.analysis_cost_type = None  # Remove the client time for this test
        cost_line_item.config.subcomponent_analysis_allocations = {
            "0": "20",
            "1": "20",
            "2": "20",
            "3": "20",
            "4": "20",
        }
        cost_line_item.config.save()

    return AnalysisWorkflow(analysis)


@pytest.fixture
def analysis_workflow_with_all_cost_lines_allocated_to_subcomponents_and_some_non_contributing(
    analysis_workflow_with_analysis,
):
    analysis_wf = analysis_workflow_with_analysis
    analysis = analysis_wf.analysis

    analysis.grants = ["DF119", "XXXXX"]
    analysis.client_time = True
    analysis.save()

    contributing_cost_line_item_config = CostLineItemConfigFactory(
        cost_line_item=CostLineItemFactory(
            analysis=analysis,
            grant_code="DF119",
        ),
    )

    contributing_cost_line_item_config = CostLineItemConfigFactory(
        cost_line_item=CostLineItemFactory(
            analysis=analysis,
            grant_code="DF119",
        ),
        cost_type=contributing_cost_line_item_config.cost_type,
        category=contributing_cost_line_item_config.category,
    )

    noncontributing_cost_line_item_config = CostLineItemConfigFactory(
        cost_line_item=CostLineItemFactory(
            analysis=analysis,
            grant_code="DF119",
        ),
        # category=contributing_cost_line_item_config.category,
        cost_type=contributing_cost_line_item_config.cost_type,
    )

    contributing_cost_type_category = AnalysisCostTypeCategoryFactory(
        analysis=analysis,
        category=contributing_cost_line_item_config.category,
        cost_type=contributing_cost_line_item_config.cost_type,
        confirmed=True,
    )

    noncontributing_cost_type_category = AnalysisCostTypeCategoryFactory(
        analysis=analysis,
        category=noncontributing_cost_line_item_config.category,
        cost_type=contributing_cost_line_item_config.cost_type,
        confirmed=True,
    )

    AnalysisCostTypeCategoryGrantFactory(
        cost_type_category=contributing_cost_type_category,
        grant="DF119",
    )

    AnalysisCostTypeCategoryGrantFactory(
        cost_type_category=noncontributing_cost_type_category,
        grant="DF119",
    )

    SubcomponentCostAnalysisFactory(
        analysis=analysis,
        subcomponent_labels_confirmed=True,
    )

    contributing_cost_line_item_config.allocation = Decimal("0.1")
    contributing_cost_line_item_config.analysis_cost_type = AnalysisCostType.CLIENT_TIME
    contributing_cost_line_item_config.subcomponent_analysis_allocations = {
        "0": "20",
        "1": "20",
        "2": "20",
        "3": "20",
        "4": "20",
    }
    contributing_cost_line_item_config.save()

    return AnalysisWorkflow(analysis)


@pytest.fixture
def analysis_workflow_with_some_cost_lines_allocated(
    analysis_workflow_with_analysis,
):
    analysis_wf = analysis_workflow_with_analysis
    analysis = analysis_wf.analysis

    analysis.grants = ["DF119", "XXXXX"]
    analysis.client_time = True
    analysis.save()
    intervention = analysis.interventions.first()

    contributing_cost_line_item_config = CostLineItemConfigFactory(
        cost_line_item=CostLineItemFactory(
            analysis=analysis,
            grant_code="DF119",
        ),
    )
    contributing_cost_line_item_config = CostLineItemConfigFactory(
        cost_line_item=CostLineItemFactory(
            analysis=analysis,
            grant_code="DF119",
        ),
        category=contributing_cost_line_item_config.category,
        cost_type=contributing_cost_line_item_config.cost_type,
    )

    noncontributing_cost_line_item_config = CostLineItemConfigFactory(
        cost_line_item=CostLineItemFactory(
            analysis=analysis,
            grant_code="DF119",
        ),
        category=contributing_cost_line_item_config.category,
        cost_type=contributing_cost_line_item_config.cost_type,
    )

    CostLineItemInterventionAllocationFactory(
        cli_config=noncontributing_cost_line_item_config,
        intervention_instance=analysis.interventioninstance_set.first(),
        allocation=0,
    )

    contributing_cost_type_category = AnalysisCostTypeCategoryFactory(
        analysis=analysis,
        category=contributing_cost_line_item_config.category,
        cost_type=contributing_cost_line_item_config.cost_type,
        confirmed=True,
    )

    noncontributing_cost_type_category = AnalysisCostTypeCategoryFactory(
        analysis=analysis,
        category=contributing_cost_line_item_config.category,
        cost_type=contributing_cost_line_item_config.cost_type,
        confirmed=True,
    )

    AnalysisCostTypeCategoryGrantFactory(
        cost_type_category=contributing_cost_type_category,
        grant="DF119",
    )

    AnalysisCostTypeCategoryGrantFactory(
        cost_type_category=noncontributing_cost_type_category,
        grant="DF119",
    )

    SubcomponentCostAnalysisFactory(
        analysis=analysis,
        subcomponent_labels_confirmed=True,
    )

    contributing_cost_line_item_config.allocation = Decimal("0.1")
    contributing_cost_line_item_config.analysis_cost_type = AnalysisCostType.CLIENT_TIME
    contributing_cost_line_item_config.subcomponent_analysis_allocations = {
        "0": "20",
        "1": "20",
        "2": "20",
        "3": "20",
        "4": "20",
    }
    contributing_cost_line_item_config.save()

    return AnalysisWorkflow(analysis)


@pytest.fixture
def analysis_with_output_metrics(defaults):
    intervention = InterventionFactory(
        name="My Test Intervention",
        output_metrics=[
            "NumberOfTeacherDaysOfTraining",
            "NumberOfTeacherYearsOfSupport",
        ],
    )

    analysis_type = AnalysisType.objects.create(title="My Test AnalysisType")
    country = CountryFactory(name="Jordan", code="JO")
    CountryFactory(name="United States", code="USA")

    category_1 = CategoryFactory(name="My Test Category 1")
    category_2 = CategoryFactory(name="My Test Category 2")

    owner = User.objects.create(name="Rusty Shackleford")
    analysis: Analysis = AnalysisFactory(
        title="My Test Analysis",
        description="My Test Analysis Description",
        owner=owner,
        analysis_type=analysis_type,
        country=country,
        start_date=date(2021, 1, 1),
        end_date=date(2022, 1, 1),
        grants="GRANT123",
        output_count_source="My Output Count Source",
        in_kind_contributions=True,
        client_time=True,
    )
    analysis.add_intervention(
        intervention,
        parameters={
            "number_of_teachers": 1,
            "number_of_days_of_training": 1,
            "number_of_years_of_support": 1,
        },
    )
    # set cost_type and category as confirmed
    cost_type_category_1 = AnalysisCostTypeCategoryFactory(
        analysis=analysis,
        category=category_1,
        confirmed=True,
        cost_type=CostType.objects.get(name=settings.DEFAULT_COST_TYPE),
    )
    cost_type_category_2 = AnalysisCostTypeCategoryFactory(
        analysis=analysis,
        category=category_2,
        confirmed=True,
        cost_type=CostType.objects.get(name="Support Costs"),
    )
    # combine cost_type, category, and grant
    AnalysisCostTypeCategoryGrantFactory(
        cost_type_category=cost_type_category_1,
        grant="GRANT123",
    )
    AnalysisCostTypeCategoryGrantFactory(
        cost_type_category=cost_type_category_2,
        grant="GRANT123",
    )

    line_item_1 = CostLineItemFactory(
        analysis=analysis,
        budget_line_description="My Budget Line Description 1",
        country_code="JO",
        grant_code="GRANT123",
        sector_code="HEAL",
        total_cost=50000.00,
    )
    line_item_2 = CostLineItemFactory(
        analysis=analysis,
        budget_line_description="My Budget Line Description 2",
        country_code="JO",
        grant_code="GRANT123",
        sector_code="HEAL",
        total_cost=36000.00,
    )
    line_item_3 = CostLineItemFactory(
        analysis=analysis,
        budget_line_description="My Special Country Line Item",
        country_code="USA",
        grant_code="GRANT123",
        total_cost=14000.00,
        is_special_lump_sum=True,
    )
    line_item_4 = CostLineItemFactory(
        analysis=analysis,
        budget_line_description="In Kind Line Item",
        total_cost=10000.00,
    )
    line_item_5 = CostLineItemFactory(
        analysis=analysis,
        budget_line_description="Client Line Item",
        total_cost=5000.00,
    )
    # set allocation, category, and cost_type for the line items
    config1 = CostLineItemConfigFactory(
        cost_line_item=line_item_1,
        category=category_1,
    )

    CostLineItemInterventionAllocationFactory(
        cli_config=config1,
        intervention_instance=analysis.interventioninstance_set.first(),
        allocation=50,
    )
    config2 = CostLineItemConfigFactory(
        cost_line_item=line_item_2,
        category=category_2,
        cost_type=CostType.objects.get(name="Support Costs"),
    )
    CostLineItemInterventionAllocationFactory(
        cli_config=config2,
        intervention_instance=analysis.interventioninstance_set.first(),
        allocation=25,
    )
    config3 = CostLineItemConfigFactory(
        cost_line_item=line_item_3,
        cost_type=None,
        category=None,
    )
    CostLineItemInterventionAllocationFactory(
        cli_config=config3,
        intervention_instance=analysis.interventioninstance_set.first(),
        allocation=75,
    )
    config4 = CostLineItemConfigFactory(
        cost_line_item=line_item_4,
        analysis_cost_type=AnalysisCostType.IN_KIND,
    )
    CostLineItemInterventionAllocationFactory(
        cli_config=config4,
        intervention_instance=analysis.interventioninstance_set.first(),
        allocation=75,
    )
    config5 = CostLineItemConfigFactory(
        cost_line_item=line_item_5,
        analysis_cost_type=AnalysisCostType.CLIENT_TIME,
    )
    CostLineItemInterventionAllocationFactory(
        cli_config=config5,
        intervention_instance=analysis.interventioninstance_set.first(),
        allocation=100,
    )
    return analysis


@pytest.fixture
def analysis_with_output_metrics_conditional_cash_transfer(defaults):
    intervention = InterventionFactory(
        name="Conditional Cash Transfer",
        output_metrics=["ValueOfCashDistributed"],
    )

    analysis_type = AnalysisType.objects.create(title="My Test AnalysisType")
    country = CountryFactory(name="Jordan", code="JO")

    category_1 = CategoryFactory(name="My Test Category")

    owner = User.objects.create(name="Rusty Shackleford")
    analysis: Analysis = AnalysisFactory(
        title="My Test Analysis",
        description="My Test Analysis Description",
        owner=owner,
        analysis_type=analysis_type,
        country=country,
        start_date=date(2021, 1, 1),
        end_date=date(2022, 1, 1),
        grants="GRANT123",
        output_count_source="My Output Count Source",
    )
    analysis.add_intervention(intervention, label="First", parameters={"value_of_cash_distributed": 3500})
    analysis.add_intervention(intervention, label="Second", parameters={"value_of_cash_distributed": 5200})
    # set cost_type and category as confirmed
    cost_type_category_1 = AnalysisCostTypeCategoryFactory(
        analysis=analysis,
        category=category_1,
        confirmed=True,
        cost_type=CostType.objects.get(name=settings.DEFAULT_COST_TYPE),
    )

    # combine cost_type, category, and grant
    AnalysisCostTypeCategoryGrantFactory(
        cost_type_category=cost_type_category_1,
        grant="GRANT123",
    )

    line_item_1 = CostLineItemFactory(
        analysis=analysis,
        budget_line_description="My Budget Line Description 1",
        country_code="JO",
        grant_code="GRANT123",
        sector_code="HEAL",
        total_cost=50000.00,
    )

    # set allocation, category, and cost_type for the line items
    config1 = CostLineItemConfigFactory(
        cost_line_item=line_item_1,
        category=category_1,
    )

    CostLineItemInterventionAllocationFactory(
        cli_config=config1,
        intervention_instance=analysis.interventioninstance_set.filter(label="First").first(),
        allocation=50,
    )

    CostLineItemInterventionAllocationFactory(
        cli_config=config1,
        intervention_instance=analysis.interventioninstance_set.filter(label="Second").first(),
        allocation=25,
    )
    return analysis


# Aliases for clarity
analysis_workflow_with_define_complete = analysis_workflow_with_analysis

analysis_workflow_with_allocate_complete = analysis_workflow_with_allocations
analysis_workflow_with_addothercosts_complete = analysis_workflow_with_client_time_added
analysis_workflow_main_flow_complete = analysis_workflow_with_client_time_added
