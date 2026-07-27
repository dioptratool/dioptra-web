import pytest

from website.tests.factories import InterventionFactory, InterventionInstanceFactory
from website.workflows.analysis.steps.interventions import Interventions
from .common import StepTest


@pytest.mark.django_db
class TestInterventionsStep(StepTest):
    step_under_test = Interventions

    @pytest.fixture()
    def up_to_date_workflow(self, analysis_workflow_with_analysis_only):
        return analysis_workflow_with_analysis_only

    @pytest.fixture()
    def workflow_with_completed_step(self, analysis_workflow_with_analysis):
        return analysis_workflow_with_analysis

    def test_get_href_returns_the_interventions_url(self, up_to_date_workflow):
        step = self.step_under_test(workflow=up_to_date_workflow)
        assert step.get_href() == f"/analysis/{step.workflow.analysis.pk}/interventions/"

    def test_get_href_returns_none_without_an_analysis(self, empty_analysis_workflow):
        step = self.step_under_test(workflow=empty_analysis_workflow)
        assert step.get_href() is None

    def test_incomplete_without_interventions(self, up_to_date_workflow):
        step = self.step_under_test(workflow=up_to_date_workflow)
        assert not step.is_complete

    def test_incomplete_when_intervention_is_missing_parameters(self, up_to_date_workflow):
        analysis = up_to_date_workflow.analysis
        intervention = InterventionFactory(
            output_metrics=["NumberOfTeacherDaysOfTraining"],
        )
        InterventionInstanceFactory(analysis=analysis, intervention=intervention, parameters={})

        step = self.step_under_test(workflow=up_to_date_workflow)
        assert not step.is_complete

    def test_load_data_dependencies_gate_on_interventions(
        self, up_to_date_workflow, workflow_with_completed_step
    ):
        assert not up_to_date_workflow.get_step("load-data").dependencies_met
        assert workflow_with_completed_step.get_step("load-data").dependencies_met

    def test_step_ordering(self, workflow_with_completed_step):
        workflow = workflow_with_completed_step
        define = workflow.get_step("define")
        interventions = workflow.get_step("interventions")
        assert workflow.get_next(define) is interventions
        assert workflow.get_next(interventions) is workflow.get_step("load-data")
        assert workflow.get_prev(interventions) is define

    def test_invalidate_step_works(self, workflow_with_completed_step):
        workflow_with_completed_step.invalidate_step(step_name=self.step_under_test.name)
        last_complete = workflow_with_completed_step.get_last_complete()
        assert (
            last_complete.name == self.step_under_test.name
        ), "There is no invalidation logic for this step so nothing should change."


class TestInterventionsStepMultiIntervention(TestInterventionsStep):
    @pytest.fixture()
    def workflow_with_completed_step(self, analysis_workflow_with_analysis_multiintervention):
        return analysis_workflow_with_analysis_multiintervention


class TestInterventionsStepMultiInterventionDuplicates(TestInterventionsStep):
    @pytest.fixture()
    def workflow_with_completed_step(self, analysis_workflow_with_analysis_multiintervention_duplicates):
        return analysis_workflow_with_analysis_multiintervention_duplicates
