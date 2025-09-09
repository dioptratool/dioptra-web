from django.core.management.base import BaseCommand

from website.models import Analysis


class Command(BaseCommand):
    help = "Runs auto-categorization on provided list of Analyses"

    def add_arguments(self, parser):
        parser.add_argument(
            "pkeys",
            type=str,
            help='Comma-separated list of primary keys of the Analysis objects (e.g., "18,24,41")',
        )

    def handle(self, *args, **kwargs):
        pkeys_str = kwargs["pkeys"]
        pkey_list = [pkey.strip() for pkey in pkeys_str.split(",") if pkey.strip()]
        success_count = 0
        failure_count = 0

        for pkey in pkey_list:
            try:
                pkey_int = int(pkey)
                analysis = Analysis.objects.get(pk=pkey_int)
                analysis.auto_categorize_cost_line_items()
                analysis.ensure_cost_type_category_objects()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully auto-categorized cost line items for Analysis with pkey {pkey_int}"
                    )
                )
                success_count += 1
            except Analysis.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"Analysis with pkey {pkey} does not exist"))
                failure_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Processing complete: {success_count} successes, {failure_count} failures.")
        )
