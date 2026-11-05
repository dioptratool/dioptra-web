"""
Feature 86: the label editor panel, round-tripped the way a browser does it. GET the panel,
collect every input in document order (a browser submits them all; Django keeps the last
value per name), change what the editor script would change, and POST it back.
"""

from decimal import Decimal
from html.parser import HTMLParser

import pytest
from django.urls import reverse

from website.models import SubcomponentCostAnalysis
from website.tests.factories import (
    CostLineItemConfigFactory,
    CostLineItemFactory,
    CostLineItemInterventionAllocationFactory,
    InterventionFactory,
    InterventionInstanceFactory,
    SubcomponentCostAllocationFactory,
    SubcomponentCostAnalysisFactory,
)


class _Inputs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs = []  # (name, value) in document order

    def handle_starttag(self, tag, attrs):
        if tag != "input":
            return
        attrs = dict(attrs)
        if attrs.get("type") in ("checkbox", "radio", "submit", "button"):
            return
        if attrs.get("name"):
            self.inputs.append((attrs["name"], attrs.get("value", "")))


def browser_fields(response):
    """Every submittable input of the panel, as a browser would send it."""
    parser = _Inputs()
    parser.feed(response.content.decode())
    return parser.inputs


def as_post_data(fields):
    """Repeated names become lists so the test client posts them all, in order."""
    data = {}
    for name, value in fields:
        data.setdefault(name, []).append(value)
    return data


def set_editor_value(fields, name, value):
    """
    The editor script updates the widget's own input (the first one with that name). Any
    later input of the same name is left exactly as the page rendered it.
    """
    index = next(i for i, (field_name, _) in enumerate(fields) if field_name == name)
    fields[index] = (name, value)


def labels_url(instance):
    return reverse(
        "analysis-interventions-subcomponent-labels",
        kwargs={"pk": instance.analysis.pk, "instance_pk": instance.pk},
    )


@pytest.fixture
def labelled(defaults):
    instance = InterventionInstanceFactory()
    subcomponent_analysis = SubcomponentCostAnalysisFactory(
        intervention_instance=instance, subcomponent_labels=["A", "B", "C"]
    )
    config = CostLineItemConfigFactory(cost_line_item=CostLineItemFactory(analysis=instance.analysis))
    CostLineItemInterventionAllocationFactory(
        cli_config=config, intervention_instance=instance, allocation=Decimal("100")
    )
    row = SubcomponentCostAllocationFactory(
        subcomponent_analysis=subcomponent_analysis,
        cli_config=config,
        allocations={"0": "20", "1": "30", "2": "50"},
    )
    return instance, subcomponent_analysis, row


@pytest.mark.django_db
class TestLabelPanelRoundTrip:
    def test_panel_renders_each_identity_input_once(self, client_with_admin, labelled):
        instance, subcomponent_analysis, row = labelled

        fields = browser_fields(client_with_admin.get(labels_url(instance)))

        names = [name for name, _ in fields]
        for name in (
            "subcomponent_labels",
            "subcomponent_sources",
            "subcomponent_analysis_id",
            "subcomponent_revision",
        ):
            assert names.count(name) == 1, (name, fields)
        assert dict(fields)["subcomponent_sources"] == "[0, 1, 2]"

    def test_remove_middle_component_through_the_browser(self, client_with_admin, labelled):
        instance, subcomponent_analysis, row = labelled
        fields = browser_fields(client_with_admin.get(labels_url(instance)))
        set_editor_value(fields, "subcomponent_labels", '["A", "C"]')
        set_editor_value(fields, "subcomponent_sources", "[0, 2]")

        response = client_with_admin.post(labels_url(instance), as_post_data(fields))

        assert response.status_code == 200
        assert not response.context["form"].errors, response.context["form"].errors
        row.refresh_from_db()
        subcomponent_analysis.refresh_from_db()
        assert subcomponent_analysis.subcomponent_labels == ["A", "C"]
        assert row.allocations == {"0": "20", "1": "50"}
        assert subcomponent_analysis.revision == 1

    def test_remove_and_add_in_one_save_through_the_browser(self, client_with_admin, labelled):
        instance, subcomponent_analysis, row = labelled
        fields = browser_fields(client_with_admin.get(labels_url(instance)))
        set_editor_value(fields, "subcomponent_labels", '["A", "C", "D"]')
        set_editor_value(fields, "subcomponent_sources", "[0, 2, null]")

        response = client_with_admin.post(labels_url(instance), as_post_data(fields))

        assert not response.context["form"].errors, response.context["form"].errors
        row.refresh_from_db()
        assert row.allocations == {"0": "20", "1": "50"}

    def test_reorder_through_the_browser(self, client_with_admin, labelled):
        instance, subcomponent_analysis, row = labelled
        fields = browser_fields(client_with_admin.get(labels_url(instance)))
        set_editor_value(fields, "subcomponent_labels", '["B", "A", "C"]')
        set_editor_value(fields, "subcomponent_sources", "[1, 0, 2]")

        response = client_with_admin.post(labels_url(instance), as_post_data(fields))

        assert not response.context["form"].errors, response.context["form"].errors
        row.refresh_from_db()
        assert row.allocations == {"0": "30", "1": "20", "2": "50"}

    def test_adding_an_analysis_from_intervention_defaults(self, client_with_admin, defaults):
        instance = InterventionInstanceFactory(
            intervention=InterventionFactory(subcomponent_labels=["Default A", "Default B"])
        )
        response = client_with_admin.get(labels_url(instance))
        fields = browser_fields(response)
        # Defaults are not saved labels, so they carry no source position.
        assert dict(fields)["subcomponent_sources"] == "[null, null]"

        response = client_with_admin.post(labels_url(instance), as_post_data(fields))

        assert not response.context["form"].errors, response.context["form"].errors
        assert SubcomponentCostAnalysis.objects.get(intervention_instance=instance).subcomponent_labels == [
            "Default A",
            "Default B",
        ]

    def test_redisplay_after_an_error_keeps_the_posted_mapping(self, client_with_admin, labelled):
        instance, subcomponent_analysis, row = labelled
        fields = browser_fields(client_with_admin.get(labels_url(instance)))
        set_editor_value(fields, "subcomponent_labels", '["B", "A", "C", "c"]')  # duplicate of C
        set_editor_value(fields, "subcomponent_sources", "[1, 0, 2, null]")

        response = client_with_admin.post(labels_url(instance), as_post_data(fields))
        assert response.context["form"].errors["subcomponent_labels"]
        fields = browser_fields(response)
        assert dict(fields)["subcomponent_labels"] == '["B", "A", "C", "c"]'
        assert dict(fields)["subcomponent_sources"] == "[1, 0, 2, null]"

        # The user removes the duplicate and saves again.
        set_editor_value(fields, "subcomponent_labels", '["B", "A", "C"]')
        set_editor_value(fields, "subcomponent_sources", "[1, 0, 2]")
        response = client_with_admin.post(labels_url(instance), as_post_data(fields))

        assert not response.context["form"].errors, response.context["form"].errors
        row.refresh_from_db()
        assert row.allocations == {"0": "30", "1": "20", "2": "50"}
