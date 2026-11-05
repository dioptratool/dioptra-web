"""
Feature 86, Issue 4: an intervention's sub-component analysis is removed only through the
Delete panel, which works after data has been loaded; the label editor rejects an empty list.
"""

from decimal import Decimal

import pytest
from django.urls import reverse

from app_log.models import AppLogEntry
from website.forms.analysis import SubcomponentLabelsForm
from website.models import (
    Analysis,
    AnalysisStatus,
    CostLineItemInterventionAllocation,
    SubcomponentCostAllocation,
    SubcomponentCostAnalysis,
)
from website.tests.factories import (
    CostLineItemConfigFactory,
    CostLineItemFactory,
    CostLineItemInterventionAllocationFactory,
    InterventionInstanceFactory,
    SubcomponentCostAllocationFactory,
    SubcomponentCostAnalysisFactory,
    UserFactory,
)


def _row(subcomponent_analysis, allocations):
    config = CostLineItemConfigFactory(
        cost_line_item=CostLineItemFactory(analysis=subcomponent_analysis.analysis)
    )
    CostLineItemInterventionAllocationFactory(
        cli_config=config,
        intervention_instance=subcomponent_analysis.intervention_instance,
        allocation=Decimal("100"),
    )
    return SubcomponentCostAllocationFactory(
        subcomponent_analysis=subcomponent_analysis, cli_config=config, allocations=allocations
    )


def delete_url(instance):
    return reverse(
        "analysis-interventions-subcomponent-labels-delete",
        kwargs={"pk": instance.analysis.pk, "instance_pk": instance.pk},
    )


def labels_url(instance):
    return reverse(
        "analysis-interventions-subcomponent-labels",
        kwargs={"pk": instance.analysis.pk, "instance_pk": instance.pk},
    )


@pytest.fixture
def loaded(analysis_workflow_with_subcomponent_labels):
    """An analysis with data loaded, one labelled sub-component analysis and one allocation row."""
    analysis = analysis_workflow_with_subcomponent_labels.analysis
    instance = analysis.interventioninstance_set.first()
    subcomponent_analysis = instance.subcomponent_cost_analysis
    row = _row(subcomponent_analysis, {"0": "100"})
    return analysis, instance, subcomponent_analysis, row


