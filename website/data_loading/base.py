import logging
from typing import AnyStr, IO


from .types import LoadExcelSheetResult
from .utils import excel_file_to_dict
from .validation.error_messages import ERROR_MESSAGES

logger = logging.getLogger(__name__)


class Importer:
    headers = None

    def __init__(self) -> None:
        self.errors = []
        self.imported_count = 0
        self.data = None

    def result(self) -> LoadExcelSheetResult:
        return {
            "errors": self.errors,
            "imported_count": self.imported_count,
        }

    def required_file_header_names(self) -> list[str]:
        return [h["name"] for h in self.headers if h.get("required", False)]

    def _parse_row_to_dict(self, row_num: int, row_data: dict) -> dict[str, str]:
        raise NotImplementedError

    def _base_file_validation(self) -> None:
        self._validate_file_is_not_empty()
        self._validate_file_is_not_too_large()
        if not self.errors:
            self._validate_required_headers_are_present()

    def _validate_file_is_not_empty(self) -> None:
        if len(self.data) < 1:
            self.errors.append(ERROR_MESSAGES["file_empty"]())

    def _validate_file_is_not_too_large(self) -> None:
        if len(self.data) > 5000:
            self.errors.append(ERROR_MESSAGES["file_too_large"]())

    def _validate_required_headers_are_present(self) -> None:
        if len(self.data[0]) != len(self.headers):
            missing_headers = sorted(set(self.required_file_header_names()) - set(self.data[0]))
            missing_header_names = []
            for missing_header in missing_headers:
                for header_info in self.headers:
                    if missing_header == header_info["name"]:
                        missing_header_names.append(header_info["display_name"])
            if missing_header_names:
                self.errors.append(ERROR_MESSAGES["incorrect_headers"](missing_header_names))

    def _load_file(self, f: IO[AnyStr]) -> bool:
        try:
            self.data = excel_file_to_dict(f)
        except Exception as e:
            logger.debug(e)
            self.errors.append(ERROR_MESSAGES["error_reading_file"]())
            return False

        self._base_file_validation()
        if self.errors:
            return False
        else:
            return True

    def load_file(self, f: IO[AnyStr]) -> tuple[bool, LoadExcelSheetResult]:
        success = self._load_file(f)
        return success, self.result()
