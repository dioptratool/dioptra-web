import pytest
from django.urls import reverse

from website.models import Intervention, SubcomponentCostAnalysis
from website.models.output_metric import OUTPUT_METRIC_CHOICES
from website.tests.factories import InterventionFactory


@pytest.mark.django_db
class TestEditSubcomponentLabels:
    def test_can_view_edit_subcomponent_labels_form(
        self, client_with_admin, analysis_workflow_with_subcomponent_labels
    ):
        response = client_with_admin.get(
            reverse(
                "subcomponent-cost-analysis-label-edit",
                kwargs={
                    "pk": analysis_workflow_with_subcomponent_labels.analysis.pk,
                    "subcomponent_pk": analysis_workflow_with_subcomponent_labels.analysis.subcomponent_cost_analysis.pk,
                },
            ),
        )
        assert response.status_code == 200

    def test_can_add_subcomponent_label_to_analysis(
        self, client_with_admin, analysis_workflow_with_subcomponent_labels
    ):
        subcomponent_cost_analysis = (
            analysis_workflow_with_subcomponent_labels.analysis.subcomponent_cost_analysis
        )
        response = client_with_admin.post(
            reverse(
                "subcomponent-cost-analysis-label-edit",
                kwargs={
                    "pk": analysis_workflow_with_subcomponent_labels.analysis.pk,
                    "subcomponent_pk": subcomponent_cost_analysis.pk,
                },
            ),
            data={
                "subcomponent_labels": '["one","two","three"]',
            },
        )
        assert response.status_code == 200
        subcomponent_cost_analysis = SubcomponentCostAnalysis.objects.get(pk=subcomponent_cost_analysis.pk)
        assert subcomponent_cost_analysis.subcomponent_labels == ["one", "two", "three"]

    def test_can_add_subcomponent_label_to_intervention(self, client_with_admin):
        intervention = InterventionFactory(output_metrics=[OUTPUT_METRIC_CHOICES[0][0]])
        response = client_with_admin.get(
            reverse(
                "ombucore.admin:website_intervention_change",
                kwargs={
                    "pk": intervention.pk,
                },
            ),
        )
        form = response.context["form"]

        new_data = form.initial
        new_data["subcomponent_labels"] = '["five", "six", "seven", "eight", "nine"]'
        response = client_with_admin.post(
            reverse(
                "ombucore.admin:website_intervention_change",
                kwargs={
                    "pk": intervention.pk,
                },
            ),
            data=new_data,
        )
        assert response.status_code == 200
        intervention = Intervention.objects.get(pk=intervention.pk)
        assert intervention.subcomponent_labels == [
            "five",
            "six",
            "seven",
            "eight",
            "nine",
        ]

    def test_cant_add_more_than_eight_subcomponent_label_to_analysis(
        self, client_with_admin, analysis_workflow_with_subcomponent_labels
    ):
        subcomponent_cost_analysis = (
            analysis_workflow_with_subcomponent_labels.analysis.subcomponent_cost_analysis
        )

        og_labels = subcomponent_cost_analysis.subcomponent_labels
        response = client_with_admin.post(
            reverse(
                "subcomponent-cost-analysis-label-edit",
                kwargs={
                    "pk": analysis_workflow_with_subcomponent_labels.analysis.pk,
                    "subcomponent_pk": subcomponent_cost_analysis.pk,
                },
            ),
            data={
                "subcomponent_labels": '["one","two","three","four","five","six","seven","eight","nine"]',
            },
        )

        subcomponent_cost_analysis = SubcomponentCostAnalysis.objects.get(pk=subcomponent_cost_analysis.pk)
        assert subcomponent_cost_analysis.subcomponent_labels == og_labels
