import pytest

from website.workflows import AnalysisWorkflow


@pytest.mark.django_db
class TestConditionalCashTransferOuputMetrics:
    def test_value_of_cash_distributed_multiintervention(
        self, analysis_with_output_metrics_conditional_cash_transfer
    ):
        analysis = analysis_with_output_metrics_conditional_cash_transfer
        wf = AnalysisWorkflow(analysis)
        assert (
            wf.get_last_complete().name == "insights"
        ), f"{wf.get_last_incomplete_or_last().name} step is not complete!"

        params1 = analysis.interventioninstance_set.get(label="First").parameters
        assert params1["value_of_cash_distributed"] == 3500

        params2 = analysis.interventioninstance_set.get(label="Second").parameters
        assert params2["value_of_cash_distributed"] == 5200
