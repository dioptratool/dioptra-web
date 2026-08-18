from __future__ import annotations

from website.data_loading.cost_line_items import COST_LINE_ITEM_IMPORT_HEADERS
from website.data_loading.download_template import (
    DECIMAL_FIELD_TYPE,
    DownloadTemplate,
    TEXT_FIELD_TYPE,
)

CUSTOM_FIELD_PREFIX = "dummy_field_"
DECIMAL_BUDGET_FIELDS = frozenset({"total_cost", "loe_or_unit", "months_or_unit", "unit_cost"})
REQUIRED_MARKER = " *"


class BudgetTemplate(DownloadTemplate):
    """The blank budget upload workbook offered on the Load Data step.

    Generated from COST_LINE_ITEM_IMPORT_HEADERS so the columns a user downloads are
    always the columns load_cost_line_items_from_file actually reads. The importer is
    positional and skips row 1, so these headers are labels only -- renaming one cannot
    break an upload.
    """

    download_filename = "budget_upload_template.xlsx"
    download_sheet_title = "Budget"

    def get_download_columns(self) -> list[tuple[str, str]]:
        """(header label, cost line item field name) in upload column order."""
        from website.models.cost_line_item import CostLineItem
        from website.models.utils import load_field_label_override

        columns = []
        for header in COST_LINE_ITEM_IMPORT_HEADERS:
            name = header["name"]
            field = CostLineItem._meta.get_field(name)
            if name.startswith(CUSTOM_FIELD_PREFIX):
                number = name.removeprefix(CUSTOM_FIELD_PREFIX)
                label = load_field_label_override(f"ci_dummy_field_{number}", f"Budget Custom Field {number}")
            else:
                label = str(field.verbose_name)
            # The importer's own "required" flag, plus fields the model refuses to leave empty.
            if header.get("required", False) or not field.blank:
                label += REQUIRED_MARKER
            columns.append((label, name))
        return columns

    def get_download_headers(self) -> list[str]:
        return [label for label, _ in self.get_download_columns()]

    def get_download_field_type(self, header: str) -> str:
        field_name = dict(self.get_download_columns()).get(header)
        if field_name in DECIMAL_BUDGET_FIELDS:
            return DECIMAL_FIELD_TYPE
        return TEXT_FIELD_TYPE


def get_budget_template() -> BudgetTemplate:
    return BudgetTemplate()
