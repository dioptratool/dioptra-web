import pytest

from website.workflows.analysis.steps.define import Define
from .common import StepTest


@pytest.mark.django_db
class TestDefineStep(StepTest):
    step_under_test = Define

    @pytest.fixture()
    def up_to_date_workflow(self, empty_analysis_workflow):
        return empty_analysis_workflow

    @pytest.fixture()
    def workflow_with_completed_step(self, analysis_workflow_with_analysis):
        return analysis_workflow_with_analysis

    def test_dependencies_are_met_on_creation(self, up_to_date_workflow, workflow_with_completed_step):
        step = self.step_under_test(workflow=up_to_date_workflow)
        assert step.dependencies_met
        step = self.step_under_test(workflow=workflow_with_completed_step)
        assert step.dependencies_met

    def test_get_href_returns_a_create_url_when_empty(self, up_to_date_workflow):
        step = self.step_under_test(workflow=up_to_date_workflow)
        assert step.get_href()
        assert step.get_href() == "/analysis/define/"

    def test_get_href_returns_an_update_url_when_analysis_is_defined(self, workflow_with_completed_step):
        step = self.step_under_test(workflow=workflow_with_completed_step)
        assert step.get_href()
        assert step.get_href() == f"/analysis/{step.workflow.analysis.pk}/define/"

    # noinspection PyMethodOverriding
    def test_dependencies_are_not_met_on_creation_of_empty_analysis(self):
        """As the first step Define always has its dependencies met"""
        assert True

    def test_invalidate_step_works(self, workflow_with_completed_step):
        workflow_with_completed_step.invalidate_step(step_name=self.step_under_test.name)
        assert (
            workflow_with_completed_step.get_last_complete().name == self.step_under_test.name
        ), "There is no invalidation logic for this step so nothing should change."


class TestDefineStepMultiIntervention(TestDefineStep):
    @pytest.fixture()
    def up_to_date_workflow(self, empty_analysis_workflow):
        return empty_analysis_workflow

    @pytest.fixture()
    def workflow_with_completed_step(self, analysis_workflow_with_analysis_multiintervention):
        return analysis_workflow_with_analysis_multiintervention


class TestDefineStepMultiInterventionDuplicates(TestDefineStep):
    @pytest.fixture()
    def up_to_date_workflow(self, empty_analysis_workflow):
        return empty_analysis_workflow

    @pytest.fixture()
    def workflow_with_completed_step(self, analysis_workflow_with_analysis_multiintervention_duplicates):
        return analysis_workflow_with_analysis_multiintervention_duplicates

    def test_completed_steps_is_complete(self, workflow_with_completed_step):
        step = self.step_under_test(workflow=workflow_with_completed_step)
        assert step.is_complete
