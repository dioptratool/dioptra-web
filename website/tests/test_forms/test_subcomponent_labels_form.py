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
def test_locked_form_prevents_add_remove(intervention_instance):
    SubcomponentCostAnalysisFactory(
        intervention_instance=intervention_instance,
        subcomponent_labels=["Setup", "Delivery"],
    )

    form = SubcomponentLabelsForm(intervention_instance=intervention_instance, locked=True)

    assert form.fields["subcomponent_labels"].widget.attrs["prevent_add_remove"]


@pytest.mark.django_db
def test_locked_form_rejects_label_count_change(intervention_instance):
    SubcomponentCostAnalysisFactory(
        intervention_instance=intervention_instance,
        subcomponent_labels=["Setup", "Delivery"],
    )

    form = SubcomponentLabelsForm(
        data={"subcomponent_labels": '["Setup", "Delivery", "Admin"]'},
        intervention_instance=intervention_instance,
        locked=True,
    )

    assert not form.is_valid()
    assert "Sub-component labels cannot be added or removed" in str(form.errors)


@pytest.mark.django_db
def test_locked_form_allows_renaming_labels(intervention_instance):
    SubcomponentCostAnalysisFactory(
        intervention_instance=intervention_instance,
        subcomponent_labels=["Setup", "Delivery"],
    )

    form = SubcomponentLabelsForm(
        data={"subcomponent_labels": '["Setup", "Handover"]'},
        intervention_instance=intervention_instance,
        locked=True,
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
def test_save_with_empty_labels_deletes_subcomponent_cost_analysis(intervention_instance):
    SubcomponentCostAnalysisFactory(
        intervention_instance=intervention_instance,
        subcomponent_labels=["Setup", "Delivery"],
    )

    form = SubcomponentLabelsForm(
        data={"subcomponent_labels": "[]"},
        intervention_instance=intervention_instance,
    )

    assert form.is_valid(), form.errors
    form.save()

    assert not SubcomponentCostAnalysis.objects.filter(intervention_instance=intervention_instance).exists()
