import pytest
from django.urls import reverse

from website.models import InterventionInstance


@pytest.mark.django_db
class TestFullCostModelSpreadsheetEndpoint:
    def test_with_colon_in_intervention_name(self, admin_client, analysis_workflow_main_flow_complete):
        intervention_instance: InterventionInstance = (
            analysis_workflow_main_flow_complete.analysis.interventioninstance_set.first()
        )
        intervention_instance.label = "Foo:bar"
        intervention_instance.save()
        resp = admin_client.get(
            reverse(
                "analysis-cost-model-spreadsheet",
                kwargs={
                    "pk": analysis_workflow_main_flow_complete.analysis.pk,
                },
            )
        )
        assert resp.status_code == 200

    def test_no_subcomponent_flow(self, admin_client, analysis_workflow_main_flow_complete):
        resp = admin_client.get(
            reverse(
                "analysis-cost-model-spreadsheet",
                kwargs={
                    "pk": analysis_workflow_main_flow_complete.analysis.pk,
                },
            )
        )
        assert resp.status_code == 200

    def test_incomplete_subcomponent_flow(
        self,
        admin_client,
        analysis_workflow_with_subcomponent_labels_and_client_time_added,
    ):
        resp = admin_client.get(
            reverse(
                "analysis-cost-model-spreadsheet",
                kwargs={
                    "pk": analysis_workflow_with_subcomponent_labels_and_client_time_added.analysis.pk,
                },
            )
        )
        assert resp.status_code == 200

    def test_complete_subcomponent_flow(
        self,
        admin_client,
        analysis_workflow_with_subcomponent_labels_and_client_time_added,
    ):
        resp = admin_client.get(
            reverse(
                "analysis-cost-model-spreadsheet",
                kwargs={
                    "pk": analysis_workflow_with_subcomponent_labels_and_client_time_added.analysis.pk,
                },
            )
        )
        assert resp.status_code == 200
