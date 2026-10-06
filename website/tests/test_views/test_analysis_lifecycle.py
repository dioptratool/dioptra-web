"""Feature 94: lifecycle reconciliation through the real views, panels and API."""

import datetime
import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from app_log.models import AppLogEntry
from website.models import Analysis, AnalysisStatus, Settings
from website.tests.factories import AnalysisFactory, CategoryFactory, InterventionFactory, UserFactory
from website.tests.utils import import_test_transaction_store
from website.workflows import AnalysisWorkflow

User = get_user_model()

ONE_WORKFLOW_VARIANT = pytest.mark.parametrize(
    "analysis_workflow_with_loaddata_complete", ["analysis_workflow_with_analysis"], indirect=True
)


def stored(analysis):
    return Analysis.objects.get(pk=analysis.pk)


def set_status(analysis, status, actor=None):
    Analysis.objects.filter(pk=analysis.pk).update(analysis_status=status, status_changed_by=actor)


def reset_entries(analysis):
    return list(
        AppLogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(Analysis),
            object_id=analysis.pk,
            action="Status reset",
        )
    )


def break_readiness(analysis):
    """Un-confirm one category directly, as a change outside an analysis edit would."""
    category = analysis.cost_type_categories.first()
    category.confirmed = False
    category.save()


def allocation_url(analysis, cost_line_item):
    return reverse(
        "analysis-allocate-cost_type-grant",
        kwargs={
            "pk": analysis.pk,
            "cost_type_pk": cost_line_item.config.cost_type.pk,
            "grant": cost_line_item.grant_code,
        },
    )


@pytest.fixture
def admin():
    return UserFactory(role=User.ADMIN)


@pytest.fixture
def admin_client(client, admin):
    client.force_login(admin)
    return client


@pytest.fixture
def complete_analysis(analysis_workflow_main_flow_complete):
    """Complete, with every cost item turned into a Client Time item by the fixture chain."""
    return analysis_workflow_main_flow_complete.analysis


@pytest.fixture
def complete_analysis_with_regular_items(analysis_workflow_with_allocations):
    """Complete because the optional Add Other Costs step is switched off; ordinary cost items."""
    analysis = analysis_workflow_with_allocations.analysis
    Analysis.objects.filter(pk=analysis.pk).update(client_time=False)
    analysis.refresh_from_db()
    assert AnalysisWorkflow(analysis).all_steps_complete
    return analysis


