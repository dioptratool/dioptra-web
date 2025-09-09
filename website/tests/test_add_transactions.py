import datetime
import mimetypes
from io import BytesIO
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from website.data_loading.transactions import load_transactions
from website.models import Analysis, Settings
from website.tests.factories import AnalysisFactory, CountryFactory, InterventionFactory
from website.tests.utils import import_test_transaction_store

test_data_dir = Path(__file__).resolve().parent / "test_data"


@pytest.mark.django_db(databases=["default", "transaction_store"])
class TestCostLineItemsFromTransactionsDB:
    def test_transaction_loading(self):
        import_test_transaction_store(
            "dioptra__testing-transaction-store__20200331-1656PM_test_transaction_loading.sql"
        )
        intervention = InterventionFactory(
            name="GBV Case Management",
            output_metrics=["NumberOfPeople"],
        )
        country = CountryFactory(name="Jordan", code="7WX")
        analysis: Analysis = AnalysisFactory(
            title="AB234 WPE CM Jordan Ex-Post Analysis (April 2015) – OMBU #39422 test",
            start_date=datetime.date(2015, 5, 1),
            end_date=datetime.date(2016, 4, 30),
            country=country,
            grants="AB234",
        )

        analysis.add_intervention(
            intervention,
            parameters={"number_of_people": 2992},
        )
        dioptra_settings = Settings.objects.first()
        if dioptra_settings:
            dioptra_settings.transaction_country_filter = False
            dioptra_settings.save(update_fields=["transaction_country_filter"])

        success, messages = load_transactions(analysis, from_datastore=True)
        assert success, messages["errors"]
        assert messages["imported_count"] == 4

        analysis.create_cost_line_items_from_transactions()

        assert analysis.cost_line_items.count() == 4
        assert analysis.all_transactions_total_cost == "587.0300"

        for each_cost_line_item in analysis.cost_line_items.all():
            assert (
                each_cost_line_item.transactions.count() == 1
            ), f"{each_cost_line_item.budget_line_description} doesn't have any transactions associated with it"

    def test_transaction_loading_large(self):
        import_test_transaction_store(
            "dioptra__testing-transaction-store__20200331-1656PM_test_transaction_loading_1800.sql"
        )
        intervention = InterventionFactory(
            name="GBV Case Management",
            output_metrics=["NumberOfPeople"],
        )
        country = CountryFactory(name="Jordan", code="JO")
        analysis: Analysis = AnalysisFactory(
            title="DF119 WPE CM Jordan Ex-Post Analysis (April 2015) – OMBU #39422 test",
            start_date=datetime.date(2015, 5, 1),
            end_date=datetime.date(2016, 4, 30),
            country=country,
            grants="DB2021",
        )
        analysis.add_intervention(
            intervention,
            parameters={"number_of_people": 2992},
        )

        dioptra_settings = Settings.objects.first()
        if dioptra_settings:
            dioptra_settings.transaction_country_filter = False
            dioptra_settings.save(update_fields=["transaction_country_filter"])

        success, messages = load_transactions(analysis, from_datastore=True)
        assert success, messages["errors"]
        assert messages["imported_count"] == 1800

        analysis.create_cost_line_items_from_transactions()

        assert analysis.cost_line_items.count() == 1800
        assert analysis.all_transactions_total_cost == "914430.2000"

        for each_cost_line_item in analysis.cost_line_items.all():
            assert (
                each_cost_line_item.transactions.count() == 1
            ), f"{each_cost_line_item.budget_line_description} doesn't have any transactions associated with it"

    def test_transaction_loading_with_country_filter(self):
        import_test_transaction_store(
            "dioptra__testing-transaction-store__20200331-1656PM_test_transaction_loading.sql"
        )
        intervention = InterventionFactory(
            name="GBV Case Management",
            output_metrics=["NumberOfPeople"],
        )
        country = CountryFactory(name="Jordan", code="7WX")
        analysis: Analysis = AnalysisFactory(
            title="AB234 WPE CM Jordan Ex-Post Analysis (April 2015) – OMBU #39422 test",
            start_date=datetime.date(2015, 5, 1),
            end_date=datetime.date(2016, 4, 30),
            country=country,
            grants="AB234",
        )
        analysis.add_intervention(
            intervention,
            parameters={"number_of_people": 2992},
        )
        dioptra_settings = Settings.objects.first()
        if dioptra_settings:
            dioptra_settings.transaction_country_filter = True
            dioptra_settings.save(update_fields=["transaction_country_filter"])
        else:
            Settings.objects.create(transaction_country_filter=True)

        success, messages = load_transactions(analysis, filter_by_country=True, from_datastore=True)
        assert success, messages["errors"]
        assert messages["imported_count"] == 3

        analysis.create_cost_line_items_from_transactions()

        assert analysis.cost_line_items.count() == 3
        assert analysis.all_transactions_total_cost == "587.0300"

        for each_cost_line_item in analysis.cost_line_items.all():
            assert (
                each_cost_line_item.transactions.count() == 1
            ), f"{each_cost_line_item.budget_line_description} doesn't have any transactions associated with it"

        for standard_cost_line_item in analysis.cost_line_items.cost_type_category_items():
            assert not standard_cost_line_item.is_special_lump_sum
            assert standard_cost_line_item.country_code == country.code

    def test_transaction_loading_with_country_filter_with_special(self):
        import_test_transaction_store(
            "dioptra__testing-transaction-store__20200331-1656PM_test_transaction_loading.sql"
        )
        intervention = InterventionFactory(
            name="GBV Case Management",
            output_metrics=["NumberOfPeople"],
        )
        country = CountryFactory(name="Jordan", code="7WX")
        special_country = CountryFactory(name="Special Country", code="2HI", always_include_costs=True)
        analysis: Analysis = AnalysisFactory(
            title="AB234 WPE CM Jordan Ex-Post Analysis (April 2015) – OMBU #39422 test",
            start_date=datetime.date(2015, 5, 1),
            end_date=datetime.date(2016, 4, 30),
            country=country,
            grants="AB234",
        )
        analysis.add_intervention(
            intervention,
            parameters={"number_of_people": 2992},
        )
        dioptra_settings = Settings.objects.first()
        if dioptra_settings:
            dioptra_settings.transaction_country_filter = True
            dioptra_settings.save(update_fields=["transaction_country_filter"])
        else:
            Settings.objects.create(transaction_country_filter=True)

        success, messages = load_transactions(analysis, filter_by_country=True, from_datastore=True)
        assert success, messages["errors"]
        assert messages["imported_count"] == 4

        analysis.create_cost_line_items_from_transactions()
        assert analysis.all_transactions_total_cost == "587.0300"

        assert analysis.cost_line_items.count() == 4
        assert analysis.cost_line_items.cost_type_category_items().count() == 3
        assert len(analysis.special_country_cost_line_items) == 1

        for each_cost_line_item in analysis.cost_line_items.all():
            assert (
                each_cost_line_item.transactions.count() == 1
            ), f"{each_cost_line_item.budget_line_description} doesn't have any transactions associated with it"

        for standard_cost_line_item in analysis.cost_line_items.cost_type_category_items():
            assert not standard_cost_line_item.is_special_lump_sum
            assert standard_cost_line_item.country_code == country.code

        for special_cost_line_item in analysis.special_country_cost_line_items:
            assert special_cost_line_item.is_special_lump_sum
            assert special_cost_line_item.country_code == special_country.code

    def test_transaction_loading_with_country_filter_with_special_and_multiple_grants(
        self,
    ):
        import_test_transaction_store(
            "dioptra__testing-transaction-store__20200331-1656PM_test_transaction_loading.sql"
        )
        intervention = InterventionFactory(
            name="GBV Case Management",
            output_metrics=["NumberOfPeople"],
        )
        country = CountryFactory(name="Jordan", code="7WX")
        special_country = CountryFactory(name="Special Country1", code="2LM", always_include_costs=True)
        analysis: Analysis = AnalysisFactory(
            title="AB234 WPE CM Jordan Ex-Post Analysis (April 2015) – OMBU #39422 test",
            start_date=datetime.date(2015, 5, 1),
            end_date=datetime.date(2016, 4, 30),
            country=country,
            grants="AB234,GH012",
        )
        analysis.add_intervention(
            intervention,
            parameters={"number_of_people": 2992},
        )
        dioptra_settings = Settings.objects.first()
        if dioptra_settings:
            dioptra_settings.transaction_country_filter = True
            dioptra_settings.save(update_fields=["transaction_country_filter"])
        else:
            Settings.objects.create(transaction_country_filter=True)

        success, messages = load_transactions(analysis, filter_by_country=True, from_datastore=True)
        assert success, messages["errors"]
        assert messages["imported_count"] == 6

        analysis.create_cost_line_items_from_transactions()
        assert analysis.all_transactions_total_cost == "587.0300,17681.0000"

        assert analysis.cost_line_items.count() == 4
        assert analysis.cost_line_items.cost_type_category_items().count() == 3
        assert len(analysis.special_country_cost_line_items) == 1

        for standard_cost_line_item in analysis.cost_line_items.cost_type_category_items():
            assert not standard_cost_line_item.is_special_lump_sum
            assert standard_cost_line_item.country_code == country.code

        for special_cost_line_item in analysis.special_country_cost_line_items:
            assert special_cost_line_item.is_special_lump_sum
            assert special_cost_line_item.country_code == special_country.code


