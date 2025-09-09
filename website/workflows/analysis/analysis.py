from website.workflows._workflow_base import Workflow
from .steps.add_other_costs import AddOtherCosts
from .steps.allocate import Allocate
from .steps.categorize import Categorize
from .steps.define import Define
from .steps.insights import Insights
from .steps.load_data import LoadData
from .steps.subcomponent_analysis_allocate.subcomponent_analysis_allocate import (
    SubcomponentsAllocate,
)
from .steps.subcomponent_analysis_confirm.subcomponent_analysis_confirm import (
    SubcomponentsConfirm,
)

"""
Manages the flow and logic of individual steps in the analysis workflow.
"""


class AnalysisWorkflow(Workflow):
    step_classes = [
        Define,
        LoadData,
        Categorize,
        Allocate,
        AddOtherCosts,
        Insights,
        # Subcomponent Analysis Steps Follow
        SubcomponentsConfirm,
        SubcomponentsAllocate,
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.main_analysis_steps = self.steps[:-2]
        self.subcomponent_analysis_steps = self.steps[-2:]

    def calculate_if_possible(self) -> None:
        insight_step: Insights | None = self.get_step("insights")
        if insight_step:
            insight_step.calculate_if_possible()
