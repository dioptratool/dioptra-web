import datetime
from unittest.mock import MagicMock

import pytest
from django.conf import settings

from website.models.cost_type import CostType
from website.tests.factories import (
    AnalysisCostTypeCategoryFactory,
    AnalysisCostTypeCategoryGrantFactory,
    AnalysisFactory,
    CategoryFactory,
    CostLineItemConfigFactory,
    CostLineItemFactory,
    CostLineItemInterventionAllocationFactory,
    CountryFactory,
    InterventionFactory,
)
from website.views.analysis.steps.allocate import AllocateSupportingCosts


@pytest.mark.django_db
class TestSuggestionCalculatorSingleCategory:
    """
    Test case for someone requesting allocation help and
    valid allocations are assigned for the current category.
    """

    @pytest.fixture(autouse=True)
    def setUp(self, defaults):
        category = CategoryFactory(name="National Staff")
        country = CountryFactory(code="5JOR", name="Jordan")

        analysis = AnalysisFactory.create(
            title="Suggest test 1",
            start_date=datetime.date(2015, 5, 1),
            end_date=datetime.date(2016, 4, 30),
            country=country,
            grants="DF119",
        )

        intervention = InterventionFactory()
        analysis.add_intervention(intervention)

        # set cost_type and category as confirmed
        cost_type_category = AnalysisCostTypeCategoryFactory(
            analysis=analysis,
            category=category,
            confirmed=True,
            cost_type=CostType.objects.get(name=settings.DEFAULT_COST_TYPE),
        )

        # combine cost_type, category, and grant
        self.cost_type_category_grant = AnalysisCostTypeCategoryGrantFactory(
            cost_type_category=cost_type_category,
            grant="DF119",
        )

        # assign cost line items
        line_item_1 = CostLineItemFactory(
            analysis=analysis,
            budget_line_description="Data Clerk 1",
            country_code="5JOR",
            grant_code="DF119",
            sector_code="HEAL",
            total_cost=50000.00,
        )
        line_item_2 = CostLineItemFactory(
            analysis=analysis,
            budget_line_description="District Clinical Mentors",
            country_code="2SLE",
            grant_code="DF119",
            sector_code="HEAL",
            total_cost=60000.00,
        )
        line_item_3 = CostLineItemFactory(
            analysis=analysis,
            budget_line_description="District Delivery Manager",
            country_code="2SLE",
            grant_code="DF119",
            sector_code="HEAL",
            total_cost=40000.00,
        )
        line_item_4 = CostLineItemFactory(
            analysis=analysis,
            budget_line_description="Program Officer",
            country_code="2SLE",
            grant_code="DF119",
            sector_code="HEAL",
            total_cost=55000.00,
        )

        # set allocation, category, and cost_type for the line items
        config1 = CostLineItemConfigFactory(
            cost_line_item=line_item_1,
            category=category,
        )
        CostLineItemInterventionAllocationFactory(
            cli_config=config1,
            intervention_instance=analysis.interventioninstance_set.first(),
            allocation=50,
        )

        config2 = CostLineItemConfigFactory(
            cost_line_item=line_item_2,
            category=category,
        )
        CostLineItemInterventionAllocationFactory(
            cli_config=config2,
            intervention_instance=analysis.interventioninstance_set.first(),
            allocation=50,
        )

        config3 = CostLineItemConfigFactory(
            cost_line_item=line_item_3,
            category=category,
        )
        CostLineItemInterventionAllocationFactory(
            cli_config=config3,
            intervention_instance=analysis.interventioninstance_set.first(),
            allocation=0,
        )

        CostLineItemConfigFactory(
            cost_line_item=line_item_4,
            category=category,
        )

    def test_assigned_items_cost(self):
        """
        Sum of line items that have allocations in this category,
        with total cost multiplied by the allocation percentage.
        """
        identified_cost = self.cost_type_category_grant.assigned_items_cost()
        assert identified_cost == 55000.00

    def test_assigned_items_total(self):
        """
        Sum of line items in this category that have allocations.
        """
        total_cost = self.cost_type_category_grant.assigned_items_total()
        assert total_cost == 150000.00

    def test_suggested_allocation_percentage(self):
        """
        Suggested allocation percentage, which is assigned_items_cost / assigned_items_total.
        """
        suggested_allocation = self.cost_type_category_grant.suggested_allocation()
        assert suggested_allocation == "36.67%"


