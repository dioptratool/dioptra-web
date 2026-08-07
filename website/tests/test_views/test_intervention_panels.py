import pytest
from django.urls import reverse

from website.models import (
    AnalysisCostType,
    CostLineItem,
    CostLineItemInterventionAllocation,
    InterventionInstance,
    SubcomponentCostAnalysis,
)
from website.tests.factories import (
    AnalysisFactory,
    CostLineItemConfigFactory,
    CostLineItemFactory,
    CostLineItemInterventionAllocationFactory,
    InterventionFactory,
    InterventionInstanceFactory,
    SubcomponentCostAnalysisFactory,
    UserFactory,
)
from website.workflows import AnalysisWorkflow


def changelist_url(analysis):
    return reverse("ombucore.admin:website_interventioninstance_changelist") + f"?analysis={analysis.pk}"


def add_url(analysis):
    return reverse("ombucore.admin:website_interventioninstance_add") + f"?analysis={analysis.pk}"


def change_url(instance):
    return reverse("ombucore.admin:website_interventioninstance_change", args=[instance.pk])


def delete_url(instance):
    return reverse("ombucore.admin:website_interventioninstance_delete", args=[instance.pk])


def reorder_url(analysis):
    return reverse("ombucore.admin:website_interventioninstance_reorder") + f"?analysis={analysis.pk}"


def client_time_item(analysis, intervention_instance, description, others=()):
    """
    Mirror ClientTimeCostLineItemForm.save(): one 100% allocation to the chosen
    intervention, 0% rows for every other intervention.
    """
    cost_line_item = CostLineItemFactory(
        analysis=analysis,
        budget_line_description=description,
        grant_code="DF119",
    )
    config = CostLineItemConfigFactory(
        cost_line_item=cost_line_item,
        cost_type=None,
        category=None,
        analysis_cost_type=AnalysisCostType.CLIENT_TIME,
    )
    CostLineItemInterventionAllocationFactory(
        cli_config=config,
        intervention_instance=intervention_instance,
        allocation=100,
    )
    for other in others:
        CostLineItemInterventionAllocationFactory(
            cli_config=config,
            intervention_instance=other,
            allocation=0,
        )
    return cost_line_item


@pytest.mark.django_db
class TestInterventionInstanceChangelist:
    def test_requires_analysis_parameter(self, client_with_admin, defaults):
        AnalysisFactory()
        url = reverse("ombucore.admin:website_interventioninstance_changelist")
        response = client_with_admin.get(url)
        assert response.status_code == 404

    def test_lists_only_the_analysis_interventions(self, client_with_admin, defaults):
        analysis = AnalysisFactory()
        intervention = InterventionFactory(output_metrics=["NumberOfChildren"])
        mine = InterventionInstanceFactory(
            analysis=analysis,
            intervention=intervention,
            label="Mine",
            parameters={"number_of_children": 4444},
        )
        other = InterventionInstanceFactory(label="Somebody Elses")

        response = client_with_admin.get(changelist_url(analysis))

        assert response.status_code == 200
        content = response.content.decode()
        assert "<form" not in content
        assert mine.label in content
        assert intervention.name in content
        assert "Number of Children" in content
        assert "4,444.00" in content
        assert delete_url(mine) in content
        assert other.label not in content

    def test_owner_has_access(self, client, defaults):
        owner = UserFactory()
        analysis = AnalysisFactory(owner=owner)
        client.force_login(owner)

        response = client.get(changelist_url(analysis))

        assert response.status_code == 200

    def test_unrelated_basic_user_is_denied(self, client, defaults):
        analysis = AnalysisFactory()
        client.force_login(UserFactory())

        response = client.get(changelist_url(analysis))

        assert response.status_code == 403

    def test_shows_delete_after_data_is_loaded(
        self, client_with_admin, analysis_workflow_with_loaddata_complete
    ):
        analysis = analysis_workflow_with_loaddata_complete.analysis
        instances = list(analysis.interventioninstance_set.all())

        response = client_with_admin.get(changelist_url(analysis))

        assert response.status_code == 200
        content = response.content.decode()
        for instance in instances:
            assert delete_url(instance) in content
        assert ">Open</a>" in content


