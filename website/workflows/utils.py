from website.workflows.analysis import AnalysisWorkflow


def recalculate_analysis(analysis) -> None:
    """
    Refresh derived analysis state after interventions or sub-components change.
    """
    analysis.ensure_cost_type_category_objects()
    workflow = AnalysisWorkflow(analysis)
    workflow.invalidate_step("insights")
    workflow.calculate_if_possible()
