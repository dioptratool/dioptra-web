import html
import json
import uuid

import pytest
from django.conf import settings as django_settings

from website.forms.intervention_instance import InterventionInstanceForm
from website.forms.intervention_metadata import metadata_field_name as name_of
from website.models import (
    CostLineItemInterventionAllocation,
    InterventionInstance,
    MetadataFieldType,
    MetadataNumberType,
    SubcomponentCostAnalysis,
)
from website.tests.factories import (
    AnalysisFactory,
    CostLineItemConfigFactory,
    CostLineItemInterventionAllocationFactory,
    InterventionFactory,
    InterventionInstanceFactory,
    InterventionMetadataFieldFactory,
    InterventionMetadataOptionFactory,
    SubcomponentCostAnalysisFactory,
)


@pytest.fixture
def analysis():
    return AnalysisFactory()


@pytest.fixture
def intervention():
    return InterventionFactory(output_metrics=["NumberOfTeacherDaysOfTraining"])


@pytest.fixture
def add_form_data(intervention):
    return {
        "intervention": str(intervention.pk),
        "label": "My Custom Label",
        "parameter__number_of_teachers": "5",
        "parameter__number_of_days_of_training": "3",
    }


@pytest.mark.django_db
def test_add_sets_analysis_order_and_parameters(analysis, intervention, add_form_data):
    form = InterventionInstanceForm(data=add_form_data, analysis=analysis)

    assert form.is_valid(), form.errors
    instance = form.save()

    assert instance.analysis == analysis
    assert instance.order == 0
    assert instance.label == "My Custom Label"
    assert instance.parameters == {
        "number_of_teachers": 5.0,
        "number_of_days_of_training": 3.0,
    }


@pytest.mark.django_db
def test_added_interventions_are_ordered_after_existing_ones(analysis, intervention, add_form_data):
    InterventionInstanceFactory(analysis=analysis, order=0)

    form = InterventionInstanceForm(data=add_form_data, analysis=analysis)

    assert form.is_valid(), form.errors
    assert form.save().order == 1


@pytest.mark.django_db
def test_requires_parameters_of_selected_intervention(analysis, intervention):
    form = InterventionInstanceForm(
        data={"intervention": str(intervention.pk)},
        analysis=analysis,
    )

    assert not form.is_valid()
    assert "parameter__number_of_teachers" in form.errors
    assert "parameter__number_of_days_of_training" in form.errors


@pytest.mark.django_db
def test_intervention_remains_required_server_side(analysis):
    form = InterventionInstanceForm(data={}, analysis=analysis)

    assert form.fields["intervention"].required
    assert "required" not in form["intervention"].as_widget()
    assert not form.is_valid()
    assert "intervention" in form.errors


@pytest.mark.django_db
def test_does_not_require_parameters_of_other_interventions(analysis, intervention, add_form_data):
    InterventionFactory(output_metrics=["ValueOfCashDistributed"])

    form = InterventionInstanceForm(data=add_form_data, analysis=analysis)

    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_rejects_add_when_at_maximum_interventions(analysis, intervention, add_form_data):
    for _ in range(django_settings.MAX_ANALYSIS_INTERVENTIONS):
        InterventionInstanceFactory(analysis=analysis)

    form = InterventionInstanceForm(data=add_form_data, analysis=analysis)

    assert not form.is_valid()
    assert (
        f"No more than {django_settings.MAX_ANALYSIS_INTERVENTIONS} interventions are allowed."
        in form.non_field_errors()
    )


@pytest.mark.django_db
def test_edit_seeds_parameter_initials(analysis, intervention):
    instance = InterventionInstanceFactory(
        analysis=analysis,
        intervention=intervention,
        parameters={"number_of_teachers": 5.0, "number_of_days_of_training": 3.0},
    )

    form = InterventionInstanceForm(instance=instance)

    assert form.fields["parameter__number_of_teachers"].initial == 5.0
    assert form.fields["parameter__number_of_days_of_training"].initial == 3.0


@pytest.mark.django_db
def test_edit_updates_parameters_in_place(analysis, intervention, add_form_data):
    instance = InterventionInstanceFactory(
        analysis=analysis,
        intervention=intervention,
        parameters={"number_of_teachers": 1.0, "number_of_days_of_training": 1.0},
    )

    form = InterventionInstanceForm(data=add_form_data, instance=instance)

    assert form.is_valid(), form.errors
    updated = form.save()

    assert updated.pk == instance.pk
    assert updated.parameters == {
        "number_of_teachers": 5.0,
        "number_of_days_of_training": 3.0,
    }


