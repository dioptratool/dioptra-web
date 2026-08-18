from __future__ import annotations

from .base import TransactionTemplate, source_header_key


class PositionalTransactionTemplate(TransactionTemplate):
    """Base for templates whose source files identify columns by position, not header text.

    Raw exports of this shape usually arrive with no header row at all, so the synthetic
    ``column_N`` headers in ``download_headers`` are injected before the normal mapping step.
    A file that already carries those headers is used as-is.
    """

    def rows_with_source_headers(self, rows):
        if rows and not self._has_column_headers(rows[0]):
            rows = [self.download_headers, *rows]
        return rows

    def get_first_data_row_number(self, rows):
        if rows and not self._has_column_headers(rows[0]):
            return 1
        return 2

    def _has_column_headers(self, row):
        source_headers = {source_header_key(header) for header in row}
        return bool(source_headers.intersection(self.download_headers))
