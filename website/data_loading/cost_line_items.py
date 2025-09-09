import logging
from collections.abc import Callable
from typing import TextIO

from django.core.exceptions import ValidationError
from django.db.models import CharField

from website.models import Analysis
from website.models.cost_line_item import CostLineItem
from .types import LoadExcelSheetResult
from .utils import (
    _human_field_name,
    cast_and_handle_numeric_strings,
    cast_to_decimal_four_decimal_places,
    excel_file_to_array,
)
from .validation.error_messages import ERROR_MESSAGES

logger = logging.getLogger(__name__)

COST_LINE_ITEM_IMPORT_HEADERS = [
    {"name": "grant_code", "cast": cast_and_handle_numeric_strings, "required": True},
    {"name": "budget_line_code", "cast": cast_and_handle_numeric_strings},
    {"name": "account_code", "cast": cast_and_handle_numeric_strings, "required": True},
    {"name": "site_code", "cast": cast_and_handle_numeric_strings},
    {"name": "sector_code", "cast": cast_and_handle_numeric_strings},
    {"name": "budget_line_description", "cast": cast_and_handle_numeric_strings, "required": True},
    {"name": "total_cost", "cast": cast_to_decimal_four_decimal_places},
    {"name": "loe_or_unit", "cast": cast_to_decimal_four_decimal_places},
    {"name": "months_or_unit", "cast": cast_to_decimal_four_decimal_places},
    {"name": "unit_cost", "cast": cast_to_decimal_four_decimal_places},
    {"name": "dummy_field_1", "cast": None},
    {"name": "dummy_field_2", "cast": None},
]


def load_cost_line_items_from_file(
    analysis: Analysis,
    f: TextIO,
) -> tuple[bool, LoadExcelSheetResult]:
    """
    Loads cost line items from an Excel or CSV file.

    f should be a readable file object.
    """

    try:
        data = excel_file_to_array(f)
    except Exception as e:
        logger.exception(e)
        result: LoadExcelSheetResult = {
            "errors": [ERROR_MESSAGES["error_reading_file"]()],
            "imported_count": 0,
        }
        return False, result

    if len(data) <= 1:
        result: LoadExcelSheetResult = {
            "errors": [ERROR_MESSAGES["file_empty"]()],
            "imported_count": 0,
        }
        return False, result

    if len(data) > 5000:
        result: LoadExcelSheetResult = {
            "errors": [ERROR_MESSAGES["file_too_large"]()],
            "imported_count": 0,
        }
        return False, result

    # Column headers in first row, skip.
    data = data[1:]

    country_code = analysis.country.code

    imported_count = 0
    errors = []
    for row_num, row_data in enumerate(data):
        cost_line_data, row_errors = _parse_cost_line_item_upload_row_to_dict(row_num, row_data)
        if len(row_errors):
            errors += row_errors
        else:
            cost_line_data.update(
                {
                    "analysis": analysis,
                    "country_code": country_code,
                }
            )

            if cost_line_data.get("total_cost") != 0:
                cost_line_item = CostLineItem(**cost_line_data)
                try:
                    cost_line_item.full_clean()
                    cost_line_item.save()
                    imported_count += 1
                except ValidationError as e:
                    if hasattr(e, "message_dict"):
                        for field_name, messages in e.message_dict.items():
                            for message in messages:
                                errors.append(
                                    ERROR_MESSAGES["invalid_model_field"](
                                        row=row_num,
                                        column=_human_field_name(field_name),
                                        error_message=message,
                                    )
                                )
                    else:
                        errors.append(ERROR_MESSAGES["invalid_row_generic"](row=row_num))
                except Exception:
                    errors.append(ERROR_MESSAGES["invalid_row_generic"](row=row_num))

    if len(errors):
        # Clean up if there were any errors.
        analysis.cost_line_items.all().delete()
        result: LoadExcelSheetResult = {"errors": errors, "imported_count": 0}
        return False, result

    analysis.source = f.name
    analysis.save()

    result = {"imported_count": imported_count, "errors": errors}
    return True, result


def _parse_cost_line_item_upload_row_to_dict(row_num: int, row_data: dict) -> tuple[dict, list[str]]:
    d = {}
    row_errors = []
    header: dict[str, str | Callable | None | bool]
    for i, header in enumerate(COST_LINE_ITEM_IMPORT_HEADERS):
        try:
            value = row_data[i]
        except IndexError:
            continue
        if header.get("required", False) is False and (value is None or value == ""):
            field = CostLineItem._meta.get_field(header.get("name"))
            if isinstance(field, CharField) and field.null is False and field.default == "":
                value = ""
            else:
                value = None

        if header.get("required", False) and (value is None or value == ""):
            row_errors.append(
                ERROR_MESSAGES["required_row_column"](
                    row=row_num + 1,
                    column=_human_field_name(header["name"]),
                )
            )
        if value and header["cast"]:
            try:
                value = header["cast"](value)
            except Exception:
                row_errors.append(
                    ERROR_MESSAGES["invalid_row_column"](
                        row=row_num + 1,
                        column=_human_field_name(header["name"]),
                        value=value,
                    )
                )

        d[header["name"]] = value
    return d, row_errors
