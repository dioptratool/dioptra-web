from website.models import Analysis
from website.data_loading.transaction_templates.base import CANONICAL_TRANSACTION_FIELDS
from .result import ValidationResult

REPLACEMENT_CHARACTER = "\ufffd"


def validate_transaction_row(
    index: int,
    row: list | dict[str, str],
    analysis: Analysis | None = None,
    *,
    field_labels: dict[str, str],
    currency_required: bool = True,
) -> ValidationResult | None:
    v = ValidationResult(index, analysis)
    if isinstance(row, dict):
        mapped_row = row
        field_values = [
            (field_name, mapped_row.get(field_name, "")) for field_name in CANONICAL_TRANSACTION_FIELDS
        ]
    else:
        if not 12 <= len(row) <= 17:
            v.add_error(f"12 to 17 columns required (got {len(row)})")
            return v
        mapped_row = dict(zip(CANONICAL_TRANSACTION_FIELDS, row))
        field_values = list(zip(CANONICAL_TRANSACTION_FIELDS, row))

    for field_name, cell in field_values:
        if not isinstance(cell, str):
            raise ValueError(
                f"Every item in the data row must be a string, this is a programming error.  {cell} :: {type(cell)}"
            )
        # We use 'errors=replace' for decoding text. See importer code for details.
        if REPLACEMENT_CHARACTER in cell:
            v.add_error(
                f"{field_labels[field_name]} contains the Unicode replacement character "
                f"({REPLACEMENT_CHARACTER}, U+FFFD). This usually means the file was not decoded "
                "with the correct character encoding. Re-save or export the file as UTF-8, "
                "or correct the value in that cell."
            )
            return v

    v.check(
        mapped_row.get("transaction_date", ""),
        field_labels["transaction_date"],
        v.require,
        v.date,
        v.date_range,
    )
    v.check(
        mapped_row.get("country_code", ""),
        field_labels["country_code"],
        v.require,
        v.shortlength,
    )
    v.check(
        mapped_row.get("grant_code", ""),
        field_labels["grant_code"],
        v.require,
        v.shortlength,
        v.grant_codes,
    )
    v.check(
        mapped_row.get("budget_line_code", ""),
        field_labels["budget_line_code"],
        v.shortlength,
    )
    v.check(
        mapped_row.get("account_code", ""),
        field_labels["account_code"],
        v.require,
        v.shortlength,
    )
    v.check(
        mapped_row.get("site_code", ""),
        field_labels["site_code"],
        v.shortlength,
    )
    v.check(
        mapped_row.get("sector_code", ""),
        field_labels["sector_code"],
        v.shortlength,
    )
    v.check(
        mapped_row.get("transaction_code", ""),
        field_labels["transaction_code"],
        v.shortlength,
    )
    # A blank currency is left to the instance currency, so it is only an error when
    # the caller says the row has to carry one.
    currency_value = mapped_row.get("currency_code", "")
    if currency_required or currency_value:
        v.check(
            currency_value,
            field_labels["currency_code"],
            v.require,
            v.currency,
        )
    v.check(
        mapped_row.get("budget_line_description", ""),
        field_labels["budget_line_description"],
        v.require,
        v.shortlength,
    )
    v.check(
        mapped_row.get("amount", ""),
        field_labels["amount"],
        v.require,
        v.float,
    )
    v.check(
        mapped_row.get("dummy_field_1", ""),
        field_labels["dummy_field_1"],
        v.shortlength,
    )
    v.check(
        mapped_row.get("dummy_field_2", ""),
        field_labels["dummy_field_2"],
        v.shortlength,
    )
    v.check(
        mapped_row.get("dummy_field_3", ""),
        field_labels["dummy_field_3"],
        v.shortlength,
    )
    v.check(
        mapped_row.get("dummy_field_4", ""),
        field_labels["dummy_field_4"],
        v.shortlength,
    )
    v.check(
        mapped_row.get("dummy_field_5", ""),
        field_labels["dummy_field_5"],
        v.shortlength,
    )
    return v
