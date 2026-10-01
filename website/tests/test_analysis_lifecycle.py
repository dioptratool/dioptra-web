"""Feature 94: the lifecycle fields on Analysis and the two lifecycle services.

The permission matrix behind the services is covered in test_permissions, the log helpers in
test_app_log, and workflow reconciliation after edits in the step tests.
"""

import datetime
import io
from itertools import permutations

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.db import DataError, connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from app_log.models import AppLogEntry, Email, Subscription
from website.analysis_lifecycle import (
    AnalysisLifecycleError,
    AnalysisLifecyclePermissionDenied,
    AnalysisNotReady,
    analysis_is_ready,
    change_analysis_status,
    permitted_status_targets,
    set_analysis_archived,
)
from website.models import Analysis, AnalysisStatus
from website.tests.factories import AnalysisFactory, CountryFactory, UserFactory
from website.workflows import AnalysisWorkflow
from website.workflows.utils import WORKFLOW_PREFETCHES, recalculate_analysis

User = get_user_model()

# The complete-workflow fixtures run once per workflow variant; the services do not care which
# variant built the analysis, so these tests pin one.
ONE_WORKFLOW_VARIANT = pytest.mark.parametrize(
    "analysis_workflow_with_loaddata_complete", ["analysis_workflow_with_analysis"], indirect=True
)


def stored(analysis):
    """A fresh copy of the row from the database."""
    return Analysis.objects.get(pk=analysis.pk)


def assert_fresh_lifecycle(row, owner):
    assert row.analysis_status == AnalysisStatus.IN_PROGRESS
    assert row.is_archived is False
    assert row.status_changed_by == owner
    assert row.status_changed_at == row.created
    assert row.archived_by is None
    assert row.archived_at is None


@pytest.mark.django_db
class TestNewAnalysisInitialization:
    def test_factory_created_analysis_starts_in_progress_and_unarchived(self):
        owner = UserFactory()
        analysis = AnalysisFactory(owner=owner)
        assert_fresh_lifecycle(stored(analysis), owner)

    def test_instance_matches_the_stored_lifecycle_values(self):
        analysis = AnalysisFactory()
        row = stored(analysis)
        for field in Analysis.LIFECYCLE_FIELDS:
            assert getattr(analysis, field) == getattr(row, field), field

    def test_missing_owner_leaves_status_actor_null(self):
        analysis = AnalysisFactory(owner=None)
        assert_fresh_lifecycle(stored(analysis), None)

    def test_objects_create_uses_the_same_initialization(self):
        owner = UserFactory()
        analysis = Analysis.objects.create(
            title="Created directly",
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 12, 31),
            country=CountryFactory(),
            owner=owner,
        )
        assert_fresh_lifecycle(stored(analysis), owner)

    def test_supplied_lifecycle_values_are_replaced_on_insert(self):
        """A row built from another row's values, as the duplicator does, does not inherit its audits."""
        owner = UserFactory()
        someone_else = UserFactory()
        long_ago = timezone.now() - datetime.timedelta(days=30)
        analysis = Analysis(
            title="Copied",
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 12, 31),
            country=CountryFactory(),
            owner=owner,
            analysis_status=AnalysisStatus.VALIDATED,
            status_changed_by=someone_else,
            status_changed_at=long_ago,
            is_archived=True,
            archived_by=someone_else,
            archived_at=long_ago,
        )
        analysis.save()
        row = stored(analysis)
        assert_fresh_lifecycle(row, owner)
        assert analysis.status_changed_at == row.created


