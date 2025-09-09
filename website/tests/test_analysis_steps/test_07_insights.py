import pytest

from .common import StepTest
from ...workflows.analysis.steps.insights import Insights


@pytest.mark.django_db
class TestInsights(StepTest):
    step_under_test = Insights

    @pytest.fixture()
    def up_to_date_workflow(self, analysis_workflow_with_addothercosts_complete):
        return analysis_workflow_with_addothercosts_complete

    @pytest.fixture()
    def workflow_with_completed_step(self, analysis_workflow_with_client_time_added):
        return analysis_workflow_with_client_time_added

    @pytest.mark.skip(
        'Insights has no action items on it.  It is "complete" when ' "all the previous steps are complete"
    )
    def test_step_starts_incomplete(self, up_to_date_workflow):
        pass

    def test_calculate_if_possible_smoke_test(self, analysis_workflow_with_client_time_added):
        self.step_under_test(analysis_workflow_with_client_time_added).calculate_if_possible()

    def test_calculation_done_is_true(self, analysis_workflow_with_client_time_added):
        step = self.step_under_test(analysis_workflow_with_client_time_added)
        step.calculate_if_possible()
        assert step.calculations_done()

    def test_invalidate_step_works(self, workflow_with_completed_step):
        workflow_with_completed_step.invalidate_step(step_name=self.step_under_test.name)
        assert workflow_with_completed_step.get_last_complete().name == "insights", (
            "The invalidation logic here removes the cached values but they "
            "are recomputed on demand and this step should 'remain' complete."
        )
