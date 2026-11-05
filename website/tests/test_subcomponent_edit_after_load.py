"""
Feature 86, Issue 7 (86.5): sub-components can be added to and removed from an intervention
after cost data has been loaded, keeping the data and the surviving allocations.
"""

import json

import pytest
from django.urls import reverse

from website.models import Analysis, AnalysisStatus, SubcomponentCostAllocation, SubcomponentCostAnalysis
from website.workflows import AnalysisWorkflow


def labels_url(instance):
    return reverse(
        "analysis-interventions-subcomponent-labels",
        kwargs={"pk": instance.analysis.pk, "instance_pk": instance.pk},
    )


def post_labels(client, instance, labels, sources):
    subcomponent_analysis = getattr(instance, "subcomponent_cost_analysis", None)
    data = {"subcomponent_labels": json.dumps(labels), "subcomponent_sources": json.dumps(sources)}
    if subcomponent_analysis is not None:
        data["subcomponent_analysis_id"] = subcomponent_analysis.id
        data["subcomponent_revision"] = subcomponent_analysis.revision
    return client.post(labels_url(instance), data)


def set_rows(subcomponent_analysis, allocations, skipped=False):
    SubcomponentCostAllocation.objects.filter(subcomponent_analysis=subcomponent_analysis).update(
        allocations=allocations, skipped=skipped
    )


def subcomponent_step_complete(analysis):
    return (
        AnalysisWorkflow(Analysis.objects.get(pk=analysis.pk)).get_step("allocate-subcomponents").is_complete
    )


@pytest.fixture
def loaded(analysis_workflow_with_all_cost_lines_allocated_to_subcomponents):
    """Data loaded, one intervention with a 2-label sub-component analysis, every row at 60/40."""
    analysis = analysis_workflow_with_all_cost_lines_allocated_to_subcomponents.analysis
    instance = analysis.interventioninstance_set.select_related("subcomponent_cost_analysis").first()
    subcomponent_analysis = instance.subcomponent_cost_analysis
    subcomponent_analysis.subcomponent_labels = ["A", "B"]
    subcomponent_analysis.save()
    set_rows(subcomponent_analysis, {"0": "60", "1": "40"})
    assert subcomponent_step_complete(analysis)
    return analysis, instance, subcomponent_analysis