@pytest.mark.django_db
class TestExistingAnalysisSaves:
    def test_plain_save_persists_ordinary_fields(self):
        analysis = AnalysisFactory(title="Before")
        new_owner = UserFactory()
        analysis.title = "After"
        analysis.description = "Described"
        analysis.grants = "G1,G2"
        analysis.source = "Source system"
        analysis.output_costs = {"1": {"metric": {"all": "1.0"}}}
        analysis.other_hq_costs = True
        analysis.needs_transaction_resync = True
        analysis.owner = new_owner
        analysis.save()
        row = stored(analysis)
        assert row.title == "After"
        assert row.description == "Described"
        assert row.grants == "G1,G2"
        assert row.source == "Source system"
        assert row.output_costs == {"1": {"metric": {"all": "1.0"}}}
        assert row.other_hq_costs is True
        assert row.needs_transaction_resync is True
        assert row.owner == new_owner

    def test_plain_save_writes_every_field_except_the_lifecycle_fields(self):
        """A field added to Analysis later must not be silently dropped from plain saves."""
        analysis = AnalysisFactory()
        all_fields = {field.name for field in Analysis._meta.concrete_fields if not field.primary_key}
        assert set(Analysis.LIFECYCLE_FIELDS) <= all_fields
        assert set(analysis.ordinary_update_fields()) == all_fields - set(Analysis.LIFECYCLE_FIELDS)

    def test_plain_save_still_refreshes_updated(self):
        analysis = AnalysisFactory()
        before = stored(analysis).updated
        analysis.title = "Touched"
        analysis.save()
        assert stored(analysis).updated > before

    def test_stale_instance_cannot_overwrite_lifecycle_fields(self):
        analysis = AnalysisFactory()
        stale = stored(analysis)
        actor = UserFactory()
        when = timezone.now()
        # The kind of update-only write the lifecycle services make.
        Analysis.objects.filter(pk=analysis.pk).update(
            analysis_status=AnalysisStatus.COMPLETE,
            status_changed_by=actor,
            status_changed_at=when,
            is_archived=True,
            archived_by=actor,
            archived_at=when,
        )

        stale.title = "Edited from a stale instance"
        stale.save()

        row = stored(analysis)
        assert row.title == "Edited from a stale instance"
        assert row.analysis_status == AnalysisStatus.COMPLETE
        assert row.status_changed_by == actor
        assert row.status_changed_at == when
        assert row.is_archived is True
        assert row.archived_by == actor
        assert row.archived_at == when

    def test_explicit_update_fields_are_honored(self):
        analysis = AnalysisFactory(title="Original")
        analysis.analysis_status = AnalysisStatus.COMPLETE
        analysis.title = "Not saved"
        analysis.save(update_fields=["analysis_status"])
        row = stored(analysis)
        assert row.analysis_status == AnalysisStatus.COMPLETE
        assert row.title == "Original"

    def test_ownership_change_keeps_the_status_actor(self):
        creator = UserFactory()
        analysis = AnalysisFactory(owner=creator)
        analysis.owner = UserFactory()
        analysis.save()
        row = stored(analysis)
        assert row.owner != creator
        assert row.status_changed_by == creator

    def test_partially_loaded_instance_writes_only_loaded_fields(self):
        analysis = AnalysisFactory(title="Original", description="Keep me")
        partial = Analysis.objects.only("title").get(pk=analysis.pk)
        assert "description" not in partial.ordinary_update_fields()
        partial.title = "Changed"
        partial.save()
        row = stored(analysis)
        assert row.title == "Changed"
        assert row.description == "Keep me"


@pytest.mark.django_db
class TestFactoryLifecycleHook:
    def test_lifecycle_kwargs_write_the_fields_directly(self):
        actor = UserFactory()
        analysis = AnalysisFactory(
            lifecycle__analysis_status=AnalysisStatus.VALIDATED,
            lifecycle__status_changed_by=actor,
            lifecycle__is_archived=True,
        )
        row = stored(analysis)
        assert row.analysis_status == AnalysisStatus.VALIDATED
        assert row.status_changed_by == actor
        assert row.is_archived is True
        assert analysis.analysis_status == AnalysisStatus.VALIDATED
        assert analysis.status_changed_by == actor


# ---------------------------------------------------------------------------------------------
# Lifecycle services
# ---------------------------------------------------------------------------------------------


@pytest.fixture
def admin():
    return UserFactory(role=User.ADMIN)


@pytest.fixture
def complete_analysis(analysis_workflow_main_flow_complete):
    """An analysis whose every workflow step, Insights included, is complete."""
    return analysis_workflow_main_flow_complete.analysis


@pytest.fixture
def incomplete_analysis(analysis_workflow_with_analysis):
    """Define and Interventions done, no data loaded."""
    return analysis_workflow_with_analysis.analysis


@pytest.fixture
def notifier_registry():
    """Load the app_log notifiers from the real settings, whatever an earlier test left behind."""
    apps.get_app_config("app_log").load_notifiers()


def set_status(analysis, status):
    """Put an analysis into a status directly, as the service stores it, keeping its audits."""
    Analysis.objects.filter(pk=analysis.pk).update(analysis_status=status)
    analysis.refresh_from_db()


def break_readiness(analysis):
    """Un-confirm one category: Categorize, and every step after it, is then incomplete."""
    category = analysis.cost_type_categories.first()
    category.confirmed = False
    category.save()


def primary_country_editor(analysis):
    user = UserFactory()
    user.primary_countries.add(analysis.country)
    return user


