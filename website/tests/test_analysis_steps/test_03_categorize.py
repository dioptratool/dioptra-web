import pytest

from website.workflows.analysis.steps.categorize import Categorize
from .common import StepTest


@pytest.mark.django_db
class TestCategorize(StepTest):
    step_under_test = Categorize

    @pytest.fixture()
    def up_to_date_workflow(self, analysis_workflow_with_loaddata_complete):
        return analysis_workflow_with_loaddata_complete

    @pytest.fixture()
    def workflow_with_completed_step(self, analysis_workflow_with_confirmed_categories_cost_line_item):
        return analysis_workflow_with_confirmed_categories_cost_line_item

    def test_invalidate_step_works(self, workflow_with_completed_step):
        workflow_with_completed_step.invalidate_step(step_name=self.step_under_test.name)
        assert (
            workflow_with_completed_step.get_last_complete().parent.name == self.step_under_test.name
        ), "There is no invalidation logic for this step so nothing should change."
