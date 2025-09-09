import logging
from collections.abc import Callable
from typing import AnyStr, IO

from django.db import transaction

from .base import Importer
from .types import LoadExcelSheetResult
from .utils import cast_and_handle_numeric_strings, cast_boolean_type
from .validation.error_messages import ERROR_MESSAGES
from ..models import AccountCodeDescription, Category, CostType, CostTypeCategoryMapping

logger = logging.getLogger(__name__)


class CostTypeCategoryMappingImporter(Importer):
    headers = [
        {
            "db_name": "CostTypeCategoryMapping.country_code",
            "display_name": "Country code",
            "name": "country_code",
        },
        {
            "db_name": "CostTypeCategoryMapping.grant_code",
            "display_name": "Grant code",
            "name": "grant_code",
            "cast": cast_and_handle_numeric_strings,
        },
        {
            "db_name": "CostTypeCategoryMapping.budget_line_code",
            "display_name": "Budget line code",
            "name": "budget_line_code",
            "cast": cast_and_handle_numeric_strings,
        },
        {
            "db_name": "AccountCodeDescription.account_code",
            "display_name": "Account Code",
            "name": "account_code",
            "cast": cast_and_handle_numeric_strings,
        },
        {
            "db_name": "AccountCodeDescription.account_description",
            "display_name": "Account Code Description",
            "name": "account_code_description",
        },
        {
            "db_name": "CostTypeCategoryMapping.site_code",
            "display_name": "Site code",
            "name": "site_code",
            "cast": cast_and_handle_numeric_strings,
        },
        {
            "db_name": "CostTypeCategoryMapping.sector_code",
            "display_name": "Sector code",
            "name": "sector_code",
            "cast": cast_and_handle_numeric_strings,
        },
        {
            "db_name": "CostTypeCategoryMapping.budget_line_description",
            "display_name": "Budget line description",
            "name": "budget_line_description",
            "cast": cast_and_handle_numeric_strings,
        },
        {
            "db_name": "CostTypeCategoryMapping.category",
            "display_name": "Category",
            "name": "category",
        },
        {
            "db_name": "CostTypeCategoryMapping.cost_type",
            "display_name": "Cost type",
            "name": "cost_type",
        },
        {
            "db_name": "AccountCodeDescription.sensitive_data",
            "display_name": "Sensitive Data?",
            "name": "sensitive_data?",
            "cast": cast_boolean_type,
        },
    ]

    def __init__(self) -> None:
        super().__init__()
        self.category_lookup: dict[str, Category] = {c.name: c for c in Category.objects.all()}
        self.cost_type_lookup: dict[str, CostType] = {ct.name: ct for ct in CostType.objects.all()}

    def _parse_row_to_dict(self, row_num: int, row_data: dict) -> dict[str, str]:
        d = {}

        # Check for missing key columns.
        if not any(
            [
                row_data.get("category"),
                row_data.get("cost_type"),
                row_data.get("account_code_description"),
            ]
        ):
            self.errors.append(
                ERROR_MESSAGES["missing_data"](
                    row=row_num + 1,
                    columns=[
                        "Category",
                        "Cost type",
                        "Account Code Description",
                    ],
                )
            )

        header: dict[str, str | Callable | None | bool]
        for header in self.headers:
            value = row_data.get(header["name"])

            if header.get("required", False) and (value is None or value == ""):
                self.errors.append(
                    ERROR_MESSAGES["required_row_column"](
                        row=row_num + 1,
                        column=header["display_name"],
                    )
                )

            if header.get("cast"):
                try:
                    value = header["cast"](value)
                except Exception as e:
                    logger.debug(e)
                    self.errors.append(
                        ERROR_MESSAGES["invalid_row_column"](
                            row=row_num + 1,
                            column=header["display_name"],
                            value=value,
                        )
                    )

            if (
                header["display_name"]
                in [
                    "Country code",
                    "Grant code",
                    "Budget line code",
                    "Account Code",
                    "Account Code Description",
                    "Site code",
                    "Sector code",
                    "Budget line description",
                ]
                and value
                and len(value) > 255
            ):
                self.errors.append(
                    ERROR_MESSAGES["value_too_long"](
                        row=row_num + 1,
                        column=header["display_name"],
                        char_limit=255,
                    )
                )

            if header["display_name"] == "Cost type":
                if value and value not in self.cost_type_lookup:
                    self.errors.append(
                        ERROR_MESSAGES["invalid_row_column"](
                            row=row_num + 1,
                            column=header["display_name"],
                            value=value,
                            reason="Invalid Cost Type",
                        )
                    )
            if header["display_name"] == "Category":
                if value and value not in self.category_lookup:
                    self.errors.append(
                        ERROR_MESSAGES["invalid_row_column"](
                            row=row_num + 1,
                            column=header["display_name"],
                            value=value,
                            reason="Invalid Category",
                        )
                    )

            d[header["db_name"]] = value
        return d

    def load_file(self, f: IO[AnyStr]) -> tuple[bool, LoadExcelSheetResult]:
        """
        This file has a bunch of interdependent validators.   Work has been done to separate and label them below.
        """
        success, _ = super().load_file(f)
        if not success:
            return success, self.result()

        with transaction.atomic():
            mappings_to_create = []
            account_code_descriptions_to_ensure_exist: dict[str, AccountCodeDescription] = {}

            for row_num, row_data in enumerate(self.data):
                parsed_row = self._parse_row_to_dict(row_num, row_data)
                ct_c_mapping_obj = CostTypeCategoryMapping()
                for col_db_name, v in parsed_row.items():
                    model, field = col_db_name.split(".")
                    if model == "CostTypeCategoryMapping":
                        if self.errors:
                            # Collect all the parsed row errors without doing any other processing
                            continue
                        if field == "category" and v:
                            setattr(ct_c_mapping_obj, field, self.category_lookup[v])
                        elif field == "cost_type" and v:
                            setattr(ct_c_mapping_obj, field, self.cost_type_lookup[v])
                        elif v:
                            setattr(ct_c_mapping_obj, field, v)
                    if model == "AccountCodeDescription":
                        if field == "account_code":
                            setattr(ct_c_mapping_obj, field, v)
                            if v not in account_code_descriptions_to_ensure_exist:
                                account_code_descriptions_to_ensure_exist[v] = AccountCodeDescription(
                                    account_code=v,
                                    account_description=parsed_row[
                                        "AccountCodeDescription.account_description"
                                    ],
                                    sensitive_data=parsed_row["AccountCodeDescription.sensitive_data"],
                                )
                            else:
                                first_seen = account_code_descriptions_to_ensure_exist[v]
                                if (
                                    parsed_row["AccountCodeDescription.account_description"]
                                    != first_seen.account_description
                                ):
                                    self.errors.append(
                                        ERROR_MESSAGES["inconsistent_account_code_description"](v)
                                    )
                                elif (
                                    parsed_row["AccountCodeDescription.sensitive_data"]
                                    != first_seen.sensitive_data
                                ):
                                    self.errors.append(
                                        ERROR_MESSAGES["inconsistent_account_code_description"](v)
                                    )
                mappings_to_create.append(ct_c_mapping_obj)
                self.imported_count += 1

            existing_account_codes = {
                acd.account_code: acd
                for acd in AccountCodeDescription.objects.filter(
                    account_code__in=account_code_descriptions_to_ensure_exist.keys()
                )
            }
            account_codes_to_create = []
            account_codes_to_update = []
            for account_code, new_obj in account_code_descriptions_to_ensure_exist.items():
                if account_code in existing_account_codes:
                    existing_obj = existing_account_codes[account_code]
                    existing_obj.account_description = new_obj.account_description
                    existing_obj.sensitive_data = new_obj.sensitive_data
                    account_codes_to_update.append(existing_obj)
                else:
                    account_codes_to_create.append(new_obj)

            if self.errors:
                # Clean/Rollback up if there were any errors
                transaction.set_rollback(True)
                self.imported_count = 0
                return False, self.result()

            CostTypeCategoryMapping.objects.all().delete()
            CostTypeCategoryMapping.objects.bulk_create(mappings_to_create)
            AccountCodeDescription.objects.bulk_create(account_codes_to_create)
            AccountCodeDescription.objects.bulk_update(
                account_codes_to_update,
                fields=[
                    "account_description",
                    "sensitive_data",
                ],
            )

        return True, self.result()