@pytest.mark.django_db
class TestEditAfterDataLoad:
    def test_add_component_keeps_values_and_makes_rows_incomplete(self, client_with_admin, loaded):
        analysis, instance, subcomponent_analysis = loaded

        response = post_labels(client_with_admin, instance, ["A", "B", "C"], [0, 1, None])

        assert response.status_code == 200
        assert not response.context["form"].errors, response.context["form"].errors
        subcomponent_analysis.refresh_from_db()
        assert subcomponent_analysis.subcomponent_labels == ["A", "B", "C"]
        rows = SubcomponentCostAllocation.objects.filter(subcomponent_analysis=subcomponent_analysis)
        assert rows.exists()
        assert all(row.allocations == {"0": "60", "1": "40"} for row in rows)
        assert not subcomponent_step_complete(analysis)

        set_rows(subcomponent_analysis, {"0": "60", "1": "40", "2": "0"})
        assert subcomponent_step_complete(analysis)

    def test_remove_component_keeps_survivors_and_makes_rows_incomplete(self, client_with_admin, loaded):
        analysis, instance, subcomponent_analysis = loaded
        subcomponent_analysis.subcomponent_labels = ["A", "B", "C"]
        subcomponent_analysis.save()
        set_rows(subcomponent_analysis, {"0": "20", "1": "30", "2": "50"})

        response = post_labels(client_with_admin, instance, ["A", "C"], [0, 2])

        assert response.status_code == 200
        assert not response.context["form"].errors, response.context["form"].errors
        rows = SubcomponentCostAllocation.objects.filter(subcomponent_analysis=subcomponent_analysis)
        assert all(row.allocations == {"0": "20", "1": "50"} for row in rows)
        assert not subcomponent_step_complete(analysis)

    def test_remove_zero_component_keeps_rows_complete(self, client_with_admin, loaded):
        analysis, instance, subcomponent_analysis = loaded
        set_rows(subcomponent_analysis, {"0": "100", "1": "0"})

        response = post_labels(client_with_admin, instance, ["A"], [0])

        assert response.status_code == 200
        assert not response.context["form"].errors, response.context["form"].errors
        rows = SubcomponentCostAllocation.objects.filter(subcomponent_analysis=subcomponent_analysis)
        assert all(row.allocations == {"0": "100"} for row in rows)
        assert subcomponent_step_complete(analysis)

    def test_skipped_rows_stay_skipped(self, client_with_admin, loaded):
        analysis, instance, subcomponent_analysis = loaded
        set_rows(subcomponent_analysis, {}, skipped=True)

        post_labels(client_with_admin, instance, ["A", "B", "C"], [0, 1, None])

        rows = SubcomponentCostAllocation.objects.filter(subcomponent_analysis=subcomponent_analysis)
        assert all(row.skipped and row.allocations == {} for row in rows)
        assert subcomponent_step_complete(analysis)

    def test_complete_analysis_returns_to_in_progress(self, client_with_admin, loaded):
        analysis, instance, subcomponent_analysis = loaded
        Analysis.objects.filter(pk=analysis.pk).update(analysis_status=AnalysisStatus.COMPLETE)

        post_labels(client_with_admin, instance, ["A", "B", "C"], [0, 1, None])

        analysis.refresh_from_db()
        assert analysis.analysis_status == AnalysisStatus.IN_PROGRESS
        assert not AnalysisWorkflow(analysis).get_step("insights").dependencies_met

    def test_basic_user_cannot_edit_a_validated_analysis(self, client, loaded):
        analysis, instance, subcomponent_analysis = loaded
        Analysis.objects.filter(pk=analysis.pk).update(analysis_status=AnalysisStatus.VALIDATED)
        client.force_login(analysis.owner)

        response = post_labels(client, instance, ["A", "B", "C"], [0, 1, None])

        assert response.status_code == 403
        subcomponent_analysis.refresh_from_db()
        assert subcomponent_analysis.subcomponent_labels == ["A", "B"]

    def test_editor_help_text_after_data_load(self, client_with_admin, loaded):
        analysis, instance, subcomponent_analysis = loaded

        response = client_with_admin.get(labels_url(instance))

        content = " ".join(response.content.decode().split())
        assert "must be reset" not in content
        assert "same output count" in content
        assert "Add a label" in content


@pytest.mark.django_db
class TestAddAnalysisAfterDataLoad:
    def test_adding_creates_incomplete_substeps(self, client_with_admin, analysis_workflow_with_allocations):
        analysis = analysis_workflow_with_allocations.analysis
        instance = analysis.interventioninstance_set.first()
        assert not AnalysisWorkflow(analysis).get_step("allocate-subcomponents").is_enabled

        response = post_labels(client_with_admin, instance, ["X", "Y"], [None, None])

        assert response.status_code == 200
        assert not response.context["form"].errors, response.context["form"].errors
        assert SubcomponentCostAnalysis.objects.get(intervention_instance=instance).subcomponent_labels == [
            "X",
            "Y",
        ]
        step = AnalysisWorkflow(Analysis.objects.get(pk=analysis.pk)).get_step("allocate-subcomponents")
        assert step.is_enabled
        assert step.steps
        assert not step.is_complete

    def test_interventions_page_offers_add_after_data_load(
        self, client_with_admin, analysis_workflow_with_loaddata_complete
    ):
        analysis = analysis_workflow_with_loaddata_complete.analysis

        response = client_with_admin.get(reverse("analysis-interventions", kwargs={"pk": analysis.pk}))

        assert response.status_code == 200
        assert "Add Sub-Component Analysis" in response.content.decode()