def secondary_country_viewer(analysis):
    user = UserFactory()
    user.secondary_countries.add(analysis.country)
    return user


def log_entries(analysis):
    return list(
        AppLogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(Analysis), object_id=analysis.pk
        ).order_by("pk")
    )


DIRECTED_TRANSITIONS = list(permutations(AnalysisStatus, 2))


def test_permission_errors_are_django_permission_denied():
    assert issubclass(AnalysisLifecyclePermissionDenied, PermissionDenied)


@pytest.mark.django_db
@ONE_WORKFLOW_VARIANT
class TestChangeAnalysisStatus:
    def test_complete_fixture_is_ready(self, complete_analysis):
        assert analysis_is_ready(complete_analysis)

    @pytest.mark.parametrize(
        "current,target", DIRECTED_TRANSITIONS, ids=[f"{c.value}-{t.value}" for c, t in DIRECTED_TRANSITIONS]
    )
    def test_admin_makes_every_directed_transition(self, complete_analysis, admin, current, target):
        set_status(complete_analysis, current)

        result = change_analysis_status(complete_analysis.pk, admin, target)

        row = stored(complete_analysis)
        assert row.analysis_status == target
        assert row.status_changed_by == admin
        assert result.analysis_status == target
        assert result.status_changed_at == row.status_changed_at
        [entry] = log_entries(row)
        assert entry.action == "Status changed"
        assert entry.actor_user == admin
        assert str(current.label) in entry.message
        assert str(target.label) in entry.message

    def test_complete_to_validated_rechecks_readiness(self, complete_analysis, admin):
        set_status(complete_analysis, AnalysisStatus.COMPLETE)
        break_readiness(complete_analysis)
        with pytest.raises(AnalysisNotReady):
            change_analysis_status(complete_analysis.pk, admin, AnalysisStatus.VALIDATED)
        assert stored(complete_analysis).analysis_status == AnalysisStatus.COMPLETE
        assert log_entries(complete_analysis) == []

    def test_validated_to_complete_rechecks_readiness(self, complete_analysis, admin):
        set_status(complete_analysis, AnalysisStatus.VALIDATED)
        break_readiness(complete_analysis)
        with pytest.raises(AnalysisNotReady):
            change_analysis_status(complete_analysis.pk, admin, AnalysisStatus.COMPLETE)
        assert stored(complete_analysis).analysis_status == AnalysisStatus.VALIDATED

    def test_returning_to_in_progress_needs_no_readiness(self, complete_analysis, admin):
        set_status(complete_analysis, AnalysisStatus.VALIDATED)
        break_readiness(complete_analysis)
        change_analysis_status(complete_analysis.pk, admin, AnalysisStatus.IN_PROGRESS)
        assert stored(complete_analysis).analysis_status == AnalysisStatus.IN_PROGRESS

    def test_owner_moves_between_in_progress_and_complete(self, complete_analysis):
        owner = complete_analysis.owner
        change_analysis_status(complete_analysis.pk, owner, AnalysisStatus.COMPLETE)
        assert stored(complete_analysis).analysis_status == AnalysisStatus.COMPLETE
        change_analysis_status(complete_analysis.pk, owner, AnalysisStatus.IN_PROGRESS)
        row = stored(complete_analysis)
        assert row.analysis_status == AnalysisStatus.IN_PROGRESS
        assert row.status_changed_by == owner
        assert [entry.action for entry in log_entries(row)] == ["Status changed", "Status changed"]

    def test_primary_country_editor_moves_between_in_progress_and_complete(self, complete_analysis):
        editor = primary_country_editor(complete_analysis)
        change_analysis_status(complete_analysis.pk, editor, AnalysisStatus.COMPLETE)
        assert stored(complete_analysis).analysis_status == AnalysisStatus.COMPLETE
        change_analysis_status(complete_analysis.pk, editor, AnalysisStatus.IN_PROGRESS)
        row = stored(complete_analysis)
        assert row.analysis_status == AnalysisStatus.IN_PROGRESS
        assert row.status_changed_by == editor

    def test_basic_users_cannot_enter_validated(self, complete_analysis):
        set_status(complete_analysis, AnalysisStatus.COMPLETE)
        for actor in (complete_analysis.owner, primary_country_editor(complete_analysis)):
            with pytest.raises(AnalysisLifecyclePermissionDenied):
                change_analysis_status(complete_analysis.pk, actor, AnalysisStatus.VALIDATED)
        assert stored(complete_analysis).analysis_status == AnalysisStatus.COMPLETE
        assert log_entries(complete_analysis) == []

    def test_basic_users_cannot_leave_validated(self, complete_analysis):
        set_status(complete_analysis, AnalysisStatus.VALIDATED)
        for actor in (complete_analysis.owner, primary_country_editor(complete_analysis)):
            for target in (AnalysisStatus.COMPLETE, AnalysisStatus.IN_PROGRESS):
                with pytest.raises(AnalysisLifecyclePermissionDenied):
                    change_analysis_status(complete_analysis.pk, actor, target)
        assert stored(complete_analysis).analysis_status == AnalysisStatus.VALIDATED
        assert log_entries(complete_analysis) == []

    def test_users_without_edit_access_are_denied(self, complete_analysis):
        actors = [secondary_country_viewer(complete_analysis), UserFactory(), AnonymousUser(), None]
        for actor in actors:
            with pytest.raises(AnalysisLifecyclePermissionDenied):
                change_analysis_status(complete_analysis.pk, actor, AnalysisStatus.COMPLETE)
        assert stored(complete_analysis).analysis_status == AnalysisStatus.IN_PROGRESS
        assert log_entries(complete_analysis) == []

    def test_requesting_the_current_status_is_a_no_op(self, complete_analysis, admin):
        before = stored(complete_analysis)
        change_analysis_status(complete_analysis.pk, admin, AnalysisStatus.IN_PROGRESS)
        row = stored(complete_analysis)
        assert row.status_changed_by == before.status_changed_by
        assert row.status_changed_at == before.status_changed_at
        assert log_entries(row) == []

    def test_transition_records_actor_and_time(self, complete_analysis, admin):
        before = timezone.now()
        change_analysis_status(complete_analysis.pk, admin, AnalysisStatus.COMPLETE)
        row = stored(complete_analysis)
        assert row.status_changed_by == admin
        assert before <= row.status_changed_at <= timezone.now()

    def test_transition_leaves_every_other_field_alone(self, complete_analysis, admin):
        before = stored(complete_analysis)
        change_analysis_status(complete_analysis.pk, admin, AnalysisStatus.COMPLETE)
        row = stored(complete_analysis)
        assert row.updated == before.updated
        assert row.output_costs == before.output_costs
        assert row.title == before.title
        assert row.is_archived is False
        assert row.archived_by is None
        assert row.archived_at is None

    def test_unknown_status_is_rejected(self, complete_analysis, admin):
        with pytest.raises(AnalysisLifecycleError):
            change_analysis_status(complete_analysis.pk, admin, "finished")
        assert stored(complete_analysis).analysis_status == AnalysisStatus.IN_PROGRESS
        assert log_entries(complete_analysis) == []