@pytest.mark.django_db
class TestDeletePanelAfterDataLoad:
    def test_deletes_only_this_interventions_analysis(self, client_with_admin, loaded):
        analysis, instance, subcomponent_analysis, row = loaded
        other = SubcomponentCostAnalysisFactory(
            intervention_instance=InterventionInstanceFactory(analysis=analysis),
            subcomponent_labels=["X", "Y"],
        )
        other_row = _row(other, {"0": "50", "1": "50"})
        cost_items_before = analysis.cost_line_items.count()
        intervention_allocations_before = CostLineItemInterventionAllocation.objects.filter(
            intervention_instance=instance
        ).count()

        response = client_with_admin.post(delete_url(instance), {})

        assert response.status_code == 200
        assert not SubcomponentCostAnalysis.objects.filter(pk=subcomponent_analysis.pk).exists()
        assert not SubcomponentCostAllocation.objects.filter(pk=row.pk).exists()
        assert SubcomponentCostAnalysis.objects.filter(pk=other.pk).exists()
        assert SubcomponentCostAllocation.objects.filter(pk=other_row.pk).exists()
        assert analysis.cost_line_items.count() == cost_items_before
        assert (
            CostLineItemInterventionAllocation.objects.filter(intervention_instance=instance).count()
            == intervention_allocations_before
        )

    def test_confirmation_page_changes_nothing_and_names_what_goes(self, client_with_admin, loaded):
        analysis, instance, subcomponent_analysis, row = loaded

        response = client_with_admin.get(delete_url(instance))

        assert response.status_code == 200
        content = " ".join(response.content.decode().split())
        assert "percentages" in content and "skip" in content.lower()
        assert "All work done in the analysis will be cleared" not in content
        assert SubcomponentCostAnalysis.objects.filter(pk=subcomponent_analysis.pk).exists()
        assert SubcomponentCostAllocation.objects.filter(pk=row.pk).exists()

    def test_re_adding_starts_blank(self, client_with_admin, defaults):
        # No cost items here, so data is not loaded; re-adding after data load is Issue 7's scenario.
        instance = InterventionInstanceFactory()
        subcomponent_analysis = SubcomponentCostAnalysisFactory(
            intervention_instance=instance, subcomponent_labels=["Old A", "Old B"]
        )
        client_with_admin.post(delete_url(instance), {})

        response = client_with_admin.post(
            labels_url(instance),
            {"subcomponent_labels": '["Fresh A", "Fresh B"]', "subcomponent_sources": "[null, null]"},
        )

        assert response.status_code == 200
        assert not response.context["form"].errors, response.context["form"].errors
        recreated = SubcomponentCostAnalysis.objects.get(intervention_instance=instance)
        assert recreated.pk != subcomponent_analysis.pk
        assert recreated.subcomponent_labels == ["Fresh A", "Fresh B"]
        assert recreated.revision == 0
        assert not recreated.allocations.exists()

    def test_writes_an_audit_log_entry(self, client_with_admin, loaded):
        analysis, instance, subcomponent_analysis, row = loaded

        client_with_admin.post(delete_url(instance), {})

        assert AppLogEntry.objects.filter(
            action="Deleted",
            object_id=subcomponent_analysis.pk,
            content_type__model="subcomponentcostanalysis",
        ).exists()

    def test_primary_country_editor_can_delete(self, client, loaded):
        analysis, instance, subcomponent_analysis, row = loaded
        editor = UserFactory()
        editor.primary_countries.add(analysis.country)
        client.force_login(editor)

        response = client.post(delete_url(instance), {})

        assert response.status_code == 200
        assert not SubcomponentCostAnalysis.objects.filter(pk=subcomponent_analysis.pk).exists()

    def test_basic_user_cannot_delete_on_a_validated_analysis(self, client, loaded):
        analysis, instance, subcomponent_analysis, row = loaded
        Analysis.objects.filter(pk=analysis.pk).update(analysis_status=AnalysisStatus.VALIDATED)
        client.force_login(analysis.owner)

        response = client.post(delete_url(instance), {})

        assert response.status_code == 403
        assert SubcomponentCostAnalysis.objects.filter(pk=subcomponent_analysis.pk).exists()

    def test_delete_link_is_shown_after_data_load(self, client_with_admin, loaded):
        analysis, instance, subcomponent_analysis, row = loaded

        response = client_with_admin.get(reverse("analysis-interventions", kwargs={"pk": analysis.pk}))

        assert delete_url(instance) in response.content.decode()


@pytest.mark.django_db
class TestLabelEditorRejectsEmptyList:
    def test_empty_list_is_rejected_when_an_analysis_exists(self, defaults):
        instance = InterventionInstanceFactory()
        subcomponent_analysis = SubcomponentCostAnalysisFactory(
            intervention_instance=instance, subcomponent_labels=["Setup", "Delivery"]
        )

        form = SubcomponentLabelsForm(
            data={"subcomponent_labels": "[]", "subcomponent_sources": "[]"}, intervention_instance=instance
        )

        assert not form.is_valid()
        assert "Delete" in str(form.errors["subcomponent_labels"])
        assert SubcomponentCostAnalysis.objects.filter(pk=subcomponent_analysis.pk).exists()

    def test_empty_list_without_an_analysis_saves_nothing(self, defaults):
        instance = InterventionInstanceFactory()

        form = SubcomponentLabelsForm(data={"subcomponent_labels": "[]"}, intervention_instance=instance)

        assert form.is_valid(), form.errors
        form.save()
        assert not SubcomponentCostAnalysis.objects.filter(intervention_instance=instance).exists()

    def test_old_reset_route_is_gone(self):
        from django.urls import NoReverseMatch

        with pytest.raises(NoReverseMatch):
            reverse("subcomponent-cost-analysis-delete", kwargs={"pk": 1, "subcomponent_pk": 1})