@pytest.mark.django_db
@ONE_WORKFLOW_VARIANT
class TestEditsReconcileTheStatus:
    def test_allocation_errors_still_save_valid_rows_and_reset_the_status(
        self, complete_analysis, admin, admin_client
    ):
        set_status(complete_analysis, AnalysisStatus.COMPLETE)
        # Readiness lost since the page was opened: an optional step was enabled with nothing in it.
        Analysis.objects.filter(pk=complete_analysis.pk).update(in_kind_contributions=True)
        first, second = complete_analysis.cost_line_items.order_by("pk")
        [instance] = complete_analysis.interventioninstance_set.all()

        response = admin_client.post(
            allocation_url(complete_analysis, first),
            data={
                f"cost_line_item_allocation_{first.id}_{instance.id}": "0.2",  # valid, saved
                f"cost_line_item_allocation_{second.id}_{instance.id}": "abc",  # redisplayed as an error
            },
        )

        assert response.status_code == 200
        assert str(first.config.allocations.get(intervention_instance=instance).allocation) == "0.2000"
        row = stored(complete_analysis)
        assert row.analysis_status == AnalysisStatus.IN_PROGRESS
        assert row.status_changed_by == admin
        [entry] = reset_entries(row)
        assert entry.actor_user == admin

    def test_edit_that_keeps_the_workflow_complete_preserves_the_status(
        self, complete_analysis, admin_client
    ):
        actor = UserFactory()
        set_status(complete_analysis, AnalysisStatus.COMPLETE, actor)
        before = stored(complete_analysis)
        first = complete_analysis.cost_line_items.order_by("pk").first()
        data = {
            f"cost_line_item_allocation_{item.id}_{instance.id}": "0.1"
            for item in complete_analysis.cost_line_items.all()
            for instance in complete_analysis.interventioninstance_set.all()
        }

        response = admin_client.post(allocation_url(complete_analysis, first), data=data)

        assert response.status_code == 302
        row = stored(complete_analysis)
        assert row.analysis_status == AnalysisStatus.COMPLETE
        assert row.status_changed_by == actor
        assert row.status_changed_at == before.status_changed_at
        assert reset_entries(row) == []

    def test_load_data_reset_resets_the_status(self, complete_analysis, admin, admin_client):
        set_status(complete_analysis, AnalysisStatus.COMPLETE)

        response = admin_client.post(
            reverse("analysis-load-data", kwargs={"pk": complete_analysis.pk}), data={"action": "reset_data"}
        )

        assert response.status_code == 302
        row = stored(complete_analysis)
        assert row.cost_line_items.count() == 0
        assert row.analysis_status == AnalysisStatus.IN_PROGRESS
        assert row.status_changed_by == admin
        assert len(reset_entries(row)) == 1

    def test_api_unconfirming_a_category_resets_the_status(self, complete_analysis, admin, admin_client):
        set_status(complete_analysis, AnalysisStatus.COMPLETE)
        item = complete_analysis.cost_line_items.order_by("pk").first()

        response = admin_client.post(
            reverse("api--costlineitem--edit-cost_type-category", kwargs={"pk": item.pk}),
            data=json.dumps({"cost_type_id": item.config.cost_type_id, "category_id": CategoryFactory().pk}),
            content_type="application/json",
        )

        assert response.status_code == 200
        row = stored(complete_analysis)
        assert row.analysis_status == AnalysisStatus.IN_PROGRESS
        assert row.status_changed_by == admin
        assert len(reset_entries(row)) == 1

    def test_correction_panel_records_the_correcting_user(
        self, complete_analysis_with_regular_items, admin, admin_client
    ):
        analysis = complete_analysis_with_regular_items
        set_status(analysis, AnalysisStatus.COMPLETE)
        item = analysis.cost_line_items.order_by("pk").first()
        url = reverse("analysis-correct-cost-items", kwargs={"pk": analysis.pk, "step": "categorize"})

        response = admin_client.post(
            f"{url}?cost_line_item_id={item.id}", data={"category": str(CategoryFactory().pk)}
        )

        assert '"operation": "saved"' in response.content.decode()
        row = stored(analysis)
        assert row.analysis_status == AnalysisStatus.IN_PROGRESS
        assert row.status_changed_by == admin
        [entry] = reset_entries(row)
        assert entry.actor_user == admin


