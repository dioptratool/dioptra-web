"""
Feature 86, Issue 2: one set of label rules for analysis sub-component labels and
intervention-type defaults, and an edit panel that survives any label text.
"""

import json
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from website.forms.analysis import SubcomponentLabelsForm
from website.forms.fields import SubcomponentLabelField
from website.models import Intervention
from website.models.output_metric import OUTPUT_METRIC_CHOICES
from website.tests.factories import (
    CostLineItemConfigFactory,
    CostLineItemFactory,
    CostLineItemInterventionAllocationFactory,
    InterventionFactory,
    InterventionInstanceFactory,
    SubcomponentCostAllocationFactory,
    SubcomponentCostAnalysisFactory,
)


def clean(labels):
    return SubcomponentLabelField(required=False).clean(json.dumps(labels))


class TestSubcomponentLabelField:
    def test_trims_surrounding_whitespace_and_keeps_casing(self):
        assert clean(["  Setup ", "Delivery\t"]) == ["Setup", "Delivery"]

    @pytest.mark.parametrize("labels", [[""], ["   "], ["Setup", " "]])
    def test_rejects_blank_labels(self, labels):
        with pytest.raises(ValidationError, match="blank"):
            clean(labels)

    @pytest.mark.parametrize("labels", [["Setup", "setup"], ["Setup", "Setup "], ["A", "a", "b"]])
    def test_rejects_duplicates_ignoring_case_and_whitespace(self, labels):
        with pytest.raises(ValidationError, match="unique"):
            clean(labels)

    def test_allows_255_characters_but_not_256(self):
        assert clean(["x" * 255]) == ["x" * 255]
        with pytest.raises(ValidationError, match="255"):
            clean(["x" * 256])

    def test_still_rejects_a_ninth_label(self):
        with pytest.raises(ValidationError, match="No more than 8"):
            clean([f"Label {i}" for i in range(9)])


@pytest.fixture
def labelled_instance(defaults):
    instance = InterventionInstanceFactory()
    subcomponent_analysis = SubcomponentCostAnalysisFactory(
        intervention_instance=instance, subcomponent_labels=["Setup", "Delivery"]
    )
    config = CostLineItemConfigFactory(cost_line_item=CostLineItemFactory(analysis=instance.analysis))
    CostLineItemInterventionAllocationFactory(
        cli_config=config, intervention_instance=instance, allocation=Decimal("100")
    )
    row = SubcomponentCostAllocationFactory(
        subcomponent_analysis=subcomponent_analysis, cli_config=config, allocations={"0": "70", "1": "30"}
    )
    return instance, subcomponent_analysis, row


@pytest.mark.django_db
class TestSubcomponentLabelsFormRules:
    def test_invalid_labels_change_nothing(self, labelled_instance):
        instance, subcomponent_analysis, row = labelled_instance

        form = SubcomponentLabelsForm(
            data={"subcomponent_labels": '["Setup", "setup"]', "subcomponent_sources": "[0, 1]"},
            intervention_instance=instance,
        )

        assert not form.is_valid()
        assert "unique" in str(form.errors["subcomponent_labels"])
        subcomponent_analysis.refresh_from_db()
        row.refresh_from_db()
        assert subcomponent_analysis.subcomponent_labels == ["Setup", "Delivery"]
        assert row.allocations == {"0": "70", "1": "30"}

    def test_labels_are_saved_trimmed_with_percentages_intact(self, labelled_instance):
        instance, subcomponent_analysis, row = labelled_instance

        form = SubcomponentLabelsForm(
            data={"subcomponent_labels": '[" Delivery ", "Setup"]', "subcomponent_sources": "[1, 0]"},
            intervention_instance=instance,
        )

        assert form.is_valid(), form.errors
        form.save()
        subcomponent_analysis.refresh_from_db()
        row.refresh_from_db()
        assert subcomponent_analysis.subcomponent_labels == ["Delivery", "Setup"]
        assert row.allocations == {"0": "30", "1": "70"}


@pytest.mark.django_db
class TestInterventionDefaultLabelRules:
    def _post_labels(self, client, intervention, labels):
        url = reverse("ombucore.admin:website_intervention_change", kwargs={"pk": intervention.pk})
        data = client.get(url).context["form"].initial
        data["subcomponent_labels"] = json.dumps(labels)
        return client.post(url, data=data)

    def test_rejects_duplicate_defaults(self, client_with_admin):
        intervention = InterventionFactory(
            output_metrics=[OUTPUT_METRIC_CHOICES[0][0]], subcomponent_labels=["One", "Two"]
        )

        response = self._post_labels(client_with_admin, intervention, ["One", "one"])

        assert response.status_code == 200
        assert "unique" in str(response.context["form"].errors["subcomponent_labels"])
        assert Intervention.objects.get(pk=intervention.pk).subcomponent_labels == ["One", "Two"]

    def test_saves_trimmed_defaults(self, client_with_admin):
        intervention = InterventionFactory(output_metrics=[OUTPUT_METRIC_CHOICES[0][0]])

        response = self._post_labels(client_with_admin, intervention, [" # of children screened ", "Two"])

        assert response.status_code == 200
        assert Intervention.objects.get(pk=intervention.pk).subcomponent_labels == [
            "# of children screened",
            "Two",
        ]


@pytest.mark.django_db
class TestEditSubcomponentLabelPanel:
    def test_label_travels_in_the_query_string(self, client_with_admin):
        url = reverse("subcomponent-label-edit-label")

        response = client_with_admin.get(url, {"label": "# of children screened / referred?"})

        assert response.status_code == 200
        assert response.context["form"].initial["label"] == "# of children screened / referred?"

    def test_resolves_with_the_trimmed_new_label(self, client_with_admin):
        response = client_with_admin.post(reverse("subcomponent-label-edit-label"), {"label": "  Renamed  "})

        assert response.status_code == 200
        commands = json.dumps(
            [getattr(command, "payload", None) for command in response.context["panel_commands"]]
        )
        assert '"new_label": "Renamed"' in commands

    def test_rejects_a_blank_new_label(self, client_with_admin):
        response = client_with_admin.post(reverse("subcomponent-label-edit-label"), {"label": "   "})

        assert response.status_code == 200
        assert response.context["form"].errors["label"]
