from django.core.management.base import BaseCommand

from website.models import CostLineItem


class Command(BaseCommand):
    help = "Delete CostLineItem objects with specified IDs."

    def add_arguments(self, parser):
        parser.add_argument(
            "ids",
            type=str,
            help='Comma-separated list of IDs to delete (e.g., "1,2,3").',
        )

    def handle(self, *args, **options):
        ids_str = options["ids"]
        ids_list = [pk.strip() for pk in ids_str.split(",") if pk.strip().isdigit()]

        if not ids_list:
            self.stdout.write(self.style.ERROR("No valid IDs provided."))
            return

        objects_to_delete = CostLineItem.objects.filter(pk__in=ids_list)
        count = objects_to_delete.count()

        if count != len(ids_list):
            self.stdout.write(
                self.style.ERROR(
                    f"Only found {count} of the expected"
                    f" {len(ids_list)} Cost Line Items.  Please double check the input."
                )
            )

        # List the IDs that will be deleted
        self.stdout.write(
            "You are about to delete the following CostLineItem IDs: {}".format(", ".join(ids_list))
        )

        # Confirm deletion
        confirm = input('Are you sure you want to delete these objects? Type "yes" to confirm: ')
        if confirm.lower() != "yes":
            self.stdout.write(self.style.ERROR("Deletion cancelled."))
            return

        # Delete the objects
        objects_to_delete.delete()
        self.stdout.write(self.style.SUCCESS(f"Successfully deleted {count} CostLineItem(s)."))
