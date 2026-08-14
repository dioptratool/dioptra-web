import pytest
from django.urls import reverse

from website.models import Intervention
from website.models.output_metric import OUTPUT_METRIC_CHOICES
from website.tests.factories import InterventionFactory


@pytest.mark.django_db
class TestEditSubcomponentLabels:
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
