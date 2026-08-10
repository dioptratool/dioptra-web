import importlib
from types import SimpleNamespace

import pytest
from django.apps import apps as django_apps

from website.models import SubcomponentCostAllocation, SubcomponentCostAnalysis
from website.tests.factories import CostLineItemConfigFactory, InterventionInstanceFactory
from website.management.commands.utils import _get_last_completed_step_name
from website.workflows import AnalysisWorkflow
from website.workflows.analysis.steps.allocate_subcomponents import AllocateSubcomponents
from .common import StepTest


def _make_subcomponent_analysis(intervention_instance, labels):
    """SubcomponentCostAnalysis.save() backfills empty labels from the
    intervention, so force the labels with a queryset update."""
    subcomponent_analysis = SubcomponentCostAnalysis.objects.create(
        intervention_instance=intervention_instance,
    )
    SubcomponentCostAnalysis.objects.filter(pk=subcomponent_analysis.pk).update(subcomponent_labels=labels)
    subcomponent_analysis.refresh_from_db()
    return subcomponent_analysis


@pytest.mark.django_db
class TestAllocateSubcomponents(StepTest):
    step_under_test = AllocateSubcomponents

    @pytest.fixture()
    def up_to_date_workflow(self, analysis_workflow_with_subcomponent_labels):
        return analysis_workflow_with_subcomponent_labels

    @pytest.fixture()
    def workflow_with_completed_step(
        self,
        analysis_workflow_with_all_cost_lines_allocated_to_subcomponents,
    ):
        return analysis_workflow_with_all_cost_lines_allocated_to_subcomponents

    @pytest.mark.skip(
        "The next step is insights (add-other-costs is disabled on this fixture) "
        "which is only incomplete if its dependencies aren't met"
    )
    def test_next_step_is_incomplete(self, workflow_with_completed_step):
        pass

    def test_step_is_disabled_without_subcomponent_analyses(self, analysis_workflow_with_allocations):
        step = analysis_workflow_with_allocations.get_step(self.step_under_test.name)
        assert not step.is_enabled

    def test_labelless_husk_does_not_gate_a_finished_analysis(
        self,
        analysis_workflow_with_client_time_added,
    ):
        """
        The pre-2.2 side flow created a SubcomponentCostAnalysis as soon as it
        was opened, leaving label-less husks on migrated analyses. A husk has
        nothing to allocate, so it must not enable this step and re-open an
        analysis that was complete in 2.1.
        """
        analysis = analysis_workflow_with_client_time_added.analysis
        assert _get_last_completed_step_name(analysis) == "insights"

        _make_subcomponent_analysis(analysis.interventioninstance_set.first(), labels=[])

        workflow = AnalysisWorkflow(analysis)
        assert not workflow.get_step(self.step_under_test.name).is_enabled
        assert _get_last_completed_step_name(analysis) == "insights"

    def test_get_next_skips_disabled_step(self, analysis_workflow_with_allocations):
        workflow = analysis_workflow_with_allocations
        next_step = workflow.get_next(workflow.get_step("allocate"))
        assert next_step.name != self.step_under_test.name

    def test_allocate_is_complete_without_subcomponent_allocations(
        self,
        analysis_workflow_with_subcomponent_labels,
    ):
        """
        Regression guard for the fused (pre-split) rule: missing subcomponent
        allocations must no longer hold the allocate step incomplete.
        """
        workflow = analysis_workflow_with_subcomponent_labels
        assert workflow.get_step("allocate").is_complete
        assert not workflow.get_step(self.step_under_test.name).is_complete


@pytest.mark.django_db
class TestHuskCleanupMigration:
    def _run_migration(self):
        module = importlib.import_module("website.migrations.0007_remove_subcomponent_husks")
        schema_editor = SimpleNamespace(connection=SimpleNamespace(alias="default"))
        module.delete_husk_subcomponent_analyses(django_apps, schema_editor)

    def test_deletes_only_labelless_unallocated_husks(self, defaults):
        husk = _make_subcomponent_analysis(InterventionInstanceFactory(), labels=[])
        null_husk = _make_subcomponent_analysis(InterventionInstanceFactory(), labels=None)
        labeled = _make_subcomponent_analysis(InterventionInstanceFactory(), labels=["A", "B"])

        allocated_instance = InterventionInstanceFactory()
        allocated = _make_subcomponent_analysis(allocated_instance, labels=[])
        SubcomponentCostAllocation.objects.create(
            subcomponent_analysis=allocated,
            cli_config=CostLineItemConfigFactory(
                cost_line_item__analysis=allocated_instance.analysis,
            ),
            skipped=True,
        )

        self._run_migration()

        remaining = set(SubcomponentCostAnalysis.objects.values_list("pk", flat=True))
        assert husk.pk not in remaining
        assert null_husk.pk not in remaining
        assert labeled.pk in remaining
        assert allocated.pk in remaining
