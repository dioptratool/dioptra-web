from website.models import Analysis
from .result import ValidationResult


def validate_transaction_row(
    index: int, row: list, analysis: Analysis | None = None
) -> ValidationResult | None:
    v = ValidationResult(index, analysis)
    if not 12 <= len(row) <= 17:
        v.add_error(f"12 to 17 columns required (got {len(row)})")
        return v
    for cell in row:
        if not isinstance(cell, str):
            raise ValueError(
                f"Every item in the data row must be a string, this is a programming error.  {cell} :: {type(cell)}"
            )
        # We use 'errors=replace' for decoding text. See importer code for details.
        if "\ufffd" in cell:
            v.add_error(
                "Contains invalid characters. Re-save the file with utf-8 encoding, "
                "or remove the funny-looking characters"
            )
            return v

    v.check(row[0], "Transaction date (column A)", v.require, v.date, v.date_range)
    v.check(row[1], "Country code (column B)", v.require, v.shortlength)
    v.check(row[2], "Grant code (column C)", v.require, v.shortlength, v.grant_codes)
    v.check(row[3], "Budget line code (column D)", v.shortlength)
    v.check(row[4], "Account code (column E)", v.require, v.shortlength)
    v.check(row[5], "Site code (column F)", v.shortlength)
    v.check(row[6], "Sector code (column G)", v.shortlength)
    v.check(row[7], "Transaction code (column H)", v.shortlength)
    # v.check(row[8], 'Transaction description (column I)', v.shortlength)
    v.check(row[9], "Currency code (column J)", v.require, v.currency)
    v.check(row[10], "Budget line description (column K)", v.require, v.shortlength)
    v.check(row[11], "Amount (column L)", v.require, v.float)
    v.check_optional(row, 12, "Dummy field 1 (column M)", v.shortlength)
    v.check_optional(row, 13, "Dummy field 2 (column N)", v.shortlength)
    v.check_optional(row, 14, "Dummy field 3 (column O)", v.shortlength)
    v.check_optional(row, 15, "Dummy field 4 (column P)", v.shortlength)
    v.check_optional(row, 16, "Dummy field 5 (column Q)", v.shortlength)
    return v
