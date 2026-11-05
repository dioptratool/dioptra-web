"""
The build command's "Main Flow Complete - With Sub-Components" sample: a complete analysis with
filled-in sub-component splits (including a skipped row) and an in-kind item with a split, for
demonstrating and testing Feature 86.
"""

from decimal import Decimal

import pytest

from website.management.commands.build import Command
from website.management.commands.seed_data.default import CATEGORIES, COST_TYPES, MAPPINGS
from website.models import Analysis, AnalysisStatus, SubcomponentCostAllocation
from website.models.cost_type import ProgramCost
from website.models.subcomponent import subcomponent_allocation_complete
from website.workflows import AnalysisWorkflow

SAMPLE_TITLE = "Sample Analysis - Main Flow Complete - With Sub-Components"


def build_sample():
    """Seed the reference data the sample needs, then the sample itself (no flush, no media clean)."""
    command = Command()
    command.add_settings()
    command.add_countries_and_regions()
    command.add_categories(CATEGORIES)
    command.add_cost_types(COST_TYPES)
    command.add_cost_type_category_mappings(mappings=MAPPINGS)
    command.add_interventions()
    command.add_analysis_types()
    command.add_users()
    command.add_debug_analysis_with_subcomponents_complete()
    return Analysis.objects.get(title=SAMPLE_TITLE)


@pytest.fixture
def sample(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    return build_sample()


@pytest.mark.django_db(databases=["default", "transaction_store"])
class TestSubcomponentSample:
    def test_is_complete_with_outputs(self, sample):
        assert sample.analysis_status == AnalysisStatus.COMPLETE
        assert sample.output_costs
        workflow = AnalysisWorkflow(sample)
        assert workflow.all_steps_complete
        assert workflow.get_step("insights").dependencies_met

    def test_two_interventions_with_three_and_two_sub_components(self, sample):
        analyses = {
            instance.intervention.name: instance.subcomponent_cost_analysis
            for instance in sample.interventioninstance_set.select_related(
                "intervention", "subcomponent_cost_analysis"
            )
        }
        assert sorted(len(a.subcomponent_labels) for a in analyses.values()) == [2, 3]
        assert all(a.revision == 0 for a in analyses.values())
        assert all(
            len(set(map(str.casefold, a.subcomponent_labels))) == len(a.subcomponent_labels)
            for a in analyses.values()
        )

    def test_program_cost_rows_are_split_with_varied_values_and_one_skipped(self, sample):
        rows = SubcomponentCostAllocation.objects.filter(
            subcomponent_analysis__intervention_instance__analysis=sample,
            cli_config__analysis_cost_type__isnull=True,
        ).select_related("cli_config__cost_line_item", "subcomponent_analysis")
        assert rows.exists()
        assert rows.filter(skipped=True).count() == 1
        for row in rows:
            assert subcomponent_allocation_complete(row.cli_config.cost_line_item, row.subcomponent_analysis)
        values = {tuple(sorted(row.allocations.items())) for row in rows if not row.skipped}
        assert len(values) >= 3, "splits should vary across rows"
        assert any("0" in row.allocations.values() for row in rows), "at least one explicit 0% component"
        program_items = sample.cost_line_items.filter(config__cost_type__type=ProgramCost.id)
        assert program_items.exists()
        for item in program_items:
            for allocation in item.config.allocations.all():
                if allocation.allocation and hasattr(
                    allocation.intervention_instance, "subcomponent_cost_analysis"
                ):
                    assert subcomponent_allocation_complete(
                        item, allocation.intervention_instance.subcomponent_cost_analysis
                    )

    def test_in_kind_item_has_a_complete_split(self, sample):
        assert sample.in_kind_contributions
        item = sample.in_kind_contributions_cost_line_items.get()
        assert item.total_cost == item.quantity * item.unit_cost
        allocation = item.config.allocations.get()
        assert allocation.allocation == Decimal("100")
        row = SubcomponentCostAllocation.objects.get(cli_config=item.config)
        assert not row.skipped
        assert sum(Decimal(v) for v in row.allocations.values()) == Decimal("100")
        assert len(row.allocations) == len(row.subcomponent_analysis.subcomponent_labels)
        in_kind_step = next(
            step
            for step in AnalysisWorkflow(sample).get_step("add-other-costs").steps
            if step.name == "add-in-kind-contributor-costs"
        )
        assert in_kind_step.is_complete
        assert in_kind_step.items_needing_subcomponent_split() == []
