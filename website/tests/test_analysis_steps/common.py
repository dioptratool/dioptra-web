import pytest

from website.tests.factories import UserFactory
from website.utils.duplicator import clone_analysis
from website.workflows import AnalysisWorkflow
from website.workflows._steps_base import MultiStep, SubStep


class StepTest:
    step_under_test = None

    @pytest.fixture
    def up_to_date_workflow(self, empty_analysis_workflow):
        raise NotImplementedError(
            "This needs to be assigned to a workflow that is " "up to date enough for the step to proceed."
        )

    @pytest.fixture
    def workflow_with_completed_step(self, empty_analysis_workflow):
        raise NotImplementedError(
            "This needs to be assigned to a workflow that is " "complete for the step under test."
        )

    def test_step_is_enabled_for_this_test_suite(self, up_to_date_workflow):
        step = up_to_date_workflow.get_step(self.step_under_test.name)
        assert step.is_enabled

    def test_step_starts_incomplete_on_empty(self, empty_analysis_workflow):
        step = empty_analysis_workflow.get_step(self.step_under_test.name)
        assert not step.is_complete

    def test_step_starts_incomplete(self, up_to_date_workflow):
        step = up_to_date_workflow.get_step(self.step_under_test.name)
        assert not step.is_complete

    def test_previous_steps_complete(self, up_to_date_workflow):
        wf = up_to_date_workflow
        current_step_index = wf.step_classes.index(self.step_under_test)
        for each_step in wf.steps[:current_step_index]:
            assert each_step.is_complete, f"{each_step.name} step is not complete"

    def test_next_step_is_incomplete(self, workflow_with_completed_step):
        current_step = workflow_with_completed_step.get_step(self.step_under_test.name)
        next_step = workflow_with_completed_step.get_next(current_step)
        assert not next_step.is_complete, (
            f"For step: {current_step.name} the Next Step "
            f"was determined to be {next_step.name} and it shouldn't already be complete."
        )

    def test_completed_steps_is_complete(self, workflow_with_completed_step):
        step = self.step_under_test(workflow=workflow_with_completed_step)
        assert step.is_complete

    def test_dependencies_are_not_met_on_creation_of_empty_analysis(
        self,
        empty_analysis_workflow,
    ):
        step = self.step_under_test(workflow=empty_analysis_workflow)
        assert not step.dependencies_met

    def test_dependencies_are_met_correctly(
        self,
        up_to_date_workflow,
    ):
        step = self.step_under_test(workflow=up_to_date_workflow)
        assert step.dependencies_met

    def test_get_href_returns_a_value(self, up_to_date_workflow):
        step = self.step_under_test(workflow=up_to_date_workflow)
        assert isinstance(step.get_href(), str)

    def test_multistep_test_has_substeps(self, up_to_date_workflow):
        if not issubclass(self.step_under_test, MultiStep):
            pytest.skip("Only Applicable to MultiStep objects")
        step = self.step_under_test(workflow=up_to_date_workflow)
        assert step.steps, (
            f"Test Class for {self.step_under_test.__name__} was not setup "
            f"correctly.  Multistep Objects require substeps"
        )

    def test_multistep_test_still_has_substeps_after_completed(self, workflow_with_completed_step):
        if not issubclass(self.step_under_test, MultiStep):
            pytest.skip("Only Applicable to MultiStep objects")
        step = self.step_under_test(workflow=workflow_with_completed_step)
        assert step.steps, (
            f"Test Class for {self.step_under_test.__name__} was not setup "
            f"correctly.  Multistep Objects require substeps"
        )

    def test_incomplete_step_view_smoke_test(self, up_to_date_workflow, client_with_admin):
        response = client_with_admin.get(
            self.step_under_test(workflow=up_to_date_workflow).get_href(),
            follow=True,
        )
        assert response.status_code == 200, f"Expected view to load.  Instead got: {response.status_code}"

    def test_complete_step_view_smoke_test(self, workflow_with_completed_step, client_with_admin):
        response = client_with_admin.get(
            self.step_under_test(workflow=workflow_with_completed_step).get_href(),
            follow=True,
        )
        assert response.status_code == 200, f"Expected view to load.  Instead got: {response.status_code}"

    def test_cloned_analysis_is_still_complete_up_to_the_same_step(self, workflow_with_completed_step):
        cloned_analysis = clone_analysis(workflow_with_completed_step.analysis.pk, owner=UserFactory())
        new_wf = AnalysisWorkflow(analysis=cloned_analysis)
        assert (
            new_wf.get_last_incomplete().name == workflow_with_completed_step.get_last_incomplete().name
        ), f"Expected {workflow_with_completed_step.get_last_incomplete().name} Got: {new_wf.get_last_incomplete().name}"

    def test_invalidate_step_works(self, workflow_with_completed_step):
        workflow_with_completed_step.invalidate_step(step_name=self.step_under_test.name)
        refreshed_workflow = AnalysisWorkflow(workflow_with_completed_step.analysis)

        assert (
            refreshed_workflow.get_last_complete().name != self.step_under_test.name
        ), f"Step {self.step_under_test.name} should have been invalidated.  Instead it remained completed."

        last_incomplete_step = refreshed_workflow.get_last_incomplete()
        if isinstance(last_incomplete_step, SubStep):
            last_incomplete_step = last_incomplete_step.parent

        assert self.step_under_test.name == last_incomplete_step.name, (
            f"Currently testing {self.step_under_test.name}.  "
            f"Step {self.step_under_test.name} was not invalidated correctly. "
            "It should have been the last incomplete step."
            f"It is{' NOT' if refreshed_workflow.get_step(self.step_under_test.name).is_complete else ' STILL'} complete.  "
            f"Instead the last incomplete step is: {refreshed_workflow.get_last_incomplete().name}"
        )
