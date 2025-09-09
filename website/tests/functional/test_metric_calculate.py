from unittest.mock import MagicMock

from django.test import TestCase

from website.models.output_metric import OUTPUT_METRICS, OutputMetric


class MockMetric(OutputMetric):
    parameters = {
        "number_of_people_served": MagicMock(label="Number of people"),
        "number_of_years_water_was_provided": MagicMock(label="Number of years"),
    }

    def calculate(
        self,
        cost_output_sum,
        number_of_people_served,
        number_of_years_water_was_provided,
        **kwargs,
    ):
        return cost_output_sum / (
            (number_of_people_served * number_of_years_water_was_provided) / number_of_people_served
        )


class MetricTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.mock_metric = MockMetric()

    def test_all_metrics_have_valid_calculate(self):
        for metric in OUTPUT_METRICS:
            param_to_excel_map = {"cost_output_sum": "SUM(B1, B2, B3)"}
            for i, param in enumerate(metric.parameters):
                param_to_excel_map[param] = f"A{i+1}"

            excel_formula = metric.convert_calculate_to_excel_formula(param_to_excel_map)
            assert excel_formula is not None, (
                f'The "calculate" method on {metric.id} must be defined as a simple '
                f"arithmetic function that can be converted to an Excel formula "
                f"via the convert_calculate_to_excel_formula method"
            )

    def test_convert_calculate_to_excel_formula(self):
        param_to_excel_map = {
            "cost_output_sum": "SUM(A1, A2, A3)",
            "number_of_people_served": "B4",
            "number_of_years_water_was_provided": "B5",
        }

        excel_formula = self.mock_metric.convert_calculate_to_excel_formula(param_to_excel_map)
        expected_formula = "IFERROR(SUM(A1, A2, A3) / ((B4 * B5) / B4), 0)"
        assert excel_formula == expected_formula
