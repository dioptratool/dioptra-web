import datetime
import io

import pytest
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.db import connection
from django.utils import timezone

from app_log.logger import create_entry, get_subscriptions_for_entry, log
from app_log.management.commands import app_log__send_emails
from app_log.models import AppLogEntry, Email, Subscription
from app_log.notifiers import Notifier, SendEmailNotifier
from website.app_log.loggers import (
    log_analysis_archived,
    log_analysis_status_changed,
    log_analysis_unarchived,
)
from .models import ExampleObject1, ExampleObject2
from ..factories import AnalysisFactory, UserFactory


@pytest.fixture
def test_models_db():
    ContentType.objects.clear_cache()

    # Create the tables
    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(ExampleObject1)
        schema_editor.create_model(ExampleObject2)
    try:
        yield
    finally:
        # Drop in reverse order (FK safety)
        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(ExampleObject2)
            schema_editor.delete_model(ExampleObject1)

            # drop any ContentType rows we just created and clear the cache again
            ContentType.objects.filter(app_label="tests_app_log").delete()
            ContentType.objects.clear_cache()


@pytest.fixture
def reload_app_log_notifiers(settings):
    """
    Clear and reload the app_log notifier registry for every test
    that tweaks settings.APP_LOG.  Avoids inter-test bleed-over.
    """
    yield
    app_config = apps.get_app_config("app_log")
    app_config.notifiers = {}
    app_config.load_notifiers()


@pytest.mark.django_db
@pytest.mark.usefixtures("reload_app_log_notifiers")
class TestAppLogEntryModel:

    def test_add_log_entries(self, test_models_db):
        user = UserFactory()
        obj1 = ExampleObject1.objects.create(name="Object 1")
        obj2 = ExampleObject2.objects.create(name="Object 2")
        entry1 = create_entry(user, "Created", obj1)
        entry2 = create_entry(user, "Created", obj2)
        assert AppLogEntry.objects.all().count() == 2
        assert entry1 != entry2

    def test_object_deleted_after_logging(self, test_models_db):
        user = UserFactory()
        obj = ExampleObject1.objects.create(name="To Delete")
        create_entry(user, "Created", obj)
        obj.delete()
        entry = AppLogEntry.objects.last()
        assert entry.obj is None
        assert entry.content_type.model_class() == ExampleObject1

    def test_user_deleted_after_logging(self, test_models_db):
        user = UserFactory(name="User To Delete")
        obj = ExampleObject1.objects.create(name="Object 1")
        create_entry(user, "Created", obj)
        user.delete()
        entry = AppLogEntry.objects.last()
        assert entry.actor_user is None
        assert entry.actor_name == "User To Delete"


