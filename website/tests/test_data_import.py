import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from website.data_loading.cost_line_items import load_cost_line_items_from_file
from website.data_loading.transactions import get_transactions_data_store_count, load_transactions
from website.tests.factories import AnalysisFactory, CountryFactory
from website.tests.utils import import_test_transaction_store

test_data_dir = Path(__file__).resolve().parent / "test_data"


@pytest.mark.django_db
class TestBudgetUpload:
    def test_load_data_from_xlsx_file_succeeds(self):
        file_path = test_data_dir / "MC - YDP Budget - Clean Year 1.xlsx"

        with open(file_path, "rb") as f:
            succeeded, result = load_cost_line_items_from_file(AnalysisFactory(), f)
            assert succeeded, result["errors"]

    def test_load_data_from_csv_file_succeeds(self):
        file_path = test_data_dir / "MC - YDP Budget - Clean Year 1.xlsx - Sheet1.csv"

        with open(file_path, "rb") as f:
            succeeded, result = load_cost_line_items_from_file(AnalysisFactory(), f)
            assert succeeded, result["errors"]

    def test_load_data_from_csv_file_with_windows_encoding(self):
        file_path = test_data_dir / "Budget - Shared Costs, ICR Calculators_LL.csv"

        with open(file_path, "rb") as f:
            succeeded, result = load_cost_line_items_from_file(AnalysisFactory(), f)
            assert succeeded, result["errors"]

    def test_load_data_from_csv_file_with_missing_account_code_fails(self):
        file_path = test_data_dir / "MC - YDP Budget - Clean Year 1.xlsx - Sheet1 - MissingAccountCode.csv"

        with open(file_path, "rb") as f:
            succeeded, result = load_cost_line_items_from_file(AnalysisFactory(), f)
            assert not succeeded

    @pytest.mark.parametrize(
        "field,value",
        [
            ("grant_code", "100"),
            ("budget_line_code", "200"),
            ("account_code", "300"),
            ("site_code", "400"),
            ("sector_code", "500"),
            ("budget_line_description", "600"),
        ],
    )
    def test_load_data_from_xlsx_file_numeric_formatting(self, field, value):
        """
        Loading values from excel can be problematic for types.
        Here we are testing that the values come in as strings even if they are numeric on the excel sheet.
        """

        analysis = AnalysisFactory()
        file_path = test_data_dir / "Budget Import with Numeric Values.xlsx"

        with open(file_path, "rb") as f:
            succeeded, result = load_cost_line_items_from_file(analysis, f)
            assert succeeded, result["errors"]
        assert analysis.cost_line_items.count() == 1

        first_item = analysis.cost_line_items.first()

        # Use getattr to fetch the desired field, then compare with the expected value
        assert getattr(first_item, field) == value

    def test_load_data_from_xlsx_file_large_number(self):
        """
        Loading values from excel can be problematic for types.
        This checks to ensure that very large numbers (999999999999998) are read as such and not "1E+15"
        """

        analysis = AnalysisFactory()
        file_path = test_data_dir / "Budget Import with Very Large Number.xlsx"

        with open(file_path, "rb") as f:
            succeeded, result = load_cost_line_items_from_file(analysis, f)
            assert succeeded, result["errors"]
        assert analysis.cost_line_items.count() == 1

        first_item = analysis.cost_line_items.first()
        assert first_item.grant_code == "739465819275036"


