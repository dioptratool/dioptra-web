import csv
from pathlib import Path

from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand

from website.models import Analysis


class Command(BaseCommand):
    help = "Backup and Restore Analysis.updated field.  Used before bulk editing them."

    def add_arguments(self, parser):
        parser.add_argument(
            "--restore",
            action="store_true",
            help="Restore the Analysis.updated field from the CSV file",
        )

        parser.add_argument(
            "file_path",
            nargs="?",
            default="backup.csv",
            help="Path of backup file",
        )

    def handle(self, *args, **options):
        restore = options["restore"]
        file_path = Path(options["file_path"])

        if restore:
            if not file_path.exists():
                self.stdout.write(self.style.ERROR("Backup file does not exist"))
                return

            with open(file_path) as file:
                reader = csv.DictReader(file)
                for row in reader:
                    try:
                        Analysis.objects.filter(id=row["id"]).update(updated=row["updated"])
                    except ObjectDoesNotExist:
                        self.stdout.write(self.style.ERROR(f"Analysis with id {row['id']} does not exist"))

            self.stdout.write(self.style.SUCCESS("Successfully restored dates to Analyses from backup file"))

        else:
            with open(file_path, "w") as file:
                fieldnames = ["id", "updated"]
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()

                for analysis in Analysis.objects.all():
                    writer.writerow({"id": analysis.id, "updated": analysis.updated})

            self.stdout.write(self.style.SUCCESS("Successfully backed up dates for Analyses"))
