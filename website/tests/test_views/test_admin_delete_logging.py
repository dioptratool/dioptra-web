"""Deleting through the stock ombucore delete panel writes an application-log entry."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from app_log.models import AppLogEntry
from website.models import Country
from website.tests.factories import AnalysisFactory, CountryFactory, UserFactory

User = get_user_model()


@pytest.fixture
def admin():
    return UserFactory(role=User.ADMIN)


@pytest.fixture
def admin_client(client, admin):
    client.force_login(admin)
    return client


def delete_url(country):
    return reverse("ombucore.admin:website_country_delete", args=[country.pk])


@pytest.mark.django_db
class TestStockDeletePanelLogging:
    def test_a_confirmed_delete_is_logged_against_the_deleted_object(self, admin, admin_client):
        country = CountryFactory(name="Freedonia")

        response = admin_client.get(delete_url(country), {"confirmed": ""})

        assert response.status_code == 200
        assert not Country.objects.filter(pk=country.pk).exists()
        [entry] = AppLogEntry.objects.filter(action="Deleted")
        assert entry.actor_user == admin
        assert entry.content_type == ContentType.objects.get_for_model(Country)
        assert entry.object_id == country.pk
        assert entry.message == "Freedonia was successfully deleted."

    def test_a_protected_object_is_neither_deleted_nor_logged(self, admin_client):
        country = AnalysisFactory().country

        response = admin_client.get(delete_url(country), {"confirmed": ""})

        assert response.status_code == 200
        assert Country.objects.filter(pk=country.pk).exists()
        assert not AppLogEntry.objects.filter(action="Deleted").exists()
