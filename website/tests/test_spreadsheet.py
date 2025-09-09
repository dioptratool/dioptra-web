import io
from datetime import date

import pytest
from django.conf import settings
from openpyxl.reader.excel import load_workbook

from website.models import AnalysisCostType, AnalysisType, CostType
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
    UserFactory,
)
from website.views.documents import full_cost_model_spreadsheet


@pytest.fixture
def spreadsheet_analysis(defaults):
    intervention = InterventionFactory(
        name="My Test Intervention",
        output_metrics=[
            "NumberOfTeacherDaysOfTraining",
            "NumberOfTeacherYearsOfSupport",
        ],
    )
    analysis_type = AnalysisType.objects.create(title="My Test AnalysisType")
    country = CountryFactory(name="'Merica", code="USofA")
    owner = UserFactory(name="The True Author")
    analysis = AnalysisFactory(
        title="My Test Analysis",
        description="My Test Analysis Description",
        owner=owner,
        analysis_type=analysis_type,
        country=country,
        start_date=date(2021, 1, 1),
        end_date=date(2022, 1, 1),
        grants="DF119",
        output_count_source="My Output Count Source",
        in_kind_contributions=True,
        client_time=True,
    )
    analysis.add_intervention(
        intervention,
        parameters={
            "number_of_teachers": 40,
            "number_of_days_of_training": 80,
            "number_of_years_of_support": 10,
        },
    )
    category_1 = CategoryFactory(name="My Test Category 1")
    category_2 = CategoryFactory(name="My Test Category 2")

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
        cost_type=CostType.objects.get(name=settings.DEFAULT_COST_TYPE),
    )
    # combine cost_type, category, and grant
    AnalysisCostTypeCategoryGrantFactory(
        cost_type_category=cost_type_category_1,
        grant="DF119",
    )
    AnalysisCostTypeCategoryGrantFactory(
        cost_type_category=cost_type_category_2,
        grant="DF119",
    )

    line_item_1 = CostLineItemFactory(
        analysis=analysis,
        budget_line_description="My Budget Line Description 1",
        country_code="USofA",
        grant_code="DF119",
        sector_code="HEAL",
        total_cost=50000.00,
    )
    line_item_2 = CostLineItemFactory(
        analysis=analysis,
        budget_line_description="My Budget Line Description 2",
        country_code="USofA",
        grant_code="DF119",
        sector_code="HEAL",
        total_cost=25000.00,
    )
    line_item_3 = CostLineItemFactory(
        analysis=analysis,
        budget_line_description="In Kind Line Item",
        total_cost=10000.00,
    )
    line_item_4 = CostLineItemFactory(
        analysis=analysis,
        budget_line_description="Client Time Line Item",
        total_cost=5000.00,
    )
    # set allocation and category for the line items
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
    )
    CostLineItemInterventionAllocationFactory(
        cli_config=config2,
        intervention_instance=analysis.interventioninstance_set.first(),
        allocation=25,
    )

    config3 = CostLineItemConfigFactory(
        cost_line_item=line_item_3,
        analysis_cost_type=AnalysisCostType.IN_KIND,
    )

    CostLineItemInterventionAllocationFactory(
        cli_config=config3,
        intervention_instance=analysis.interventioninstance_set.first(),
        allocation=75,
    )
    config4 = CostLineItemConfigFactory(
        cost_line_item=line_item_4,
        analysis_cost_type=AnalysisCostType.CLIENT_TIME,
    )

    CostLineItemInterventionAllocationFactory(
        cli_config=config4,
        intervention_instance=analysis.interventioninstance_set.first(),
        allocation=75,
    )

    analysis.calculate_output_costs()
    return analysis


class TestAnalysisSpreadsheet:
    @pytest.mark.django_db
    def test_full_cost_model_spreadsheet(self, spreadsheet_analysis, rf):
        rf.user = UserFactory()

        # Run method to produce spreadsheet
        response = full_cost_model_spreadsheet(rf, spreadsheet_analysis.pk)
        assert response.status_code == 200

        virtual_workbook = io.BytesIO()

        for chunk in response.streaming_content:
            virtual_workbook.write(chunk)

        virtual_workbook.seek(0)
        wb = load_workbook(filename=virtual_workbook)

        worksheet = wb.active

        assert worksheet["A9"].value == "Number of Teachers"
        assert worksheet["A10"].value == "Number of Days of Training"
        assert worksheet["A11"].value == "Number of Years of Support"
        assert worksheet["B9"].value == 40
        assert worksheet["B10"].value == 80
        assert worksheet["B11"].value == 10
        assert worksheet["B14"].value == "The True Author"  # Author
        assert (
            worksheet["B15"].value == f"{settings.BASE_URL}/analysis/{spreadsheet_analysis.pk}/insights/"
        )  # Analysis URL
        assert worksheet["B19"].value, "=FIXED(SUM(C30) / (B9 * B10) ==  2)"
        assert worksheet["B20"].value, "=FIXED(C32 / (B9 * B10) ==  2)"
        assert (
            worksheet["B21"].value
            == "=FIXED((IFERROR(C34 / (B9 * B10), 0)) + (IFERROR(SUM(E45) / (B9 * B10), 0)), 2)"
        )
        assert worksheet["B22"].value, "=FIXED(SUM(C30) / (B9 / B11) ==  2)"
        assert worksheet["B23"].value, "=FIXED(C32 / (B9 / B11) ==  2)"
        assert (
            worksheet["B24"].value
            == "=FIXED((IFERROR(C34 / (B9 / B11), 0)) + (IFERROR(SUM(E45) / (B9 / B11), 0)), 2)"
        )
        assert worksheet["B25"].value, "=FIXED(SUM(E42) ==  2)"
