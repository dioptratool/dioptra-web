import logging
from collections.abc import Callable
from typing import AnyStr, IO

from django.db import transaction

from .base import Importer
from .types import LoadExcelSheetResult
from .utils import (
    cast_dollar_to_decimal_four_decimal_places,
    cast_to_decimal_four_decimal_places,
)
from .validation.error_messages import ERROR_MESSAGES
from ..models import (
    Country,
    InsightComparisonData,
    Intervention,
)

logger = logging.getLogger(__name__)


class InsightComparisonDataImporter(Importer):
    headers = [
        {
            "db_name": "InsightComparisonData.name",
            "display_name": "Name",
            "name": "name",
            "required": True,
        },
        {
            "db_name": "InsightComparisonData.country",
            "display_name": "Country Code",
            "name": "country_code",
            "required": True,
        },
        {
            "db_name": "InsightComparisonData.grants",
            "display_name": "Grants",
            "name": "grants",
            "required": True,
        },
        {
            "db_name": "InsightComparisonData.intervention",
            "display_name": "Intervention Being Analyzed",
            "name": "intervention_being_analyzed",
            "required": True,
        },
        {
            "db_name": "",
            "display_name": "Output Metric Parameter Label 1",
            "name": "output_metric_parameter_label_1",
        },
        {
            "db_name": "",
            "display_name": "Output Metric Parameter Value 1",
            "name": "output_metric_parameter_value_1",
            "cast": cast_to_decimal_four_decimal_places,
        },
        {
            "db_name": "",
            "display_name": "Output Metric Parameter Label 2",
            "name": "output_metric_parameter_label_2",
        },
        {
            "db_name": "",
            "display_name": "Output Metric Parameter Value 2",
            "name": "output_metric_parameter_value_2",
            "cast": cast_to_decimal_four_decimal_places,
        },
        {
            "db_name": "",
            "display_name": "Output Metric Parameter Label 3",
            "name": "output_metric_parameter_label_3",
        },
        {
            "db_name": "",
            "display_name": "Output Metric Parameter Value 3",
            "name": "output_metric_parameter_value_3",
            "cast": cast_to_decimal_four_decimal_places,
        },
        {
            "db_name": "",
            "display_name": "Output Metric Parameter Label 4",
            "name": "output_metric_parameter_label_4",
        },
        {
            "db_name": "",
            "display_name": "Output Metric Parameter Value 4",
            "name": "output_metric_parameter_value_4",
            "cast": cast_to_decimal_four_decimal_places,
        },
        {
            "db_name": "",
            "display_name": "Cost per output (program costs only) 1",
            "name": "cost_per_output_(program_costs_only)_1",
            "cast": cast_dollar_to_decimal_four_decimal_places,
        },
        {
            "db_name": "",
            "display_name": "Cost per output (including program costs, support costs, and indirect costs) 1",
            "name": "cost_per_output_(including_program_costs_support_costs_and_indirect_costs)_1",
            "cast": cast_dollar_to_decimal_four_decimal_places,
        },
        {
            "db_name": "",
            "display_name": "Cost per output (program costs only) 2",
            "name": "cost_per_output_(program_costs_only)_2",
            "cast": cast_dollar_to_decimal_four_decimal_places,
        },
        {
            "db_name": "",
            "display_name": "Cost per output (including program costs, support costs, and indirect costs) 2",
            "name": "cost_per_output_(including_program_costs_support_costs_and_indirect_costs)_2",
            "cast": cast_dollar_to_decimal_four_decimal_places,
        },
    ]

    def __init__(self) -> None:
        super().__init__()
        self.intervention_lookup: dict[str, Intervention] = {i.name: i for i in Intervention.objects.all()}
        self.country_lookup: dict[str, Country] = {c.code: c for c in Country.objects.all()}

    def _parse_row_to_dict(
        self,
        row_num: int,
        row_data: dict,
    ) -> dict[str, str]:

        d = {}

        header: dict[str, str | Callable | None | bool]
        for i, header in enumerate(self.headers):
            value = row_data[header["name"]]

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
                    "Grants",
                ]
                and len(value) > 255
            ):
                self.errors.append(
                    ERROR_MESSAGES["value_too_long"](
                        row=row_num, column=header["display_name"], char_limit=255
                    )
                )

            if header["display_name"] == "Grants":
                try:
                    value = [v.strip() for v in value.split(",")]
                except Exception as e:
                    logger.debug(e)
                    self.errors.append(
                        ERROR_MESSAGES["invalid_row_column"](
                            row=row_num,
                            column=header["display_name"],
                            value=value,
                        )
                    )
                    continue

                for grant in value:
                    if len(grant) > 50:
                        self.errors.append(
                            ERROR_MESSAGES["value_too_long"](
                                row=row_num, column=header["display_name"], char_limit=50
                            )
                        )

            if header["display_name"] == "Country Code":
                if value not in self.country_lookup:
                    self.errors.append(
                        ERROR_MESSAGES["invalid_row_column"](
                            row=row_num,
                            column=header["display_name"],
                            value=value,
                            reason="Invalid Country",
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
            for row_num, row_data in enumerate(self.data, 1):
                parsed_row = self._parse_row_to_dict(row_num, row_data)
                insight_comparison_data_obj = InsightComparisonData()

                output_metrics = self._create_output_metric_dict(parsed_row)
                intervention = self.intervention_lookup.get(parsed_row.get("intervention_being_analyzed"))

                if not intervention:
                    self.errors.append(
                        ERROR_MESSAGES["invalid_row_column"](
                            row=row_num,
                            column="Intervention Being Analyzed",
                            value=parsed_row.get("intervention_being_analyzed"),
                            reason="Invalid Intervention",
                        )
                    )
                    continue

                insight_comparison_data_obj.intervention = intervention

                ## Handle Parameters
                valid_params = intervention.get_all_parameter_names_by_label()
                for label, value in output_metrics.items():
                    if label not in valid_params:
                        formatted_valid_params = ", ".join(str(key) for key in valid_params.keys())
                        self.errors.append(
                            ERROR_MESSAGES["invalid_row_column"](
                                row=row_num,
                                column="Output Metric Parameter Label",
                                value=label,
                                reason=f"Incorrect Output Metric Parameter Label for Intervention {intervention.name}.   "
                                f"Expected: {formatted_valid_params}  Got: {label}",
                            )
                        )
                    else:
                        if value:
                            insight_comparison_data_obj.parameters[valid_params[label]] = str(value)
                for each_output_metric in intervention.output_metric_objects():
                    for param_key, param in each_output_metric.parameters.items():
                        if param_key not in insight_comparison_data_obj.parameters:
                            self.errors.append(
                                ERROR_MESSAGES["missing_parameter"](parameter=param.label, row=row_num)
                            )

                        elif insight_comparison_data_obj.parameters.get(param_key, None) in [None, ""]:
                            self.errors.append(
                                ERROR_MESSAGES["missing_parameter"](parameter=param.label, row=row_num)
                            )

                if self.check_for_duplicate_parameter_labels(parsed_row):
                    self.errors.append(
                        ERROR_MESSAGES["invalid_row_generic"](
                            row=row_num, reason="Duplicate parameter labels found."
                        )
                    )

                ## END Handle Parameters

                ## Handle Output Costs
                output_costs = {}
                for i, output_metric_name in enumerate(intervention.output_metrics, 1):
                    all_value = parsed_row.get(
                        f"cost_per_output_(including_program_costs_support_costs_and_indirect_costs)_{i}"
                    )
                    direct_only_value = parsed_row.get(f"cost_per_output_(program_costs_only)_{i}")

                    output_costs[output_metric_name] = {
                        "all": float(all_value) if all_value else None,
                        "direct_only": float(direct_only_value) if direct_only_value else None,
                    }
                insight_comparison_data_obj.output_costs = output_costs
                ## END Handle Output Costs

                for header_name, v in parsed_row.items():

                    if self.errors:
                        # We collect all the parsed row errors without doing any other processing
                        continue

                    if header_name == "country_code":
                        setattr(insight_comparison_data_obj, "country", self.country_lookup[v])
                    elif header_name == "grants":
                        setattr(insight_comparison_data_obj, header_name, ", ".join(v))
                    elif header_name == "name":
                        setattr(insight_comparison_data_obj, header_name, v)

                imported_count += 1
                to_create.append(insight_comparison_data_obj)

            if len(self.errors):
                # Clean/Rollback up if there were any errors
                transaction.set_rollback(True)
                result: LoadExcelSheetResult = {"errors": self.errors, "imported_count": 0}
                return False, result

            InsightComparisonData.objects.all().delete()
            InsightComparisonData.objects.bulk_create(to_create)

        result: LoadExcelSheetResult = {
            "errors": self.errors,
            "imported_count": imported_count,
        }

        return True, result

    @staticmethod
    def _create_output_metric_dict(row: dict[str, float | None]):
        o = {}
        val_1 = row.get("output_metric_parameter_value_1")
        val_2 = row.get("output_metric_parameter_value_2")
        val_3 = row.get("output_metric_parameter_value_3")
        val_4 = row.get("output_metric_parameter_value_4")

        o[row.get("output_metric_parameter_label_1")] = float(val_1) if val_1 else None
        o[row.get("output_metric_parameter_label_2")] = float(val_2) if val_2 else None
        o[row.get("output_metric_parameter_label_3")] = float(val_3) if val_3 else None
        o[row.get("output_metric_parameter_label_4")] = float(val_4) if val_4 else None
        if "" in o:
            o.pop("")
        if None in o:
            o.pop(None)
        return o

    def check_for_duplicate_parameter_labels(self, row: dict) -> bool:
        keys = [
            "output_metric_parameter_label_1",
            "output_metric_parameter_label_2",
            "output_metric_parameter_label_3",
            "output_metric_parameter_label_4",
        ]
        filtered_values = [row.get(key) for key in keys if row.get(key) not in (None, "")]
        return len(filtered_values) != len(set(filtered_values))
