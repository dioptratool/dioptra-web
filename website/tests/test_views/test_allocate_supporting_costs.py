from decimal import Decimal

import pytest
from django.urls import reverse

from website.models import CostLineItemInterventionAllocation
from website.tests.factories import CostLineItemConfigFactory, CostLineItemFactory
from website.workflows import AnalysisWorkflow

GRANT = "DF119"


def supporting_costs_url(analysis):
    return reverse(
        "analysis-allocate-supporting-costs",
        kwargs={"pk": analysis.pk, "grant": GRANT},
    )


def add_special_cost_line_item(analysis):
    cost_line_item = CostLineItemFactory(
        analysis=analysis,
        budget_line_description="My Special Country Line Item",
        grant_code=GRANT,
        total_cost=14000.00,
        is_special_lump_sum=True,
    )
    CostLineItemConfigFactory(cost_line_item=cost_line_item, cost_type=None, category=None)
    return cost_line_item


def supporting_substeps(analysis):
    workflow = AnalysisWorkflow(analysis)
    return [
        substep
        for substep in workflow.get_step("allocate").steps
        if substep.name == "allocate-supporting-costs" and substep.grant_code == GRANT
    ]


@pytest.mark.django_db
class TestAllocateSupportingCostsSave:
    def test_post_persists_allocations(self, client_with_admin, analysis_workflow_with_allocations):
        analysis = analysis_workflow_with_allocations.analysis
        special = add_special_cost_line_item(analysis)
        instances = list(analysis.interventioninstance_set.all())
        data = {f"cost_line_item_allocation_{special.id}_{instance.id}": "10" for instance in instances}

        response = client_with_admin.post(supporting_costs_url(analysis), data=data, follow=True)

        assert response.status_code == 200
        allocations = CostLineItemInterventionAllocation.objects.filter(cli_config=special.config)
        assert allocations.count() == len(instances)
        assert all(allocation.allocation == Decimal("10") for allocation in allocations)
        substeps = supporting_substeps(analysis)
        assert substeps
        assert all(substep.is_complete for substep in substeps)

    def test_blank_post_stores_none_and_substep_stays_incomplete(
        self, client_with_admin, analysis_workflow_with_allocations
    ):
        analysis = analysis_workflow_with_allocations.analysis
        special = add_special_cost_line_item(analysis)
        instances = list(analysis.interventioninstance_set.all())
        data = {f"cost_line_item_allocation_{special.id}_{instance.id}": "" for instance in instances}

        response = client_with_admin.post(supporting_costs_url(analysis), data=data, follow=True)

        assert response.status_code == 200
        allocations = CostLineItemInterventionAllocation.objects.filter(cli_config=special.config)
        assert allocations.count() == len(instances)
        assert all(allocation.allocation is None for allocation in allocations)
        assert all(not substep.is_complete for substep in supporting_substeps(analysis))

    def test_page_renders_saved_values(self, client_with_admin, analysis_workflow_with_allocations):
        analysis = analysis_workflow_with_allocations.analysis
        special = add_special_cost_line_item(analysis)
        instances = list(analysis.interventioninstance_set.all())
        data = {f"cost_line_item_allocation_{special.id}_{instance.id}": "12.5" for instance in instances}
        client_with_admin.post(supporting_costs_url(analysis), data=data)

        response = client_with_admin.get(supporting_costs_url(analysis))

        assert response.status_code == 200
        content = response.content.decode()
        assert "My Special Country Line Item" in content
        assert "12.5" in content