@pytest.mark.django_db(databases=["default", "transaction_store"])
class TestTransactionUpload:
    @pytest.fixture
    def _analysis_for_transactions(self):
        return AnalysisFactory(
            start_date=datetime.date(1970, 5, 1),
            end_date=datetime.date(2025, 4, 30),
            grants="9116,GX922,82602992",
        )

    def test_load_data_from_xlsx_file_succeeds(self, _analysis_for_transactions):
        file_path = test_data_dir / "Transactions_default_test_sheet.xlsx"

        with open(file_path, "rb") as f:
            succeeded, result = load_transactions(_analysis_for_transactions, f=f)
            assert succeeded, result["errors"]

    @pytest.mark.parametrize(
        "field,value",
        [
            ("grant_code", "100"),
            ("budget_line_code", "200"),
            ("account_code", "300"),
            ("site_code", "400"),
            ("sector_code", "500"),
            ("budget_line_description", "600"),
        ],
    )
    def test_load_data_from_xlsx_file_numeric_formatting(self, field, value):
        """
        Loading values from excel can be problematic for types.
        Here we are testing that the values come in as strings even if they are numeric on the excel sheet.
        """

        analysis = AnalysisFactory(
            start_date=datetime.date(1970, 5, 1),
            end_date=datetime.date(2025, 4, 30),
            grants="100",
        )

        file_path = test_data_dir / "Transaction Import with Numeric Values.xlsx"

        with open(file_path, "rb") as f:
            succeeded, result = load_transactions(analysis, f=f)
            assert succeeded, result["errors"]
        assert analysis.transactions.count() == 1
        first_item = analysis.transactions.first()

        # Use getattr to fetch the desired field, then compare with the expected value
        assert getattr(first_item, field) == value

    def test_load_data_from_xlsx_file_large_number(self):
        """
        Loading values from excel can be problematic for types.
        This checks to ensure that very large numbers (999999999999998) are read as such and not "1E+15"
        """

        analysis = AnalysisFactory(
            start_date=datetime.date(1970, 5, 1),
            end_date=datetime.date(2025, 4, 30),
            grants="999999999999998",
        )

        file_path = test_data_dir / "Transaction Import with Very Large Number.xlsx"

        with open(file_path, "rb") as f:
            succeeded, result = load_transactions(analysis, f=f)
            assert succeeded, result["errors"]
        assert analysis.transactions.count() == 1
        first_item = analysis.transactions.first()

        assert first_item.amount_in_source_currency == Decimal("9999999998.0000")
        assert first_item.grant_code == "999999999999998"


@pytest.mark.django_db(databases=["default", "transaction_store"])
class TestTransactionsImportFromDatastore:
    def test_get_transactions_data_store_count(self):
        import_test_transaction_store(
            "dioptra__testing-transaction-store__20200331-1656PM_test_transaction_loading.sql"
        )
        count = get_transactions_data_store_count(
            grant_codes="AB234",
            date_start=datetime.date(2001, 1, 10),
            date_end=datetime.date(2020, 6, 30),
        )
        assert isinstance(count, int)
        assert count > 0

    def test_get_transactions_data_store_count_no_results_for_no_match(self):
        import_test_transaction_store(
            "dioptra__testing-transaction-store__20200331-1656PM_test_transaction_loading.sql"
        )
        count = get_transactions_data_store_count(
            ["fakegrantcode"],
            date_start=datetime.date(2001, 1, 10),
            date_end=datetime.date(2020, 6, 30),
        )
        assert count == 0

    def test_load_transactions_from_data_store(self):
        import_test_transaction_store(
            "dioptra__testing-transaction-store__20200331-1656PM_test_transaction_loading.sql"
        )
        transaction_count = get_transactions_data_store_count(
            "AB234",
            date_start=datetime.date(2001, 1, 10),
            date_end=datetime.date(2020, 6, 30),
        )

        analysis = AnalysisFactory(
            grants="AB234",
            country=CountryFactory(name="Gabon", code="5JO"),
            start_date=datetime.date(2001, 1, 10),
            end_date=datetime.date(2020, 6, 30),
        )
        succeeded, import_run = load_transactions(analysis, from_datastore=True)
        assert succeeded
        assert transaction_count > 0
        assert transaction_count == analysis.transactions.all().count()


class TestFilterZeroCostLineItems:
    """
    Given Budget spreadsheet with 0 dollar cost items.csv  file,
    I can create an analysis: 01-Apr-2000 to 01-Apr-2020, Afghanistan, grant = Unknown
    """

    @pytest.mark.django_db
    def test_load_data_from_xlsx_file(self):
        file_path = test_data_dir / "Budget spreadsheet with 0 dollar cost items.csv"

        analysis = AnalysisFactory(
            country=CountryFactory(name="Afghanistan", code="AF"),
            grants="Unknown",
            start_date=datetime.date(2000, 4, 1),
            end_date=datetime.date(2020, 4, 1),
        )

        with open(file_path, "rb") as f:
            succeeded, result = load_cost_line_items_from_file(analysis, f)
            assert succeeded
            assert result["imported_count"] == 183
