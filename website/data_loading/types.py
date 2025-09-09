from typing import TypedDict


class LoadExcelSheetResult(TypedDict):
    errors: list[str]
    imported_count: int