@pytest.mark.django_db
def test_intervention_type_change_clears_dependent_data(analysis, intervention, defaults):
    instance = InterventionInstanceFactory(
        analysis=analysis,
        intervention=intervention,
        parameters={"number_of_teachers": 1.0, "number_of_days_of_training": 1.0},
    )
    SubcomponentCostAnalysisFactory(intervention_instance=instance)
    allocation = CostLineItemInterventionAllocationFactory(
        cli_config=CostLineItemConfigFactory(),
        intervention_instance=instance,
    )
    new_intervention = InterventionFactory(output_metrics=["ValueOfCashDistributed"])

    form = InterventionInstanceForm(
        data={
            "intervention": str(new_intervention.pk),
            "parameter__value_of_cash_distributed": "1000",
        },
        instance=instance,
    )

    assert form.is_valid(), form.errors
    updated = form.save()

    assert updated.pk == instance.pk
    assert updated.intervention == new_intervention
    assert updated.parameters == {"value_of_cash_distributed": 1000.0}
    assert not SubcomponentCostAnalysis.objects.filter(intervention_instance=instance).exists()
    assert not CostLineItemInterventionAllocation.objects.filter(pk=allocation.pk).exists()


# ---------------------------------------------------------------------------------------------
# Metadata values
# ---------------------------------------------------------------------------------------------


@pytest.fixture
def defined(intervention):
    """Definitions on the test intervention plus a second intervention with its own field."""
    text = InterventionMetadataFieldFactory(intervention=intervention, name="Partner", order=0)
    single = InterventionMetadataFieldFactory(
        intervention=intervention, name="Age", field_type=MetadataFieldType.SINGLE_CHOICE, order=1
    )
    a = InterventionMetadataOptionFactory(field=single, label="A", order=0)
    multi = InterventionMetadataFieldFactory(
        intervention=intervention, name="Approach", field_type=MetadataFieldType.MULTIPLE_CHOICE, order=2
    )
    x = InterventionMetadataOptionFactory(field=multi, label="X", order=0)
    y = InterventionMetadataOptionFactory(field=multi, label="Y", order=1)
    number = InterventionMetadataFieldFactory(
        intervention=intervention,
        name="Volunteers",
        field_type=MetadataFieldType.NUMBER,
        number_type=MetadataNumberType.INTEGER,
        order=3,
    )
    other = InterventionFactory(output_metrics=["NumberOfTeacherDaysOfTraining"])
    budget = InterventionMetadataFieldFactory(
        intervention=other,
        name="Budget",
        field_type=MetadataFieldType.NUMBER,
        number_type=MetadataNumberType.DECIMAL,
    )
    return {
        "text": text,
        "single": single,
        "a": a,
        "multi": multi,
        "x": x,
        "y": y,
        "number": number,
        "other": other,
        "budget": budget,
    }


def mapping_of(form):
    return json.loads(html.unescape(form.fields["intervention"].widget.attrs["data-metadata-mapping"]))


