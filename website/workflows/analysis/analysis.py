from website.models import Analysis, AnalysisStatus
from website.workflows._workflow_base import WORKFLOW_PREFETCHES, Workflow
from .steps.add_other_costs import AddOtherCosts
from .steps.allocate import Allocate
from .steps.allocate_subcomponents import AllocateSubcomponents
from .steps.categorize import Categorize
from .steps.define import Define
from .steps.insights import Insights
from .steps.interventions import Interventions
from .steps.load_data import LoadData

"""
Manages the flow and logic of individual steps in the analysis workflow.
"""


class AnalysisWorkflow(Workflow):
    step_classes = [
        Define,
        Interventions,
        LoadData,
        Categorize,
        Allocate,
        AllocateSubcomponents,
        AddOtherCosts,
        Insights,
    ]

    def calculate_if_possible(self, actor=None) -> None:
        """
        Recalculate the outputs when the workflow allows it, then reconcile the lifecycle status.

        `actor` is the user whose edit led here; it is recorded if that edit reset the status.
        Leave it None for system work.
        """
        insight_step: Insights | None = self.get_step("insights")
        if insight_step:
            insight_step.calculate_if_possible()
        self.reconcile_lifecycle_status(actor)

    def reconcile_lifecycle_status(self, actor=None) -> None:
        """
        Reset Complete or Validated to In Progress when the workflow, as now stored, is incomplete.

        Call this once a mutation has finished. An In Progress analysis needs nothing. Otherwise
        readiness is checked on a freshly loaded analysis with a new workflow, so step results
        and relations cached before the edit cannot hide a step that is no longer complete; only
        when that check fails does the lifecycle service take its row lock and check again. The
        final lifecycle fields are copied onto this workflow's analysis either way. Becoming
        complete again never advances the status.
        """
        analysis = self.analysis
        if analysis is None or not getattr(analysis, "pk", None):
            return
        if analysis.analysis_status == AnalysisStatus.IN_PROGRESS:
            return
        fresh = Analysis.objects.prefetch_related(*WORKFLOW_PREFETCHES).get(pk=analysis.pk)
        if fresh.analysis_status != AnalysisStatus.IN_PROGRESS and not type(self)(fresh).all_steps_complete:
            from website.analysis_lifecycle import change_analysis_status  # the service imports workflows

            fresh = change_analysis_status(analysis.pk, actor, AnalysisStatus.IN_PROGRESS, automatic=True)
        analysis.copy_lifecycle_fields_from(fresh)