@pytest.mark.django_db
class TestInterventionInstanceAdd:
    def test_add_creates_intervention_instance(self, client_with_admin, defaults):
        analysis = AnalysisFactory()
        intervention = InterventionFactory(output_metrics=["NumberOfTeacherDaysOfTraining"])

        response = client_with_admin.post(
            add_url(analysis),
            {
                "intervention": intervention.pk,
                "label": "Added via panel",
                "parameter__number_of_teachers": "5",
                "parameter__number_of_days_of_training": "3",
            },
        )

        assert response.status_code == 200
        instance = analysis.interventioninstance_set.get()
        assert instance.label == "Added via panel"
        assert instance.parameters == {
            "number_of_teachers": 5.0,
            "number_of_days_of_training": 3.0,
        }

    def test_add_requires_analysis_permission(self, client, defaults):
        analysis = AnalysisFactory()
        intervention = InterventionFactory()
        client.force_login(UserFactory())

        response = client.post(add_url(analysis), {"intervention": intervention.pk})

        assert response.status_code == 403
        assert not analysis.interventioninstance_set.exists()


@pytest.mark.django_db
class TestInterventionInstanceChange:
    def test_change_updates_parameters(self, client_with_admin, defaults):
        intervention = InterventionFactory(output_metrics=["NumberOfTeacherDaysOfTraining"])
        instance = InterventionInstanceFactory(
            intervention=intervention,
            parameters={"number_of_teachers": 1.0, "number_of_days_of_training": 1.0},
        )

        response = client_with_admin.post(
            change_url(instance),
            {
                "intervention": intervention.pk,
                "label": "Updated",
                "parameter__number_of_teachers": "7",
                "parameter__number_of_days_of_training": "2",
            },
        )

        assert response.status_code == 200
        instance.refresh_from_db()
        assert instance.label == "Updated"
        assert instance.parameters == {
            "number_of_teachers": 7.0,
            "number_of_days_of_training": 2.0,
        }

    def test_change_requires_analysis_permission(self, client, defaults):
        instance = InterventionInstanceFactory()
        client.force_login(UserFactory())

        response = client.get(change_url(instance))

        assert response.status_code == 403

    def test_change_panel_shows_wipe_warning_with_dependent_data(
        self, client_with_admin, analysis_workflow_with_allocations
    ):
        analysis = analysis_workflow_with_allocations.analysis
        instance = analysis.interventioninstance_set.first()

        response = client_with_admin.get(change_url(instance))

        assert response.status_code == 200
        content = response.content.decode()
        assert "js-intervention-change-warning" in content
        assert f'data-initial="{instance.intervention_id}"' in content

    def test_change_panel_shows_wipe_warning_with_subcomponents_only(self, client_with_admin, defaults):
        instance = InterventionInstanceFactory()
        SubcomponentCostAnalysisFactory(
            intervention_instance=instance,
            subcomponent_labels=["Setup", "Delivery"],
        )

        response = client_with_admin.get(change_url(instance))

        assert response.status_code == 200
        assert "js-intervention-change-warning" in response.content.decode()

    def test_change_panel_omits_wipe_warning_without_dependent_data(self, client_with_admin, defaults):
        instance = InterventionInstanceFactory()

        response = client_with_admin.get(change_url(instance))

        assert response.status_code == 200
        assert "js-intervention-change-warning" not in response.content.decode()