@pytest.mark.django_db
@ONE_WORKFLOW_VARIANT
class TestInsightsAccess:
    def test_readiness_lost_outside_an_edit_resets_on_access_despite_cached_outputs(
        self, complete_analysis, admin_client
    ):
        set_status(complete_analysis, AnalysisStatus.COMPLETE)
        assert stored(complete_analysis).output_costs
        break_readiness(complete_analysis)

        response = admin_client.get(reverse("analysis-insights", kwargs={"pk": complete_analysis.pk}))

        assert response.status_code == 302
        assert response.url == reverse("analysis", kwargs={"pk": complete_analysis.pk})
        row = stored(complete_analysis)
        assert row.analysis_status == AnalysisStatus.IN_PROGRESS
        assert row.status_changed_by is None
        [entry] = reset_entries(row)
        assert entry.actor_name == "System"

    def test_access_to_a_complete_validated_analysis_locks_nothing_and_changes_nothing(
        self, complete_analysis, admin_client
    ):
        set_status(complete_analysis, AnalysisStatus.VALIDATED, UserFactory())
        before = stored(complete_analysis)

        with CaptureQueriesContext(connection) as context:
            response = admin_client.get(reverse("analysis-insights", kwargs={"pk": complete_analysis.pk}))

        assert response.status_code == 200
        assert not any("FOR UPDATE" in query["sql"] for query in context.captured_queries)
        row = stored(complete_analysis)
        for field in Analysis.LIFECYCLE_FIELDS:
            assert getattr(row, field) == getattr(before, field), field
        assert reset_entries(row) == []

    def test_basic_viewer_recalculation_keeps_the_lifecycle_fields(self, complete_analysis, client):
        viewer = UserFactory()
        viewer.secondary_countries.add(complete_analysis.country)
        set_status(complete_analysis, AnalysisStatus.VALIDATED, UserFactory())
        Analysis.objects.filter(pk=complete_analysis.pk).update(output_costs={})
        before = stored(complete_analysis)
        client.force_login(viewer)

        response = client.get(reverse("analysis-insights", kwargs={"pk": complete_analysis.pk}))

        assert response.status_code == 200
        row = stored(complete_analysis)
        assert row.output_costs  # recalculated for the viewer: a system write
        for field in Analysis.LIFECYCLE_FIELDS:
            assert getattr(row, field) == getattr(before, field), field


@pytest.mark.django_db(databases=["default", "transaction_store"])
class TestLoadDataImports:
    """The import handlers against the real transaction store."""

    @pytest.fixture
    def datastore_analysis(self, defaults):
        # The smaller dump holds a transaction with a NULL site code, which the import path does
        # not survive (noted in the hand-off); the larger dump is clean.
        import_test_transaction_store(
            "dioptra__testing-transaction-store__20200331-1656PM_test_transaction_loading_1800.sql"
        )
        Settings.objects.update(transaction_country_filter=False)
        analysis = AnalysisFactory(
            grants="DB2021", start_date=datetime.date(2015, 5, 1), end_date=datetime.date(2016, 4, 30)
        )
        analysis.add_intervention(
            InterventionFactory(output_metrics=["NumberOfPeople"]), parameters={"number_of_people": 2992}
        )
        return analysis

    def test_import_from_the_data_store_reconciles_the_status(self, datastore_analysis, admin, admin_client):
        # A stored Complete status on an analysis without data: the import must bring it back.
        set_status(datastore_analysis, AnalysisStatus.COMPLETE)

        response = admin_client.post(
            reverse("analysis-load-data", kwargs={"pk": datastore_analysis.pk}),
            data={"action": "import_data"},
        )

        assert response.status_code == 302
        row = stored(datastore_analysis)
        assert row.cost_line_items.count() == 1800
        assert row.analysis_status == AnalysisStatus.IN_PROGRESS
        assert row.status_changed_by == admin
        assert len(reset_entries(row)) == 1

    def test_resync_reconciles_the_status(self, datastore_analysis, admin, admin_client):
        step = AnalysisWorkflow(datastore_analysis).get_step("load-data")
        succeeded, result = step.load_transactions(filter_by_country=False, from_datastore=True)
        assert succeeded, result
        Analysis.objects.filter(pk=datastore_analysis.pk).update(
            needs_transaction_resync=True, analysis_status=AnalysisStatus.COMPLETE
        )

        response = admin_client.post(
            reverse("analysis-load-data", kwargs={"pk": datastore_analysis.pk}),
            data={"action": "transaction_resync"},
        )

        assert response.status_code == 302
        row = stored(datastore_analysis)
        assert row.needs_transaction_resync is False
        assert row.analysis_status == AnalysisStatus.IN_PROGRESS
        assert row.status_changed_by == admin
        assert len(reset_entries(row)) == 1


# ---------------------------------------------------------------------------------------------
# Confirm panels
# ---------------------------------------------------------------------------------------------


def status_url(analysis, status):
    return reverse("analysis-change-status", kwargs={"pk": analysis.pk, "status": status})


