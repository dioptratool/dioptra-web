# Note: The transaction store DB container must be running (`make up`). A store
# populated via the Transaction Pipeline is desirable but not required — an
# unpopulated store just shows a transaction count of 0 on the load-data page
# for analyses that haven't loaded data yet, and store counts are never part of
# validation results. Pipeline repo:
# https://github.com/dioptratool/dioptra-service-transaction-pipeline
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
from django.core.management.base import BaseCommand, CommandError
from django.test import Client, override_settings

from website.models import Analysis
from website.workflows import AnalysisWorkflow

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

APP_LOG_ENDPOINT = "/panels/app_log/applogentry/"


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

        parser.add_argument(
            "--all-step-urls",
            action="store_true",
            help="Derive the URLs to check from each analysis' workflow (every step and "
            "sub-step, including per-grant and subcomponent pages) instead of the "
            "fixed top-level endpoint list.",
        )

        parser.add_argument("args", nargs="*")

    def format_summary(self):
        self.stdout.write("| Name | Date Created | Analysis ID | Endpoint | Error Message |")
        self.stdout.write("| ---- | ------------ | ----------- | -------- | ------------- |")

        if not self.summary:
            self.stdout.write("No errors found.")

        for analysis_data, endpoint_errors in self.summary.items():
            a_id, a_title, a_created = analysis_data
            for endpoint, msg in endpoint_errors.items():
                self.stdout.write(f"| {a_title} | {a_created:%Y-%m-%d} | {a_id:>11} | {endpoint} | {msg} |")

    def _check_url(self, client, analysis_data, label, url, command_debug):
        """
        GET one URL and record any failure in self.summary. Failures are ALWAYS
        recorded; --debug only controls per-request console output.
        """
        try:
            response = client.get(url, follow=True)
        except Exception as e:
            self.summary[analysis_data][label] = str(e)
            if command_debug:
                self.stdout.write(self.style.ERROR(f"Request failed for {label}: {e}"))
            return

        if response.status_code != requests.codes.ok:
            self.summary[analysis_data][label] = f"Status {response.status_code}"
            if command_debug:
                self.stdout.write(self.style.WARNING(f"{label}: Status {response.status_code}"))
        elif command_debug:
            self.stdout.write(self.style.SUCCESS(f"{label}: Status {response.status_code}"))

    def _urls_to_check(self, analysis_id, all_step_urls, analysis_data):
        """
        Return (label, url) pairs. With --all-step-urls the list is derived from
        the analysis' workflow so every step AND sub-step page is visited
        (per-grant allocate pages, subcomponent pages, add-other-costs pages);
        otherwise the fixed top-level list is used.
        """
        if not all_step_urls:
            return [
                (f"analysis/{analysis_id}/{endpoint}", f"/analysis/{analysis_id}/{endpoint}")
                for endpoint in ENDPOINTS_TO_CHECK
            ]

        urls = []
        seen = set()
        try:
            workflow = AnalysisWorkflow(Analysis.objects.get(pk=analysis_id))
            candidates = []
            for step in workflow.steps:
                candidates.append(step)
                candidates.extend(getattr(step, "steps", []))
            for candidate in candidates:
                href = candidate.get_href()
                if href and href not in seen:
                    seen.add(href)
                    urls.append((href, href))
        except Exception as e:
            self.summary[analysis_data]["(workflow url discovery)"] = str(e)
        # The download endpoint is not a workflow step but exercises the
        # spreadsheet writer (including subcomponent averages) — keep it.
        download = f"/analysis/{analysis_id}/download"
        if download not in seen:
            urls.append((f"analysis/{analysis_id}/download", download))
        return urls

    @override_settings(ALLOWED_HOSTS=["testserver"], DEBUG=False)
    def handle(self, *args, **options):
        start_time = time.time()
        max_analysis_time = 0
        max_analysis_id = None

        try:
            username = options["username"]

            command_debug = options["debug"]
            all_step_urls = options["all_step_urls"]

            User = get_user_model()
            try:
                user = User.objects.get(email=username)
            except User.DoesNotExist:
                raise CommandError(f'User with username "{username}" does not exist.')

            client = Client()
            client.force_login(user)

            analysis_info = Analysis.objects.values_list("id", "title", "created").order_by("id")
            analysis_count = analysis_info.count()
            self.stdout.write(f"Checking {analysis_count} analyses...")

            for i, analysis_data in enumerate(analysis_info.iterator()):
                analysis_start_time = time.time()  # Start timing for this analysis

                a_id, a_title, a_created = analysis_data
                if i % 20 == 0:
                    self.stdout.write(f"Checking analysis {i}/{analysis_count} ...")
                for label, url in self._urls_to_check(a_id, all_step_urls, analysis_data):
                    self._check_url(client, analysis_data, label, url, command_debug)

                # Check applog page loads
                self._check_url(client, analysis_data, APP_LOG_ENDPOINT, APP_LOG_ENDPOINT, command_debug)

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

        if self.summary:
            failure_count = sum(len(errors) for errors in self.summary.values())
            raise CommandError(f"{failure_count} endpoint failure(s) recorded — see summary above.")
