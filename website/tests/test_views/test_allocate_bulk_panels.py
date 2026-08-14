from decimal import Decimal

import pytest
from django.urls import reverse

from website.models import CostType
from website.models.cost_line_item import CostLineItemInterventionAllocation
from website.models.cost_type import ProgramCost, Support
from website.models.subcomponent import SubcomponentCostAllocation
from website.tests.factories import (
    CostLineItemConfigFactory,
    CostLineItemFactory,
    SubcomponentCostAllocationFactory,
    SubcomponentCostAnalysisFactory,
)


@pytest.mark.django_db
class TestAllocateInterventionBulkPanel:
    def _setup(self, analysis):
        cost_type_category_grant = analysis.cost_type_category_grants.filter(
            cost_type_category__cost_type__type=ProgramCost.id
        ).first()
        cost_line_items = list(
            analysis.cost_line_items.filter(
                grant_code=cost_type_category_grant.grant,
                config__cost_type=cost_type_category_grant.cost_type_category.cost_type,
            )
        )
        url = reverse(
            "analysis-allocate-cost_type-grant-bulk",
            kwargs={
                "pk": analysis.pk,
                "cost_type_pk": cost_type_category_grant.cost_type_category.cost_type.pk,
                "grant": cost_type_category_grant.grant,
            },
        )
        return url, cost_line_items

    def test_get_renders_panel(
        self,
        analysis_workflow_with_confirmed_categories_cost_line_item,
        client_with_admin,
    ):
        analysis = analysis_workflow_with_confirmed_categories_cost_line_item.analysis
        url, cost_line_items = self._setup(analysis)
        config_ids = ",".join(str(cli.config.id) for cli in cost_line_items)

        response = client_with_admin.get(f"{url}?config_ids={config_ids}")

        assert response.status_code == 200
        for intervention_instance in analysis.interventioninstance_set.all():
            assert f"allocation_{intervention_instance.id}".encode() in response.content

    def test_post_sets_allocations_and_note(
        self,
        analysis_workflow_with_confirmed_categories_cost_line_item,
        client_with_admin,
    ):
        analysis = analysis_workflow_with_confirmed_categories_cost_line_item.analysis
        url, cost_line_items = self._setup(analysis)
        intervention_instances = list(analysis.interventioninstance_set.all())
        allocation = Decimal(100 // len(intervention_instances))

        data = {
            "config_ids": [str(cli.config.id) for cli in cost_line_items],
            "notes": "From project budget",
        }
        for intervention_instance in intervention_instances:
            data[f"allocation_{intervention_instance.id}"] = str(allocation)

        response = client_with_admin.post(url, data=data)

        assert response.status_code == 200
        for cli in cost_line_items:
            cli.refresh_from_db()
            assert cli.note == "From project budget"
            allocations = CostLineItemInterventionAllocation.objects.filter(cli_config=cli.config)
            assert allocations.count() == len(intervention_instances)
            for each_allocation in allocations:
                assert each_allocation.allocation == allocation

    def test_post_ignores_spurious_characters(
        self,
        analysis_workflow_with_confirmed_categories_cost_line_item,
        client_with_admin,
    ):
        analysis = analysis_workflow_with_confirmed_categories_cost_line_item.analysis
        url, cost_line_items = self._setup(analysis)
        intervention_instances = list(analysis.interventioninstance_set.all())
        allocation = Decimal(100 // len(intervention_instances))

        data = {
            "config_ids": [str(cli.config.id) for cli in cost_line_items],
        }
        for intervention_instance in intervention_instances:
            data[f"allocation_{intervention_instance.id}"] = f" {allocation}% "

        response = client_with_admin.post(url, data=data)

        assert response.status_code == 200
        for cli in cost_line_items:
            allocations = CostLineItemInterventionAllocation.objects.filter(cli_config=cli.config)
            assert allocations.count() == len(intervention_instances)
            for each_allocation in allocations:
                assert each_allocation.allocation == allocation

    def test_post_rejects_invalid_allocation(
        self,
        analysis_workflow_with_confirmed_categories_cost_line_item,
        client_with_admin,
    ):
        analysis = analysis_workflow_with_confirmed_categories_cost_line_item.analysis
        url, cost_line_items = self._setup(analysis)

        data = {
            "config_ids": [str(cli.config.id) for cli in cost_line_items],
        }
        for intervention_instance in analysis.interventioninstance_set.all():
            data[f"allocation_{intervention_instance.id}"] = "150"

        response = client_with_admin.post(url, data=data)

        assert response.status_code == 200
        for cli in cost_line_items:
            assert not CostLineItemInterventionAllocation.objects.filter(cli_config=cli.config).exists()

    def test_configs_outside_the_step_are_ignored(
        self,
        analysis_workflow_with_confirmed_categories_cost_line_item,
        client_with_admin,
    ):
        analysis = analysis_workflow_with_confirmed_categories_cost_line_item.analysis
        url, cost_line_items = self._setup(analysis)
        support_config = CostLineItemConfigFactory(
            cost_line_item=CostLineItemFactory(
                analysis=analysis,
                grant_code=cost_line_items[0].grant_code,
            ),
            cost_type=CostType.objects.get(type=Support.id),
        )

        data = {
            "config_ids": [str(support_config.id)],
        }
        for intervention_instance in analysis.interventioninstance_set.all():
            data[f"allocation_{intervention_instance.id}"] = "10"

        response = client_with_admin.post(url, data=data)

        assert response.status_code == 200
        assert not CostLineItemInterventionAllocation.objects.filter(cli_config=support_config).exists()

    def test_zero_allocation_deletes_subcomponent_allocations(
        self,
        analysis_workflow_with_confirmed_categories_cost_line_item,
        client_with_admin,
    ):
        analysis = analysis_workflow_with_confirmed_categories_cost_line_item.analysis
        url, cost_line_items = self._setup(analysis)
        subcomponent_analysis = SubcomponentCostAnalysisFactory(
            intervention_instance=analysis.interventioninstance_set.first(),
            subcomponent_labels=["Treatment", "Outreach"],
        )
        for cli in cost_line_items:
            SubcomponentCostAllocationFactory(
                subcomponent_analysis=subcomponent_analysis,
                cli_config=cli.config,
                allocations={"0": "60", "1": "40"},
            )

        data = {
            "config_ids": [str(cli.config.id) for cli in cost_line_items],
        }
        for intervention_instance in analysis.interventioninstance_set.all():
            data[f"allocation_{intervention_instance.id}"] = "0"

        response = client_with_admin.post(url, data=data)

        assert response.status_code == 200
        assert not SubcomponentCostAllocation.objects.filter(
            subcomponent_analysis=subcomponent_analysis,
            cli_config__in=[cli.config for cli in cost_line_items],
        ).exists()


@pytest.mark.django_db
class TestAllocateSubcomponentsBulkPanel:
    def _setup(self, analysis):
        intervention_instance = analysis.interventioninstance_set.first()
        subcomponent_analysis = SubcomponentCostAnalysisFactory(
            intervention_instance=intervention_instance,
            subcomponent_labels=["Treatment", "Outreach"],
        )
        cost_type_category_grant = analysis.cost_type_category_grants.filter(
            cost_type_category__cost_type__type=ProgramCost.id
        ).first()
        cost_line_items = list(
            analysis.cost_line_items.filter(
                grant_code=cost_type_category_grant.grant,
                config__cost_type=cost_type_category_grant.cost_type_category.cost_type,
            )
        )
        url = reverse(
            "analysis-allocate-subcomponents-intervention-grant-bulk",
            kwargs={
                "pk": analysis.pk,
                "intervention_instance_pk": intervention_instance.pk,
                "grant": cost_type_category_grant.grant,
            },
        )
        return url, subcomponent_analysis, cost_line_items

    def test_get_renders_panel(
        self,
        analysis_workflow_with_allocations,
        client_with_admin,
    ):
        analysis = analysis_workflow_with_allocations.analysis
        url, subcomponent_analysis, cost_line_items = self._setup(analysis)
        config_ids = ",".join(str(cli.config.id) for cli in cost_line_items)

        response = client_with_admin.get(f"{url}?config_ids={config_ids}")

        assert response.status_code == 200
        assert b"Treatment" in response.content
        assert b"Outreach" in response.content

    def test_post_sets_subcomponent_allocations(
        self,
        analysis_workflow_with_allocations,
        client_with_admin,
    ):
        analysis = analysis_workflow_with_allocations.analysis
        url, subcomponent_analysis, cost_line_items = self._setup(analysis)

        data = {
            "config_ids": [str(cli.config.id) for cli in cost_line_items],
            "subcomponent_allocation_0": "60",
            "subcomponent_allocation_1": "40",
        }

        response = client_with_admin.post(url, data=data)

        assert response.status_code == 200
        assert SubcomponentCostAllocation.objects.filter(
            subcomponent_analysis=subcomponent_analysis,
            cli_config__cost_line_item__in=cost_line_items,
            allocations={"0": "60", "1": "40"},
            skipped=False,
        ).count() == len(cost_line_items)

    def test_post_ignores_spurious_characters(
        self,
        analysis_workflow_with_allocations,
        client_with_admin,
    ):
        analysis = analysis_workflow_with_allocations.analysis
        url, subcomponent_analysis, cost_line_items = self._setup(analysis)

        data = {
            "config_ids": [str(cli.config.id) for cli in cost_line_items],
            "subcomponent_allocation_0": "60%",
            "subcomponent_allocation_1": " 40% ",
        }

        response = client_with_admin.post(url, data=data)

        assert response.status_code == 200
        assert SubcomponentCostAllocation.objects.filter(
            subcomponent_analysis=subcomponent_analysis,
            cli_config__cost_line_item__in=cost_line_items,
            allocations={"0": "60", "1": "40"},
            skipped=False,
        ).count() == len(cost_line_items)

    def test_configs_without_positive_allocation_are_ignored(
        self,
        analysis_workflow_with_allocations,
        client_with_admin,
    ):
        analysis = analysis_workflow_with_allocations.analysis
        url, subcomponent_analysis, cost_line_items = self._setup(analysis)
        # A program-cost row with no intervention allocation is not shown on the
        # step and must not be reachable through the bulk panel.
        unallocated_config = CostLineItemConfigFactory(
            cost_line_item=CostLineItemFactory(
                analysis=analysis,
                grant_code=cost_line_items[0].grant_code,
            ),
        )

        data = {
            "config_ids": [str(unallocated_config.id)],
            "subcomponent_allocation_0": "60",
            "subcomponent_allocation_1": "40",
        }

        response = client_with_admin.post(url, data=data)

        assert response.status_code == 200
        assert not SubcomponentCostAllocation.objects.filter(cli_config=unallocated_config).exists()

    def test_post_rejects_totals_not_equal_to_100(
        self,
        analysis_workflow_with_allocations,
        client_with_admin,
    ):
        analysis = analysis_workflow_with_allocations.analysis
        url, subcomponent_analysis, cost_line_items = self._setup(analysis)

        data = {
            "config_ids": [str(cli.config.id) for cli in cost_line_items],
            "subcomponent_allocation_0": "60",
            "subcomponent_allocation_1": "30",
        }

        response = client_with_admin.post(url, data=data)

        assert response.status_code == 200
        assert not SubcomponentCostAllocation.objects.filter(
            subcomponent_analysis=subcomponent_analysis,
        ).exists()
        assert b"Must Equal 100%" in response.content