@pytest.mark.django_db
@pytest.mark.usefixtures("reload_app_log_notifiers")
class TestGetSubscriptions:
    def test_get_subscriptions_by_timestamp_after(self, test_models_db):
        subscription = Subscription.objects.create(
            notifier="placeholder",
            timestamp_start=timezone.now() - datetime.timedelta(days=3),
        )

        # In timestamp range.
        entry = AppLogEntry(
            timestamp=timezone.now(),
            actor_name="some user",
            action="some action",
        )
        subscriptions = get_subscriptions_for_entry(entry)
        assert len(subscriptions) == 1
        assert subscription.pk == subscriptions[0].pk

    def test_get_subscriptions_by_timestamp_before(self, test_models_db):
        subscription = Subscription.objects.create(
            notifier="placeholder",
            timestamp_end=timezone.now(),
        )

        # In timestamp range.
        entry = AppLogEntry(
            timestamp=timezone.now() - datetime.timedelta(days=3),
            actor_name="some user",
            action="some action",
        )
        subscriptions = get_subscriptions_for_entry(entry)
        assert len(subscriptions) == 1
        assert subscription.pk == subscriptions[0].pk

    def test_get_subscriptions_by_timestamp_range(self, test_models_db):
        subscription = Subscription.objects.create(
            notifier="placeholder",
            timestamp_start=timezone.now() - datetime.timedelta(days=3),
            timestamp_end=timezone.now() + datetime.timedelta(days=3),
        )

        # In timestamp range.
        entry = AppLogEntry(
            timestamp=timezone.now(),
            actor_name="some user",
            action="some action",
        )
        subscriptions = get_subscriptions_for_entry(entry)
        assert len(subscriptions) == 1
        assert subscription.pk == subscriptions[0].pk

        # Outside of timestamp range.
        entry = AppLogEntry(
            timestamp=timezone.now() + datetime.timedelta(days=10),
            actor_name="some user",
            action="some action",
        )
        subscriptions = get_subscriptions_for_entry(entry)
        assert len(subscriptions) == 0

    def test_get_subscriptions_by_actor_name(self, test_models_db):
        subscription = Subscription.objects.create(
            notifier="placeholder",
            actor_name="steve",
        )

        entry = AppLogEntry(
            actor_name="steve",
            action="some action",
        )
        subscriptions = get_subscriptions_for_entry(entry)
        assert len(subscriptions) == 1
        assert subscription.pk == subscriptions[0].pk

        entry = AppLogEntry(
            actor_name="stephen",
            action="some action",
        )
        subscriptions = get_subscriptions_for_entry(entry)
        assert len(subscriptions) == 0

    def test_get_subscriptions_by_action(self, test_models_db):
        subscription = Subscription.objects.create(
            notifier="placeholder",
            action="created",
        )

        entry = AppLogEntry(
            action="created",
        )
        subscriptions = get_subscriptions_for_entry(entry)
        assert len(subscriptions) == 1
        assert subscription.pk == subscriptions[0].pk

        entry = AppLogEntry(
            action="updated",
        )
        subscriptions = get_subscriptions_for_entry(entry)
        assert len(subscriptions) == 0

    def test_get_subscriptions_by_message_keywords(self, test_models_db):
        subscription = Subscription.objects.create(
            notifier="placeholder",
            action="created",
            message_keywords="download",
        )

        entry = AppLogEntry(
            action="created",
            message="Steve Downloaded the Document",
        )
        subscriptions = get_subscriptions_for_entry(entry)
        assert len(subscriptions) == 1
        assert subscription.pk == subscriptions[0].pk

        entry = AppLogEntry(
            action="created",
            message="Steve Uploaded the Document",
        )
        subscriptions = get_subscriptions_for_entry(entry)
        assert len(subscriptions) == 0

    def test_get_subscriptions_without_keywords_by_message_keywords(self, test_models_db):
        subscription = Subscription.objects.create(
            notifier="placeholder",
            action="created",
        )

        entry = AppLogEntry(
            action="created",
            message="Steve Downloaded the Document",
        )
        subscriptions = get_subscriptions_for_entry(entry)
        assert len(subscriptions) == 1

    def test_get_subscriptions_by_content_type(self, test_models_db):
        obj1 = ExampleObject1.objects.create(name="Object 1")
        obj2 = ExampleObject2.objects.create(name="Object 2")
        subscription = Subscription.objects.create(
            notifier="placeholder",
            action="created",
            content_type=ContentType.objects.get_for_model(obj1),
        )

        entry = AppLogEntry(
            action="created",
            content_type=ContentType.objects.get_for_model(obj1),
        )
        subscriptions = get_subscriptions_for_entry(entry)
        assert len(subscriptions) == 1

        entry = AppLogEntry(
            action="created",
            content_type=ContentType.objects.get_for_model(obj2),
        )
        subscriptions = get_subscriptions_for_entry(entry)
        assert len(subscriptions) == 0


@pytest.mark.django_db
@pytest.mark.usefixtures("reload_app_log_notifiers")
class TestNotifier:
    def test_notifier_creates_email(self, test_models_db):
        obj1 = ExampleObject1.objects.create(name="Object 1")
        user = UserFactory()
        entry = AppLogEntry(
            actor_name="Test Actor Name",
            action="Updated",
            obj=obj1,
            message=f"{obj1} was updated.",
        )
        subscription = Subscription(
            owner=user,
            notifier="app_log.notifiers.SendEmailNotifier",
            notifier_config={},
        )
        notifier = SendEmailNotifier()
        notifier.notify(subscription, entry)

        email = Email.objects.last()
        assert Email.objects.all().count() == 1
        assert entry.message in email.subject
        assert user.email == email.to_address

    def test_notifier_sends_emails(self, test_models_db):
        email = Email.objects.create(
            subject="Test Email",
            to_address="test@dioptratool.org",
            body="Test Body",
            body_html="<p>Test Body</p>",
        )

        notifier = SendEmailNotifier()
        results = notifier.send_emails()

        assert len(mail.outbox) == 1
        assert results["sent"] == 1
        assert email.subject in mail.outbox[0].subject
        assert Email.objects.all().count() == 0  # Email was successfully deleted.