@pytest.mark.django_db
class TestInterventionInstanceDelete:
    def test_delete_removes_intervention_instance(self, client_with_admin, defaults):
        instance = InterventionInstanceFactory()

        response = client_with_admin.get(f"{delete_url(instance)}?confirmed")

        assert response.status_code == 200
        assert not InterventionInstance.objects.filter(pk=instance.pk).exists()

    def test_intervention_can_be_deleted_after_data_is_loaded(
        self, client_with_admin, analysis_workflow_with_loaddata_complete
    ):
        analysis = analysis_workflow_with_loaddata_complete.analysis
        instance = analysis.interventioninstance_set.first()

        response = client_with_admin.get(f"{delete_url(instance)}?confirmed")

        assert response.status_code == 200
        assert not InterventionInstance.objects.filter(pk=instance.pk).exists()

    def test_post_load_delete_cascades_and_recalculates(
        self, client_with_admin, analysis_workflow_with_allocations
    ):
        analysis = analysis_workflow_with_allocations.analysis
        instances = list(analysis.interventioninstance_set.all())
        target, survivors = instances[0], instances[1:]
        SubcomponentCostAnalysisFactory(
            intervention_instance=target,
            subcomponent_labels=["Setup", "Delivery"],
        )
        assert str(target.pk) in analysis.output_costs

        response = client_with_admin.get(f"{delete_url(target)}?confirmed")

        assert response.status_code == 200
        assert not InterventionInstance.objects.filter(pk=target.pk).exists()
        assert not CostLineItemInterventionAllocation.objects.filter(
            intervention_instance_id=target.pk
        ).exists()
        assert not SubcomponentCostAnalysis.objects.filter(intervention_instance_id=target.pk).exists()
        analysis.refresh_from_db()
        assert str(target.pk) not in analysis.output_costs
        for survivor in survivors:
            assert CostLineItemInterventionAllocation.objects.filter(intervention_instance=survivor).exists()

    def test_post_load_delete_removes_orphaned_client_time_items(
        self, client_with_admin, analysis_workflow_with_allocations
    ):
        analysis = analysis_workflow_with_allocations.analysis
        instances = list(analysis.interventioninstance_set.all())
        target, survivors = instances[0], instances[1:]
        orphan = client_time_item(analysis, target, "Orphaned Client Time", others=survivors)
        keeper = None
        if survivors:
            keeper = client_time_item(
                analysis,
                survivors[0],
                "Surviving Client Time",
                others=[target, *survivors[1:]],
            )

        response = client_with_admin.get(f"{delete_url(target)}?confirmed")

        assert response.status_code == 200
        assert not CostLineItem.objects.filter(pk=orphan.pk).exists()
        if keeper:
            assert CostLineItem.objects.filter(pk=keeper.pk).exists()

    def test_add_other_costs_page_renders_after_intervention_deleted(
        self, client_with_admin, analysis_workflow_with_allocations
    ):
        analysis = analysis_workflow_with_allocations.analysis
        instances = list(analysis.interventioninstance_set.all())
        target, survivors = instances[0], instances[1:]
        client_time_item(analysis, target, "Orphaned Client Time", others=survivors)
        client_with_admin.get(f"{delete_url(target)}?confirmed")

        response = client_with_admin.get(
            reverse(
                "analysis-add-other-costs-detail",
                kwargs={"pk": analysis.pk, "cost_type": int(AnalysisCostType.CLIENT_TIME)},
            )
        )

        if survivors:
            assert response.status_code == 200
            assert "Orphaned Client Time" not in response.content.decode()
        else:
            # Deleting the only intervention rewinds the workflow, so the step
            # guard redirects instead of rendering.
            assert response.status_code == 302

    def test_deleting_last_intervention_post_load_succeeds_and_rewinds_workflow(
        self, client_with_admin, analysis_workflow_with_allocations
    ):
        analysis = analysis_workflow_with_allocations.analysis

        for instance in list(analysis.interventioninstance_set.all()):
            response = client_with_admin.get(f"{delete_url(instance)}?confirmed")
            assert response.status_code == 200

        assert not analysis.interventioninstance_set.exists()
        analysis.refresh_from_db()
        assert analysis.output_costs == {}
        workflow = AnalysisWorkflow(analysis)
        assert not workflow.get_step("interventions").is_complete
        assert not workflow.get_step("load-data").is_complete
        # Loaded data survives; re-adding an intervention restores the workflow.
        assert analysis.cost_line_items.exists()

    def test_delete_confirmation_shows_post_load_warning(
        self, client_with_admin, analysis_workflow_with_loaddata_complete
    ):
        analysis = analysis_workflow_with_loaddata_complete.analysis
        instance = analysis.interventioninstance_set.first()
        others = list(analysis.interventioninstance_set.exclude(pk=instance.pk))
        SubcomponentCostAnalysisFactory(
            intervention_instance=instance,
            subcomponent_labels=["Setup", "Delivery"],
        )
        client_time_item(analysis, instance, "Named Client Time Item", others=others)

        response = client_with_admin.get(delete_url(instance))

        assert response.status_code == 200
        content = response.content.decode()
        assert "Cost data has been loaded" in content
        assert "sub-component labels" in content
        assert "Named Client Time Item" in content
        assert InterventionInstance.objects.filter(pk=instance.pk).exists()

    def test_delete_confirmation_omits_warning_pre_load(self, client_with_admin, defaults):
        instance = InterventionInstanceFactory()

        response = client_with_admin.get(delete_url(instance))

        assert response.status_code == 200
        assert "Cost data has been loaded" not in response.content.decode()
        assert InterventionInstance.objects.filter(pk=instance.pk).exists()

    def test_delete_requires_analysis_permission(self, client, defaults):
        instance = InterventionInstanceFactory()
        client.force_login(UserFactory())

        response = client.get(f"{delete_url(instance)}?confirmed")

        assert response.status_code == 403
        assert InterventionInstance.objects.filter(pk=instance.pk).exists()