@pytest.mark.django_db
@ONE_WORKFLOW_VARIANT
class TestAutomaticReset:
    def test_resets_an_incomplete_complete_analysis_recording_the_editor(self, complete_analysis):
        editor = primary_country_editor(complete_analysis)
        set_status(complete_analysis, AnalysisStatus.COMPLETE)
        break_readiness(complete_analysis)

        result = change_analysis_status(
            complete_analysis.pk, editor, AnalysisStatus.IN_PROGRESS, automatic=True
        )

        row = stored(complete_analysis)
        assert row.analysis_status == AnalysisStatus.IN_PROGRESS
        assert row.status_changed_by == editor
        assert result.status_changed_at == row.status_changed_at
        [entry] = log_entries(row)
        assert entry.action == "Status reset"
        assert entry.actor_user == editor
        assert "automatically reset from Complete to In Progress" in entry.message

    def test_resets_an_incomplete_validated_analysis_for_system_work(self, complete_analysis):
        set_status(complete_analysis, AnalysisStatus.VALIDATED)
        break_readiness(complete_analysis)

        change_analysis_status(complete_analysis.pk, None, AnalysisStatus.IN_PROGRESS, automatic=True)

        row = stored(complete_analysis)
        assert row.analysis_status == AnalysisStatus.IN_PROGRESS
        assert row.status_changed_by is None
        [entry] = log_entries(row)
        assert entry.action == "Status reset"
        assert entry.actor_user is None
        assert entry.actor_name == "System"

    def test_reset_from_validated_does_not_need_an_admin(self, complete_analysis):
        """It is a system rule, not the editing user's status permission."""
        set_status(complete_analysis, AnalysisStatus.VALIDATED)
        break_readiness(complete_analysis)
        change_analysis_status(
            complete_analysis.pk, complete_analysis.owner, AnalysisStatus.IN_PROGRESS, automatic=True
        )
        row = stored(complete_analysis)
        assert row.analysis_status == AnalysisStatus.IN_PROGRESS
        assert row.status_changed_by == complete_analysis.owner

    def test_no_reset_while_the_workflow_is_complete(self, complete_analysis, admin):
        set_status(complete_analysis, AnalysisStatus.COMPLETE)
        before = stored(complete_analysis)
        change_analysis_status(complete_analysis.pk, admin, AnalysisStatus.IN_PROGRESS, automatic=True)
        row = stored(complete_analysis)
        assert row.analysis_status == AnalysisStatus.COMPLETE
        assert row.status_changed_at == before.status_changed_at
        assert log_entries(row) == []

    def test_only_in_progress_can_be_targeted(self, complete_analysis, admin):
        with pytest.raises(ValueError):
            change_analysis_status(complete_analysis.pk, admin, AnalysisStatus.COMPLETE, automatic=True)


