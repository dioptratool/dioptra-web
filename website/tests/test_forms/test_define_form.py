import pytest
from django.contrib.auth import get_user_model

from website.forms.analysis import DefineForm
from website.models import InterventionInstance, Settings
from website.tests.factories import AnalysisFactory, CountryFactory, InterventionFactory, UserFactory

User = get_user_model()


@pytest.fixture
def a_user():
    return UserFactory(role=User.ADMIN)


@pytest.fixture
def form_data():
    intervention = InterventionFactory()
    country = CountryFactory()
    return {
        "title": "Test Analysis",
        "description": "Test Description",
        "start_date": "01-Jan-2023",
        "end_date": "31-Dec-2023",
        "country": str(country.id),
        "grants": "Grant",
        "intervention_data": [{"id": intervention.id, "instance_pk": -1}],
        "output_count_source": "Test Source",
        "other_hq_costs": False,
        "in_kind_contributions": False,
        "client_time": False,
    }


@pytest.fixture
def define_form(a_user, form_data):
    return DefineForm(data=form_data, user=a_user)


@pytest.mark.django_db
def test_define_form_valid_data(define_form):
    assert define_form.is_valid(), define_form.errors


@pytest.mark.django_db
def test_define_form_very_long_intervention_custom_name(form_data, a_user):
    form_data["intervention_data"][0]["intervention_label"] = (
        "This is a very long string that is specifically "
        "designed to exceed the 100-character limit by "
        "a significant margin."
    )

    define_form = DefineForm(data=form_data, user=a_user)
    assert not define_form.is_valid()


@pytest.mark.django_db
def test_define_form_no_intervention_custom_name(form_data, a_user):
    form_data["intervention_data"][0]["intervention_label"] = None
    define_form = DefineForm(data=form_data, user=a_user)
    assert define_form.is_valid()


@pytest.mark.django_db
def test_define_form_invalid_date_range(form_data, a_user):
    form_data["start_date"] = "31-Dec-2023"
    form_data["end_date"] = "01-Jan-2023"
    form = DefineForm(data=form_data, user=a_user)
    assert not form.is_valid()
    assert form.errors["start_date"] == ["Start date must be before end date."]


@pytest.mark.django_db
def test_define_form_clean_grants(define_form):
    define_form.data["grants"] = "Grant1, Grant2, Invalid Grant"
    form = DefineForm(data=define_form.data, user=define_form.user)
    assert not form.is_valid()
    assert 'Invalid grant format: "Invalid Grant"' in form.errors["grants"]


@pytest.mark.django_db
def test_define_form_disable_fields_when_data_loaded(
    a_user,
    form_data,
):
    Settings.objects.create()
    analysis = AnalysisFactory()

    form = DefineForm(data=form_data, user=a_user, instance=analysis, data_loaded=True)
    assert form.fields["start_date"].disabled
    assert form.fields["end_date"].disabled
    assert form.fields["grants"].disabled


@pytest.mark.django_db
def test_define_form_save(define_form):
    assert define_form.is_valid()
    instance = define_form.save()
    assert instance.title == "Test Analysis"
    assert instance.description == "Test Description"


@pytest.mark.django_db
def test_define_form_intervention_json(a_user):
    analysis = AnalysisFactory()
    form = DefineForm(user=a_user, instance=analysis)
    intervention_instance = InterventionInstance.objects.create(
        analysis=analysis,
        intervention=InterventionFactory(name="Test Intervention"),
    )
    intervention_json = form._get_intervention_json(intervention_instance)
    assert intervention_json["title"] == intervention_instance.display_name()
    assert intervention_json["intervention_name"] == "Test Intervention"


@pytest.mark.django_db
def test_define_form_clean_method_sets_owner(a_user, form_data):
    form = DefineForm(data=form_data, user=a_user)
    assert form.is_valid()
    form.clean()
    assert form.instance.owner == a_user


@pytest.mark.django_db
def test_intervention_type_change(a_user, form_data):
    intervention2 = InterventionFactory(name="Intervention 2")

    form = DefineForm(data=form_data, user=a_user)
    analysis = form.save()
    existing_intervention_instance = analysis.interventioninstance_set.first()

    form_data = {
        "title": analysis.title,
        "description": analysis.description,
        "start_date": analysis.start_date,
        "end_date": analysis.end_date,
        "country": analysis.country,
        "grants": analysis.grants,
        "intervention_data": [
            {
                "id": intervention2.pk,  # Changing the intervention
                "instance_pk": existing_intervention_instance.pk,
            }
        ],
        "output_count_source": analysis.output_count_source,
        "other_hq_costs": analysis.other_hq_costs,
        "in_kind_contributions": analysis.in_kind_contributions,
        "client_time": analysis.client_time,
    }

    form = DefineForm(data=form_data, user=a_user, instance=analysis)

    # Ensure the form is valid before saving
    assert form.is_valid(), form.errors
    instance = form.save()

    # Verify the old InterventionInstance is deleted
    with pytest.raises(InterventionInstance.DoesNotExist):
        InterventionInstance.objects.get(pk=existing_intervention_instance.pk)

    # Verify the new InterventionInstance is created
    new_intervention_instance = InterventionInstance.objects.get(analysis=instance)
    assert new_intervention_instance.intervention == intervention2
