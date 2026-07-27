import pytest

from website.workflows.analysis.steps.allocate_subcomponents import AllocateSubcomponents
from .common import StepTest


@pytest.mark.django_db
class TestAllocateSubcomponents(StepTest):
    step_under_test = AllocateSubcomponents

    @pytest.fixture()
    def up_to_date_workflow(self, analysis_workflow_with_subcomponent_labels):
        return analysis_workflow_with_subcomponent_labels

    @pytest.fixture()
    def workflow_with_completed_step(
        self,
        analysis_workflow_with_all_cost_lines_allocated_to_subcomponents,
    ):
        return analysis_workflow_with_all_cost_lines_allocated_to_subcomponents

    @pytest.mark.skip(
        "The next step is insights (add-other-costs is disabled on this fixture) "
        "which is only incomplete if its dependencies aren't met"
    )
    def test_next_step_is_incomplete(self, workflow_with_completed_step):
        pass

    def test_step_is_disabled_without_subcomponent_analyses(self, analysis_workflow_with_allocations):
        step = analysis_workflow_with_allocations.get_step(self.step_under_test.name)
        assert not step.is_enabled

    def test_get_next_skips_disabled_step(self, analysis_workflow_with_allocations):
        workflow = analysis_workflow_with_allocations
        next_step = workflow.get_next(workflow.get_step("allocate"))
        assert next_step.name != self.step_under_test.name

    def test_allocate_is_complete_without_subcomponent_allocations(
        self,
        analysis_workflow_with_subcomponent_labels,
    ):
        """
        Regression guard for the fused (pre-split) rule: missing subcomponent
        allocations must no longer hold the allocate step incomplete.
        """
        workflow = analysis_workflow_with_subcomponent_labels
        assert workflow.get_step("allocate").is_complete
        assert not workflow.get_step(self.step_under_test.name).is_complete