@pytest.mark.django_db
class TestIncompleteAnalyses:
    """Cases that need no complete workflow, so they skip the workflow-variant fixtures."""

    def test_incomplete_fixture_is_not_ready(self, incomplete_analysis):
        assert not analysis_is_ready(incomplete_analysis)

    @pytest.mark.parametrize("target", [AnalysisStatus.COMPLETE, AnalysisStatus.VALIDATED])
    def test_entering_complete_or_validated_requires_readiness(self, incomplete_analysis, admin, target):
        before = stored(incomplete_analysis)
        with pytest.raises(AnalysisNotReady):
            change_analysis_status(incomplete_analysis.pk, admin, target)
        row = stored(incomplete_analysis)
        assert row.analysis_status == AnalysisStatus.IN_PROGRESS
        assert row.status_changed_by == before.status_changed_by
        assert row.status_changed_at == before.status_changed_at
        assert log_entries(row) == []

    def test_automatic_reset_is_a_no_op_when_already_in_progress(self, incomplete_analysis):
        before = stored(incomplete_analysis)
        change_analysis_status(incomplete_analysis.pk, None, AnalysisStatus.IN_PROGRESS, automatic=True)
        row = stored(incomplete_analysis)
        assert row.status_changed_by == before.status_changed_by
        assert row.status_changed_at == before.status_changed_at
        assert log_entries(row) == []


