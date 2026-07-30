from openpyxl.utils import get_column_letter

from website.data_loading.transaction_templates.base import (
    CANONICAL_TRANSACTION_FIELDS,
    TransactionTemplate,
    TransactionTemplateError,
    canonical_transaction_row,
)


class Template(TransactionTemplate):
    id = "dioptra_default"
    label = "Dioptra default"
    download_headers = CANONICAL_TRANSACTION_FIELDS
    download_date_fields = ("transaction_date",)
    download_decimal_fields = ("amount",)
    source_date_formats = {
        "transaction_date": ("%Y-%m-%d",),
    }
    canonical_field_sources = {field_name: field_name for field_name in CANONICAL_TRANSACTION_FIELDS}

    def get_first_data_row_number(self, rows):
        if rows and rows[0] == CANONICAL_TRANSACTION_FIELDS:
            return 2
        return 1

    def get_source_header_columns(self, rows):
        return {
            field_name: get_column_letter(column_index)
            for column_index, field_name in enumerate(CANONICAL_TRANSACTION_FIELDS, 1)
        }

    def source_rows_from_upload(self, rows):
        first_data_row_num = 1
        if rows and rows[0] == CANONICAL_TRANSACTION_FIELDS:
            rows = rows[1:]
            first_data_row_num = 2

        source_rows = []
        errors = []
        for row_num, row in enumerate(rows, first_data_row_num):
            if not any(cell for cell in row):
                continue
            source_row = canonical_transaction_row(dict(zip(CANONICAL_TRANSACTION_FIELDS, row)))
            try:
                source_row["transaction_date"] = self.parse_source_date(
                    "transaction_date",
                    source_row["transaction_date"],
                )
            except ValueError as e:
                errors.append(f"Row {row_num}: {e}")
            source_rows.append(source_row)

        if errors:
            raise TransactionTemplateError(errors)
        return source_rows
