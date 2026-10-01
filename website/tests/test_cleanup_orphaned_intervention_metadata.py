"""The administrative cleanup of orphaned intervention metadata values."""

import datetime
import io

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from website.intervention_metadata import validate_draft
from website.models import Analysis, AnalysisStatus, InterventionInstance
from website.models.intervention_metadata import MetadataFieldType, MetadataNumberType
from website.tests.factories import (
    AnalysisFactory,
    InterventionFactory,
    InterventionInstanceFactory,
    InterventionMetadataFieldFactory,
    InterventionMetadataOptionFactory,
    UserFactory,
)

COMMAND = "cleanup_orphaned_intervention_metadata"


def run(*args):
    out = io.StringIO()
    call_command(COMMAND, *args, stdout=out)
    return out.getvalue()


def stored(instance):
    return InterventionInstance.objects.get(pk=instance.pk).metadata


@pytest.fixture
def definitions():
    """A text, an integer, a single-choice (A, B) and a multiple-choice (X, Y, Z) field."""
    intervention = InterventionFactory()
    text = InterventionMetadataFieldFactory(intervention=intervention, name="Partner", order=1)
    number = InterventionMetadataFieldFactory(
        intervention=intervention,
        name="Volunteers",
        field_type=MetadataFieldType.NUMBER,
        number_type=MetadataNumberType.INTEGER,
        order=2,
    )
    single = InterventionMetadataFieldFactory(
        intervention=intervention, name="Age", field_type=MetadataFieldType.SINGLE_CHOICE, order=3
    )
    a, b = (
        InterventionMetadataOptionFactory(field=single, label=label, order=i) for i, label in enumerate("AB")
    )
    multi = InterventionMetadataFieldFactory(
        intervention=intervention, name="Approach", field_type=MetadataFieldType.MULTIPLE_CHOICE, order=4
    )
    x, y, z = (
        InterventionMetadataOptionFactory(field=multi, label=label, order=i) for i, label in enumerate("XYZ")
    )
    return {
        "intervention": intervention,
        "text": text,
        "number": number,
        "single": single,
        "A": a,
        "B": b,
        "multi": multi,
        "X": x,
        "Y": y,
        "Z": z,
    }


def live_values(d):
    return {
        d["text"].storage_key: "Save the Children",
        d["number"].storage_key: "0",
        d["single"].storage_key: d["A"].storage_key,
        d["multi"].storage_key: [d["X"].storage_key, d["Z"].storage_key],
    }


