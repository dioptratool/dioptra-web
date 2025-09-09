import pytest


@pytest.mark.django_db
class TestAnalysisOutputCosts:
    def test_calculate_output_costs(self, analysis_with_output_metrics):
        analysis_with_output_metrics.calculate_output_costs()

        expected_output_costs = {
            str(analysis_with_output_metrics.interventioninstance_set.first().id): {
                "NumberOfTeacherDaysOfTraining": {
                    "all": 44500.0,
                    "direct_only": 25000.0,
                    "in_kind": 7500.0,
                    "client": 5000.0,
                },
                "NumberOfTeacherYearsOfSupport": {
                    "all": 44500.0,
                    "direct_only": 25000.0,
                    "in_kind": 7500.0,
                    "client": 5000.0,
                },
            }
        }
        assert analysis_with_output_metrics.output_costs == expected_output_costs