def archive_url(analysis):
    return reverse("analysis-archive", kwargs={"pk": analysis.pk})


def unarchive_url(analysis):
    return reverse("analysis-unarchive", kwargs={"pk": analysis.pk})


def status_entries(analysis):
    return list(
        AppLogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(Analysis),
            object_id=analysis.pk,
            action="Status changed",
        )
    )


@pytest.mark.django_db
@ONE_WORKFLOW_VARIANT
class TestStatusChangePanel:
    def test_get_shows_the_question_and_changes_nothing(self, complete_analysis, admin_client):
        before = stored(complete_analysis)

        response = admin_client.get(status_url(complete_analysis, "complete"))

        assert response.status_code == 200
        content = response.content.decode()
        assert "Mark" in content and "Complete" in content
        assert "Yes, mark as Complete" in content
        row = stored(complete_analysis)
        assert row.analysis_status == AnalysisStatus.IN_PROGRESS
        assert row.status_changed_at == before.status_changed_at
        assert status_entries(row) == []

    def test_post_changes_the_status_and_resolves_the_panel(self, complete_analysis, admin, admin_client):
        response = admin_client.post(status_url(complete_analysis, "validated"), data={})

        assert response.status_code == 200
        content = response.content.decode()
        assert '"operation": "status-changed"' in content
        assert "is now Validated" in content
        row = stored(complete_analysis)
        assert row.analysis_status == AnalysisStatus.VALIDATED
        assert row.status_changed_by == admin
        assert len(status_entries(row)) == 1

    def test_unknown_status_is_not_found(self, complete_analysis, admin_client):
        assert admin_client.get(status_url(complete_analysis, "finished")).status_code == 404
        assert admin_client.post(status_url(complete_analysis, "finished"), data={}).status_code == 404

    def test_readiness_lost_since_opening_is_shown_in_the_panel(self, complete_analysis, admin_client):
        assert admin_client.get(status_url(complete_analysis, "complete")).status_code == 200
        break_readiness(complete_analysis)

        response = admin_client.post(status_url(complete_analysis, "complete"), data={})

        assert response.status_code == 200
        content = response.content.decode()
        assert "must be complete" in content
        assert '"operation"' not in content
        assert stored(complete_analysis).analysis_status == AnalysisStatus.IN_PROGRESS
        assert status_entries(complete_analysis) == []

    def test_basic_user_cannot_reach_validated_through_the_url(self, complete_analysis, client):
        client.force_login(complete_analysis.owner)

        response = client.post(status_url(complete_analysis, "validated"), data={})

        assert response.status_code == 200
        content = response.content.decode()
        assert "Only an administrator" in content
        assert '"operation"' not in content
        assert stored(complete_analysis).analysis_status == AnalysisStatus.IN_PROGRESS

    def test_owner_marks_complete_and_back(self, complete_analysis, client):
        client.force_login(complete_analysis.owner)
        assert (
            '"operation": "status-changed"'
            in client.post(status_url(complete_analysis, "complete"), data={}).content.decode()
        )
        assert stored(complete_analysis).analysis_status == AnalysisStatus.COMPLETE
        assert (
            '"operation": "status-changed"'
            in client.post(status_url(complete_analysis, "in_progress"), data={}).content.decode()
        )
        assert stored(complete_analysis).analysis_status == AnalysisStatus.IN_PROGRESS

    def test_viewer_is_forbidden_and_anonymous_is_sent_to_log_in(self, complete_analysis, client):
        response = client.get(status_url(complete_analysis, "complete"))
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")

        viewer = UserFactory()
        viewer.secondary_countries.add(complete_analysis.country)
        client.force_login(viewer)
        assert client.get(status_url(complete_analysis, "complete")).status_code == 403
        assert client.post(status_url(complete_analysis, "complete"), data={}).status_code == 403
        assert stored(complete_analysis).analysis_status == AnalysisStatus.IN_PROGRESS

    def test_post_without_a_csrf_token_is_rejected(self, complete_analysis, admin):
        strict_client = Client(enforce_csrf_checks=True)
        strict_client.force_login(admin)

        response = strict_client.post(status_url(complete_analysis, "complete"), data={})

        assert response.status_code == 403
        assert stored(complete_analysis).analysis_status == AnalysisStatus.IN_PROGRESS

    def test_repeated_submission_changes_nothing_more(self, complete_analysis, admin_client):
        admin_client.post(status_url(complete_analysis, "complete"), data={})
        first = stored(complete_analysis)

        response = admin_client.post(status_url(complete_analysis, "complete"), data={})

        assert '"operation": "status-changed"' in response.content.decode()
        row = stored(complete_analysis)
        assert row.status_changed_at == first.status_changed_at
        assert len(status_entries(row)) == 1


