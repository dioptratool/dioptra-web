import pytest
from django.conf import settings as django_settings

from website.forms.intervention_instance import InterventionInstanceForm
from website.models import CostLineItemInterventionAllocation, SubcomponentCostAnalysis
from website.tests.factories import (
    AnalysisFactory,
    CostLineItemConfigFactory,
    CostLineItemInterventionAllocationFactory,
    InterventionFactory,
    InterventionInstanceFactory,
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