@pytest.mark.django_db
class TestInterventionInstanceReorder:
    def test_reorder_persists_new_order(self, client_with_admin, defaults):
        analysis = AnalysisFactory()
        first = InterventionInstanceFactory(analysis=analysis, order=0)
        second = InterventionInstanceFactory(analysis=analysis, order=1)

        response = client_with_admin.post(
            reorder_url(analysis),
            {"choices": [second.pk, first.pk]},
        )

        assert response.status_code == 200
        first.refresh_from_db()
        second.refresh_from_db()
        assert second.order < first.order

    def test_reorder_panel_wires_up_save_button_dirty_tracking(self, client_with_admin, defaults):
        """
        The panel JS enables Save (`disable-when-form-unchanged`) only when a
        `.form-group` inside the form is marked changed, and the reorder JS
        fires `change` on the select — so the select must live in a
        `.form-group` or Save stays disabled forever.
        """
        analysis = AnalysisFactory()
        InterventionInstanceFactory(analysis=analysis, order=0)
        InterventionInstanceFactory(analysis=analysis, order=1)

        response = client_with_admin.get(reorder_url(analysis))

        assert response.status_code == 200
        content = response.content.decode()
        assert "disable-when-form-unchanged" in content
        assert "panel-analysis-intervention" in content
        form_group_index = content.index('<div class="form-group"')
        select_index = content.index('name="choices"')
        results_index = content.index("panels--reorder--results")
        assert form_group_index < select_index < results_index
        assert "panels-reorder.js" in content

    def test_reorder_with_stale_pk_shows_validation_error(self, client_with_admin, defaults):
        analysis = AnalysisFactory()
        first = InterventionInstanceFactory(analysis=analysis, order=0)
        second = InterventionInstanceFactory(analysis=analysis, order=1)
        deleted = InterventionInstanceFactory(analysis=analysis, order=2)
        stale_pk = deleted.pk
        deleted.delete()

        response = client_with_admin.post(
            reorder_url(analysis),
            {"choices": [stale_pk, second.pk, first.pk]},
        )

        assert response.status_code == 200
        assert "Select a valid choice" in response.content.decode()
        first.refresh_from_db()
        assert first.order == 0

    def test_reorder_rejects_pk_from_another_analysis(self, client_with_admin, defaults):
        analysis = AnalysisFactory()
        first = InterventionInstanceFactory(analysis=analysis, order=0)
        second = InterventionInstanceFactory(analysis=analysis, order=1)
        other = InterventionInstanceFactory(order=0)

        response = client_with_admin.post(
            reorder_url(analysis),
            {"choices": [other.pk, first.pk, second.pk]},
        )

        assert response.status_code == 200
        assert "Select a valid choice" in response.content.decode()
        other.refresh_from_db()
        assert other.order == 0

    def test_reorder_unavailable_with_fewer_than_two_interventions(self, client_with_admin, defaults):
        """
        An empty scoped queryset must 404, never fall back to listing (or
        reordering) every analysis's interventions.
        """
        empty_analysis = AnalysisFactory()
        other = InterventionInstanceFactory(order=0)

        response = client_with_admin.get(reorder_url(empty_analysis))
        assert response.status_code == 404

        response = client_with_admin.post(reorder_url(empty_analysis), {"choices": [other.pk]})
        assert response.status_code == 404
        other.refresh_from_db()
        assert other.order == 0

        InterventionInstanceFactory(analysis=empty_analysis, order=0)
        response = client_with_admin.get(reorder_url(empty_analysis))
        assert response.status_code == 404