@pytest.mark.django_db
class TestSuggestionCalculatorSpecialCountries:
    @pytest.fixture(autouse=True)
    def setUp(self, defaults):
        self.view = AllocateSupportingCosts()

        country = CountryFactory(code="5JOR", name="Jordan")
        CountryFactory(name="Special Country", code="SPC", always_include_costs=True)

        analysis = AnalysisFactory.create(
            title="Suggest test 1",
            start_date=datetime.date(2015, 5, 1),
            end_date=datetime.date(2016, 4, 30),
            country=country,
            grants="GRANT123,GRANT456",
            all_transactions_total_cost="200000.00,300000.00",
        )

        intervention = InterventionFactory()
        analysis.add_intervention(intervention)
        self.view.analysis = analysis
        self.view.object = analysis
        self.view.dioptra_settings = MagicMock()
        self.view.workflow = MagicMock()
        self.view.step = MagicMock()
        self.view.parent_step = MagicMock(is_complete=False)

        category_1 = CategoryFactory(name="My Test Category 1")

        cost_type_category_1 = AnalysisCostTypeCategoryFactory(
            analysis=analysis,
            category=category_1,
            confirmed=True,
            cost_type=CostType.objects.get(name=settings.DEFAULT_COST_TYPE),
        )
        AnalysisCostTypeCategoryGrantFactory(
            cost_type_category=cost_type_category_1,
            grant="GRANT123",
        )
        category_2 = CategoryFactory(name="My Test Category 2")

        cost_type_category_2 = AnalysisCostTypeCategoryFactory(
            analysis=analysis,
            category=category_2,
            confirmed=True,
            cost_type=CostType.objects.get(name=settings.DEFAULT_COST_TYPE),
        )
        AnalysisCostTypeCategoryGrantFactory(
            cost_type_category=cost_type_category_2,
            grant="GRANT456",
        )

        category_3 = CategoryFactory(name="My Test Category 3")

        cost_type_category_3 = AnalysisCostTypeCategoryFactory(
            analysis=analysis,
            category=category_3,
            confirmed=True,
            cost_type=CostType.objects.get(name=settings.DEFAULT_COST_TYPE),
        )
        AnalysisCostTypeCategoryGrantFactory(
            cost_type_category=cost_type_category_3,
            grant="GRANT456",
        )

        category_4 = CategoryFactory(name="My Test Category 4")

        cost_type_category_4 = AnalysisCostTypeCategoryFactory(
            analysis=analysis,
            category=category_4,
            confirmed=True,
            cost_type=CostType.objects.get(name="Support Costs"),
        )
        AnalysisCostTypeCategoryGrantFactory(
            cost_type_category=cost_type_category_4,
            grant="GRANT123",
        )

        category_5 = CategoryFactory(name="My Test Category 5")

        cost_type_category_5 = AnalysisCostTypeCategoryFactory(
            analysis=analysis,
            category=category_5,
            confirmed=True,
            cost_type=CostType.objects.get(name="Indirect Costs"),
        )
        AnalysisCostTypeCategoryGrantFactory(
            cost_type_category=cost_type_category_5,
            grant="GRANT123",
        )

        # assign cost line items
        standard_line1 = CostLineItemFactory(
            analysis=analysis,
            budget_line_description="Data Clerk 1",
            country_code="5JOR",
            grant_code="GRANT123",
            sector_code="HEAL",
            total_cost=50000.00,
        )
        config1 = CostLineItemConfigFactory(
            cost_line_item=standard_line1,
            category=category_1,
        )
        CostLineItemInterventionAllocationFactory(
            cli_config=config1,
            intervention_instance=analysis.interventioninstance_set.first(),
            allocation=50,
        )

        self.special_line1 = CostLineItemFactory(
            analysis=analysis,
            budget_line_description="District Clinical Mentors",
            country_code="SPC",
            grant_code="GRANT123",
            sector_code="HEAL",
            total_cost=75000.00,
            is_special_lump_sum=True,
        )
        config2 = CostLineItemConfigFactory(
            cost_line_item=self.special_line1,
        )
        CostLineItemInterventionAllocationFactory(
            cli_config=config2,
            intervention_instance=analysis.interventioninstance_set.first(),
            allocation=75,
        )
        # Create Cost Line items within other Grant to verify they have no effect
        standard_line2 = CostLineItemFactory(
            analysis=analysis,
            budget_line_description="Data Clerk 2",
            country_code="5JOR",
            grant_code="GRANT456",
            sector_code="HEAL",
            total_cost=60000.00,
        )
        config3 = CostLineItemConfigFactory(
            cost_line_item=standard_line2,
            category=category_2,
        )
        CostLineItemInterventionAllocationFactory(
            cli_config=config3,
            intervention_instance=analysis.interventioninstance_set.first(),
            allocation=60,
        )
        self.special_line2 = CostLineItemFactory(
            analysis=analysis,
            budget_line_description="District Clinical Mentors 2",
            country_code="SPC",
            grant_code="GRANT456",
            sector_code="HEAL",
            total_cost=70000.00,
            is_special_lump_sum=True,
        )
        config4 = CostLineItemConfigFactory(cost_line_item=self.special_line2)
        CostLineItemInterventionAllocationFactory(
            cli_config=config4,
            intervention_instance=analysis.interventioninstance_set.first(),
            allocation=85,
        )

        # This cost line item is marked as not contributing, and therefore should have be factored into the total cost,
        # but not the contributing cost
        standard_line3 = CostLineItemFactory(
            analysis=analysis,
            budget_line_description="Data Clerk 3",
            country_code="5JOR",
            grant_code="GRANT456",
            sector_code="HEAL",
            total_cost=12000.00,
        )
        config5 = CostLineItemConfigFactory(
            cost_line_item=standard_line3,
            category=category_3,
        )
        CostLineItemInterventionAllocationFactory(
            cli_config=config5,
            intervention_instance=analysis.interventioninstance_set.first(),
            allocation=0,
        )

        standard_line4 = CostLineItemFactory(
            analysis=analysis,
            budget_line_description="Data Clerk 4",
            country_code="5JOR",
            grant_code="GRANT123",
            sector_code="HEAL",
            total_cost=40000.00,
        )
        config6 = CostLineItemConfigFactory(
            cost_line_item=standard_line4,
            category=category_4,
            cost_type=CostType.objects.get(name="Support Costs"),
        )
        CostLineItemInterventionAllocationFactory(
            cli_config=config6,
            intervention_instance=analysis.interventioninstance_set.first(),
            allocation=75,
        )
        # This cost line corresponds to a Indirect CostType, and therefore should not factor in to either
        # the total or allocated cost values of the Grant Proportion
        standard_line5 = CostLineItemFactory(
            analysis=analysis,
            budget_line_description="Data Clerk 5",
            country_code="5JOR",
            grant_code="GRANT123",
            sector_code="HEAL",
            total_cost=10000.00,
        )
        config7 = CostLineItemConfigFactory(
            cost_line_item=standard_line5,
            category=category_5,
            cost_type=CostType.objects.get(name="Indirect Costs"),
        )
        CostLineItemInterventionAllocationFactory(
            cli_config=config7,
            intervention_instance=analysis.interventioninstance_set.first(),
            allocation=90,
        )

    def test_other_supporting_costs_allocation(self):
        # Call calculator with first Grant
        self.view.grant_code = "GRANT123"
        self.view.special_cost_line_items = [
            c
            for c in self.view.analysis.special_country_cost_line_items
            if c.grant_code == self.view.grant_code
        ]

        context = self.view.get_context_data()
        assert context["show_special_calculator"]
        assert context["grant_proportions"] == "61.11%"
        assert context["country_proportions"] == "80.00%"
        assert round(float(context["suggested_allocation"]), 2) == 48.89
        assert context["other_suggested_allocation"] == "48.89%"

        # Call calculator with second Grant
        self.view.grant_code = "GRANT456"
        self.view.special_cost_line_items = [
            c
            for c in self.view.analysis.special_country_cost_line_items
            if c.grant_code == self.view.grant_code
        ]
        context = self.view.get_context_data()
        assert context["show_special_calculator"]
        assert context["grant_proportions"] == "50.00%"
        assert context["country_proportions"] == "31.30%"
        assert round(float(context["suggested_allocation"]), 2) == 15.65
        assert context["other_suggested_allocation"] == "15.65%"
