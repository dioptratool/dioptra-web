import pytest
from django.urls import reverse

from website.models import InterventionInstance, SubcomponentCostAnalysis
from website.tests.factories import (
    AnalysisFactory,
    InterventionFactory,
    InterventionInstanceFactory,
    SubcomponentCostAnalysisFactory,
    UserFactory,
)


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

    def test_hides_delete_after_data_is_loaded(
        self, client_with_admin, analysis_workflow_with_loaddata_complete
    ):
        analysis = analysis_workflow_with_loaddata_complete.analysis
        instances = list(analysis.interventioninstance_set.all())

        response = client_with_admin.get(changelist_url(analysis))

        assert response.status_code == 200
        content = response.content.decode()
        for instance in instances:
            assert delete_url(instance) not in content
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


@pytest.mark.django_db
class TestInterventionInstanceDelete:
    def test_delete_removes_intervention_instance(self, client_with_admin, defaults):
        instance = InterventionInstanceFactory()

        response = client_with_admin.get(f"{delete_url(instance)}?confirmed")

        assert response.status_code == 200
        assert not InterventionInstance.objects.filter(pk=instance.pk).exists()

    def test_intervention_cannot_be_deleted_after_data_is_loaded(
        self, client_with_admin, analysis_workflow_with_loaddata_complete
    ):
        analysis = analysis_workflow_with_loaddata_complete.analysis
        instance = analysis.interventioninstance_set.first()

        response = client_with_admin.get(f"{delete_url(instance)}?confirmed")

        assert response.status_code == 200
        assert InterventionInstance.objects.filter(pk=instance.pk).exists()
        assert "Interventions cannot be deleted after cost data has been loaded." in response.content.decode()

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
        assert "Design / Setup - Delivery" in content
        assert "Design / Setup / Delivery" not in content


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