@pytest.mark.django_db
class TestInterventionsStepPage:
    def test_page_renders_interventions(self, client_with_admin, analysis_workflow_with_analysis):
        analysis = analysis_workflow_with_analysis.analysis

        response = client_with_admin.get(reverse("analysis-interventions", kwargs={"pk": analysis.pk}))

        assert response.status_code == 200
        content = response.content.decode()
        assert "My Test Intervention" in content
        assert "Add Sub-Component Analysis" in content
        assert "Manage Interventions" in content

    def test_page_hides_subcomponent_actions_when_locked(
        self, client_with_admin, analysis_workflow_with_loaddata_complete
    ):
        analysis = analysis_workflow_with_loaddata_complete.analysis

        response = client_with_admin.get(reverse("analysis-interventions", kwargs={"pk": analysis.pk}))

        assert response.status_code == 200
        assert "Add Sub-Component Analysis" not in response.content.decode()

    def test_page_renders_with_no_interventions(self, client_with_admin, defaults):
        analysis = AnalysisFactory()

        response = client_with_admin.get(reverse("analysis-interventions", kwargs={"pk": analysis.pk}))

        assert response.status_code == 200
        assert "Add Interventions" in response.content.decode()

    def test_page_separates_subcomponent_labels_with_hyphens(self, client_with_admin, defaults):
        instance = InterventionInstanceFactory()
        SubcomponentCostAnalysisFactory(
            intervention_instance=instance,
            subcomponent_labels=["Design / Setup", "Delivery"],
        )

        response = client_with_admin.get(
            reverse("analysis-interventions", kwargs={"pk": instance.analysis.pk})
        )

        assert response.status_code == 200
        content = " ".join(response.content.decode().split())
        assert "Design / Setup" in content
        assert "Delivery" in content


@pytest.mark.django_db
class TestSubcomponentLabelsPanels:
    def _labels_url(self, instance):
        return reverse(
            "analysis-interventions-subcomponent-labels",
            kwargs={"pk": instance.analysis.pk, "instance_pk": instance.pk},
        )

    def _delete_url(self, instance):
        return reverse(
            "analysis-interventions-subcomponent-labels-delete",
            kwargs={"pk": instance.analysis.pk, "instance_pk": instance.pk},
        )

    def test_save_labels_creates_subcomponent_cost_analysis(self, client_with_admin, defaults):
        instance = InterventionInstanceFactory()

        response = client_with_admin.post(
            self._labels_url(instance),
            {"subcomponent_labels": '["Setup", "Delivery"]'},
        )

        assert response.status_code == 200
        subcomponent_analysis = SubcomponentCostAnalysis.objects.get(intervention_instance=instance)
        assert subcomponent_analysis.subcomponent_labels == ["Setup", "Delivery"]

    def test_labels_panel_404s_for_mismatched_analysis(self, client_with_admin, defaults):
        instance = InterventionInstanceFactory()
        other_analysis = AnalysisFactory()

        response = client_with_admin.get(
            reverse(
                "analysis-interventions-subcomponent-labels",
                kwargs={"pk": other_analysis.pk, "instance_pk": instance.pk},
            )
        )

        assert response.status_code == 404

    def test_locked_labels_panel_rejects_count_change(
        self, client_with_admin, analysis_workflow_with_loaddata_complete
    ):
        analysis = analysis_workflow_with_loaddata_complete.analysis
        instance = analysis.interventioninstance_set.first()
        SubcomponentCostAnalysisFactory(
            intervention_instance=instance,
            subcomponent_labels=["Setup", "Delivery"],
        )

        response = client_with_admin.post(
            self._labels_url(instance),
            {"subcomponent_labels": '["Setup", "Delivery", "Admin"]'},
        )

        assert response.status_code == 200
        assert "Sub-component labels cannot be added or removed" in response.content.decode()
        instance.refresh_from_db()
        assert instance.subcomponent_cost_analysis.subcomponent_labels == ["Setup", "Delivery"]

    def test_delete_panel_removes_subcomponent_cost_analysis(self, client_with_admin, defaults):
        instance = InterventionInstanceFactory()
        SubcomponentCostAnalysisFactory(
            intervention_instance=instance,
            subcomponent_labels=["Setup", "Delivery"],
        )

        response = client_with_admin.post(self._delete_url(instance), {})

        assert response.status_code == 200
        assert not SubcomponentCostAnalysis.objects.filter(intervention_instance=instance).exists()

    def test_delete_panel_denied_when_locked(
        self, client_with_admin, analysis_workflow_with_loaddata_complete
    ):
        analysis = analysis_workflow_with_loaddata_complete.analysis
        instance = analysis.interventioninstance_set.first()
        SubcomponentCostAnalysisFactory(
            intervention_instance=instance,
            subcomponent_labels=["Setup", "Delivery"],
        )

        response = client_with_admin.post(self._delete_url(instance), {})

        assert response.status_code == 403
        assert SubcomponentCostAnalysis.objects.filter(intervention_instance=instance).exists()