@pytest.mark.django_db
class TestArchivePanels:
    def test_owner_archives_and_unarchives_a_validated_analysis(self, client):
        analysis = AnalysisFactory(lifecycle__analysis_status=AnalysisStatus.VALIDATED)
        client.force_login(analysis.owner)

        response = client.get(archive_url(analysis))
        assert response.status_code == 200
        assert "Yes, archive" in response.content.decode()
        assert stored(analysis).is_archived is False

        response = client.post(archive_url(analysis), data={})
        assert '"operation": "archived"' in response.content.decode()
        row = stored(analysis)
        assert row.is_archived is True
        assert row.archived_by == analysis.owner

        response = client.post(unarchive_url(analysis), data={})
        assert '"operation": "unarchived"' in response.content.decode()
        row = stored(analysis)
        assert row.is_archived is False
        assert row.archived_by is None
        assert row.analysis_status == AnalysisStatus.VALIDATED

    def test_primary_country_editor_archives_and_unarchives_a_validated_analysis(self, client):
        analysis = AnalysisFactory(lifecycle__analysis_status=AnalysisStatus.VALIDATED)
        editor = UserFactory()
        editor.primary_countries.add(analysis.country)
        client.force_login(editor)

        assert client.get(archive_url(analysis)).status_code == 200
        response = client.post(archive_url(analysis), data={})
        assert '"operation": "archived"' in response.content.decode()
        row = stored(analysis)
        assert row.is_archived is True
        assert row.archived_by == editor

        response = client.post(unarchive_url(analysis), data={})
        assert '"operation": "unarchived"' in response.content.decode()
        row = stored(analysis)
        assert row.is_archived is False
        assert row.archived_by is None
        assert row.analysis_status == AnalysisStatus.VALIDATED

    def test_secondary_country_viewer_is_forbidden(self, client):
        analysis = AnalysisFactory()
        viewer = UserFactory()
        viewer.secondary_countries.add(analysis.country)
        client.force_login(viewer)

        assert client.get(archive_url(analysis)).status_code == 403
        assert client.post(archive_url(analysis), data={}).status_code == 403
        assert client.get(unarchive_url(analysis)).status_code == 403
        assert stored(analysis).is_archived is False

    def test_anonymous_is_sent_to_log_in(self, client):
        analysis = AnalysisFactory()
        for url in (archive_url(analysis), unarchive_url(analysis)):
            response = client.get(url)
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")

    def test_repeated_archive_changes_nothing_more(self, client):
        analysis = AnalysisFactory()
        client.force_login(analysis.owner)
        client.post(archive_url(analysis), data={})
        first = stored(analysis)

        response = client.post(archive_url(analysis), data={})

        assert '"operation": "archived"' in response.content.decode()
        assert stored(analysis).archived_at == first.archived_at
        assert AppLogEntry.objects.filter(action="Archived", object_id=analysis.pk).count() == 1

    def test_basic_users_cannot_delete_but_admins_can(self, client, admin):
        analysis = AnalysisFactory()
        url = reverse("ombucore.admin:website_analysis_delete", args=[analysis.pk])
        client.force_login(analysis.owner)
        assert client.get(url).status_code == 403

        client.force_login(admin)
        assert client.get(url).status_code == 200


