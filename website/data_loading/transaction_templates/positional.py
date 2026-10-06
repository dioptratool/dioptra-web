from __future__ import annotations

from .base import TransactionTemplate, source_header_key


class PositionalTransactionTemplate(TransactionTemplate):
    """Base for templates whose source files identify columns by position, not header text.

    The synthetic ``column_N`` headers in ``download_headers`` are injected before the normal
    mapping step so that every row is read by position.

    Exports that open with a header row set ``first_row_is_header``: the first row is then
    always dropped and whatever it says is ignored. Otherwise the file is taken to be
    headerless, unless it already carries ``column_N`` headers, which are used as-is.
    """

    first_row_is_header = False

    def rows_with_source_headers(self, rows):
        if not rows:
            return rows
        if self.first_row_is_header:
            return [self.download_headers, *rows[1:]]
        if not self._has_column_headers(rows[0]):
            return [self.download_headers, *rows]
        return rows

    def get_first_data_row_number(self, rows):
        if rows and not self.first_row_is_header and not self._has_column_headers(rows[0]):
            return 1
        return 2

    def _has_column_headers(self, row):
        source_headers = {source_header_key(header) for header in row}
        return bool(source_headers.intersection(self.download_headers))