@pytest.mark.django_db
class TestSetAnalysisArchived:
    @pytest.mark.parametrize("status", list(AnalysisStatus))
    def test_admin_archives_and_unarchives_in_every_status(self, admin, status):
        analysis = AnalysisFactory(lifecycle__analysis_status=status)

        set_analysis_archived(analysis.pk, admin, True)
        row = stored(analysis)
        assert row.is_archived is True
        assert row.archived_by == admin
        assert row.archived_at is not None
        assert row.analysis_status == status

        set_analysis_archived(analysis.pk, admin, False)
        row = stored(analysis)
        assert row.is_archived is False
        assert row.archived_by is None
        assert row.archived_at is None
        assert row.analysis_status == status
        assert [entry.action for entry in log_entries(row)] == ["Archived", "Unarchived"]

    @pytest.mark.parametrize("status", list(AnalysisStatus))
    def test_owner_archives_and_unarchives_in_every_status(self, status):
        analysis = AnalysisFactory(lifecycle__analysis_status=status)
        owner = analysis.owner

        set_analysis_archived(analysis.pk, owner, True)
        row = stored(analysis)
        assert row.is_archived is True
        assert row.archived_by == owner

        set_analysis_archived(analysis.pk, owner, False)
        row = stored(analysis)
        assert row.is_archived is False
        assert row.archived_by is None
        assert row.archived_at is None
        assert row.analysis_status == status

    def test_users_who_do_not_own_the_analysis_are_denied(self):
        analysis = AnalysisFactory()
        actors = [
            primary_country_editor(analysis),
            secondary_country_viewer(analysis),
            UserFactory(),
            AnonymousUser(),
            None,
        ]
        for actor in actors:
            with pytest.raises(AnalysisLifecyclePermissionDenied):
                set_analysis_archived(analysis.pk, actor, True)
        assert stored(analysis).is_archived is False

        archived = AnalysisFactory(lifecycle__is_archived=True)
        for actor in actors[:3] + [AnonymousUser(), None]:
            with pytest.raises(AnalysisLifecyclePermissionDenied):
                set_analysis_archived(archived.pk, actor, False)
        assert stored(archived).is_archived is True
        assert log_entries(analysis) == []
        assert log_entries(archived) == []

    def test_archive_sets_audit_fields_and_logs_once(self):
        analysis = AnalysisFactory()
        before = timezone.now()
        result = set_analysis_archived(analysis.pk, analysis.owner, True)
        row = stored(analysis)
        assert before <= row.archived_at <= timezone.now()
        assert result.archived_at == row.archived_at
        [entry] = log_entries(row)
        assert entry.action == "Archived"
        assert entry.actor_user == analysis.owner
        assert entry.obj == analysis

    def test_unarchive_clears_audit_fields_and_keeps_the_history(self):
        analysis = AnalysisFactory()
        set_analysis_archived(analysis.pk, analysis.owner, True)
        set_analysis_archived(analysis.pk, analysis.owner, False)
        row = stored(analysis)
        assert row.is_archived is False
        assert row.archived_by is None
        assert row.archived_at is None
        assert [entry.action for entry in log_entries(row)] == ["Archived", "Unarchived"]

    def test_repeated_requests_are_no_ops(self):
        analysis = AnalysisFactory()
        set_analysis_archived(analysis.pk, analysis.owner, True)
        first = stored(analysis)
        set_analysis_archived(analysis.pk, analysis.owner, True)
        assert stored(analysis).archived_at == first.archived_at
        assert len(log_entries(analysis)) == 1

        set_analysis_archived(analysis.pk, analysis.owner, False)
        set_analysis_archived(analysis.pk, analysis.owner, False)
        assert len(log_entries(analysis)) == 2

    def test_archiving_preserves_status_outputs_and_status_audits(self, admin):
        actor = UserFactory()
        analysis = AnalysisFactory(
            output_costs={"1": {"metric": {"all": "2.5"}}},
            lifecycle__analysis_status=AnalysisStatus.VALIDATED,
            lifecycle__status_changed_by=actor,
        )
        before = stored(analysis)
        set_analysis_archived(analysis.pk, admin, True)
        row = stored(analysis)
        assert row.analysis_status == AnalysisStatus.VALIDATED
        assert row.status_changed_by == actor
        assert row.status_changed_at == before.status_changed_at
        assert row.output_costs == before.output_costs
        assert row.updated == before.updated


@pytest.mark.django_db
@ONE_WORKFLOW_VARIANT
class TestLifecycleWritesAreAtomic:
    def test_a_failed_log_entry_rolls_back_the_status_change(self, complete_analysis, admin):
        # The log entry stores str(actor) in a 255-character column. An actor whose name does not
        # fit makes that insert fail for real, after the status itself has been written.
        admin.name = "x" * 300  # In memory only; the stored user is untouched.
        before = stored(complete_analysis)
        with pytest.raises(DataError):
            change_analysis_status(complete_analysis.pk, admin, AnalysisStatus.COMPLETE)
        row = stored(complete_analysis)
        assert row.analysis_status == AnalysisStatus.IN_PROGRESS
        assert row.status_changed_by == before.status_changed_by
        assert row.status_changed_at == before.status_changed_at
        assert log_entries(row) == []


@pytest.mark.django_db
@pytest.mark.usefixtures("notifier_registry")
class TestLifecycleNotifications:
    def test_subscribers_are_notified_only_after_commit(self, django_capture_on_commit_callbacks):
        subscriber = UserFactory()
        analysis = AnalysisFactory()
        Subscription.objects.create(
            owner=subscriber, notifier="app_log.notifiers.SendEmailNotifier", action="Archived"
        )

        with django_capture_on_commit_callbacks() as callbacks:
            set_analysis_archived(analysis.pk, analysis.owner, True)
            assert Email.objects.count() == 0

        assert len(callbacks) == 1
        callbacks[0]()
        [email] = Email.objects.all()
        assert email.to_address == subscriber.email
        assert analysis.title in email.subject

    def test_a_no_op_schedules_no_notification(self, django_capture_on_commit_callbacks):
        analysis = AnalysisFactory(lifecycle__is_archived=True)
        Subscription.objects.create(
            owner=UserFactory(), notifier="app_log.notifiers.SendEmailNotifier", action="Archived"
        )
        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            set_analysis_archived(analysis.pk, analysis.owner, True)
        assert callbacks == []
        assert Email.objects.count() == 0

    def test_a_failing_notification_does_not_undo_the_operation(self, django_capture_on_commit_callbacks):
        analysis = AnalysisFactory()
        # No such notifier is registered, so notifying this subscription raises after commit.
        Subscription.objects.create(
            owner=UserFactory(), notifier="website.nowhere.MissingNotifier", action="Archived"
        )

        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            set_analysis_archived(analysis.pk, analysis.owner, True)

        assert len(callbacks) == 1
        row = stored(analysis)
        assert row.is_archived is True
        assert [entry.action for entry in log_entries(row)] == ["Archived"]
        assert Email.objects.count() == 0


