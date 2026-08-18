from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime
from typing import TYPE_CHECKING

from django.core.exceptions import ImproperlyConfigured
from openpyxl.utils import get_column_letter

from website.data_loading.download_template import (
    DATE_FIELD_TYPE,
    DECIMAL_FIELD_TYPE,
    DownloadTemplate,
    INTEGER_FIELD_TYPE,
    TEXT_FIELD_TYPE,
)

if TYPE_CHECKING:
    from website.models import Analysis


CANONICAL_TRANSACTION_FIELDS = [
    "transaction_date",
    "country_code",
    "grant_code",
    "budget_line_code",
    "account_code",
    "site_code",
    "sector_code",
    "transaction_code",
    "transaction_description",
    "currency_code",
    "budget_line_description",
    "amount",
    "dummy_field_1",
    "dummy_field_2",
    "dummy_field_3",
    "dummy_field_4",
    "dummy_field_5",
]

CANONICAL_TRANSACTION_FIELD_LABELS = {
    "transaction_date": "Transaction Date",
    "country_code": "Country Code",
    "grant_code": "Grant Code",
    "budget_line_code": "Budget Line Code",
    "account_code": "Account Code",
    "site_code": "Site Code",
    "sector_code": "Sector Code",
    "transaction_code": "Transaction Code",
    "transaction_description": "Transaction Description",
    "currency_code": "Currency Code",
    "budget_line_description": "Budget Line Description",
    "amount": "Amount",
    "dummy_field_1": "Dummy Field 1",
    "dummy_field_2": "Dummy Field 2",
    "dummy_field_3": "Dummy Field 3",
    "dummy_field_4": "Dummy Field 4",
    "dummy_field_5": "Dummy Field 5",
}

ISO_SOURCE_DATE_FORMAT = "%Y-%m-%d"
GROUPED_AMOUNT_PATTERN = re.compile(r"^[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d*)?$")


class TransactionTemplateError(Exception):
    def __init__(self, errors: Iterable[str]):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


