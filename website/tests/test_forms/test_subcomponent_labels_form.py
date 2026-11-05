import pytest

from website.forms.analysis import SubcomponentLabelsForm
from website.models import SubcomponentCostAnalysis
from website.tests.factories import (
    InterventionFactory,
    InterventionInstanceFactory,
    SubcomponentCostAnalysisFactory,
)


@pytest.fixture
def intervention_instance():
    return InterventionInstanceFactory(
        intervention=InterventionFactory(subcomponent_labels=["Default A", "Default B"]),
    )


@pytest.mark.django_db
def test_uses_intervention_defaults_when_adding(intervention_instance):
    form = SubcomponentLabelsForm(intervention_instance=intervention_instance)

    assert form.fields["subcomponent_labels"].initial == ["Default A", "Default B"]


@pytest.mark.django_db
def test_uses_existing_labels_when_present(intervention_instance):
    SubcomponentCostAnalysisFactory(
        intervention_instance=intervention_instance,
        subcomponent_labels=["Setup", "Delivery"],
    )

    form = SubcomponentLabelsForm(intervention_instance=intervention_instance)

    assert form.fields["subcomponent_labels"].initial == ["Setup", "Delivery"]


@pytest.mark.django_db
def test_renaming_labels_in_place(intervention_instance):
    SubcomponentCostAnalysisFactory(
        intervention_instance=intervention_instance,
        subcomponent_labels=["Setup", "Delivery"],
    )

    form = SubcomponentLabelsForm(
        data={"subcomponent_labels": '["Setup", "Handover"]'},
        intervention_instance=intervention_instance,
    )

    assert form.is_valid(), form.errors
    form.save()
    subcomponent_analysis = SubcomponentCostAnalysis.objects.get(intervention_instance=intervention_instance)
    assert subcomponent_analysis.subcomponent_labels == ["Setup", "Handover"]


@pytest.mark.django_db
def test_rejects_more_than_eight_labels(intervention_instance):
    labels = [f"Label {i}" for i in range(9)]
    form = SubcomponentLabelsForm(
        data={"subcomponent_labels": str(labels).replace("'", '"')},
        intervention_instance=intervention_instance,
    )

    assert not form.is_valid()
    assert "No more than 8 sublabels are allowed." in str(form.errors)


@pytest.mark.django_db
def test_save_creates_subcomponent_cost_analysis(intervention_instance):
    form = SubcomponentLabelsForm(
        data={"subcomponent_labels": '["Setup", "Delivery"]'},
        intervention_instance=intervention_instance,
    )

    assert form.is_valid(), form.errors
    form.save()

    subcomponent_analysis = SubcomponentCostAnalysis.objects.get(intervention_instance=intervention_instance)
    assert subcomponent_analysis.subcomponent_labels == ["Setup", "Delivery"]


@pytest.mark.django_db
def test_empty_labels_are_rejected_in_favour_of_the_delete_panel(intervention_instance):
    SubcomponentCostAnalysisFactory(
        intervention_instance=intervention_instance,
        subcomponent_labels=["Setup", "Delivery"],
    )

    form = SubcomponentLabelsForm(
        data={"subcomponent_labels": "[]"},
        intervention_instance=intervention_instance,
    )

    assert not form.is_valid()
    assert "Delete" in str(form.errors["subcomponent_labels"])
    assert SubcomponentCostAnalysis.objects.filter(intervention_instance=intervention_instance).exists()


# --- Feature 86, Issue 1: component identity through the form -------------------------------


def _row(subcomponent_analysis, allocations):
    from decimal import Decimal

    from website.tests.factories import (
        CostLineItemConfigFactory,
        CostLineItemFactory,
        CostLineItemInterventionAllocationFactory,
        SubcomponentCostAllocationFactory,
    )

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


@pytest.mark.django_db
def test_reorder_with_sources_moves_percentages_with_their_labels(defaults, intervention_instance):
    subcomponent_analysis = SubcomponentCostAnalysisFactory(
        intervention_instance=intervention_instance, subcomponent_labels=["Setup", "Delivery"]
    )
    row = _row(subcomponent_analysis, {"0": "70", "1": "30"})

    form = SubcomponentLabelsForm(
        data={"subcomponent_labels": '["Delivery", "Setup"]', "subcomponent_sources": "[1, 0]"},
        intervention_instance=intervention_instance,
    )

    assert form.is_valid(), form.errors
    form.save()
    subcomponent_analysis.refresh_from_db()
    row.refresh_from_db()
    assert subcomponent_analysis.subcomponent_labels == ["Delivery", "Setup"]
    assert row.allocations == {"0": "30", "1": "70"}


@pytest.mark.django_db
def test_missing_sources_are_treated_as_a_rename_in_place(defaults, intervention_instance):
    subcomponent_analysis = SubcomponentCostAnalysisFactory(
        intervention_instance=intervention_instance, subcomponent_labels=["Setup", "Delivery"]
    )
    row = _row(subcomponent_analysis, {"0": "70", "1": "30"})

    form = SubcomponentLabelsForm(
        data={"subcomponent_labels": '["Setup", "Handover"]'},
        intervention_instance=intervention_instance,
    )

    assert form.is_valid(), form.errors
    form.save()
    row.refresh_from_db()
    assert row.allocations == {"0": "70", "1": "30"}


@pytest.mark.django_db
@pytest.mark.parametrize("sources", ["[0]", "[0, 0]", "[0, 5]", '["0", 1]'])
def test_rejects_sources_that_do_not_match_the_labels(intervention_instance, sources):
    SubcomponentCostAnalysisFactory(
        intervention_instance=intervention_instance, subcomponent_labels=["Setup", "Delivery"]
    )

    form = SubcomponentLabelsForm(
        data={"subcomponent_labels": '["Setup", "Delivery"]', "subcomponent_sources": sources},
        intervention_instance=intervention_instance,
    )

    assert not form.is_valid()
    assert "Invalid sub-component reference" in str(form.non_field_errors())


@pytest.mark.django_db
def test_widget_renders_the_sources_input(intervention_instance):
    SubcomponentCostAnalysisFactory(
        intervention_instance=intervention_instance, subcomponent_labels=["Setup", "Delivery"]
    )

    html = str(SubcomponentLabelsForm(intervention_instance=intervention_instance)["subcomponent_labels"])

    assert 'name="subcomponent_sources"' in html
    assert 'value="[0, 1]"' in html
    assert '"source": 0' in html or "&quot;source&quot;: 0" in html