# ---------------------------------------------------------------------------------------------
# Reconciliation after edits
# ---------------------------------------------------------------------------------------------


def request_workflow(analysis):
    """A workflow the way a view builds one: around a prefetched analysis."""
    return AnalysisWorkflow(Analysis.objects.prefetch_related(*WORKFLOW_PREFETCHES).get(pk=analysis.pk))


def no_row_locks(captured_queries):
    return not any("FOR UPDATE" in query["sql"] for query in captured_queries)


@pytest.mark.django_db
@ONE_WORKFLOW_VARIANT
class TestReconcileLifecycleStatus:
    @pytest.mark.parametrize("status", [AnalysisStatus.COMPLETE, AnalysisStatus.VALIDATED])
    def test_edit_leaving_the_workflow_incomplete_resets_once_with_the_editor(
        self, complete_analysis, status
    ):
        editor = primary_country_editor(complete_analysis)
        set_status(complete_analysis, status)
        workflow = request_workflow(complete_analysis)
        # Step results and the confirmed categories are now cached from before the edit.
        assert workflow.all_steps_complete
        break_readiness(complete_analysis)
        before = timezone.now()

        workflow.invalidate_step("insights")
        workflow.calculate_if_possible(editor)

        row = stored(complete_analysis)
        assert row.analysis_status == AnalysisStatus.IN_PROGRESS
        assert row.status_changed_by == editor
        assert before <= row.status_changed_at <= timezone.now()
        [entry] = log_entries(row)
        assert entry.action == "Status reset"
        assert entry.actor_user == editor
        # The request's analysis carries the stored values for the rest of the request.
        assert workflow.analysis.analysis_status == AnalysisStatus.IN_PROGRESS
        assert workflow.analysis.status_changed_by_id == editor.pk
        assert workflow.analysis.status_changed_at == row.status_changed_at
        # Reconciling again changes nothing more.
        workflow.reconcile_lifecycle_status(editor)
        assert len(log_entries(row)) == 1

    @pytest.mark.parametrize("status", [AnalysisStatus.COMPLETE, AnalysisStatus.VALIDATED])
    def test_edit_leaving_the_workflow_complete_preserves_status_and_audits(self, complete_analysis, status):
        actor = UserFactory()
        Analysis.objects.filter(pk=complete_analysis.pk).update(
            analysis_status=status, status_changed_by=actor
        )
        before = stored(complete_analysis)
        workflow = request_workflow(complete_analysis)

        # Invalidation is a passing stage of an edit that ends complete; it must not demote.
        workflow.invalidate_step("insights")
        workflow.calculate_if_possible(UserFactory())

        row = stored(complete_analysis)
        assert row.analysis_status == status
        assert row.status_changed_by == actor
        assert row.status_changed_at == before.status_changed_at
        assert log_entries(row) == []

    def test_in_progress_analysis_is_reconciled_without_queries(
        self, complete_analysis, django_assert_num_queries
    ):
        editor = primary_country_editor(complete_analysis)
        workflow = request_workflow(complete_analysis)
        with django_assert_num_queries(0):
            workflow.reconcile_lifecycle_status(editor)

    def test_complete_analysis_is_checked_without_a_row_lock(self, complete_analysis):
        set_status(complete_analysis, AnalysisStatus.COMPLETE)
        workflow = request_workflow(complete_analysis)
        with CaptureQueriesContext(connection) as context:
            workflow.reconcile_lifecycle_status(UserFactory())
        assert context.captured_queries  # the fresh readiness check reads
        assert no_row_locks(context.captured_queries)
        assert stored(complete_analysis).analysis_status == AnalysisStatus.COMPLETE
        assert log_entries(complete_analysis) == []

    def test_reset_takes_the_lock_only_once_the_fresh_check_fails(self, complete_analysis):
        set_status(complete_analysis, AnalysisStatus.COMPLETE)
        break_readiness(complete_analysis)
        workflow = request_workflow(complete_analysis)
        with CaptureQueriesContext(connection) as context:
            workflow.reconcile_lifecycle_status(UserFactory())
        assert not no_row_locks(context.captured_queries)
        assert stored(complete_analysis).analysis_status == AnalysisStatus.IN_PROGRESS

    def test_becoming_complete_again_does_not_promote(self, complete_analysis, admin):
        set_status(complete_analysis, AnalysisStatus.COMPLETE)
        break_readiness(complete_analysis)
        request_workflow(complete_analysis).calculate_if_possible(admin)
        assert stored(complete_analysis).analysis_status == AnalysisStatus.IN_PROGRESS

        complete_analysis.cost_type_categories.update(confirmed=True)
        request_workflow(complete_analysis).calculate_if_possible(admin)

        row = stored(complete_analysis)
        assert row.analysis_status == AnalysisStatus.IN_PROGRESS
        assert row.status_changed_by == admin
        assert len(log_entries(row)) == 1

    def test_reset_made_elsewhere_is_synced_without_a_second_event(self, complete_analysis):
        workflow = request_workflow(complete_analysis)
        workflow.analysis.analysis_status = AnalysisStatus.COMPLETE  # what this request loaded
        break_readiness(complete_analysis)  # the stored row is already In Progress

        workflow.reconcile_lifecycle_status(UserFactory())

        assert workflow.analysis.analysis_status == AnalysisStatus.IN_PROGRESS
        assert log_entries(complete_analysis) == []

    def test_recalculate_analysis_forwards_the_editor(self, complete_analysis):
        editor = primary_country_editor(complete_analysis)
        set_status(complete_analysis, AnalysisStatus.COMPLETE)
        break_readiness(complete_analysis)

        recalculate_analysis(
            Analysis.objects.prefetch_related(*WORKFLOW_PREFETCHES).get(pk=complete_analysis.pk), editor
        )

        row = stored(complete_analysis)
        assert row.analysis_status == AnalysisStatus.IN_PROGRESS
        assert row.status_changed_by == editor

    def test_system_recalculation_of_a_complete_validated_analysis_keeps_every_lifecycle_field(
        self, complete_analysis
    ):
        actor = UserFactory()
        Analysis.objects.filter(pk=complete_analysis.pk).update(
            analysis_status=AnalysisStatus.VALIDATED, status_changed_by=actor, output_costs={}
        )
        before = stored(complete_analysis)

        request_workflow(complete_analysis).calculate_if_possible()

        row = stored(complete_analysis)
        assert row.output_costs  # recalculated
        for field in Analysis.LIFECYCLE_FIELDS:
            assert getattr(row, field) == getattr(before, field), field
        assert log_entries(row) == []

    def test_clear_output_costs_command_reconciles_as_system_work(self, complete_analysis):
        set_status(complete_analysis, AnalysisStatus.COMPLETE)
        break_readiness(complete_analysis)

        call_command("clear_output_costs", stdout=io.StringIO())

        row = stored(complete_analysis)
        assert row.analysis_status == AnalysisStatus.IN_PROGRESS
        assert row.status_changed_by is None
        [entry] = log_entries(row)
        assert entry.action == "Status reset"
        assert entry.actor_name == "System"


