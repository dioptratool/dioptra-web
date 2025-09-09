from pathlib import Path

import pytest

from website.data_loading.insight_comparison_data import InsightComparisonDataImporter
from website.models import (
    Country,
    InsightComparisonData,
    Intervention,
)
from website.tests.factories import (
    CountryFactory,
    InterventionFactory,
)

test_data_dir = Path(__file__).resolve().parent / "test_data"


@pytest.fixture
def sample_intervention():
    CountryFactory(code="AF")
    InterventionFactory(
        name="My Test Intervention",
        output_metrics=[
            "NumberOfTeacherDaysOfTraining",
        ],
    )


@pytest.mark.django_db
class TestCostTypeCategoryMappingImport:
    def test_valid(self, defaults, sample_intervention):

        importer = InsightComparisonDataImporter()
        with open(
            test_data_dir
            / "insight_comparison_data_import_files"
            / "insight_comparison_data_import_valid.xlsx",
            "rb",
        ) as f:
            success, result = importer.load_file(f)
        assert success, result["errors"]
        assert not result["errors"]

        assert InsightComparisonData.objects.count() == 1
        obj = InsightComparisonData.objects.get()
        assert obj.name == "Valid One to Test"
        assert obj.country == Country.objects.get(code="AF")
        assert obj.grants_list() == ["1234", "3123"]
        assert obj.intervention == Intervention.objects.get(name="My Test Intervention")
        assert obj.parameters == {"number_of_days_of_training": "100.0", "number_of_teachers": "10.0"}
        assert obj.output_costs == {"NumberOfTeacherDaysOfTraining": {"all": 30.0, "direct_only": 77.01}}

    def test_grant_list_length(self, sample_intervention):
        importer = InsightComparisonDataImporter()
        with open(
            test_data_dir
            / "insight_comparison_data_import_files"
            / "insight_comparison_data_import_too_many_grants.xlsx",
            "rb",
        ) as f:
            success, result = importer.load_file(f)
        assert not success
        assert result["errors"] == ["Row 1 column Grants exceeds the character limit of 255"]

    def test_grant_list_item_length(self, sample_intervention):
        importer = InsightComparisonDataImporter()
        with open(
            test_data_dir
            / "insight_comparison_data_import_files"
            / "insight_comparison_data_import_too_long_grant.xlsx",
            "rb",
        ) as f:
            success, result = importer.load_file(f)
        assert not success
        assert result["errors"] == ["Row 1 column Grants exceeds the character limit of 50"]

    def test_missing_parameter(self, sample_intervention):
        importer = InsightComparisonDataImporter()
        with open(
            test_data_dir
            / "insight_comparison_data_import_files"
            / "insight_comparison_data_import_missing_parameter.xlsx",
            "rb",
        ) as f:
            success, result = importer.load_file(f)
        assert not success
        assert result["errors"] == [
            'The Parameter "Number of Teachers" is required for the intervention on row: 1'
        ]

    def test_missing_parameter_variant(self, sample_intervention):
        CountryFactory(code="KEN")
        InterventionFactory(
            name="Malnutrition Treatment",
            output_metrics=[
                "NumberOfChildrenTreated",
                "NumberOfChildrenRecovered",
            ],
        )
        importer = InsightComparisonDataImporter()

        with open(
            test_data_dir
            / "insight_comparison_data_import_files"
            / "insight_comparison_data_import_missing_parameter-variant.xlsx",
            "rb",
        ) as f:
            success, result = importer.load_file(f)
        assert not success
        assert result["errors"] == [
            'The Parameter "Number of Children Recovered" is required for the intervention on row: 1'
        ]

    def test_blank_2nd_parameter(self, sample_intervention):
        importer = InsightComparisonDataImporter()
        with open(
            test_data_dir
            / "insight_comparison_data_import_files"
            / "insight_comparison_data_import_blank_2nd_parameter.csv",
            "rb",
        ) as f:
            success, result = importer.load_file(f)
        assert not success
        assert result["errors"] == [
            'The Parameter "Number of Teachers" is required for the intervention on row: 1'
        ]

    def test_output_cost_not_in_first_position(self, sample_intervention):
        importer = InsightComparisonDataImporter()
        with open(
            test_data_dir
            / "insight_comparison_data_import_files"
            / "insight_comparison_data_import_valid_moved_output_costs.xlsx",
            "rb",
        ) as f:
            success, result = importer.load_file(f)
        assert success, result["errors"]
        assert not result["errors"]

        assert InsightComparisonData.objects.count() == 1
        obj = InsightComparisonData.objects.get()
        assert obj.name == "Valid One to Test"
        assert obj.country == Country.objects.get(code="AF")
        assert obj.grants_list() == ["1234", "1244"]
        assert obj.intervention == Intervention.objects.get(name="My Test Intervention")
        assert obj.parameters == {"number_of_days_of_training": "100.0", "number_of_teachers": "10.0"}
        assert obj.output_costs == {"NumberOfTeacherDaysOfTraining": {"all": 30.0, "direct_only": 77.01}}

    def test_duplicate_parameter_labels(self, sample_intervention):
        importer = InsightComparisonDataImporter()
        with open(
            test_data_dir
            / "insight_comparison_data_import_files"
            / "insight_comparison_data_import_duplicate_parameters.xlsx",
            "rb",
        ) as f:
            success, result = importer.load_file(f)
        assert not success
        assert result["errors"] == ["Row 1: Duplicate parameter labels found."]

    def test_unexpected_parameter_labels(self, sample_intervention):
        importer = InsightComparisonDataImporter()
        with open(
            test_data_dir
            / "insight_comparison_data_import_files"
            / "insight_comparison_data_import_unexpected_parameters.csv",
            "rb",
        ) as f:
            success, result = importer.load_file(f)
        assert not success
        assert result["errors"] == [
            'Row 1, column Output Metric Parameter Label contains invalid data "Number of Students".'
            "Reason: Incorrect Output Metric Parameter Label for Intervention My Test Intervention.   "
            "Expected: Number of Teachers, Number of Days of Training  Got: Number of Students",
            'The Parameter "Number of Teachers" is required for the intervention on row: 1',
        ]
