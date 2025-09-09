import logging
from collections.abc import Callable
from typing import AnyStr, IO

from django.db import transaction

from .base import Importer
from .types import LoadExcelSheetResult
from .utils import get_duplicates
from .validation.error_messages import ERROR_MESSAGES
from ..models import (
    Country,
    Region,
)

logger = logging.getLogger(__name__)


class CountriesImporter(Importer):
    headers = [
        {
            "db_name": "Country.name",
            "display_name": "Name",
            "name": "name",
            "required": True,
        },
        {
            "db_name": "Country.code",
            "display_name": "Code",
            "name": "code",
            "required": True,
        },
        {
            "db_name": "Country.region",
            "display_name": "Region",
            "name": "region",
        },
    ]

    def __init__(self) -> None:
        super().__init__()
        self.country_lookup: dict[str, Country] = {c.name: c for c in Country.objects.all()}
        self.region_lookup: dict[str, Region] = {r.name: r for r in Region.objects.all()}

    def _parse_row_to_dict(
        self,
        row_num: int,
        row_data: dict,
    ) -> dict[str, str]:

        d = {}

        header: dict[str, str | Callable | None | bool]
        for i, header in enumerate(self.headers):
            value = row_data.get(header["name"])
            if isinstance(value, str):
                value = value.strip()

            if header.get("required", False) and (value is None or value == ""):
                self.errors.append(
                    ERROR_MESSAGES["required_row_column"](
                        row=row_num,
                        column=header["display_name"],
                    )
                )

            if value and header.get("cast"):
                try:
                    value = header["cast"](value)
                except Exception as e:
                    logger.debug(e)
                    self.errors.append(
                        ERROR_MESSAGES["invalid_row_column"](
                            row=row_num,
                            column=header["display_name"],
                            value=value,
                        )
                    )

            if (
                header["display_name"]
                in [
                    "Name",
                ]
                and len(value) > 255
            ):
                self.errors.append(
                    ERROR_MESSAGES["value_too_long"](
                        row=row_num, column=header["display_name"], char_limit=255
                    )
                )

            if (
                header["display_name"]
                in [
                    "Code",
                ]
                and len(value) > 10
            ):
                self.errors.append(
                    ERROR_MESSAGES["value_too_long"](
                        row=row_num, column=header["display_name"], char_limit=10
                    )
                )

            if header["display_name"] == "Region":
                if value and value not in self.region_lookup:
                    self.errors.append(
                        ERROR_MESSAGES["invalid_region"](
                            row=row_num, column=header["display_name"], region=value
                        )
                    )

            d[header["name"]] = value
        return d

    def load_file(self, f: IO[AnyStr]) -> tuple[bool, LoadExcelSheetResult]:
        success, _ = super().load_file(f)
        if not success:
            return success, self.result()

        imported_count = 0
        with transaction.atomic():
            to_create = []
            to_update = []

            seen_country_names = []

            for row_num, row_data in enumerate(self.data, 1):
                parsed_row = self._parse_row_to_dict(row_num, row_data)
                if parsed_row.get("name"):
                    seen_country_names.append(parsed_row.get("name"))
                if self.errors:
                    # We collect all the parsed row errors without doing any other processing
                    continue

                if parsed_row.get("name") not in self.country_lookup:
                    country_obj = Country()
                    for header_name, v in parsed_row.items():
                        if not v:
                            continue
                        if header_name == "name":
                            setattr(country_obj, header_name, v)
                        elif header_name == "code":
                            setattr(country_obj, header_name, v)
                        elif header_name == "region":
                            setattr(country_obj, header_name, self.region_lookup[v])

                    to_create.append(country_obj)
                else:
                    country_obj = self.country_lookup[parsed_row.get("name")]
                    for header_name, v in parsed_row.items():
                        if header_name == "code":
                            setattr(country_obj, header_name, v)
                        elif header_name == "region":
                            if not v:
                                continue
                            setattr(country_obj, header_name, self.region_lookup[v])

                    to_update.append(country_obj)
                imported_count += 1
            dupes = get_duplicates(seen_country_names)
            if dupes:
                self.errors.append(
                    ERROR_MESSAGES["duplicate_country_names"](
                        countries=dupes,
                    )
                )
            missing_country_names = set(self.country_lookup.keys()) - set(seen_country_names)
            if missing_country_names:
                self.errors.append(ERROR_MESSAGES["missing_countries"](countries=missing_country_names))

            if len(self.errors):
                # Clean/Rollback up if there were any errors
                transaction.set_rollback(True)
                result: LoadExcelSheetResult = {"errors": self.errors, "imported_count": 0}
                return False, result

            Country.objects.bulk_create(to_create)
            Country.objects.bulk_update(
                to_update,
                fields=[
                    "code",
                    "region",
                ],
            )

        result: LoadExcelSheetResult = {
            "errors": self.errors,
            "imported_count": imported_count,
        }

        return True, result
