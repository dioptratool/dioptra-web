import pytest

from website.workflows.analysis.steps.load_data import LoadData
from .common import StepTest


@pytest.mark.django_db
class TestLoadDataStep(StepTest):
    step_under_test = LoadData

    @pytest.fixture()
    def up_to_date_workflow(self, analysis_workflow_with_define_complete):
        return analysis_workflow_with_define_complete

    @pytest.fixture()
    def workflow_with_completed_step(self, analysis_workflow_with_loaddata_complete):
        return analysis_workflow_with_loaddata_complete

    def test_step_is_not_marked_complete_correctly(
        self,
        up_to_date_workflow,
    ):
        """
        The step must have cost line items and the Analysis must not be marked `needs_transaction_resync`
        """
        # A step without cost line items:
        step = self.step_under_test(workflow=up_to_date_workflow)
        assert not step.is_complete

        step.analysis.needs_transaction_resync = True
        assert not step.is_complete

    @pytest.mark.skip(
        reason="This is an example of where caching causes problems.  Disabled to revisit later."
    )
    def test_step_is_marked_complete_correctly_when_property_changes(self, workflow_with_completed_step):
        # A step with cost line items:
        step = self.step_under_test(workflow=workflow_with_completed_step)
        step.analysis.needs_transaction_resync = True
        assert not step.is_complete

        step.analysis.needs_transaction_resync = False
        step.analysis.save()
        assert step.is_complete

    def test_get_href_returns_a_url(self, up_to_date_workflow):
        step = self.step_under_test(workflow=up_to_date_workflow)
        assert step.get_href()
        assert step.get_href() == f"/analysis/{step.workflow.analysis.pk}/load-data/"
