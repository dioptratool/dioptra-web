# Feature 94: analysis lifecycle status and archive flag, with their audit columns.
#
# One migration: the columns are added first (the status timestamp NOT NULL from the start, with a
# one-off default for the existing rows), then the status audits are backfilled from each row's
# `created` and owner. Writing the deferred user foreign keys leaves pending trigger events in the
# transaction, which PostgreSQL rejects for a later ALTER TABLE; nothing here alters the table after
# the backfill. Django's deferred CREATE INDEX statements do run after it, which PostgreSQL allows
# (exercised by the migration test on a populated database).

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models
from django.db.models import F


def initialize_lifecycle_audits(apps, schema_editor):
    """Audit every existing analysis to its creation.

    status_changed_at becomes the row's own `created` value and status_changed_by its "Created by"
    user (the owner, null when absent). The column defaults already make every row In Progress and
    not archived with null archive audits. `updated`, outputs and workflow data are untouched and
    no application-log entries are created.
    """
    Analysis = apps.get_model("website", "Analysis")
    Analysis.objects.using(schema_editor.connection.alias).update(
        status_changed_by_id=F("owner_id"),
        status_changed_at=F("created"),
    )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("website", "0011_budget_field_label_overrides"),
    ]

    operations = [
        migrations.AddField(
            model_name="analysis",
            name="analysis_status",
            field=models.CharField(
                choices=[
                    ("in_progress", "In Progress"),
                    ("complete", "Complete"),
                    ("validated", "Validated"),
                ],
                default="in_progress",
                editable=False,
                max_length=20,
                verbose_name="Status",
            ),
        ),
        migrations.AddField(
            model_name="analysis",
            name="status_changed_by",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="status_changed_analyses",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="analysis",
            name="status_changed_at",
            field=models.DateTimeField(default=django.utils.timezone.now, editable=False),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="analysis",
            name="is_archived",
            field=models.BooleanField(default=False, editable=False, verbose_name="Archived"),
        ),
        migrations.AddField(
            model_name="analysis",
            name="archived_by",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="archived_analyses",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="analysis",
            name="archived_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.RunPython(initialize_lifecycle_audits, migrations.RunPython.noop),
    ]
