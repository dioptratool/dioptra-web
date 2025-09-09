from django.core.management.base import BaseCommand

from website.help.sync import SYNC_FUNCS, sync_all


class Command(BaseCommand):
    help = "Sync help items for fields, categories and cost types."

    def add_arguments(self, parser):
        parser.add_argument("types", nargs="*")
        parser.add_argument("-r", "--reset", action="store_true")

    def handle(self, *args, **options):
        if len(options["types"]):
            for type in options["types"]:
                fn = SYNC_FUNCS.get(type)
                if fn:
                    fn(options["reset"])
                else:
                    self.stderr.write(
                        f"cannot sync type {type}. Available types: fields, categories, and cost types."
                    )
        else:
            sync_all(options["reset"])
