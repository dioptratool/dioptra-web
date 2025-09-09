from pathlib import Path

import pytest

from website.data_loading.cost_type_category_mapping import CostTypeCategoryMappingImporter
from website.models import AccountCodeDescription, CostTypeCategoryMapping
from website.tests.factories import (
    AccountCodeDescriptionFactory,
    CategoryFactory,
    CostTypeCategoryMappingFactory,
    CostTypeFactory,
)

test_data_dir = Path(__file__).resolve().parent / "test_data"


@pytest.mark.django_db
class TestCostTypeCategoryMappingImport:
    def test_valid_headers(self, defaults):

        CostTypeFactory.create(name="Cost Type Blah", type=11)
        CategoryFactory.create(name="Category Blah")
        importer = CostTypeCategoryMappingImporter()
        with open(test_data_dir / "cost_type_category_mapping_valid.xlsx", "rb") as f:
            success, result = importer.load_file(f)
        assert success, result["errors"]
        assert not result["errors"]

    def test_missing_headers(self):
        importer = CostTypeCategoryMappingImporter()

        with open(test_data_dir / "cost_type_category_mapping_invalid_missing_headers.xlsx", "rb") as f:
            success, result = importer.load_file(f)
        assert not success
        assert result["errors"] == [
            "Row 1: A value must be present in one of these columns for this row to be valid: Category, Cost type, Account Code Description"
        ]

    def test_rollback_on_invalid_table(self, defaults):

        CostTypeFactory.create(name="Cost Type Blah", type=11)
        CategoryFactory.create(name="Category Blah")
        first_mapping = CostTypeCategoryMappingFactory(country_code="5JO", category=None)
        second_mapping = CostTypeCategoryMappingFactory(country_code="5JO", cost_type=None)

        assert CostTypeCategoryMapping.objects.count() == 2
        importer = CostTypeCategoryMappingImporter()

        with open(test_data_dir / "cost_type_category_mapping_invalid_bad_data.xlsx", "rb") as f:
            success, result = importer.load_file(f)
        assert not success
        assert len(result["errors"]) == 1

        assert CostTypeCategoryMapping.objects.count() == 2

    def test_account_code_description_is_updated(self, defaults):

        AccountCodeDescriptionFactory.create(account_code="134", account_description="Original Description")
        CostTypeFactory.create(name="Cost Type Blah", type=11)
        CategoryFactory.create(name="Category Blah")
        assert AccountCodeDescription.objects.count() == 1
        importer = CostTypeCategoryMappingImporter()

        with open(test_data_dir / "cost_type_category_mapping_valid.xlsx", "rb") as f:
            success, result = importer.load_file(f)
        assert success, result["errors"]

        assert AccountCodeDescription.objects.count() == 1
        assert AccountCodeDescription.objects.get().account_description == "Blah "

    def test_unknown_account_code_description_is_updated(self, defaults):

        AccountCodeDescriptionFactory.create(account_code="000")
        CostTypeFactory.create(name="Cost Type Blah", type=11)
        CategoryFactory.create(name="Category Blah")
        assert AccountCodeDescription.objects.count() == 1
        importer = CostTypeCategoryMappingImporter()

        with open(test_data_dir / "cost_type_category_mapping_valid.xlsx", "rb") as f:
            success, result = importer.load_file(f)
        assert success, result["errors"]

        assert AccountCodeDescription.objects.count() == 2

    def test_inconsistent_account_code_descriptions(self, defaults):

        AccountCodeDescriptionFactory.create(account_code="000")
        CostTypeFactory.create(name="Cost Type Blah", type=11)
        CategoryFactory.create(name="Category Blah")
        assert AccountCodeDescription.objects.count() == 1
        importer = CostTypeCategoryMappingImporter()

        with open(
            test_data_dir / "cost_type_category_mapping_invalid_account_code_discrepancies.xlsx", "rb"
        ) as f:
            success, result = importer.load_file(f)
        assert not success

        assert result["errors"] == [
            'The account code description: "134" is inconsistent across the imported file. Please check the associated Account code description and Sensitive Data column and try again.',
            'The account code description: "135" is inconsistent across the imported file. Please check the associated Account code description and Sensitive Data column and try again.',
        ]
        assert AccountCodeDescription.objects.count() == 1

    def test_absent_cost_type(self, defaults):
        CostTypeFactory.create(name="Cost Type Blah", type=11)
        CategoryFactory.create(name="Category Blah")
        importer = CostTypeCategoryMappingImporter()

        with open(test_data_dir / "cost_type_category_mapping_no_cost_type.csv", "rb") as f:
            success, result = importer.load_file(f)
        assert success

        assert AccountCodeDescription.objects.count() == 1

    def test_absent_sensitive_data(self, defaults):
        CostTypeFactory.create(name="Cost Type Blah", type=11)
        CategoryFactory.create(name="Category Blah")
        importer = CostTypeCategoryMappingImporter()
        assert AccountCodeDescription.objects.count() == 0

        with open(test_data_dir / "cost_type_category_mapping_missing_sensitive_data.csv", "rb") as f:
            success, result = importer.load_file(f)
        assert success

        assert AccountCodeDescription.objects.count() == 1
        assert not AccountCodeDescription.objects.get().sensitive_data
        assert CostTypeCategoryMapping.objects.count() == 1
