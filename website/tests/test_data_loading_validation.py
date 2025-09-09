from datetime import date

import pytest

from website.data_loading import validation
from website.tests.factories import AnalysisFactory

long_string = "a" * 256


class TestValidations:
    def test_valid(self, transaction_data_row):
        row_data = transaction_data_row()

        result = validation.validate_transaction_row(1, row_data)
        assert result.valid()
        assert result.full_message() == ""

    def test_errors_if_not_all_strings(self, transaction_data_row):
        row_data = transaction_data_row()
        with pytest.raises(ValueError, match="Every item in the data"):
            row_data[5] = 123
            validation.validate_transaction_row(1, row_data)

    def test_row_contains_non_utf8(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[1] = "Hamreen Abdullah \ufffd SAL"
        result = validation.validate_transaction_row(1, row_data)
        assert result.full_message().startswith(
            "Row 1: Contains invalid characters. Re-save the file with utf-8 encoding"
        )

    def test_result_formatting(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[1] = ""
        row_data[2] = ""
        result = validation.validate_transaction_row(1, row_data)

        assert result.full_message() == (
            "Row 1: Country code (column B) cannot be empty, Grant code (column C) cannot be empty"
        )

    def test_row_length_too_short(self, transaction_data_row):
        row_data = transaction_data_row(0)
        row_data.pop()
        result = validation.validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: 12 to 17 columns required (got 11)"

    def test_row_length_too_long(self, transaction_data_row):
        row_data = transaction_data_row(5)

        row_data.append("")
        result = validation.validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: 12 to 17 columns required (got 18)"

    def test_date_required(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[0] = ""
        result = validation.validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: Transaction date (column A) cannot be empty"

    def test_date_format(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[0] = "123"
        result = validation.validate_transaction_row(1, row_data)

        assert (
            result.full_message()
            == "Row 1: Transaction date (column A) must be in the format YYYY-MM-DD (got 123)"
        )

    @pytest.mark.django_db
    def test_date_range_invalid(self, transaction_data_row):
        row_data = transaction_data_row()

        analysis = AnalysisFactory(
            start_date=date(1999, 10, 2),
            end_date=date(2001, 10, 2),
            grants="9116",
        )
        result = validation.validate_transaction_row(1, row_data, analysis)

        assert (
            result.full_message()
            == "Row 1: Transaction date (column A) transaction date must be within the analysis range (got 1993-10-02)"
        )

    @pytest.mark.django_db
    def test_date_range_valid(self, transaction_data_row):
        row_data = transaction_data_row()

        analysis = AnalysisFactory(
            start_date=date(1990, 10, 2),
            end_date=date(2001, 10, 2),
            grants="9116",
        )
        result = validation.validate_transaction_row(1, row_data, analysis)

        assert result.valid()

    @pytest.mark.django_db
    def test_grant_codes_invalid(self, transaction_data_row):
        row_data = transaction_data_row()

        analysis = AnalysisFactory(
            start_date=date(1990, 10, 2),
            end_date=date(2001, 10, 2),
            grants="9999,1000",
        )
        result = validation.validate_transaction_row(1, row_data, analysis)

        assert result.full_message() == "Row 1: Grant code (column C) Unexpected grant code (got 9116)"

    @pytest.mark.django_db
    def test_grant_codes_valid(self, transaction_data_row):
        row_data = transaction_data_row()

        analysis = AnalysisFactory(
            start_date=date(1990, 10, 2),
            end_date=date(2001, 10, 2),
            grants="9116",
        )
        result = validation.validate_transaction_row(1, row_data, analysis)

        assert result.valid()

    def test_country_code_required(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[1] = ""
        result = validation.validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: Country code (column B) cannot be empty"

    def test_country_code_length(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[1] = long_string
        result = validation.validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: Country code (column B) is longer than 255 characters"

    def test_grant_code_required(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[2] = ""
        result = validation.validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: Grant code (column C) cannot be empty"

    def test_grant_code_length(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[2] = long_string
        result = validation.validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: Grant code (column C) is longer than 255 characters"

    def test_budget_line_code_optional(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[3] = ""
        result = validation.validate_transaction_row(1, row_data)

        assert result.valid()

    def test_budget_line_code_length(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[3] = long_string
        result = validation.validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: Budget line code (column D) is longer than 255 characters"

    def test_account_code_required(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[4] = ""
        result = validation.validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: Account code (column E) cannot be empty"

    def test_account_code_length(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[4] = long_string
        result = validation.validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: Account code (column E) is longer than 255 characters"

    def test_site_code_length(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[5] = long_string
        result = validation.validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: Site code (column F) is longer than 255 characters"

    def test_sector_code_length(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[6] = long_string
        result = validation.validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: Sector code (column G) is longer than 255 characters"

    def test_transaction_code_length(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[7] = long_string
        result = validation.validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: Transaction code (column H) is longer than 255 characters"

    # transaction description is always valid

    def test_currency_code_enum(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[9] = "US"
        result = validation.validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: Currency code (column J) is an invalid currency code (got US)"

    def test_budget_line_description_length(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[10] = long_string
        result = validation.validate_transaction_row(1, row_data)

        assert (
            result.full_message() == "Row 1: Budget line description (column K) is longer than 255 characters"
        )

    def test_amount_float(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[11] = "e102"
        result = validation.validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: Amount (column L) is not a number (got e102)"

    def test_dummy_1_length(self, transaction_data_row):
        row_data = transaction_data_row(1)

        row_data[12] = long_string
        result = validation.validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: Dummy field 1 (column M) is longer than 255 characters"

    def test_dummy_2_length(self, transaction_data_row):
        row_data = transaction_data_row(2)

        row_data[13] = long_string
        result = validation.validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: Dummy field 2 (column N) is longer than 255 characters"

    def test_dummy_3_length(self, transaction_data_row):
        row_data = transaction_data_row(3)

        row_data[14] = long_string
        result = validation.validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: Dummy field 3 (column O) is longer than 255 characters"

    def test_dummy_4_length(self, transaction_data_row):
        row_data = transaction_data_row(4)

        row_data[15] = long_string
        result = validation.validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: Dummy field 4 (column P) is longer than 255 characters"

    def test_dummy_5_length(self, transaction_data_row):
        row_data = transaction_data_row(5)

        row_data[16] = long_string
        result = validation.validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: Dummy field 5 (column Q) is longer than 255 characters"
