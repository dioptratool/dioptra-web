import pytest

from website.workflows import AnalysisWorkflow

from .common import StepTest
from ...workflows.analysis.steps.add_other_costs import AddOtherCosts


@pytest.mark.django_db
class TestAddOtherCosts(StepTest):
    step_under_test = AddOtherCosts

    def test_step_disabled_when_no_other_cost_flags(self, analysis_workflow_with_allocations):
        analysis = analysis_workflow_with_allocations.analysis
        analysis.client_time = False
        analysis.in_kind_contributions = False
        analysis.other_hq_costs = False
        analysis.save()

        workflow = AnalysisWorkflow(analysis)

        assert workflow.get_step("add-other-costs").is_enabled is False
        # Navigation skips the disabled step (allocate-subcomponents is also
        # disabled here because no sub-component analyses exist).
        assert workflow.get_next(workflow.get_step("allocate")).name == "insights"

    def test_step_enabled_when_any_other_cost_flag_is_set(self, analysis_workflow_with_allocations):
        analysis = analysis_workflow_with_allocations.analysis
        analysis.client_time = False
        analysis.in_kind_contributions = True
        analysis.other_hq_costs = False
        analysis.save()

        workflow = AnalysisWorkflow(analysis)

        assert workflow.get_step("add-other-costs").is_enabled is True

    @pytest.fixture()
    def up_to_date_workflow(self, analysis_workflow_with_allocations):
        return analysis_workflow_with_allocations

    @pytest.fixture()
    def workflow_with_completed_step(self, analysis_workflow_with_client_time_added):
        return analysis_workflow_with_client_time_added

    @pytest.mark.skip("The next step is insights which is only incomplete " "if it's dependencies aren't met")
    def test_next_step_is_incomplete(self, workflow_with_completed_step):
        pass

    def test_invalidate_step_works(self, workflow_with_completed_step):
        workflow_with_completed_step.invalidate_step(step_name=self.step_under_test.name)
        assert (
            workflow_with_completed_step.get_last_complete().name == "insights"
        ), "There is no invalidation logic for this step so nothing should change.  Insights will remain the last complete step."