# ---------------------------------------------------------------------------------------------
# Insights and step headers
# ---------------------------------------------------------------------------------------------


def insights_page(client, analysis):
    response = client.get(reverse("analysis-insights", kwargs={"pk": analysis.pk}))
    assert response.status_code == 200
    return response.content.decode()


@pytest.mark.django_db
@ONE_WORKFLOW_VARIANT
class TestInsightsHeader:
    def test_admin_sees_the_status_control_actions_and_edit(self, complete_analysis, admin_client):
        content = insights_page(admin_client, complete_analysis)

        assert "lifecycle-status-control" in content
        assert status_url(complete_analysis, "complete") in content
        assert status_url(complete_analysis, "validated") in content
        assert status_url(complete_analysis, "in_progress") not in content  # the current one, marked
        assert 'actions-menu__item--current">In Progress<' in content
        assert "Edit Analysis" in content
        assert f'/analysis/{complete_analysis.pk}/copy"' in content
        assert archive_url(complete_analysis) in content
        assert ">Delete<" in content

    def test_owner_may_choose_complete_but_not_validated(self, complete_analysis, client):
        client.force_login(complete_analysis.owner)

        content = insights_page(client, complete_analysis)

        assert status_url(complete_analysis, "complete") in content
        assert status_url(complete_analysis, "validated") not in content
        assert "Edit Analysis" in content
        assert archive_url(complete_analysis) in content
        assert ">Delete<" not in content

    def test_owner_of_a_validated_analysis_sees_a_plain_badge_and_the_explanation(
        self, complete_analysis, client
    ):
        set_status(complete_analysis, AnalysisStatus.VALIDATED)
        client.force_login(complete_analysis.owner)

        content = insights_page(client, complete_analysis)

        assert "lifecycle-status-control" not in content
        assert 'lifecycle-badge--validated">Validated<' in content
        assert "A validated analysis cannot be edited" in content
        assert "Edit Analysis" not in content
        assert archive_url(complete_analysis) in content
        assert f'/analysis/{complete_analysis.pk}/copy"' in content

    def test_viewer_of_a_validated_analysis_gets_badge_only(self, complete_analysis, client):
        set_status(complete_analysis, AnalysisStatus.VALIDATED)
        viewer = UserFactory()
        viewer.secondary_countries.add(complete_analysis.country)
        client.force_login(viewer)

        content = insights_page(client, complete_analysis)

        assert 'lifecycle-badge--validated">Validated<' in content
        assert "lifecycle-status-control" not in content
        assert "Edit Analysis" not in content
        assert "cannot be edited" not in content
        assert "analysis-actions-trigger" not in content
        assert f'/analysis/{complete_analysis.pk}/copy"' not in content
        assert archive_url(complete_analysis) not in content
        assert ">Delete<" not in content

    def test_archived_analysis_shows_the_tag_and_offers_unarchive(self, complete_analysis, admin_client):
        Analysis.objects.filter(pk=complete_analysis.pk).update(is_archived=True)

        content = insights_page(admin_client, complete_analysis)

        assert 'class="lifecycle-tag">Archived<' in content
        assert unarchive_url(complete_analysis) in content
        assert archive_url(complete_analysis) not in content


@pytest.mark.django_db
class TestStepHeader:
    def test_step_pages_show_the_badge_and_tag_without_a_status_control(self, client_with_admin, defaults):
        analysis = AnalysisFactory(
            lifecycle__analysis_status=AnalysisStatus.COMPLETE, lifecycle__is_archived=True
        )

        response = client_with_admin.get(reverse("analysis-define-update", kwargs={"pk": analysis.pk}))

        assert response.status_code == 200
        content = response.content.decode()
        assert 'lifecycle-badge--complete">Complete<' in content
        assert 'class="lifecycle-tag">Archived<' in content
        assert "lifecycle-status-control" not in content
