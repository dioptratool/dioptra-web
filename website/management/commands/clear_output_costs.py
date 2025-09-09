from django.core.management.base import BaseCommand

from website.models import Analysis
from website.workflows import AnalysisWorkflow
from website.workflows.analysis.steps.insights import Insights


class Command(BaseCommand):
    help = "This command clears the cached JSON from the db and recomputes it"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Clearing and recomputing output costs..."), ending="\n")
        self.stdout.write("Starting...", ending="\n")
        for each_analysis in Analysis.objects.order_by("-id").all():
            self.stdout.write(
                f'Recomputing output costs on Analysis:{each_analysis.pk} "{each_analysis.title}" ...',
                ending="\n",
            )

            each_analysis.output_costs = {}
            each_analysis.save()
            analysis_wf = AnalysisWorkflow(each_analysis)
            insight_step: Insights = analysis_wf.get_step("insights")
            insight_step.calculate_if_possible()

        self.stdout.write(self.style.SUCCESS("Success!"), ending="\n")
