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

    def test_subcomponent_allocations_cannot_exceed_100(
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
            f"cost_line_item_subcomponent_allocation_{cost_line_item.id}_{subcomponent_analysis.id}_1": "50",
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
        assert b"Allocations cannot total more than 100%" in response.content

    def test_partial_allocation_saves_and_substep_stays_incomplete(
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
            f"cost_line_item_subcomponent_allocation_{cost_line_item.id}_{subcomponent_analysis.id}_0": "40",
            f"cost_line_item_subcomponent_allocation_{cost_line_item.id}_{subcomponent_analysis.id}_1": "",
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
        assert allocation.allocations == {"0": "40"}
        assert allocation.skipped is False

        workflow = AnalysisWorkflow(Analysis.objects.get(pk=analysis.pk))
        substep = next(
            step
            for step in workflow.get_step("allocate-subcomponents").steps
            if step.intervention_instance.id == intervention_instance.id and step.grant == grant
        )
        assert not substep.is_complete

    def test_blank_row_saves_empty_and_clears_previous_values(
        self,
        analysis_workflow_with_allocations,
        client_with_admin,
    ):
        analysis = analysis_workflow_with_allocations.analysis
        intervention_instance, subcomponent_analysis, grant, cost_line_items = self._setup_subcomponents(
            analysis
        )
        cost_line_item = cost_line_items.first()
        SubcomponentCostAllocation.objects.create(
            subcomponent_analysis=subcomponent_analysis,
            cli_config=cost_line_item.config,
            allocations={"0": "60", "1": "40"},
            skipped=False,
        )

        data = {
            f"cost_line_item_subcomponent_allocation_{cost_line_item.id}_{subcomponent_analysis.id}_0": "",
            f"cost_line_item_subcomponent_allocation_{cost_line_item.id}_{subcomponent_analysis.id}_1": "",
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
        assert allocation.allocations == {}
        assert allocation.skipped is False

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

    def test_unskip_persists_with_blank_allocations(
        self,
        analysis_workflow_with_allocations,
        client_with_admin,
    ):
        """
        Un-skipping re-enables the (blank) inputs; the resulting POST has no
        _skip key and all-blank values, which must persist skipped=False.
        """
        analysis = analysis_workflow_with_allocations.analysis
        intervention_instance, subcomponent_analysis, grant, cost_line_items = self._setup_subcomponents(
            analysis
        )
        cost_line_item = cost_line_items.first()
        SubcomponentCostAllocation.objects.create(
            subcomponent_analysis=subcomponent_analysis,
            cli_config=cost_line_item.config,
            allocations={},
            skipped=True,
        )

        data = {
            f"cost_line_item_subcomponent_allocation_{cost_line_item.id}_{subcomponent_analysis.id}_0": "",
            f"cost_line_item_subcomponent_allocation_{cost_line_item.id}_{subcomponent_analysis.id}_1": "",
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
        assert allocation.skipped is False
        assert allocation.allocations == {}

    def test_unskip_with_values_saves_allocations(
        self,
        analysis_workflow_with_allocations,
        client_with_admin,
    ):
        analysis = analysis_workflow_with_allocations.analysis
        intervention_instance, subcomponent_analysis, grant, cost_line_items = self._setup_subcomponents(
            analysis
        )
        cost_line_item = cost_line_items.first()
        SubcomponentCostAllocation.objects.create(
            subcomponent_analysis=subcomponent_analysis,
            cli_config=cost_line_item.config,
            allocations={},
            skipped=True,
        )

        data = {
            f"cost_line_item_subcomponent_allocation_{cost_line_item.id}_{subcomponent_analysis.id}_0": "70",
            f"cost_line_item_subcomponent_allocation_{cost_line_item.id}_{subcomponent_analysis.id}_1": "30",
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
        assert allocation.skipped is False
        assert allocation.allocations == {"0": "70", "1": "30"}

    def test_page_renders_skip_and_skipped_labels(
        self,
        analysis_workflow_with_allocations,
        client_with_admin,
    ):
        analysis = analysis_workflow_with_allocations.analysis
        intervention_instance, subcomponent_analysis, grant, cost_line_items = self._setup_subcomponents(
            analysis
        )

        response = client_with_admin.get(self._url(analysis, intervention_instance, grant))

        assert response.status_code == 200
        content = response.content.decode()
        assert ">Skip</label>" in content
        assert "analysis-table__subcomponent-skip__label--skipped" in content
        assert ">Skipped</label>" in content

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
