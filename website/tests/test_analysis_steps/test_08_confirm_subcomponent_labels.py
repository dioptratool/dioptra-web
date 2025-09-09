import pytest

from .common import StepTest
from ...workflows.analysis.steps.subcomponent_analysis_confirm.subcomponent_analysis_confirm import (
    SubcomponentsConfirm,
)


@pytest.mark.django_db
class TestSubcomponentsConfirm(StepTest):
    step_under_test = SubcomponentsConfirm

    @pytest.fixture()
    def up_to_date_workflow(self, analysis_workflow_main_flow_complete):
        return analysis_workflow_main_flow_complete

    @pytest.fixture()
    def workflow_with_completed_step(self, analysis_workflow_with_subcomponent_labels_and_client_time_added):
        return analysis_workflow_with_subcomponent_labels_and_client_time_added

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
