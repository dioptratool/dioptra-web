import csv
import json
import os

from django.core.management.base import BaseCommand

from website.management.commands.utils import _get_last_completed_step_name
from website.models import Analysis


def _first_intervention_metrics(analysis):
    """
    The output_costs metrics dict for the first intervention instance.

    Handles all three shapes without misrouting: v1.14+ instance-keyed dicts,
    the legacy v1.13 single-activity shape (metric ids at the top level —
    detected by non-digit keys), and analyses with no interventions at all
    (a legal state: the last intervention can be deleted).
    """
    output_costs = analysis.output_costs or {}
    first_instance = analysis.interventioninstance_set.first()
    if first_instance is not None and str(first_instance.id) in output_costs:
        return output_costs[str(first_instance.id)]
    if output_costs and not all(key.isdigit() for key in output_costs):
        return output_costs
    return None


def _average_row(subcomponent_analysis):
    # Error-guarded so one bad analysis can't kill a snapshot.
    try:
        return [str(value) for value in subcomponent_analysis.cost_line_item_average()]
    except Exception as e:
        return f"ERROR: {e}"


def _subcomponent_averages(analysis):
    """
    {instance_id: cost_line_item_average()} for every subcomponent analysis —
    the live-computed numbers shown in Insights and the XLSX, which output_costs
    does not capture.

    Dual-shape on purpose, so this command can be cherry-picked onto pre-2.2
    refs and produce snapshots comparable across the upgrade:
    - 2.2+: one SubcomponentCostAnalysis per InterventionInstance.
    - pre-2.2: one per Analysis (same accessor name, different model). Keyed by
      the FIRST instance by (order, id) — exactly where migration
      0002_intervention_subcomponents attaches it during the upgrade.
    """
    averages = {}
    for instance in analysis.interventioninstance_set.all():
        if hasattr(instance, "subcomponent_cost_analysis"):
            averages[str(instance.id)] = _average_row(instance.subcomponent_cost_analysis)
    if not averages and hasattr(analysis, "subcomponent_cost_analysis"):
        first_instance = analysis.interventioninstance_set.order_by("order", "id").first()
        if first_instance is not None:
            averages[str(first_instance.id)] = _average_row(analysis.subcomponent_cost_analysis)
    return averages


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
            fieldnames = [
                "id",
                "status",
                "last_updated",
                "output_cost",
                "output_costs_all",
                "subcomponent_averages",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for analysis in Analysis.objects.all().order_by("id"):
                output_metrics = _first_intervention_metrics(analysis)
                # Selection deliberately preserved from the original code (the
                # LAST metric in iteration order) so snapshots stay comparable
                # to CSVs written by older versions.
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
                        "output_costs_all": json.dumps(analysis.output_costs or {}, sort_keys=True),
                        "subcomponent_averages": json.dumps(_subcomponent_averages(analysis), sort_keys=True),
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
