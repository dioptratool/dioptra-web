import pytest
from django.contrib.auth import get_user_model

from website.forms.analysis import DefineForm
from website.models import Settings
from website.tests.factories import (
    AnalysisFactory,
    CountryFactory,
    UserFactory,
)

User = get_user_model()


@pytest.fixture
def a_user():
    return UserFactory(role=User.ADMIN)


@pytest.fixture
def form_data():
    country = CountryFactory()
    return {
        "title": "Test Analysis",
        "description": "Test Description",
        "start_date": "01-Jan-2023",
        "end_date": "31-Dec-2023",
        "country": str(country.id),
        "grants": "Grant",
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
    analysis = AnalysisFactory(title="Test Analysis", grants="Grant")

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
def test_define_form_clean_method_sets_owner(a_user, form_data):
    form = DefineForm(data=form_data, user=a_user)
    assert form.is_valid()
    form.clean()
    assert form.instance.owner == a_user
