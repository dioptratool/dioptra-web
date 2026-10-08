import pytest
from django.urls import reverse

from website.models import InterventionInstance
import io
from django.db import connection
from django.test.utils import CaptureQueriesContext
from openpyxl import load_workbook
from website.models.intervention_metadata import MetadataFieldType, MetadataNumberType
from website.tests.factories import InterventionMetadataFieldFactory, InterventionMetadataOptionFactory


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

    def test_metadata_rows_are_in_the_download(self, admin_client, analysis_workflow_main_flow_complete):
        analysis = analysis_workflow_main_flow_complete.analysis
        instance = analysis.interventioninstance_set.first()
        text = InterventionMetadataFieldFactory(intervention=instance.intervention, name="Partner", order=1)
        number = InterventionMetadataFieldFactory(
            intervention=instance.intervention,
            name="Volunteers",
            field_type=MetadataFieldType.NUMBER,
            number_type=MetadataNumberType.INTEGER,
            order=2,
        )
        single = InterventionMetadataFieldFactory(
            intervention=instance.intervention,
            name="Age",
            field_type=MetadataFieldType.SINGLE_CHOICE,
            order=3,
        )
        option = InterventionMetadataOptionFactory(field=single, label="Under 18")
        InterventionInstance.objects.filter(pk=instance.pk).update(
            metadata={
                text.storage_key: "Save the Children",
                number.storage_key: "0",
                single.storage_key: option.storage_key,
            }
        )

        with CaptureQueriesContext(connection) as context:
            resp = admin_client.get(reverse("analysis-cost-model-spreadsheet", kwargs={"pk": analysis.pk}))

        assert resp.status_code == 200
        worksheet = load_workbook(filename=io.BytesIO(b"".join(resp.streaming_content))).worksheets[0]
        labels = [cell.value for cell in worksheet["A"]]
        assert labels[:3] == ["Analysis Title", "Analysis Type", "Analysis Status"]
        assert worksheet["B3"].value == "In Progress"
        start = labels.index("Partner")
        # One empty row on each side of the intervention metadata block.
        assert labels[start - 1] is None
        assert labels[start : start + 5] == ["Partner", "Volunteers", "Age", None, "Output count data source"]
        assert [worksheet[f"B{start + 1 + offset}"].value for offset in range(3)] == [
            "Save the Children",
            0,
            "Under 18",
        ]
        # Definitions and options come with the analysis: one query each, not one per instance.
        assert (
            sum("website_interventionmetadatafield" in query["sql"] for query in context.captured_queries)
            == 1
        )
        assert (
            sum("website_interventionmetadataoption" in query["sql"] for query in context.captured_queries)
            == 1
        )
