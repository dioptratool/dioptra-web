from pathlib import Path

import pytest

from website.data_loading.countries import CountriesImporter
from website.models import Country
from website.tests.factories import (
    CountryFactory,
    RegionFactory,
)

test_data_dir = Path(__file__).resolve().parent / "test_data" / "country_import_files"


@pytest.mark.django_db
class TestCountryImport:
    def test_valid_headers(self, defaults):
        RegionFactory.create(name="Foo")
        importer = CountriesImporter()
        with open(test_data_dir / "country_import_valid.csv", "rb") as f:
            success, result = importer.load_file(f)
        assert success, result["errors"]
        assert not result["errors"]
        assert Country.objects.count() == 1
        c = Country.objects.get()
        assert c.name == "CountryA"
        assert c.code == "CA"
        assert c.region.name == "Foo"

    def test_missing_headers_code(self):

        RegionFactory.create(name="Foo")
        importer = CountriesImporter()
        with open(test_data_dir / "country_import_no_code_header.csv", "rb") as f:
            success, result = importer.load_file(f)
        assert not success
        assert result["errors"] == ["The uploaded file is missing required headers:  ['Code']"]

    def test_missing_headers_region(self):
        RegionFactory.create(name="Foo")
        importer = CountriesImporter()
        with open(test_data_dir / "country_import_no_region_header.csv", "rb") as f:
            success, result = importer.load_file(f)
        assert success, result["errors"]
        assert not result["errors"]
        assert Country.objects.count() == 1

    def test_rollback_on_invalid_table(self, defaults):
        """
        Here we have a Country existent in the system that should be in the import
        file but it isn't.    Everything should rollback in that case.
        """
        RegionFactory.create(name="Foo")
        CountryFactory(name="CountryX", code="CX")
        importer = CountriesImporter()
        with open(test_data_dir / "country_import_valid.csv", "rb") as f:
            success, result = importer.load_file(f)
        assert not success
        assert result["errors"] == [
            "All countries currently present in the system are required.  Missing 'CountryX'"
        ]

    def test_update_country(self, defaults):
        RegionFactory.create(name="Foo")
        CountryFactory(name="CountryA", code="BAD")
        importer = CountriesImporter()
        with open(test_data_dir / "country_import_valid.csv", "rb") as f:
            success, result = importer.load_file(f)
        assert success, result["errors"]
        assert not result["errors"]
        assert Country.objects.count() == 1
        c = Country.objects.get()
        assert c.name == "CountryA"
        assert c.code == "CA"
        assert c.region.name == "Foo"

    def test_update_country_region(self, defaults):
        RegionFactory.create(name="Foo")
        CountryFactory(name="CountryA", code="CA", region=RegionFactory(name="Bar"))
        importer = CountriesImporter()
        with open(test_data_dir / "country_import_valid.csv", "rb") as f:
            success, result = importer.load_file(f)
        assert success, result["errors"]
        assert not result["errors"]
        assert Country.objects.count() == 1
        c = Country.objects.get()
        assert c.name == "CountryA"
        assert c.code == "CA"
        assert c.region.name == "Foo"

    def test_duplicate_entries(self, defaults):
        RegionFactory.create(name="Foo")
        importer = CountriesImporter()
        with open(test_data_dir / "country_import_duplicates.csv", "rb") as f:
            success, result = importer.load_file(f)
        assert not success
        assert result["errors"] == ["Duplicate Country Names found: 'CountryA'"]
        assert Country.objects.count() == 0

    def test_invalid_region(self, defaults):
        RegionFactory.create(name="Bar")
        importer = CountriesImporter()
        with open(test_data_dir / "country_import_invalid_region.csv", "rb") as f:
            success, result = importer.load_file(f)
        assert not success
        assert result["errors"] == ['Row 1, column Region: "Fooafslkj" is an invalid Region.']
        assert Country.objects.count() == 0
