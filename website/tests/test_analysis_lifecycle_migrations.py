"""The Feature 94 lifecycle migration run against a populated database.

Runs the real migration backwards and forwards on PostgreSQL, so it needs a transactional test.
The migration adds the columns and then backfills the audits in one transaction; it works because
no ALTER TABLE follows the backfill, which would otherwise hit PostgreSQL's "pending trigger
events" error after rows were written to a deferred foreign-key column.
"""

import datetime

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

BEFORE_LIFECYCLE = ("website", "0011_budget_field_label_overrides")
LIFECYCLE_COMPLETE = ("website", "0012_analysis_lifecycle")


def migrate_to(target):
    executor = MigrationExecutor(connection)
    executor.migrate([target])
    executor.loader.build_graph()
    return executor.loader.project_state([target]).apps


def migrate_to_head():
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


def column_allows_null(table, column):
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, table)
    return next(col.null_ok for col in description if col.name == column)


@pytest.mark.django_db(transaction=True)
def test_backfill_initializes_every_existing_analysis():
    old_apps = migrate_to(BEFORE_LIFECYCLE)
    try:
        User = old_apps.get_model("users", "User")
        Country = old_apps.get_model("website", "Country")
        Analysis = old_apps.get_model("website", "Analysis")
        owner = User.objects.create(email="owner@example.com", name="Owner")
        country = Country.objects.create(name="Testland", code="TL")
        common = dict(
            start_date=datetime.date(2020, 1, 1),
            end_date=datetime.date(2020, 12, 31),
            country=country,
            grants="G1",
        )
        owned = Analysis.objects.create(
            title="Owned", owner=owner, output_costs={"1": {"metric": {"all": "2.5"}}}, **common
        )
        orphan = Analysis.objects.create(title="Orphan", owner=None, **common)
        # Give each row its own historical creation time, distinct from "now" and from each other.
        owned_created = timezone.now() - datetime.timedelta(days=400, seconds=1)
        orphan_created = timezone.now() - datetime.timedelta(days=200, seconds=2)
        Analysis.objects.filter(pk=owned.pk).update(created=owned_created)
        Analysis.objects.filter(pk=orphan.pk).update(created=orphan_created)
        before = {row.pk: row for row in Analysis.objects.all()}

        new_apps = migrate_to(LIFECYCLE_COMPLETE)

        Analysis = new_apps.get_model("website", "Analysis")
        after = {row.pk: row for row in Analysis.objects.all()}
        assert set(after) == set(before)
        for pk, row in after.items():
            assert row.analysis_status == "in_progress"
            assert row.is_archived is False
            assert row.status_changed_by_id == before[pk].owner_id
            assert row.status_changed_at == before[pk].created
            assert row.archived_by_id is None
            assert row.archived_at is None
            # Only the lifecycle columns were written.
            assert row.created == before[pk].created
            assert row.updated == before[pk].updated
            assert row.output_costs == before[pk].output_costs
        assert after[owned.pk].status_changed_by_id == owner.pk
        assert after[owned.pk].status_changed_at == owned_created
        assert after[orphan.pk].status_changed_by_id is None
        assert after[orphan.pk].status_changed_at == orphan_created
        assert column_allows_null("website_analysis", "status_changed_at") is False
    finally:
        # Leave the schema where the rest of the suite expects it, even if an assertion failed.
        migrate_to_head()
