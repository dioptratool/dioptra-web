"""The Feature 95 schema migration run against populated intervention instances."""

import datetime

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

BEFORE_METADATA = ("website", "0012_analysis_lifecycle")
WITH_METADATA = ("website", "0013_intervention_metadata")


def migrate_to(target):
    executor = MigrationExecutor(connection)
    executor.migrate([target])
    executor.loader.build_graph()
    return executor.loader.project_state([target]).apps


def migrate_to_head():
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


@pytest.mark.django_db(transaction=True)
def test_existing_instances_gain_empty_metadata_and_nothing_else_changes():
    old_apps = migrate_to(BEFORE_METADATA)
    try:
        User = old_apps.get_model("users", "User")
        Country = old_apps.get_model("website", "Country")
        Analysis = old_apps.get_model("website", "Analysis")
        Intervention = old_apps.get_model("website", "Intervention")
        InterventionInstance = old_apps.get_model("website", "InterventionInstance")
        owner = User.objects.create(email="owner@example.com", name="Owner")
        analysis = Analysis.objects.create(
            title="Populated",
            start_date=datetime.date(2020, 1, 1),
            end_date=datetime.date(2020, 12, 31),
            country=Country.objects.create(name="Testland", code="TL"),
            owner=owner,
            grants="G1",
            output_costs={"1": {"metric": {"all": "2.5"}}},
            analysis_status="validated",
            status_changed_by=owner,
            status_changed_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        )
        intervention = Intervention.objects.create(name="Malnutrition", output_metrics=["NumberOfPeople"])
        instance = InterventionInstance.objects.create(
            analysis=analysis, intervention=intervention, parameters={"number_of_people": 7.0}, label="Custom"
        )
        before = Analysis.objects.get(pk=analysis.pk)

        new_apps = migrate_to(WITH_METADATA)

        InterventionInstance = new_apps.get_model("website", "InterventionInstance")
        Analysis = new_apps.get_model("website", "Analysis")
        row = InterventionInstance.objects.get(pk=instance.pk)
        assert row.metadata == {}
        assert row.parameters == {"number_of_people": 7.0}
        assert row.label == "Custom"
        after = Analysis.objects.get(pk=analysis.pk)
        for field in (
            "output_costs",
            "analysis_status",
            "status_changed_by_id",
            "status_changed_at",
            "updated",
        ):
            assert getattr(after, field) == getattr(before, field), field
        # The definition tables exist and start empty.
        assert new_apps.get_model("website", "InterventionMetadataField").objects.count() == 0
        assert new_apps.get_model("website", "InterventionMetadataOption").objects.count() == 0
    finally:
        migrate_to_head()
