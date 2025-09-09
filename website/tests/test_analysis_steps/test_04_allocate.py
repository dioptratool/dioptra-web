import pytest

from website.workflows.analysis.steps.allocate import Allocate
from .common import StepTest


@pytest.mark.django_db
class TestAllocate(StepTest):
    step_under_test = Allocate

    @pytest.fixture()
    def up_to_date_workflow(self, analysis_workflow_with_confirmed_categories_cost_line_item):
        return analysis_workflow_with_confirmed_categories_cost_line_item

    @pytest.fixture()
    def workflow_with_completed_step(self, analysis_workflow_with_allocations):
        return analysis_workflow_with_allocations
