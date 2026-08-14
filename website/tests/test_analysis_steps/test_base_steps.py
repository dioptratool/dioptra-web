from website.workflows import AnalysisWorkflow
from website.workflows._steps_base import MultiStep, Step, SubStep
from website.workflows._workflow_base import Workflow


class DummyAnalysis:
    pk = 1


class StubStep(Step):
    nav_title = "Stub"

    def __init__(self, workflow, name, complete=True, enabled=True):
        super().__init__(workflow)
        self.name = name
        self._complete = complete
        self.is_enabled = enabled

    @property
    def is_complete(self):
        return self._complete

    @property
    def dependencies_met(self):
        return True


class StubSubStep(SubStep):
    nav_title = "Stub Substep"

    def __init__(self, workflow, name, complete=True, enabled=True):
        super().__init__(workflow)
        self.name = name
        self._complete = complete
        self.is_enabled = enabled

    @property
    def is_complete(self):
        return self._complete


class StubMultiStep(MultiStep):
    nav_title = "Stub Multistep"

    def __init__(self, workflow, name, steps, dependencies_met=True, enabled=True):
        super().__init__(workflow)
        self.name = name
        self.steps = steps
        self._dependencies_met = dependencies_met
        self.is_enabled = enabled
        for step in self.steps:
            step.parent = self

    @property
    def dependencies_met(self):
        return self._dependencies_met

    @property
    def is_complete(self):
        return self.dependencies_met and all(step.is_complete for step in self.steps if step.is_enabled)


def make_workflow(steps):
    workflow = Workflow(DummyAnalysis())
    workflow.steps = steps
    return workflow


def test_all_steps_have_name():
    for each_step in AnalysisWorkflow.step_classes:
        assert each_step.name, f"{each_step.__name__} does not have a `name` set"


def test_all_substeps_have_name():
    for each_step in AnalysisWorkflow.step_classes:
        if hasattr(each_step, "steps"):
            for each_substep in each_step.steps:
                assert each_substep.name, f"{each_substep.__name__} does not have a `name` set"


def test_all_steps_have_nav_title():
    for each_step in AnalysisWorkflow.step_classes:
        assert each_step.nav_title, f"{each_step.__name__} does not have a `nav_title` set"


def test_all_substeps_have_nav_title():
    for each_step in AnalysisWorkflow.step_classes:
        if hasattr(each_step, "steps"):
            for each_substep in each_step.steps:
                assert each_substep.nav_title, f"{each_substep.__name__} does not have a `nav_title` set"


def test_get_last_complete_returns_none_when_first_step_is_incomplete():
    workflow = make_workflow([])
    workflow.steps = [
        StubStep(workflow, "define", complete=False),
        StubStep(workflow, "load-data", complete=True),
    ]

    assert workflow.get_last_complete() is None


def test_get_last_complete_returns_previous_step_for_partial_workflow():
    workflow = make_workflow([])
    define = StubStep(workflow, "define", complete=True)
    load_data = StubStep(workflow, "load-data", complete=True)
    categorize = StubStep(workflow, "categorize", complete=False)
    workflow.steps = [define, load_data, categorize]

    assert workflow.get_last_complete() is load_data


def test_get_last_complete_returns_final_step_for_complete_workflow():
    workflow = make_workflow([])
    define = StubStep(workflow, "define", complete=True)
    insights = StubStep(workflow, "insights", complete=True)
    workflow.steps = [define, insights]

    assert workflow.get_last_complete() is insights


def test_get_last_complete_returns_multistep_parent_when_all_substeps_complete():
    workflow = make_workflow([])
    substep_one = StubSubStep(workflow, "allocate-a", complete=True)
    substep_two = StubSubStep(workflow, "allocate-b", complete=True)
    allocate = StubMultiStep(workflow, "allocate", [substep_one, substep_two])
    workflow.steps = [StubStep(workflow, "define", complete=True), allocate]

    assert workflow.get_last_complete() is allocate


def test_get_last_complete_returns_last_complete_substep_for_partial_multistep():
    workflow = make_workflow([])
    substep_one = StubSubStep(workflow, "allocate-a", complete=True)
    substep_two = StubSubStep(workflow, "allocate-b", complete=False)
    allocate = StubMultiStep(workflow, "allocate", [substep_one, substep_two])
    workflow.steps = [StubStep(workflow, "define", complete=True), allocate, StubStep(workflow, "insights")]

    assert workflow.get_last_complete() is substep_one


def test_get_last_complete_returns_previous_step_when_multistep_dependencies_are_not_met():
    workflow = make_workflow([])
    define = StubStep(workflow, "define", complete=True)
    allocate = StubMultiStep(
        workflow,
        "allocate",
        [StubSubStep(workflow, "allocate-a", complete=True)],
        dependencies_met=False,
    )
    workflow.steps = [define, allocate]

    assert workflow.get_last_complete() is define
