from datetime import date

import pytest

from website.data_loading import validation
from website.data_loading.transaction_templates.dioptra_default import Template as DioptraDefaultTemplate
from website.tests.factories import AnalysisFactory

long_string = "a" * 256
default_field_labels = DioptraDefaultTemplate().get_validation_field_labels([])


def _validate_transaction_row(index, row, analysis=None, currency_required=True):
    return validation.validate_transaction_row(
        index,
        row,
        analysis,
        field_labels=default_field_labels,
        currency_required=currency_required,
    )


class TestValidations:
    def test_valid(self, transaction_data_row):
        row_data = transaction_data_row()

        result = _validate_transaction_row(1, row_data)
        assert result.valid()
        assert result.full_message() == ""

    def test_errors_if_not_all_strings(self, transaction_data_row):
        row_data = transaction_data_row()
        with pytest.raises(ValueError, match="Every item in the data"):
            row_data[5] = 123
            _validate_transaction_row(1, row_data)

    def test_row_contains_non_utf8(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[1] = "Hamreen Abdullah \ufffd SAL"
        result = _validate_transaction_row(1, row_data)
        assert result.full_message() == (
            "Row 1: country_code (Column B) (Country Code) contains the Unicode replacement "
            "character (\ufffd, U+FFFD). This usually means the file was not decoded with the correct "
            "character encoding. Re-save or export the file as UTF-8, or correct the value in that cell."
        )

    def test_result_formatting(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[1] = ""
        row_data[2] = ""
        result = _validate_transaction_row(1, row_data)

        assert result.full_message() == (
            "Row 1: country_code (Column B) (Country Code) cannot be empty, grant_code (Column C) (Grant Code) cannot be empty"
        )

    def test_row_length_too_short(self, transaction_data_row):
        row_data = transaction_data_row(0)
        row_data.pop()
        result = _validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: 12 to 17 columns required (got 11)"

    def test_row_length_too_long(self, transaction_data_row):
        row_data = transaction_data_row(5)

        row_data.append("")
        result = _validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: 12 to 17 columns required (got 18)"

    def test_date_required(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[0] = ""
        result = _validate_transaction_row(1, row_data)

        assert (
            result.full_message() == "Row 1: transaction_date (Column A) (Transaction Date) cannot be empty"
        )

    def test_date_format(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[0] = "123"
        result = _validate_transaction_row(1, row_data)

        assert (
            result.full_message()
            == "Row 1: transaction_date (Column A) (Transaction Date) must be in the format YYYY-MM-DD (got 123)"
        )

    @pytest.mark.django_db
    def test_date_range_invalid(self, transaction_data_row):
        row_data = transaction_data_row()

        analysis = AnalysisFactory(
            start_date=date(1999, 10, 2),
            end_date=date(2001, 10, 2),
            grants="9116",
        )
        result = _validate_transaction_row(1, row_data, analysis)

        assert (
            result.full_message()
            == "Row 1: transaction_date (Column A) (Transaction Date) transaction date must be within the analysis range (got 1993-10-02)"
        )

    @pytest.mark.django_db
    def test_date_range_valid(self, transaction_data_row):
        row_data = transaction_data_row()

        analysis = AnalysisFactory(
            start_date=date(1990, 10, 2),
            end_date=date(2001, 10, 2),
            grants="9116",
        )
        result = _validate_transaction_row(1, row_data, analysis)

        assert result.valid()

    @pytest.mark.django_db
    def test_grant_codes_invalid(self, transaction_data_row):
        row_data = transaction_data_row()

        analysis = AnalysisFactory(
            start_date=date(1990, 10, 2),
            end_date=date(2001, 10, 2),
            grants="9999,1000",
        )
        result = _validate_transaction_row(1, row_data, analysis)

        assert (
            result.full_message()
            == "Row 1: grant_code (Column C) (Grant Code) Unexpected grant code (got 9116)"
        )

    @pytest.mark.django_db
    def test_grant_codes_valid(self, transaction_data_row):
        row_data = transaction_data_row()

        analysis = AnalysisFactory(
            start_date=date(1990, 10, 2),
            end_date=date(2001, 10, 2),
            grants="9116",
        )
        result = _validate_transaction_row(1, row_data, analysis)

        assert result.valid()

    def test_country_code_required(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[1] = ""
        result = _validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: country_code (Column B) (Country Code) cannot be empty"

    def test_country_code_length(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[1] = long_string
        result = _validate_transaction_row(1, row_data)

        assert (
            result.full_message()
            == "Row 1: country_code (Column B) (Country Code) is longer than 255 characters"
        )

    def test_grant_code_required(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[2] = ""
        result = _validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: grant_code (Column C) (Grant Code) cannot be empty"

    def test_grant_code_length(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[2] = long_string
        result = _validate_transaction_row(1, row_data)

        assert (
            result.full_message() == "Row 1: grant_code (Column C) (Grant Code) is longer than 255 characters"
        )

    def test_budget_line_code_optional(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[3] = ""
        result = _validate_transaction_row(1, row_data)

        assert result.valid()

    def test_budget_line_code_length(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[3] = long_string
        result = _validate_transaction_row(1, row_data)

        assert (
            result.full_message()
            == "Row 1: budget_line_code (Column D) (Budget Line Code) is longer than 255 characters"
        )

    def test_account_code_required(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[4] = ""
        result = _validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: account_code (Column E) (Account Code) cannot be empty"

    def test_account_code_length(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[4] = long_string
        result = _validate_transaction_row(1, row_data)

        assert (
            result.full_message()
            == "Row 1: account_code (Column E) (Account Code) is longer than 255 characters"
        )

    def test_site_code_length(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[5] = long_string
        result = _validate_transaction_row(1, row_data)

        assert (
            result.full_message() == "Row 1: site_code (Column F) (Site Code) is longer than 255 characters"
        )

    def test_sector_code_length(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[6] = long_string
        result = _validate_transaction_row(1, row_data)

        assert (
            result.full_message()
            == "Row 1: sector_code (Column G) (Sector Code) is longer than 255 characters"
        )

    def test_transaction_code_length(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[7] = long_string
        result = _validate_transaction_row(1, row_data)

        assert (
            result.full_message()
            == "Row 1: transaction_code (Column H) (Transaction Code) is longer than 255 characters"
        )

    # transaction description is always valid

    def test_currency_code_required(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[9] = ""
        result = _validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: currency_code (Column J) (Currency Code) cannot be empty"

    def test_currency_code_can_be_blank_when_something_else_supplies_it(self, transaction_data_row):
        """An instance with a currency of its own fills in the rows that have none."""
        row_data = transaction_data_row()

        row_data[9] = ""
        result = _validate_transaction_row(1, row_data, currency_required=False)

        assert result.valid()

    def test_currency_code_is_still_checked_when_it_is_not_required(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[9] = "US"
        result = _validate_transaction_row(1, row_data, currency_required=False)

        assert (
            result.full_message()
            == "Row 1: currency_code (Column J) (Currency Code) is an invalid currency code (got US)"
        )

    def test_currency_code_enum(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[9] = "US"
        result = _validate_transaction_row(1, row_data)

        assert (
            result.full_message()
            == "Row 1: currency_code (Column J) (Currency Code) is an invalid currency code (got US)"
        )

    def test_budget_line_description_length(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[10] = long_string
        result = _validate_transaction_row(1, row_data)

        assert (
            result.full_message()
            == "Row 1: budget_line_description (Column K) (Budget Line Description) is longer than 255 characters"
        )

    def test_amount_float(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[11] = "e102"
        result = _validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: amount (Column L) (Amount) is not a number (got e102)"

    def test_amount_accepts_standard_thousands_separators(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[11] = "1,000.00"
        result = _validate_transaction_row(1, row_data)

        assert result.valid()

    def test_amount_rejects_malformed_thousands_separators(self, transaction_data_row):
        row_data = transaction_data_row()

        row_data[11] = "10,00.00"
        result = _validate_transaction_row(1, row_data)

        assert result.full_message() == "Row 1: amount (Column L) (Amount) is not a number (got 10,00.00)"

    def test_dummy_1_length(self, transaction_data_row):
        row_data = transaction_data_row(1)

        row_data[12] = long_string
        result = _validate_transaction_row(1, row_data)

        assert (
            result.full_message()
            == "Row 1: dummy_field_1 (Column M) (Dummy Field 1) is longer than 255 characters"
        )

    def test_dummy_2_length(self, transaction_data_row):
        row_data = transaction_data_row(2)

        row_data[13] = long_string
        result = _validate_transaction_row(1, row_data)

        assert (
            result.full_message()
            == "Row 1: dummy_field_2 (Column N) (Dummy Field 2) is longer than 255 characters"
        )

    def test_dummy_3_length(self, transaction_data_row):
        row_data = transaction_data_row(3)

        row_data[14] = long_string
        result = _validate_transaction_row(1, row_data)

        assert (
            result.full_message()
            == "Row 1: dummy_field_3 (Column O) (Dummy Field 3) is longer than 255 characters"
        )

    def test_dummy_4_length(self, transaction_data_row):
        row_data = transaction_data_row(4)

        row_data[15] = long_string
        result = _validate_transaction_row(1, row_data)

        assert (
            result.full_message()
            == "Row 1: dummy_field_4 (Column P) (Dummy Field 4) is longer than 255 characters"
        )

    def test_dummy_5_length(self, transaction_data_row):
        row_data = transaction_data_row(5)

        row_data[16] = long_string
        result = _validate_transaction_row(1, row_data)

        assert (
            result.full_message()
            == "Row 1: dummy_field_5 (Column Q) (Dummy Field 5) is longer than 255 characters"
        )
