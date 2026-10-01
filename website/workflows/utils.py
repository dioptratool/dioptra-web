from website.workflows._workflow_base import WORKFLOW_PREFETCHES  # noqa: F401  (re-exported)
from website.workflows.analysis import AnalysisWorkflow


def recalculate_analysis(analysis, actor=None) -> None:
    """
    Refresh derived analysis state after interventions or sub-components change.

    `actor` is the user making the change; it is recorded if the change resets the lifecycle
    status. Leave it None for system work.
    """
    analysis.ensure_cost_type_category_objects()
    workflow = AnalysisWorkflow(analysis)
    workflow.invalidate_step("insights")
    workflow.calculate_if_possible(actor)
