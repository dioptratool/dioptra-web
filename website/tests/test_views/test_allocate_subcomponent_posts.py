import pytest
from django.urls import reverse

from website.models import Analysis
from website.models.cost_line_item import CostLineItem
from website.models.cost_type import ProgramCost
from website.models.subcomponent import SubcomponentCostAllocation
from website.tests.factories import SubcomponentCostAnalysisFactory
from website.workflows import AnalysisWorkflow


@pytest.mark.django_db
class TestAllocateSubcomponentFormSubmissions:
    def _setup_subcomponents(self, analysis):
        """
        Attaches a subcomponent analysis to the first intervention instance and
        returns (intervention_instance, subcomponent_analysis, grant, cost_line_items).
        """
        intervention_instance = analysis.interventioninstance_set.first()
        subcomponent_analysis = SubcomponentCostAnalysisFactory(
            intervention_instance=intervention_instance,
            subcomponent_labels=["Treatment", "Outreach"],
        )
        cost_type_category_grant = analysis.cost_type_category_grants.filter(
            cost_type_category__cost_type__type=ProgramCost.id
        ).first()
        grant = cost_type_category_grant.grant
        cost_line_items = CostLineItem.objects.filter(
            analysis=analysis,
            grant_code=grant,
            config__cost_type=cost_type_category_grant.cost_type_category.cost_type,
        )
        return intervention_instance, subcomponent_analysis, grant, cost_line_items

    def _url(self, analysis, intervention_instance, grant):
        return reverse(
            "analysis-allocate-subcomponents-intervention-grant",
            kwargs={
                "pk": analysis.pk,
                "intervention_instance_pk": intervention_instance.pk,
                "grant": grant,
            },
        )

    def test_subcomponent_allocations_save(
        self,
        analysis_workflow_with_allocations,
        client_with_admin,
    ):
        analysis = analysis_workflow_with_allocations.analysis
        intervention_instance, subcomponent_analysis, grant, cost_line_items = self._setup_subcomponents(
            analysis
        )

        data = {}
        for cli in cost_line_items:
            data[f"cost_line_item_subcomponent_allocation_{cli.id}_{subcomponent_analysis.id}_0"] = "60"
            data[f"cost_line_item_subcomponent_allocation_{cli.id}_{subcomponent_analysis.id}_1"] = "40"

        response = client_with_admin.post(
            self._url(analysis, intervention_instance, grant),
            data=data,
            follow=True,
        )

        assert response.status_code == 200
        assert (
            SubcomponentCostAllocation.objects.filter(
                subcomponent_analysis=subcomponent_analysis,
                cli_config__cost_line_item__in=cost_line_items,
                allocations={"0": "60", "1": "40"},
                skipped=False,
            ).count()
            == cost_line_items.count()
        )

    def test_subcomponent_allocations_must_total_100(
        self,
        analysis_workflow_with_allocations,
        client_with_admin,
    ):
        analysis = analysis_workflow_with_allocations.analysis
        intervention_instance, subcomponent_analysis, grant, cost_line_items = self._setup_subcomponents(
            analysis
        )
        cost_line_item = cost_line_items.first()

        data = {
            f"cost_line_item_subcomponent_allocation_{cost_line_item.id}_{subcomponent_analysis.id}_0": "60",
            f"cost_line_item_subcomponent_allocation_{cost_line_item.id}_{subcomponent_analysis.id}_1": "30",
        }

        response = client_with_admin.post(
            self._url(analysis, intervention_instance, grant),
            data=data,
        )

        assert response.status_code == 200
        assert not SubcomponentCostAllocation.objects.filter(
            subcomponent_analysis=subcomponent_analysis,
            cli_config=cost_line_item.config,
        ).exists()
        assert b"Allocations must total 100%" in response.content

    def test_skip_excludes_cost_line_item(
        self,
        analysis_workflow_with_allocations,
        client_with_admin,
    ):
        analysis = analysis_workflow_with_allocations.analysis
        intervention_instance, subcomponent_analysis, grant, cost_line_items = self._setup_subcomponents(
            analysis
        )
        cost_line_item = cost_line_items.first()

        data = {
            f"cost_line_item_subcomponent_allocation_{cost_line_item.id}_{subcomponent_analysis.id}_skip": (
                "on"
            ),
        }

        response = client_with_admin.post(
            self._url(analysis, intervention_instance, grant),
            data=data,
            follow=True,
        )

        assert response.status_code == 200
        allocation = SubcomponentCostAllocation.objects.get(
            subcomponent_analysis=subcomponent_analysis,
            cli_config=cost_line_item.config,
        )
        assert allocation.skipped
        assert allocation.allocations == {}

    def test_allocate_completes_without_subcomponents_but_new_step_does_not(
        self,
        analysis_workflow_with_allocations,
    ):
        """
        Positive intervention allocations no longer require subcomponent data for
        the allocate step; that requirement moved to the allocate-subcomponents step.
        """
        analysis = analysis_workflow_with_allocations.analysis
        intervention_instance, _, _, _ = self._setup_subcomponents(analysis)

        workflow = AnalysisWorkflow(Analysis.objects.get(pk=analysis.pk))
        assert workflow.get_step("allocate").is_complete

        subcomponents_step = workflow.get_step("allocate-subcomponents")
        assert subcomponents_step.is_enabled
        assert not subcomponents_step.is_complete
        substep = next(
            step
            for step in subcomponents_step.steps
            if step.intervention_instance.id == intervention_instance.id
        )
        assert not substep.is_complete
