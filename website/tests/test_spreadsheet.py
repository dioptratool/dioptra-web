import io
from datetime import date
from decimal import Decimal

import pytest
from django.conf import settings
from openpyxl import Workbook
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
    SubcomponentCostAllocationFactory,
    SubcomponentCostAnalysisFactory,
    UserFactory,
)
from website.utils.documents import _write_cost_efficiency_table, _write_other_cost_model_table
from website.views.documents import full_cost_model_spreadsheet
from website.utils.documents import (
    _write_cost_of_each_subcomponent_per_output_metric_table,
    _write_metadata_table,
)


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
    def test_subcomponent_metric_metadata_references_program_costs(self, spreadsheet_analysis):
        worksheet = Workbook().active
        intervention_instance = spreadsheet_analysis.interventioninstance_set.first()
        metric_metadata = {}

        _write_cost_efficiency_table(
            worksheet,
            spreadsheet_analysis,
            intervention_instance,
            metrics_all_costs_metadata=metric_metadata,
        )

        for metric in intervention_instance.intervention.output_metric_objects():
            program_cost_row = next(
                row
                for row in range(1, worksheet.max_row + 1)
                if worksheet[f"A{row}"].value == f"{metric.metric_name} Program Costs only"
            )
            assert metric_metadata[metric.metric_name] == f"B{program_cost_row}"

    @pytest.mark.django_db
    def test_other_cost_table_includes_in_kind_subcomponent_allocations(self, spreadsheet_analysis):
        intervention_instance = spreadsheet_analysis.interventioninstance_set.first()
        subcomponent_analysis = SubcomponentCostAnalysisFactory(
            intervention_instance=intervention_instance,
            subcomponent_labels=["Treatment", "Outreach"],
        )
        in_kind_item = spreadsheet_analysis.in_kind_contributions_cost_line_items.get(
            budget_line_description="In Kind Line Item"
        )
        SubcomponentCostAllocationFactory(
            subcomponent_analysis=subcomponent_analysis,
            cli_config=in_kind_item.config,
            allocations={"0": "40", "1": "60"},
        )
        worksheet = Workbook().active
        other_cost_rows = {
            int(AnalysisCostType.IN_KIND): [],
            int(AnalysisCostType.CLIENT_TIME): [],
        }

        last_row = _write_other_cost_model_table(
            worksheet,
            spreadsheet_analysis,
            intervention_instance,
            other_cost_rows,
            starting_row=1,
        )

        assert [worksheet.cell(row=2, column=column).value for column in range(7, 11)] == [
            "Treatment",
            "Treatment Total",
            "Outreach",
            "Outreach Total",
        ]
        in_kind_row = other_cost_rows[int(AnalysisCostType.IN_KIND)][0]
        assert worksheet[f"G{in_kind_row}"].value == Decimal("0.4")
        assert worksheet[f"H{in_kind_row}"].value == f"=E{in_kind_row} * G{in_kind_row}"
        assert worksheet[f"I{in_kind_row}"].value == Decimal("0.6")
        assert worksheet[f"J{in_kind_row}"].value == f"=E{in_kind_row} * I{in_kind_row}"
        client_time_row = other_cost_rows[int(AnalysisCostType.CLIENT_TIME)][0]
        assert all(
            worksheet.cell(row=client_time_row, column=column).value is None for column in range(7, 11)
        )
        assert last_row == 5

    @pytest.mark.django_db
    def test_subcomponent_cost_headers_use_cost_efficiency_unit(self):
        intervention = InterventionFactory(
            output_metrics=[
                "NumberOfPersonYearsOfWaterAccess",
            ],
        )
        analysis = AnalysisFactory()
        intervention_instance = analysis.add_intervention(
            intervention,
            parameters={
                "number_of_people": 100,
                "number_of_years_of_water_access": 2,
            },
        )
        SubcomponentCostAnalysisFactory(
            intervention_instance=intervention_instance,
            subcomponent_labels=["Infrastructure", "Maintenance"],
        )
        wb = Workbook()
        worksheet = wb.active

        _write_cost_of_each_subcomponent_per_output_metric_table(
            ws=worksheet,
            an_analysis=analysis,
            intervention_instance=intervention_instance,
            starting_row=1,
        )

        assert worksheet["A1"].value == "Cost of Each Sub-component, per Person-Year of Water Access"

    @pytest.mark.django_db
    def test_metadata_table_keeps_cash_parameter_numeric(self):
        intervention = InterventionFactory(
            output_metrics=[
                "ValueOfCashDistributed",
            ],
        )
        analysis = AnalysisFactory(
            currency_code="USD",
            output_count_source="My Output Count Source",
        )
        intervention_instance = analysis.add_intervention(
            intervention,
            parameters={
                "value_of_cash_distributed": 10000,
            },
        )
        wb = Workbook()
        worksheet = wb.active

        _write_metadata_table(
            ws=worksheet,
            an_analysis=analysis,
            intervention_instance=intervention_instance,
            parameter_metadata={},
            analysis_url="https://example.com/analysis/1/insights/",
        )

        assert worksheet["A9"].value == "Value of Cash Distributed"
        assert worksheet["B9"].value == 10000
        assert worksheet["B9"].number_format == '"$"#,##0.00'

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
        column_a_values = [cell.value for cell in worksheet["A"]]
        assert "Other Costs" in column_a_values
        assert "Other HQ Costs" not in column_a_values