class TransactionTemplate(DownloadTemplate):
    id = ""
    label = ""
    download_sheet_title = "Transactions"
    source_date_formats: dict[str, tuple[str, ...]] = {}
    source_header_aliases: dict[str, tuple[str, ...]] = {}
    canonical_field_sources: dict[str, str | None] = {}
    required_source_fields: dict[str, str] = {}

    def source_rows_from_upload(self, rows: list[list[str]]) -> list[dict[str, str]]:
        rows = self.rows_with_source_headers(rows)
        if not rows:
            return []

        source_headers = self._get_source_headers(rows[0])
        source_header_set = {header for header in source_headers if header}
        missing_fields = [
            display_name
            for field_name, display_name in self.required_source_fields.items()
            if field_name not in source_header_set
        ]
        if missing_fields:
            raise TransactionTemplateError(
                [
                    f"The {self.label} transaction file is missing required headers: "
                    + ", ".join(missing_fields)
                ]
            )

        source_rows = []
        errors = []
        for row_num, row in enumerate(rows[1:], 2):
            if not any(cell for cell in row):
                continue
            source_row = {}
            for column_index, source_header in enumerate(source_headers):
                if not source_header:
                    continue
                value = _source_cell(row, column_index)
                try:
                    value = self.normalize_source_cell(source_header, value)
                except ValueError as e:
                    errors.append(f"Row {row_num}: {e}")
                source_row[source_header] = value
            source_rows.append(source_row)

        if errors:
            raise TransactionTemplateError(errors)
        return source_rows

    def normalize_rows(self, rows: list[dict[str, str]], analysis: Analysis) -> list[dict[str, str]]:
        return rows

    def rows_with_source_headers(self, rows: list[list[str]]) -> list[list[str]]:
        return rows

    def _get_source_headers(self, header_row: list[str]) -> list[str]:
        source_headers = [source_header_key(header) for header in header_row]
        source_header_set = {header for header in source_headers if header}
        alias_replacements = {}
        for source_header, aliases in self.source_header_aliases.items():
            if source_header in source_header_set:
                continue
            for alias in aliases:
                if alias in source_header_set:
                    alias_replacements[alias] = source_header
                    break
        return [alias_replacements.get(header, header) for header in source_headers]

    def normalize_source_cell(self, source_header: str, value: str) -> str:
        if source_header in self.source_date_formats:
            return self.parse_source_date(source_header, value)
        return value

    def parse_source_date(self, source_header: str, value: str) -> str:
        value = value.strip()
        if not value:
            return ""

        date_formats = self.get_source_date_formats(source_header)
        for date_format in date_formats:
            try:
                return datetime.strptime(value, date_format).date().isoformat()
            except ValueError:
                pass

        expected_formats = " or ".join(date_formats)
        display_name = self.get_source_field_display_name(source_header)
        raise ValueError(f"{display_name} must use date format {expected_formats} (got {value})")

    def get_source_date_formats(self, source_header: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.source_date_formats[source_header], ISO_SOURCE_DATE_FORMAT)))

    def get_source_field_display_name(self, source_header: str) -> str:
        if source_header in self.required_source_fields:
            return self.required_source_fields[source_header]
        for header in self.get_download_headers():
            if source_header_key(header) == source_header:
                return header
        raise ImproperlyConfigured(
            f'Transaction data template "{self.id}" references unknown source header "{source_header}".'
        )

    def get_first_data_row_number(self, rows: list[list[str]]) -> int:
        return 2

    def get_source_header_columns(self, rows: list[list[str]]) -> dict[str, str]:
        rows = self.rows_with_source_headers(rows)
        if not rows:
            return {}

        columns = {}
        source_headers = self._get_source_headers(rows[0])
        for column_index, source_header in enumerate(source_headers, 1):
            if source_header and source_header not in columns:
                columns[source_header] = get_column_letter(column_index)
        return columns

    def get_source_header_labels(self, rows: list[list[str]]) -> dict[str, str]:
        rows = self.rows_with_source_headers(rows)
        if not rows:
            return {}

        labels = {}
        source_headers = self._get_source_headers(rows[0])
        for header, source_header in zip(rows[0], source_headers):
            if source_header and source_header not in labels:
                labels[source_header] = str(header).strip()
        return labels

    def get_validation_field_labels(self, rows: list[list[str]]) -> dict[str, str]:
        canonical_fields = set(CANONICAL_TRANSACTION_FIELDS)
        configured_fields = set(self.canonical_field_sources)
        missing_fields = [
            field_name for field_name in CANONICAL_TRANSACTION_FIELDS if field_name not in configured_fields
        ]
        if missing_fields:
            raise ImproperlyConfigured(
                f'Transaction data template "{self.id}" must define canonical_field_sources for: '
                + ", ".join(missing_fields)
            )
        extra_fields = sorted(configured_fields - canonical_fields)
        if extra_fields:
            raise ImproperlyConfigured(
                f'Transaction data template "{self.id}" defines unknown canonical_field_sources: '
                + ", ".join(extra_fields)
            )

        source_header_columns = self.get_source_header_columns(rows)
        source_header_labels = self.get_source_header_labels(rows)
        field_labels = {}
        for canonical_field, canonical_label in CANONICAL_TRANSACTION_FIELD_LABELS.items():
            source_header = self.canonical_field_sources[canonical_field]
            if source_header is None:
                field_labels[canonical_field] = canonical_label
                continue
            source_label = source_header_labels.get(source_header) or self.get_source_field_display_name(
                source_header
            )
            source_column = source_header_columns.get(source_header)
            if source_column:
                field_labels[canonical_field] = f"{source_label} (Column {source_column}) ({canonical_label})"
            else:
                field_labels[canonical_field] = f"{source_label} ({canonical_label})"
        return field_labels

    def get_download_filename(self) -> str:
        if self.download_filename:
            return self.download_filename
        return f"{self.id}_transaction_template.xlsx"


def source_header_key(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^0-9a-zA-Z]+", "_", str(value).strip().lower())).strip("_")


def canonical_transaction_row(data: dict[str, str]) -> dict[str, str]:
    return {
        field_name: (
            normalize_amount(data.get(field_name, ""))
            if field_name == "amount"
            else _canonical_cell(data.get(field_name, ""))
        )
        for field_name in CANONICAL_TRANSACTION_FIELDS
    }


def normalize_amount(value) -> str:
    value = _canonical_cell(value)
    if "," not in value:
        return value
    if GROUPED_AMOUNT_PATTERN.fullmatch(value):
        return value.replace(",", "")
    return value


def _source_cell(row: list[str], column_index: int) -> str:
    try:
        value = row[column_index]
    except IndexError:
        return ""
    return _canonical_cell(value)


def _canonical_cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()
