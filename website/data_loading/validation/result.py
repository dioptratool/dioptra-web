from datetime import datetime

from website.models import Analysis
from .constants import _currencies, _date


class ValidationResult:
    def __init__(self, row_index_in_csv: int, analysis: Analysis | None = None):
        self.analysis = analysis
        self.row_index_in_csv = row_index_in_csv
        self._errors = []

    def add_error(self, message: str):
        self._errors.append(message)
        return True

    def check(self, value, prefix, *checkers):
        for checker in checkers:
            if checker(value, prefix):
                return

    def check_optional(self, row, index, prefix, *checkers):
        try:
            value = row[index]
        except IndexError:
            return
        return self.check(value, prefix, *checkers)

    def date(self, value, prefix):
        if not _date.match(value):
            return self.add_error(f"{prefix} must be in the format YYYY-MM-DD (got {value})")

    def date_range(self, value, prefix):
        if self.analysis is not None:
            try:
                transaction_date = datetime.strptime(value, "%Y-%m-%d").date()
                if not (self.analysis.start_date <= transaction_date <= self.analysis.end_date):
                    return self.add_error(
                        f"{prefix} transaction date must be within the analysis range (got {value})"
                    )
            except ValueError:
                return self.add_error(f"{prefix} Unable to check date range (got {value})")

    def grant_codes(self, value, prefix):
        if self.analysis is not None:
            valid_grant_codes = self.analysis.grants.split(",")
            if value not in valid_grant_codes:
                return self.add_error(f"{prefix} Unexpected grant code (got {value})")

    def require(self, value, prefix):
        if not value:
            return self.add_error(prefix + " cannot be empty")

    def shortlength(self, value, prefix):
        if len(value) > 255:
            return self.add_error(prefix + " is longer than 255 characters")

    def currency(self, value, prefix):
        if value not in _currencies:
            return self.add_error(f"{prefix} is an invalid currency code (got {value})")

    def float(self, value, prefix):
        try:
            float(value)
            return
        except ValueError:
            return self.add_error(f"{prefix} is not a number (got {value})")

    def valid(self):
        return len(self._errors) == 0

    def full_message(self):
        if self.valid():
            return ""
        return f'Row {self.row_index_in_csv}: {", ".join(self._errors)}'