@pytest.mark.django_db
class TestInstanceMetadata:
    def test_controls_exist_for_every_intervention_with_only_the_selected_one_active(
        self, analysis, intervention, add_form_data, defined
    ):
        form = InterventionInstanceForm(data=add_form_data, analysis=analysis)

        assert name_of(defined["text"]) in form.fields
        assert name_of(defined["budget"]) in form.fields
        assert form.fields[name_of(defined["text"])].disabled is False
        assert form.fields[name_of(defined["budget"])].disabled is True
        mapping = mapping_of(form)
        assert mapping[str(intervention.pk)] == [
            name_of(defined[k]) for k in ("text", "single", "multi", "number")
        ]
        assert mapping[str(defined["other"].pk)] == [name_of(defined["budget"])]
        assert form.fields[name_of(defined["text"])].widget.attrs["data-intervention"] == intervention.pk

    def test_add_saves_the_selected_interventions_values_and_omits_blanks(
        self, analysis, add_form_data, defined
    ):
        data = {
            **add_form_data,
            name_of(defined["text"]): "  Amoud  ",
            name_of(defined["single"]): defined["a"].storage_key,
            name_of(defined["multi"]): [defined["x"].storage_key, defined["y"].storage_key],
            name_of(defined["number"]): "0",
            name_of(defined["budget"]): "abc",  # inactive: not validated, not saved
        }
        form = InterventionInstanceForm(data=data, analysis=analysis)

        assert form.is_valid(), form.errors
        instance = form.save()

        assert instance.metadata == {
            defined["text"].storage_key: "Amoud",
            defined["single"].storage_key: defined["a"].storage_key,
            defined["multi"].storage_key: [defined["x"].storage_key, defined["y"].storage_key],
            defined["number"].storage_key: "0",
        }
        assert InterventionInstance.objects.get(pk=instance.pk).metadata == instance.metadata

    def test_all_metadata_is_optional(self, analysis, add_form_data, defined):
        form = InterventionInstanceForm(data=add_form_data, analysis=analysis)
        assert form.is_valid(), form.errors
        assert form.save().metadata == {}

    def test_invalid_active_values_are_reported(self, analysis, add_form_data, defined):
        data = {
            **add_form_data,
            name_of(defined["number"]): "1.5",
            name_of(defined["single"]): str(uuid.uuid4()),
            name_of(defined["multi"]): [defined["x"].storage_key, str(uuid.uuid4())],
            name_of(defined["text"]): "t" * 256,
        }
        form = InterventionInstanceForm(data=data, analysis=analysis)

        assert not form.is_valid()
        assert set(form.errors) == {name_of(defined[k]) for k in ("number", "single", "multi", "text")}

    def test_retired_and_unknown_keys_are_ignored_and_orphans_dropped_on_save(
        self, analysis, intervention, add_form_data, defined
    ):
        orphan = str(uuid.uuid4())
        instance = InterventionInstanceFactory(
            analysis=analysis,
            intervention=intervention,
            parameters={"number_of_teachers": 5.0, "number_of_days_of_training": 3.0},
            metadata={defined["text"].storage_key: "Old", orphan: "stale"},
        )
        data = {**add_form_data, name_of(defined["text"]): "New", f"metadata__{orphan}": "resurrect"}
        form = InterventionInstanceForm(data=data, instance=instance)

        assert form.is_valid(), form.errors
        assert form.save().metadata == {defined["text"].storage_key: "New"}

    def test_editing_seeds_the_current_values(self, analysis, intervention, defined):
        instance = InterventionInstanceFactory(
            analysis=analysis,
            intervention=intervention,
            metadata={
                defined["text"].storage_key: "Amoud",
                defined["multi"].storage_key: [defined["y"].storage_key],
            },
        )
        form = InterventionInstanceForm(instance=instance)
        assert form.fields[name_of(defined["text"])].initial == "Amoud"
        assert form.fields[name_of(defined["multi"])].initial == [defined["y"].storage_key]
        assert form.fields[name_of(defined["number"])].initial is None
        assert form.fields[name_of(defined["budget"])].disabled is True

    def test_selections_of_deleted_options_are_not_seeded_and_do_not_block_a_switch(
        self, analysis, intervention, defined
    ):
        gone = InterventionMetadataOptionFactory(field=defined["single"], label="Gone", order=1)
        gone_multi = InterventionMetadataOptionFactory(field=defined["multi"], label="Gone", order=2)
        instance = InterventionInstanceFactory(
            analysis=analysis,
            intervention=intervention,
            metadata={
                defined["single"].storage_key: gone.storage_key,
                defined["multi"].storage_key: [defined["x"].storage_key, gone_multi.storage_key],
            },
        )
        gone.delete()
        gone_multi.delete()

        form = InterventionInstanceForm(instance=instance)
        assert form.fields[name_of(defined["single"])].initial is None
        assert form.fields[name_of(defined["multi"])].initial == [defined["x"].storage_key]

        # The old intervention's controls are inactive, and Django validates those from `initial`.
        data = {
            "intervention": str(defined["other"].pk),
            "parameter__number_of_teachers": "2",
            "parameter__number_of_days_of_training": "2",
        }
        form = InterventionInstanceForm(data=data, instance=instance)

        assert form.is_valid(), form.errors
        assert form.save().metadata == {}

    def test_switching_the_intervention_rebuilds_metadata_for_the_new_one(
        self, analysis, intervention, defined
    ):
        instance = InterventionInstanceFactory(
            analysis=analysis, intervention=intervention, metadata={defined["text"].storage_key: "Amoud"}
        )
        data = {
            "intervention": str(defined["other"].pk),
            "parameter__number_of_teachers": "2",
            "parameter__number_of_days_of_training": "2",
            name_of(defined["budget"]): "12.50",
            name_of(defined["text"]): "Still posted",  # now inactive
        }
        form = InterventionInstanceForm(data=data, instance=instance)

        assert form.is_valid(), form.errors
        saved = form.save()

        assert saved.intervention == defined["other"]
        assert saved.metadata == {defined["budget"].storage_key: "12.50"}

    def test_repeated_instances_keep_independent_values(self, analysis, intervention, add_form_data, defined):
        first = InterventionInstanceFactory(
            analysis=analysis, intervention=intervention, metadata={defined["text"].storage_key: "First"}
        )
        second = InterventionInstanceFactory(
            analysis=analysis,
            intervention=intervention,
            label="Second",
            metadata={defined["text"].storage_key: "Second"},
        )
        form = InterventionInstanceForm(
            data={**add_form_data, name_of(defined["text"]): "Changed"}, instance=first
        )
        assert form.is_valid(), form.errors
        form.save()
        assert InterventionInstance.objects.get(pk=second.pk).metadata == {
            defined["text"].storage_key: "Second"
        }
