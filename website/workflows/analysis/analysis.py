from website.workflows._workflow_base import Workflow
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

    def calculate_if_possible(self) -> None:
        insight_step: Insights | None = self.get_step("insights")
        if insight_step:
            insight_step.calculate_if_possible()
