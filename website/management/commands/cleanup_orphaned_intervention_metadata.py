"""
Remove orphaned intervention metadata values.

A deleted field, a field whose key was rotated by a type change, or a deleted option leaves its
stored value behind on every intervention instance that had one. Every reader already resolves
values through the current definitions, so the orphans are invisible; this command only tidies the
stored JSON. Each instance is reread under its own row lock in a short transaction and written only
when its metadata actually changes. Ordinary saves are not serialized with it: a stale in-flight
save may leave an orphan again, which a later save or run removes.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import prefetch_related_objects

from website.intervention_metadata import definitions_for, prune_metadata
from website.models import InterventionInstance


class Command(BaseCommand):
    help = (
        "Remove intervention metadata values that no longer belong to a current field or option. "
        "One short transaction per intervention instance; only changed rows are written."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report the instances that would change without writing anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        examined = cleaned = 0
        # The ids are fixed up front; each instance is then reread under its own lock.
        for pk in list(InterventionInstance.objects.order_by("pk").values_list("pk", flat=True)):
            examined += 1
            with transaction.atomic():
                try:
                    instance = InterventionInstance.objects.select_for_update(of=("self",)).get(pk=pk)
                except InterventionInstance.DoesNotExist:
                    continue
                prefetch_related_objects([instance], "intervention__metadata_fields__options")
                stored = instance.metadata or {}
                pruned = prune_metadata(definitions_for(instance.intervention), stored)
                if pruned == stored:
                    continue
                cleaned += 1
                removed = len(stored) - len(pruned)
                if not dry_run:
                    InterventionInstance.objects.filter(pk=pk).update(metadata=pruned)
            self.stdout.write(
                f"Intervention instance {pk} (analysis {instance.analysis_id}): "
                f"{'would remove' if dry_run else 'removed'} {removed} orphaned value(s)"
            )

        verb = "would be cleaned" if dry_run else "cleaned"
        self.stdout.write(
            self.style.SUCCESS(
                f"Examined {examined} intervention instance(s): {cleaned} {verb}, {examined - cleaned} unchanged."
            )
        )
