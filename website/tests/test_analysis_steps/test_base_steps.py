from website.workflows import AnalysisWorkflow


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