@pytest.mark.django_db
class TestCleanup:
    def test_removes_every_kind_of_orphan_and_keeps_live_values(self, definitions):
        d = definitions
        retired_field = InterventionMetadataFieldFactory(intervention=d["intervention"], name="Old", order=5)
        rotated = InterventionMetadataFieldFactory(
            intervention=d["intervention"],
            name="Budget",
            field_type=MetadataFieldType.NUMBER,
            number_type=MetadataNumberType.DECIMAL,
            order=6,
        )
        old_rotated_key = rotated.storage_key
        gone_option = InterventionMetadataOptionFactory(field=d["single"], label="Gone", order=2)
        single_with_gone = InterventionMetadataFieldFactory(
            intervention=d["intervention"], name="Region", field_type=MetadataFieldType.SINGLE_CHOICE, order=7
        )
        region_gone = InterventionMetadataOptionFactory(field=single_with_gone, label="North")
        empty_multi = InterventionMetadataFieldFactory(
            intervention=d["intervention"],
            name="Empty",
            field_type=MetadataFieldType.MULTIPLE_CHOICE,
            order=8,
        )
        InterventionMetadataOptionFactory(field=empty_multi, label="Only")
        instance = InterventionInstanceFactory(
            intervention=d["intervention"],
            metadata={
                **live_values(d),
                d["multi"].storage_key: [
                    d["Z"].storage_key,
                    "stale-option",
                    d["X"].storage_key,
                    gone_option.storage_key,
                ],
                retired_field.storage_key: "retired",
                old_rotated_key: "12.5",
                single_with_gone.storage_key: region_gone.storage_key,
                empty_multi.storage_key: [],
                "stale-field-key": "orphan",
                "blank-text": "",
            },
        )
        # Retire the field, rotate the number's key (a type change), and delete the options.
        retired_field.delete()
        rotated.rotate_key()
        rotated.save()
        gone_option.delete()
        region_gone.delete()

        output = run()

        assert stored(instance) == {
            **live_values(d),
            d["multi"].storage_key: [d["Z"].storage_key, d["X"].storage_key],
        }
        assert (
            f"Intervention instance {instance.pk} (analysis {instance.analysis_id}): removed 6 orphaned value(s)"
            in output
        )
        assert "Examined 1 intervention instance(s): 1 cleaned, 0 unchanged." in output

    def test_a_staged_but_unsaved_deletion_changes_nothing(self, definitions):
        d = definitions
        instance = InterventionInstanceFactory(intervention=d["intervention"], metadata=live_values(d))
        # A draft without the text field validates fine but is never saved: the field stays live.
        rows = validate_draft(
            d["intervention"],
            {
                "fields": [
                    {
                        "id": d["number"].pk,
                        "key": d["number"].storage_key,
                        "name": "Volunteers",
                        "field_type": MetadataFieldType.NUMBER,
                        "number_type": MetadataNumberType.INTEGER,
                        "options": [],
                    }
                ]
            },
        )
        assert [row["name"] for row in rows] == ["Volunteers"]

        output = run()

        assert stored(instance) == live_values(d)
        assert "Examined 1 intervention instance(s): 0 cleaned, 1 unchanged." in output

    def test_unchanged_rows_are_not_written_and_each_instance_has_its_own_lock(self, definitions):
        d = definitions
        clean = InterventionInstanceFactory(intervention=d["intervention"], metadata=live_values(d))
        dirty = InterventionInstanceFactory(
            intervention=d["intervention"], metadata={**live_values(d), "stale-field-key": "orphan"}
        )
        empty = InterventionInstanceFactory(intervention=InterventionFactory())

        with CaptureQueriesContext(connection) as context:
            run()

        sql = [query["sql"] for query in context.captured_queries]
        updates = [statement for statement in sql if statement.startswith("UPDATE")]
        assert len(updates) == 1
        assert f'WHERE "website_interventioninstance"."id" = {dirty.pk}' in updates[0]
        assert '"metadata" = ' in updates[0]
        assert '"parameters"' not in updates[0] and '"label"' not in updates[0]
        # One row lock on the instance itself (not its intervention) inside one transaction each.
        locks = [statement for statement in sql if "FOR UPDATE OF" in statement]
        assert len(locks) == 3
        assert all('FOR UPDATE OF "website_interventioninstance"' in statement for statement in locks)
        assert sum(statement.startswith("SAVEPOINT") for statement in sql) == 3
        assert stored(clean) == live_values(d)
        assert stored(empty) == {}

    def test_touches_nothing_else_on_archived_and_validated_analyses(self, definitions):
        d = definitions
        actor = UserFactory()
        long_ago = timezone.now() - datetime.timedelta(days=30)
        analysis = AnalysisFactory(
            lifecycle__analysis_status=AnalysisStatus.VALIDATED,
            lifecycle__status_changed_by=actor,
            lifecycle__status_changed_at=long_ago,
            lifecycle__is_archived=True,
            lifecycle__archived_by=actor,
            lifecycle__archived_at=long_ago,
            output_costs={"1": {"metric": {"all": "1.00"}}},
        )
        instance = InterventionInstanceFactory(
            analysis=analysis,
            intervention=d["intervention"],
            label="Custom",
            parameters={"number_of_teachers": 4.0},
            metadata={**live_values(d), "stale-field-key": "orphan"},
        )
        before = Analysis.objects.get(pk=analysis.pk)

        run()

        after = Analysis.objects.get(pk=analysis.pk)
        row = InterventionInstance.objects.get(pk=instance.pk)
        assert row.metadata == live_values(d)
        assert (row.label, row.parameters, row.order) == (
            "Custom",
            {"number_of_teachers": 4.0},
            instance.order,
        )
        for field in (
            "analysis_status",
            "status_changed_by_id",
            "status_changed_at",
            "is_archived",
            "archived_by_id",
            "archived_at",
            "output_costs",
            "updated",
        ):
            assert getattr(after, field) == getattr(before, field), field

    def test_a_second_run_is_a_no_op(self, definitions):
        d = definitions
        instance = InterventionInstanceFactory(
            intervention=d["intervention"], metadata={**live_values(d), "stale-field-key": "orphan"}
        )

        first = run()
        with CaptureQueriesContext(connection) as context:
            second = run()

        assert "1 cleaned, 0 unchanged" in first
        assert "0 cleaned, 1 unchanged" in second
        assert not any(query["sql"].startswith("UPDATE") for query in context.captured_queries)
        assert stored(instance) == live_values(d)

    def test_dry_run_reports_without_writing(self, definitions):
        d = definitions
        metadata = {**live_values(d), "stale-field-key": "orphan"}
        instance = InterventionInstanceFactory(intervention=d["intervention"], metadata=metadata)

        output = run("--dry-run")

        assert stored(instance) == metadata
        assert (
            f"Intervention instance {instance.pk} (analysis {instance.analysis_id}): would remove 1 orphaned value(s)"
            in output
        )
        assert "Examined 1 intervention instance(s): 1 would be cleaned, 0 unchanged." in output
