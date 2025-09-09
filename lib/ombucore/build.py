import os
import shutil

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection


class BuildCommand(BaseCommand):
    """
    A build command base class that handles cleaning and
    recreating the database and media files.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--soft",
            action="store_true",
            dest="soft",
            default=False,
            help="Soft delete, only remove content from the database instead of dropping and creating it.",
        )
        parser.add_argument(
            "-y",
            action="store_true",
            dest="y",
            default=False,
            help='"Yes" -- don\'t prompt for confirmation.',
        )

    def handle(self, *args, **options):
        if options["soft"]:
            self.database_clean_soft(*args, **options)
        else:
            self.database_clean_hard(*args, **options)
        self.media_clean()
        call_command("migrate")

    def media_clean(self, *args, **options):
        media_dir = getattr(settings, "MEDIA_ROOT", False)
        if not media_dir:
            return

        target_dir = media_dir.rstrip("//")

        # Gather directory contents
        contents = [os.path.join(target_dir, i) for i in os.listdir(target_dir)]

        # Iterate and remove each item in the appropriate manner
        for i in contents:
            if os.path.split(i)[-1] == ".gitkeep":
                pass
            elif os.path.isdir(i):
                shutil.rmtree(i)
            else:
                os.unlink(i)

    def database_clean_soft(self, *args, **options):
        if not options["y"]:
            confirm = input(
                """
You have requested a database reset.
This will IRREVERSIBLY DESTROY
ALL data in the database.
Are you sure you want to do this?

Type 'y' to continue, or 'n' to cancel: """
            )

            if confirm != "y":
                print("Reset cancelled.")
                exit()

        call_command("flush", "--no-input")

    def database_clean_hard(self, *args, **options):
        """
        Resets the database for this project.

        Note: Transaction wrappers are in reverse as a work around for
        autocommit, anybody know how to do this the right way?
        """

        verbosity = int(options.get("verbosity", 1))
        if not options["y"]:
            confirm = input(
                """
You have requested a database reset.
This will IRREVERSIBLY DESTROY
ALL Django data in the database.
Are you sure you want to do this?

Type 'y' to continue, or 'n' to cancel: """
            )

            if confirm != "y":
                print("Reset cancelled.")
                exit()

        tables = connection.introspection.django_table_names(only_existing=True, include_views=False)
        tables.append("django_migrations")
        tables = list(map(connection.ops.quote_name, tables))
        with connection.cursor() as cursor:
            if connection.vendor == "mysql":
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
                for table_name in tables:
                    cursor.execute(f"DROP TABLE {table_name}")
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            elif connection.vendor == "postgresql":
                for table_name in tables:
                    cursor.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
            cursor.execute('DROP COLLATION IF EXISTS "case_insensitive_email"')

        if verbosity >= 2:
            print("Reset successful.")