@pytest.mark.django_db
@pytest.mark.usefixtures("reload_app_log_notifiers")
class TestSubscriptionSendEmailNotifier:
    """
    Tests the whole flow put together.
    """

    def test_entire_flow(self, test_models_db, settings):
        settings.APP_LOG = {
            "notifiers": [
                "app_log.notifiers.SendEmailNotifier",
            ],
        }
        # Reload notifiers after changing settings
        app_config = apps.get_app_config("app_log")
        app_config.load_notifiers()

        obj1 = ExampleObject1.objects.create(name="Object 1")
        user = UserFactory(name="steve")

        # Clear any onboarding emails
        mail.outbox.clear()
        subscription = Subscription.objects.create(
            owner=user,
            notifier="app_log.notifiers.SendEmailNotifier",
            timestamp_start=timezone.now() - datetime.timedelta(days=3),
            timestamp_end=timezone.now() + datetime.timedelta(days=3),
            actor_name="steve",
            action="Updated",
            content_type=ContentType.objects.get_for_model(obj1),
            message_keywords="was updated by",
        )

        log(
            actor=user,
            action="Updated",
            obj=obj1,
            message=f"{str(obj1)} was updated by {user.name}",
        )

        assert Email.objects.all().count() == 1

        notifier = SendEmailNotifier()
        results = notifier.send_emails()

        assert results["sent"] == 1
        assert len(mail.outbox) == 1
        assert "Dioptra application log: Object 1 was updated by steve" in mail.outbox[0].subject
        assert Email.objects.all().count() == 0


@pytest.mark.django_db
@pytest.mark.usefixtures("reload_app_log_notifiers")
class TestSendEmailsManagementCommand:
    """
    Tests the management command sending emails.
    """

    def test_notifier_sends_emails(self, test_models_db):
        Email.objects.create(
            subject="Test Email",
            to_address="test@dioptratool.org",
            body="Test Body",
            body_html="<p>Test Body</p>",
        )

        command = app_log__send_emails.Command()

        out = io.StringIO()
        call_command(command, stdout=out)

        out.seek(0)
        output = out.read()

        assert "Emails sent: 1" in output

        call_command(command, stdout=out)
        out.seek(0)
        output = out.read()
        assert "No emails to send." in output


class MockNotifier(Notifier):
    pass


@pytest.mark.django_db
@pytest.mark.usefixtures("reload_app_log_notifiers")
class TestNotifierLoadedFromSettings:
    def test_notifiers_loaded_from_settings(self, settings, test_models_db):
        settings.APP_LOG = {
            "notifiers": [
                "website.tests.test_app_log.test_app_log.MockNotifier",
            ],
        }
        app_config = apps.get_app_config("app_log")
        app_config.load_notifiers()

        mock_notifier = app_config.get_notifier("website.tests.test_app_log.test_app_log.MockNotifier")
        assert isinstance(mock_notifier, MockNotifier)
        with pytest.raises(ImproperlyConfigured):
            app_config.get_notifier("app_log.bad_path.MockNotifier")


@pytest.mark.django_db
@pytest.mark.usefixtures("reload_app_log_notifiers")
class TestAnalysisLifecycleLoggers:
    """The lifecycle helpers create the entry only; the caller notifies after its commit."""

    def test_status_change_entry(self):
        user = UserFactory(name="Pat")
        analysis = AnalysisFactory(title="Cash transfers")
        entry = log_analysis_status_changed(analysis, "In Progress", "Complete", user=user)
        assert entry.action == "Status changed"
        assert entry.actor_user == user
        assert entry.actor_name == "Pat"
        assert entry.obj == analysis
        assert entry.message == "Changed status of analysis Cash transfers from In Progress to Complete."

    def test_automatic_reset_entry_without_a_user_is_system_work(self):
        analysis = AnalysisFactory(title="Cash transfers")
        entry = log_analysis_status_changed(analysis, "Validated", "In Progress", user=None, automatic=True)
        assert entry.action == "Status reset"
        assert entry.actor_user is None
        assert entry.actor_name == "System"
        assert "automatically reset from Validated to In Progress" in entry.message

    def test_automatic_reset_entry_records_the_editing_user(self):
        user = UserFactory(name="Pat")
        entry = log_analysis_status_changed(
            AnalysisFactory(), "Complete", "In Progress", user=user, automatic=True
        )
        assert entry.action == "Status reset"
        assert entry.actor_user == user

    def test_archive_entries(self):
        user = UserFactory()
        analysis = AnalysisFactory(title="Cash transfers")
        archived = log_analysis_archived(analysis, user=user)
        unarchived = log_analysis_unarchived(analysis, user=user)
        assert (archived.action, archived.message) == ("Archived", "Archived analysis Cash transfers.")
        assert (unarchived.action, unarchived.message) == (
            "Unarchived",
            "Unarchived analysis Cash transfers.",
        )
        assert archived.actor_user == unarchived.actor_user == user
        assert archived.obj == unarchived.obj == analysis

    def test_helpers_do_not_notify_subscribers(self, settings):
        settings.APP_LOG = {"notifiers": ["app_log.notifiers.SendEmailNotifier"]}
        apps.get_app_config("app_log").load_notifiers()
        Subscription.objects.create(
            owner=UserFactory(), notifier="app_log.notifiers.SendEmailNotifier", action="Archived"
        )
        log_analysis_archived(AnalysisFactory(), user=UserFactory())
        assert AppLogEntry.objects.filter(action="Archived").count() == 1
        assert Email.objects.count() == 0
