from django.conf import settings
from django.utils.translation import gettext_lazy as _


def file_type_not_supported() -> str:
    return _("This file type is not supported. Allowed file types are csv, tsv, xls, xlsx.")


def error_reading_file() -> str:
    return _("There was an error reading data from the file.")


def file_empty() -> str:
    return _("There is no data in this file.")


def invalid_row_column(row: int, column: int | str, value: str, reason: str | None = None) -> str:
    msg = _('Row {row}, column {column} contains invalid data "{value}".').format(
        row=row, column=column, value=value
    )

    if reason:
        msg += _(f"Reason: {reason}")
    return msg


def required_row_column(row: int, column: int) -> str:
    return _("Row {row}, column {column}: This field cannot be null.").format(row=row, column=column)


def invalid_model_field(row: int, column: int, error_message: str) -> str:
    return _("Row {row}, column {column}: {error_message}").format(
        row=row, column=column, error_message=error_message
    )


def invalid_row_generic(row: int, reason: None | str) -> str:
    if reason:
        return _("Row {row}: ").format(row=row) + reason
    return _("Row {row} could not be imported due to errors.").format(row=row)


def error_importing_from_transaction_store() -> str:
    return _("An error was encountered while importing transactions")


def file_too_large() -> str:
    return _(
        "The number of cost line items in the file submitted exceeds Dioptra’s data "
        "limit of {limit:,} rows. Please double check the file and remove any cost line items that are $0. "
        "If this error still persists, please contact the Dioptra administrator."
    ).format(limit=settings.COST_LINE_ITEMS_ROW_LIMIT)


def file_too_large_transactions() -> str:
    return _(
        "The number of transactions in the file submitted exceeds Dioptra’s data "
        "limit of {limit:,} rows. Please double check the file. If this error still "
        "persists, please contact the Dioptra administrator."
    ).format(limit=settings.IMPORTED_TRANSACTION_LIMIT)


def incorrect_headers(missing_headers: list[str]) -> str:
    return _("The uploaded file is missing required headers:  {}").format(missing_headers)


def value_too_long(row: int, column: str, char_limit: int) -> str:
    return _("Row {row} column {column} exceeds the character limit of {char_limit}").format(
        row=row, column=column, char_limit=char_limit
    )


def missing_data(row: int, columns: list[str]) -> str:
    return _(
        "Row {row}: A value must be present in one of these columns for this row to be valid: {columns}"
    ).format(row=row, columns=", ".join(columns))


def inconsistent_account_code_description(account_code: str) -> str:
    return _(
        'The account code description: "{account_code}" is inconsistent across the imported file. '
        "Please check the associated Account code description and Sensitive Data column and try again."
    ).format(
        account_code=account_code,
    )


def missing_parameter(row: int, parameter: str) -> str:
    return _('The Parameter "{parameter}" is required for the intervention on row: {row}').format(
        parameter=parameter, row=row
    )


def missing_countries(countries: list[str]) -> str:
    return _("All countries currently present in the system are required.  Missing '{countries}'").format(
        countries=", ".join(countries),
    )


def duplicate_country_names(countries: list[str]) -> str:
    return _("Duplicate Country Names found: '{countries}'").format(
        countries=", ".join(countries),
    )


def invalid_region(row: int, column: int, region: str) -> str:
    return _('Row {row}, column {column}: "{region}" is an invalid Region.').format(
        row=row, column=column, region=region
    )


ERROR_MESSAGES = {
    "file_type_not_supported": file_type_not_supported,
    "error_reading_file": error_reading_file,
    "file_empty": file_empty,
    "invalid_row_column": invalid_row_column,
    "required_row_column": required_row_column,
    "invalid_model_field": invalid_model_field,
    "invalid_row_generic": invalid_row_generic,
    "error_importing_from_transaction_store": error_importing_from_transaction_store,
    "file_too_large": file_too_large,
    "file_too_large_transactions": file_too_large_transactions,
    "incorrect_headers": incorrect_headers,
    "value_too_long": value_too_long,
    "missing_data": missing_data,
    "inconsistent_account_code_description": inconsistent_account_code_description,
    "missing_parameter": missing_parameter,
    "missing_countries": missing_countries,
    "duplicate_country_names": duplicate_country_names,
    "invalid_region": invalid_region,
}
