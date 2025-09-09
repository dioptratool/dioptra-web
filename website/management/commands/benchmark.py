import datetime
import sys
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from website.data_loading.transactions import load_transactions
from website.models import (
    Analysis,
    AnalysisCostTypeCategory,
    AnalysisCostTypeCategoryGrant,
    AnalysisType,
    Country,
    Intervention,
    InterventionGroup,
    Transaction,
)
from website.utils.duplicator import clone_analysis


class Command(BaseCommand):
    help = "Benchmark a command."

    def add_arguments(self, parser):
        parser.add_argument(
            "routine",
            help="Name of the benchmark function to run (choices: import, clone)",
        )
        parser.add_argument(
            "--debug-sql",
            action="store_true",
            help="Print sql queries for each stage",
        )
        parser.add_argument(
            "--analysis",
            type=int,
            help="ID of the analysis to use, rather than creating a new one.",
        )
        parser.add_argument(
            "--every-analysis",
            action="store_true",
            help="If passed, benchmark every analysis in the database.",
        )
        parser.add_argument(
            "--commit",
            action="store_true",
            help="If passed, do not roll back.",
        )

    def handle(self, *args, **options):
        routine = getattr(self, f"benchmark_{options.get('routine')}", None)
        if routine is None:
            self.stdout.write(f"Invalid routine '{options.get('routine')}'")
            sys.exit(1)

        def bench(a):
            try:
                self.run_routine(
                    routine,
                    commit=options.get("commit"),
                    args=[a],
                    kwargs={"debug_sql": options.get("debug_sql")},
                )
            except RollbackException:
                pass

        if options.get("every_analysis"):
            for analysis in Analysis.objects.order_by("id").all():
                bench(analysis)
        elif options.get("analysis"):
            analysis = Analysis.objects.get(id=options.get("analysis"))
            bench(analysis)
        else:
            print("Creating fixtured analysis for benchmark")
            analysis = self.create_analysis()
            bench(analysis)

    @transaction.atomic
    def run_routine(self, routine, commit=False, args=(), kwargs=None):
        routine(*args, **kwargs)
        if commit:
            print("Success. Committing changes.")
        else:
            print("Success. Rolling back.")
            raise RollbackException()

    def benchmark_import(self, analysis, debug_sql=False):
        print(f"Starting import of analysis {analysis.id}")
        sw = Stopwatch(debug_sql)
        succeeded, result = load_transactions(analysis, from_datastore=True)
        if succeeded:
            print("Imported", result["imported_count"], "pipeline transactions.")
            print("Now", Transaction.objects.count(), "web transactions")
            sw.click("load_transactions_from_data_store")
        else:
            print("Failed:", result)
            raise CommandError()
        analysis.create_cost_line_items_from_transactions()
        sw.click("create_cost_line_items_from_transactions")
        analysis.auto_categorize_cost_line_items()
        sw.click("auto_categorize_cost_line_items")
        analysis.ensure_cost_type_category_objects()
        sw.click("ensure_cost_type_category_objects")
        print(
            "AnalysisCostTypeCategory stats:",
            AnalysisCostTypeCategory.objects.count(),
            "categories,",
            AnalysisCostTypeCategoryGrant.objects.count(),
            "grants",
        )

    def benchmark_clone(self, analysis, debug_sql=False):
        print(f"Starting clone of analysis {analysis.id}")
        sw = Stopwatch(debug_sql)
        new_analysis = clone_analysis(analysis.id)
        sw.click("clone_analysis")
        print(f"Cloned into analysis {new_analysis.id}")

    def create_analysis(self):
        intervention_group, created = InterventionGroup.objects.get_or_create(name="Test Intervention Group")
        intervention, created = Intervention.objects.get_or_create(
            name="Test Intervention",
            group=intervention_group,
        )
        analysis = Analysis.objects.create(
            title="Test Grants",
            intervention=intervention,
            analysis_type=AnalysisType.objects.create(title="Budget projection data"),
            country=Country.objects.create(name="Gabon", code="DM"),
            parameters=dict(
                number_of_children_treated_for_sam=1600,
            ),
            description="Analysis description",
            start_date=datetime.date(1996, 6, 12),
            end_date=datetime.date(1998, 11, 19),
            grants="GX922",
        )
        return analysis


class RollbackException(BaseException):
    pass


class Stopwatch:
    def __init__(self, debug):
        self.start = time.perf_counter()
        self.last = self.start
        self.last_queries = len(connection.queries_log)
        self.debug = debug

    def click(self, key):
        now = time.perf_counter()
        stage = now - self.last
        total = now - self.start
        self.last = now

        nowq = len(connection.queries_log)
        stageq = nowq - self.last_queries
        self.last_queries = nowq

        print(f"{key}:\t {stage:0.2f}s\t elapsed: {total:0.2f}s\t queries: {stageq}")
        if self.debug:
            for q in connection.queries[(self.last_queries - stageq) : self.last_queries]:
                print(q["sql"][:255])