@pytest.mark.django_db(databases=["default"])
class TestCostLineItemsFromTransactionsFile:
    @pytest.mark.parametrize(
        "transaction_file_path",
        [
            test_data_dir
            / "dioptra__testing-transaction-store__20200331-1656PM_test_transaction_loading.csv",
            test_data_dir
            / "dioptra__testing-transaction-store__20200331-1656PM_test_transaction_loading.xlsx",
            test_data_dir
            / "dioptra__testing-transaction-store__20200331-1656PM_test_transaction_loading.xls",
        ],
    )
    def test_transaction_loading(self, transaction_file_path):
        with open(transaction_file_path, "rb") as f:
            content = f.read()
        content_type, _ = mimetypes.guess_type(transaction_file_path.name)

        transaction_data = SimpleUploadedFile(
            name=transaction_file_path.name,
            content=content,
            content_type=content_type,
        )

        intervention = InterventionFactory(
            name="GBV Case Management",
            output_metrics=["NumberOfPeople"],
        )
        country = CountryFactory(name="Jordan", code="JO")
        analysis: Analysis = AnalysisFactory(
            title="DF119 WPE CM Jordan Ex-Post Analysis (April 2015) – OMBU #39422 test",
            start_date=datetime.date(2015, 5, 1),
            end_date=datetime.date(2016, 4, 30),
            country=country,
            grants="AB234,GH012",
        )
        analysis.add_intervention(
            intervention,
            parameters={"number_of_people": 2992},
        )
        dioptra_settings = Settings.objects.first()
        if dioptra_settings:
            dioptra_settings.transaction_country_filter = False
            dioptra_settings.save(update_fields=["transaction_country_filter"])

        success, messages = load_transactions(analysis, f=transaction_data)
        assert success, messages["errors"]
        assert messages["imported_count"] == 7

        analysis.create_cost_line_items_from_transactions()

        assert analysis.cost_line_items.count() == 7
        assert analysis.all_transactions_total_cost == "587.0300,17681.0000"

        for each_cost_line_item in analysis.cost_line_items.all():
            assert (
                each_cost_line_item.transactions.count() == 1
            ), f"{each_cost_line_item.budget_line_description} doesn't have any transactions associated with it"

    @pytest.mark.parametrize(
        "transaction_file_path",
        [
            test_data_dir
            / "dioptra__testing-transaction-store__20200331-1656PM_test_transaction_loading_1800.csv",
            test_data_dir
            / "dioptra__testing-transaction-store__20200331-1656PM_test_transaction_loading_1800.xlsx",
            test_data_dir
            / "dioptra__testing-transaction-store__20200331-1656PM_test_transaction_loading_1800.xls",
        ],
    )
    def test_transaction_loading_large(self, transaction_file_path):
        with open(transaction_file_path, "rb") as f:
            content = f.read()
        content_type, _ = mimetypes.guess_type(transaction_file_path.name)

        transaction_data = SimpleUploadedFile(
            name=transaction_file_path.name,
            content=content,
            content_type=content_type,
        )

        intervention = InterventionFactory(
            name="GBV Case Management",
            output_metrics=["NumberOfPeople"],
        )
        country = CountryFactory(name="Jordan", code="JO")
        analysis: Analysis = AnalysisFactory(
            title="DF119 WPE CM Jordan Ex-Post Analysis (April 2015) – OMBU #39422 test",
            start_date=datetime.date(2015, 5, 1),
            end_date=datetime.date(2016, 4, 30),
            country=country,
            grants="DB2021",
        )
        analysis.add_intervention(
            intervention,
            parameters={"number_of_people": 2992},
        )
        dioptra_settings = Settings.objects.first()
        if dioptra_settings:
            dioptra_settings.transaction_country_filter = False
            dioptra_settings.save(update_fields=["transaction_country_filter"])

        success, messages = load_transactions(analysis, f=transaction_data)
        assert success, messages["errors"]
        assert messages["imported_count"] == 1800

        analysis.create_cost_line_items_from_transactions()

        assert analysis.cost_line_items.count() == 1800
        assert analysis.all_transactions_total_cost == "914430.2000"

        for each_cost_line_item in analysis.cost_line_items.all():
            assert (
                each_cost_line_item.transactions.count() == 1
            ), f"{each_cost_line_item.budget_line_description} doesn't have any transactions associated with it"

    def test_transaction_loading_too_large(self):
        sample_line = (
            "2016-01-03,BD,DB2021,BPH1799,500,AMM,OADM,JOD/CD10687,Test transaction description 599,JOD,"
            "Test budget line desc 599,257.4,dummy1,dummy2,dummy3,dummy4,dummy5\n"
        )
        in_memory_file = BytesIO()
        for _ in range(200_001):
            in_memory_file.write(sample_line.encode())
        in_memory_file.seek(0)

        content_type, _ = mimetypes.guess_type("blah.csv")

        transaction_data = SimpleUploadedFile(
            name="blah.csv",
            content=in_memory_file.read(),
            content_type=content_type,
        )

        intervention = InterventionFactory(
            name="GBV Case Management",
            output_metrics=["NumberOfPeople"],
        )
        country = CountryFactory(name="Jordan", code="JO")
        analysis: Analysis = AnalysisFactory(
            title="DF119 WPE CM Jordan Ex-Post Analysis (April 2015) – OMBU #39422 test",
            start_date=datetime.date(2015, 5, 1),
            end_date=datetime.date(2016, 4, 30),
            country=country,
            grants="DB2021",
        )
        analysis.add_intervention(
            intervention,
            parameters={"number_of_people": 2992},
        )
        dioptra_settings = Settings.objects.first()
        if dioptra_settings:
            dioptra_settings.transaction_country_filter = False
            dioptra_settings.save(update_fields=["transaction_country_filter"])

        success, messages = load_transactions(analysis, f=transaction_data)
        assert not success
        assert "The number of transactions in the file submitted exceeds" in messages["errors"][0]

    @pytest.mark.parametrize(
        "transaction_file_path",
        [
            test_data_dir
            / "dioptra__testing-transaction-store__20200331-1656PM_test_transaction_loading.csv",
            test_data_dir
            / "dioptra__testing-transaction-store__20200331-1656PM_test_transaction_loading.xlsx",
            test_data_dir
            / "dioptra__testing-transaction-store__20200331-1656PM_test_transaction_loading.xls",
        ],
    )
    def test_transaction_loading_with_country_filter(self, transaction_file_path):
        with open(transaction_file_path, "rb") as f:
            content = f.read()
        content_type, _ = mimetypes.guess_type(transaction_file_path.name)

        transaction_data = SimpleUploadedFile(
            name=transaction_file_path.name,
            content=content,
            content_type=content_type,
        )
        intervention = InterventionFactory(
            name="GBV Case Management",
            output_metrics=["NumberOfPeople"],
        )
        country = CountryFactory(name="Jordan", code="7WX")
        analysis: Analysis = AnalysisFactory(
            title="DF119 WPE CM Jordan Ex-Post Analysis (April 2015) – OMBU #39422 test",
            start_date=datetime.date(2015, 5, 1),
            end_date=datetime.date(2016, 4, 30),
            country=country,
            grants="AB234,GH012",
        )
        analysis.add_intervention(
            intervention,
            parameters={"number_of_people": 2992},
        )

        dioptra_settings = Settings.objects.first()
        if dioptra_settings:
            dioptra_settings.transaction_country_filter = True
            dioptra_settings.save(update_fields=["transaction_country_filter"])
        else:
            Settings.objects.create(transaction_country_filter=True)

        success, messages = load_transactions(analysis, filter_by_country=True, f=transaction_data)
        assert success, messages["errors"]
        assert messages["imported_count"] == 3

        analysis.create_cost_line_items_from_transactions()

        assert analysis.cost_line_items.count() == 3
        assert analysis.all_transactions_total_cost == "587.0300,17681.0000"

        for each_cost_line_item in analysis.cost_line_items.all():
            assert (
                each_cost_line_item.transactions.count() == 1
            ), f"{each_cost_line_item.budget_line_description} doesn't have any transactions associated with it"

        for standard_cost_line_item in analysis.cost_line_items.cost_type_category_items():
            assert not standard_cost_line_item.is_special_lump_sum
            assert standard_cost_line_item.country_code == country.code

    @pytest.mark.parametrize(
        "transaction_file_path",
        [
            test_data_dir
            / "dioptra__testing-transaction-store__20200331-1656PM_test_transaction_loading.csv",
            test_data_dir
            / "dioptra__testing-transaction-store__20200331-1656PM_test_transaction_loading.xlsx",
            test_data_dir
            / "dioptra__testing-transaction-store__20200331-1656PM_test_transaction_loading.xls",
        ],
    )
    def test_transaction_loading_with_country_filter_with_special(self, transaction_file_path):
        with open(transaction_file_path, "rb") as f:
            content = f.read()
        content_type, _ = mimetypes.guess_type(transaction_file_path.name)

        transaction_data = SimpleUploadedFile(
            name=transaction_file_path.name,
            content=content,
            content_type=content_type,
        )
        intervention = InterventionFactory(
            name="GBV Case Management",
            output_metrics=["NumberOfPeople"],
        )
        country = CountryFactory(name="Jordan", code="7WX")
        special_country = CountryFactory(name="Special Country", code="2HI", always_include_costs=True)
        analysis: Analysis = AnalysisFactory(
            title="DF119 WPE CM Jordan Ex-Post Analysis (April 2015) – OMBU #39422 test",
            start_date=datetime.date(2015, 5, 1),
            end_date=datetime.date(2016, 4, 30),
            country=country,
            grants="AB234,GH012",
        )
        analysis.add_intervention(
            intervention,
            parameters={"number_of_people": 2992},
        )
        dioptra_settings = Settings.objects.first()
        if dioptra_settings:
            dioptra_settings.transaction_country_filter = True
            dioptra_settings.save(update_fields=["transaction_country_filter"])
        else:
            Settings.objects.create(transaction_country_filter=True)

        success, messages = load_transactions(analysis, filter_by_country=True, f=transaction_data)
        assert success, messages["errors"]
        assert messages["imported_count"] == 4

        analysis.create_cost_line_items_from_transactions()
        assert analysis.all_transactions_total_cost == "587.0300,17681.0000"

        assert analysis.cost_line_items.count() == 4
        assert analysis.cost_line_items.cost_type_category_items().count() == 3
        assert len(analysis.special_country_cost_line_items) == 1

        for each_cost_line_item in analysis.cost_line_items.all():
            assert (
                each_cost_line_item.transactions.count() == 1
            ), f"{each_cost_line_item.budget_line_description} doesn't have any transactions associated with it"

        for standard_cost_line_item in analysis.cost_line_items.cost_type_category_items():
            assert not standard_cost_line_item.is_special_lump_sum
            assert standard_cost_line_item.country_code == country.code

        for special_cost_line_item in analysis.special_country_cost_line_items:
            assert special_cost_line_item.is_special_lump_sum
            assert special_cost_line_item.country_code == special_country.code

    @pytest.mark.parametrize(
        "transaction_file_path",
        [
            test_data_dir
            / "dioptra__testing-transaction-store__20200331-1656PM_test_transaction_loading.csv",
            test_data_dir
            / "dioptra__testing-transaction-store__20200331-1656PM_test_transaction_loading.xlsx",
            test_data_dir
            / "dioptra__testing-transaction-store__20200331-1656PM_test_transaction_loading.xls",
        ],
    )
    def test_transaction_loading_with_country_filter_with_special_and_multiple_grants(
        self, transaction_file_path
    ):
        with open(transaction_file_path, "rb") as f:
            content = f.read()
        content_type, _ = mimetypes.guess_type(transaction_file_path.name)

        transaction_data = SimpleUploadedFile(
            name=transaction_file_path.name,
            content=content,
            content_type=content_type,
        )
        intervention = InterventionFactory(
            name="GBV Case Management",
            output_metrics=["NumberOfPeople"],
        )
        country = CountryFactory(name="Jordan", code="7WX")
        special_country = CountryFactory(name="Special Country1", code="2LM", always_include_costs=True)
        analysis: Analysis = AnalysisFactory(
            title="DF119 WPE CM Jordan Ex-Post Analysis (April 2015) – OMBU #39422 test",
            start_date=datetime.date(2015, 5, 1),
            end_date=datetime.date(2016, 4, 30),
            country=country,
            grants="AB234,GH012",
        )
        analysis.add_intervention(
            intervention,
            parameters={"number_of_people": 2992},
        )
        dioptra_settings = Settings.objects.first()
        if dioptra_settings:
            dioptra_settings.transaction_country_filter = True
            dioptra_settings.save(update_fields=["transaction_country_filter"])
        else:
            Settings.objects.create(transaction_country_filter=True)

        success, messages = load_transactions(analysis, filter_by_country=True, f=transaction_data)
        assert success, messages["errors"]
        assert messages["imported_count"] == 6

        analysis.create_cost_line_items_from_transactions()
        assert analysis.all_transactions_total_cost == "587.0300,17681.0000"

        assert analysis.cost_line_items.count() == 4
        assert analysis.cost_line_items.cost_type_category_items().count() == 3
        assert len(analysis.special_country_cost_line_items) == 1

        for standard_cost_line_item in analysis.cost_line_items.cost_type_category_items():
            assert not standard_cost_line_item.is_special_lump_sum
            assert standard_cost_line_item.country_code == country.code

        for special_cost_line_item in analysis.special_country_cost_line_items:
            assert special_cost_line_item.is_special_lump_sum
            assert special_cost_line_item.country_code == special_country.code
