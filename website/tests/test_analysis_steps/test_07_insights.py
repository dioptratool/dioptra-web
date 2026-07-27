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

    def test_next_step_is_incomplete(self, workflow_with_completed_step):
        current_step = workflow_with_completed_step.get_step(self.step_under_test.name)
        assert workflow_with_completed_step.get_next(current_step) is None

    def test_cloned_analysis_is_still_complete_up_to_the_same_step(self, workflow_with_completed_step):
        from website.tests.factories import UserFactory
        from website.utils.duplicator import clone_analysis
        from website.workflows import AnalysisWorkflow

        cloned_analysis = clone_analysis(workflow_with_completed_step.analysis.pk, owner=UserFactory())
        new_wf = AnalysisWorkflow(analysis=cloned_analysis)

        assert workflow_with_completed_step.get_last_incomplete() is None
        assert new_wf.get_last_incomplete() is None

    def test_invalidate_step_works(self, workflow_with_completed_step):
        workflow_with_completed_step.invalidate_step(step_name=self.step_under_test.name)
        assert workflow_with_completed_step.get_step("insights").is_complete, (
            "The invalidation logic here removes the cached values but they "
            "are recomputed on demand and this step should 'remain' complete."
        )
        assert workflow_with_completed_step.analysis.output_costs == {}