@pytest.mark.django_db
class TestPermittedStatusTargets:
    @pytest.mark.parametrize("status", list(AnalysisStatus))
    def test_admins_may_pick_any_status(self, admin, status):
        analysis = AnalysisFactory(lifecycle__analysis_status=status)
        assert permitted_status_targets(admin, analysis) == list(AnalysisStatus)

    @pytest.mark.parametrize("status", [AnalysisStatus.IN_PROGRESS, AnalysisStatus.COMPLETE])
    def test_editors_may_pick_in_progress_and_complete(self, status):
        analysis = AnalysisFactory(lifecycle__analysis_status=status)
        expected = [AnalysisStatus.IN_PROGRESS, AnalysisStatus.COMPLETE]
        assert permitted_status_targets(analysis.owner, analysis) == expected
        assert permitted_status_targets(primary_country_editor(analysis), analysis) == expected

    def test_only_admins_get_targets_on_a_validated_analysis(self):
        analysis = AnalysisFactory(lifecycle__analysis_status=AnalysisStatus.VALIDATED)
        assert permitted_status_targets(analysis.owner, analysis) == []
        assert permitted_status_targets(primary_country_editor(analysis), analysis) == []

    def test_viewers_strangers_and_anonymous_get_nothing(self):
        analysis = AnalysisFactory()
        for user in (secondary_country_viewer(analysis), UserFactory(), AnonymousUser(), None):
            assert permitted_status_targets(user, analysis) == []
