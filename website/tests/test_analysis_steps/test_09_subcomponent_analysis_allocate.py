import pytest

from .common import StepTest
from ..factories import UserFactory
from ...utils.duplicator import clone_analysis
from ...workflows import AnalysisWorkflow
from ...workflows.analysis.steps.subcomponent_analysis_allocate.subcomponent_analysis_allocate import (
    SubcomponentsAllocate,
)


@pytest.mark.django_db
class TestSubcomponentsAllocate(StepTest):
    step_under_test = SubcomponentsAllocate

    @pytest.fixture()
    def up_to_date_workflow(self, analysis_workflow_with_subcomponent_labels_and_client_time_added):
        return analysis_workflow_with_subcomponent_labels_and_client_time_added

    @pytest.fixture()
    def workflow_with_completed_step(self, analysis_workflow_with_all_cost_lines_allocated_to_subcomponents):
        return analysis_workflow_with_all_cost_lines_allocated_to_subcomponents

    def test_step_is_marked_complete_correctly_with_non_contributing_cost_lines(
        self,
        analysis_workflow_with_all_cost_lines_allocated_to_subcomponents_and_some_non_contributing,
    ):
        assert self.step_under_test(
            workflow=analysis_workflow_with_all_cost_lines_allocated_to_subcomponents_and_some_non_contributing
        ).is_complete

    def test_step_is_marked_complete_correctly_with_allocation_percentage_of_zero(
        self,
        analysis_workflow_with_some_cost_lines_allocated,
    ):
        assert self.step_under_test(workflow=analysis_workflow_with_some_cost_lines_allocated).is_complete

    @pytest.mark.skip("There is no next step for this step.")
    def test_next_step_is_incomplete(self, workflow_with_completed_step):
        pass

    def test_cloned_analysis_is_still_complete_up_to_the_same_step(self, workflow_with_completed_step):
        if workflow_with_completed_step.analysis.interventioninstance_set.count() != 1:
            pytest.skip("Subcomponent steps are not expected to load for Multi-intervention Analyses.")
        cloned_analysis = clone_analysis(workflow_with_completed_step.analysis.pk, owner=UserFactory())
        new_wf = AnalysisWorkflow(analysis=cloned_analysis)
        # For this step being the truly last step we don't expect there to be any "incomplete" steps.
        assert new_wf.get_last_incomplete() is None, f"{new_wf.get_last_incomplete().name} is incomplete"
        assert (
            workflow_with_completed_step.get_last_incomplete() is None
        ), f"{new_wf.get_last_incomplete().name} is incomplete"

    def test_dependencies_are_met_correctly(
        self,
        up_to_date_workflow,
    ):
        step = self.step_under_test(workflow=up_to_date_workflow)
        if up_to_date_workflow.analysis.interventioninstance_set.count() == 1:
            assert step.dependencies_met
        else:
            assert (
                not step.dependencies_met
            ), "Subcomponent steps are not expected to load for Multi-intervention Analyses."

    def test_completed_steps_is_complete(self, workflow_with_completed_step):
        if workflow_with_completed_step.analysis.interventioninstance_set.count() != 1:
            pytest.skip("Subcomponent steps are not expected to load for Multi-intervention Analyses.")
        super().test_completed_steps_is_complete(workflow_with_completed_step)

    def test_invalidate_step_works(self, workflow_with_completed_step):
        workflow_with_completed_step.invalidate_step(step_name=self.step_under_test.name)
        assert workflow_with_completed_step.get_step("insights").is_complete, (
            "There is no invalidation logic for this step "
            "so nothing should change.  Insights will remain the last complete step."
        )
