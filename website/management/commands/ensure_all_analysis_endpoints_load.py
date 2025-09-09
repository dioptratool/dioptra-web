# Note: The Transaction Pipeline must be running for this command to work properly.
# Although it’s not directly used in this process, having it active prevents potential errors and warnings in the views.
# You can find the repository at: https://github.com/dioptratool/dioptra-service-transaction-pipeline
#
# Quickstart Guide for the Transaction Pipeline:
#   These commands are run in the dioptra-service-transaction-pipeline project root
#  1. Build the project:
#      make build
#      make up
#  2. Generate sample data:
#      make gen-test-data
#  3. Import test the sample data:
#      make testimport-transactionscsv
#
# Steps to take before running this script:
#   These commands are run in this project's root
#  1. Restore the database from an export:
#      BACKUP=/path/to/export make restore-db-pgdump
#  2. Apply any migrations:
#      make migrate
import time
from collections import defaultdict

import requests
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.test import Client, override_settings

from website.models import Analysis

ENDPOINTS_TO_CHECK = [
    "",
    "add-other-costs",
    "allocate",
    "categorize",
    "define",
    "insights",
    "load-data",
    "download",
]


class Command(BaseCommand):
    help = "Checks the endpoints for all analysis IDs to ensure they load without issue."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.summary = defaultdict(dict)

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            type=str,
            required=True,
            help="Username/email of the user to authenticate with",
        )

        parser.add_argument(
            "--debug",
            action="store_true",
            help="Enable debug mode for more verbose output",
        )

        parser.add_argument("args", nargs="*")

    def format_summary(self):
        self.stdout.write("| Name | Date Created | Analysis ID | Endpoint              | Error Message |")
        self.stdout.write("| ---- | ------------ | ----------- | --------------------- | ------------- |")

        if not self.summary:
            self.stdout.write("No errors found.")

        for analysis_data, endpoint_errors in self.summary.items():
            a_id, a_title, a_created = analysis_data
            for endpoint, msg in endpoint_errors.items():
                self.stdout.write(
                    f"| {a_title} | {a_created:%Y-%m-%d} | {a_id:>11} | analysis/{a_id}/{endpoint:<21} | {msg} |"
                )

    @override_settings(ALLOWED_HOSTS=["testserver"], DEBUG=False)
    def handle(self, *args, **options):
        start_time = time.time()
        max_analysis_time = 0
        max_analysis_id = None

        try:
            username = options["username"]

            command_debug = options["debug"]

            User = get_user_model()
            try:
                user = User.objects.get(email=username)
            except User.DoesNotExist:
                self.stderr.write(self.style.ERROR(f'User with username "{username}" does not exist.'))
                return

            client = Client()
            client.force_login(user)

            analysis_info = Analysis.objects.values_list("id", "title", "created").order_by("id")
            analysis_count = analysis_info.count()
            self.stdout.write(f"Checking {analysis_count} analyses...")

            api_base_url = (
                "/analysis/{analysis_id}/{endpoint}"  # Use relative URL since we're using the test client
            )

            for i, analysis_data in enumerate(analysis_info.iterator()):
                analysis_start_time = time.time()  # Start timing for this analysis

                a_id, a_title, a_created = analysis_data
                if i % 20 == 0:
                    self.stdout.write(f"Checking analysis {i}/{analysis_count} ...")
                for endpoint in ENDPOINTS_TO_CHECK:
                    url = api_base_url.format(analysis_id=a_id, endpoint=endpoint)
                    try:
                        response = client.get(url, follow=True)
                        if response.status_code != requests.codes.ok:
                            msg = f"Analysis ID {a_id}/{endpoint}: Status {response.status_code}"
                            if command_debug:
                                self.summary[analysis_data][endpoint] = msg
                                self.stdout.write(self.style.WARNING(msg))
                        else:
                            if command_debug:
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f"Analysis ID {analysis_data}/{endpoint}: Status {response.status_code}"
                                    )
                                )

                    except Exception as e:
                        self.summary[analysis_data][endpoint] = str(e)
                        if command_debug:
                            self.stdout.write(
                                self.style.ERROR(f"Request failed for analysis ID {a_id}/{endpoint}: {e}")
                            )

                # Check applog page loads
                app_log_endpoint = "/panels/app_log/applogentry/"
                app_log_response = client.get(app_log_endpoint)
                if app_log_response.status_code != requests.codes.ok:
                    msg = f"App Log {app_log_endpoint}: Status {app_log_response.status_code}"
                    if command_debug:
                        self.summary[analysis_data][app_log_response] = msg
                        self.stdout.write(self.style.WARNING(msg))
                else:
                    if command_debug:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"App Log {app_log_endpoint}: Status {app_log_response.status_code}"
                            )
                        )

                analysis_time = time.time() - analysis_start_time  # Calculate time for this analysis
                if analysis_time > max_analysis_time:
                    max_analysis_time = analysis_time
                    max_analysis_id = a_id

        finally:
            self.format_summary()
            total_time = time.time() - start_time  # Calculate total time
            self.stdout.write(
                f"Total time to run: " f"{total_time // 60} minutes {total_time % 60:.2f} seconds"
            )
            self.stdout.write(
                f"Maximum time to process a single analysis (id: {max_analysis_id}): "
                f"{max_analysis_time // 60} minutes {max_analysis_time % 60:.2f} seconds"
            )
