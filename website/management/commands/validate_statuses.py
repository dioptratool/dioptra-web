import csv
import os

from django.core.management.base import BaseCommand

from website.management.commands.utils import _get_last_completed_step_name
from website.models import Analysis


class Command(BaseCommand):
    help = (
        "Validate statuses of Analysis objects. This command can be used to save a file that "
        "can be compared later (such as after a migration)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--save",
            nargs="?",
            const=f"analysis_statuses.csv",
            help="Save statuses and last_updated of all Analysis objects to a CSV file. "
            "You can optionally specify a filename.",
        )
        parser.add_argument(
            "--validate",
            metavar="FILENAME",
            help="Validate statuses and last_updated against the specified CSV file",
        )

    def handle(self, *args, **options):
        if options["save"]:
            filename = options["save"]
            self.save_statuses(filename)
        elif options["validate"]:
            filename = options["validate"]
            self.validate_statuses(filename)
        else:
            self.stdout.write(
                self.style.ERROR("Please specify either --save or --validate with an optional filename.")
            )

    def save_statuses(self, filename):
        with open(filename, "w") as csvfile:
            fieldnames = ["id", "status", "last_updated", "output_cost"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for analysis in Analysis.objects.all().order_by("id"):
                try:
                    # This is for v1.14 and above with Multi-Activity
                    output_metrics = analysis.output_costs.get(
                        str(analysis.interventioninstance_set.first().id)
                    )
                except AttributeError as e:
                    # This is for v1.13 which was still single activity
                    output_metrics = analysis.output_costs
                output_cost = None
                if output_metrics:
                    for k, v in output_metrics.items():
                        output_cost = v.get("all", 0)

                writer.writerow(
                    {
                        "id": analysis.id,
                        "status": _get_last_completed_step_name(analysis),
                        "last_updated": analysis.updated.isoformat(),
                        "output_cost": output_cost,
                    }
                )

        self.stdout.write(self.style.SUCCESS(f"Statuses saved to {filename}"))

    def validate_statuses(self, filename):
        if not os.path.exists(filename):
            self.stdout.write(
                self.style.ERROR(
                    f"File {filename} not found. Please provide a valid CSV file created by --save."
                )
            )
            return

        discrepancies = []
        with open(filename) as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                analysis_id = row["id"]
                csv_status = row["status"]
                csv_last_updated = row["last_updated"]

                try:
                    analysis = Analysis.objects.get(id=analysis_id)
                except Analysis.DoesNotExist:
                    discrepancies.append(
                        {
                            "id": analysis_id,
                            "error": "Analysis object does not exist in the database.",
                        }
                    )
                    continue

                db_status = _get_last_completed_step_name(analysis)
                db_last_updated = analysis.updated.isoformat()

                if db_status != csv_status or db_last_updated != csv_last_updated:
                    discrepancies.append(
                        {
                            "id": analysis_id,
                            "old_status": csv_status,
                            "new_status": db_status,
                            "old_last_updated": csv_last_updated,
                            "new_last_updated": db_last_updated,
                        }
                    )

        if discrepancies:
            self.stdout.write(self.style.WARNING("Discrepancies found:"))
            for discrepancy in discrepancies:
                self.stdout.write(str(discrepancy))
            self.stdout.write(f"{len(discrepancies)} issues found.")
        else:
            self.stdout.write(self.style.SUCCESS("All statuses and last updated dates match."))
