"""
Feature 86, Issue 6: the In-Kind Contributions substep is complete only when every in-kind
item allocated to an intervention with sub-components has a complete split.
"""

from decimal import Decimal

import pytest
from django.urls import reverse

from website.models import AnalysisCostType
from website.tests.factories import (
    AnalysisFactory,
    CostLineItemConfigFactory,
    CostLineItemFactory,
    CostLineItemInterventionAllocationFactory,
    InterventionFactory,
    SubcomponentCostAllocationFactory,
    SubcomponentCostAnalysisFactory,
)
from website.workflows import AnalysisWorkflow


def in_kind_step(analysis):
    parent = AnalysisWorkflow(analysis).get_step("add-other-costs")
    return next(step for step in parent.steps if step.name == "add-in-kind-contributor-costs")


def add_in_kind_item(analysis, instance, allocation=Decimal("100"), split=None, skipped=False):
    config = CostLineItemConfigFactory(
        cost_line_item=CostLineItemFactory(analysis=analysis, grant_code="G1"),
        analysis_cost_type=AnalysisCostType.IN_KIND,
    )
    CostLineItemInterventionAllocationFactory(
        cli_config=config, intervention_instance=instance, allocation=allocation
    )
    if split is not None or skipped:
        SubcomponentCostAllocationFactory(
            subcomponent_analysis=instance.subcomponent_cost_analysis,
            cli_config=config,
            allocations=split or {},
            skipped=skipped,
        )
    return config.cost_line_item


@pytest.fixture
def setup(defaults):
    analysis = AnalysisFactory(in_kind_contributions=True)
    instance = analysis.add_intervention(InterventionFactory())
    SubcomponentCostAnalysisFactory(
        intervention_instance=instance, subcomponent_labels=["Treatment", "Outreach"]
    )
    instance.refresh_from_db()
    return analysis, instance


@pytest.mark.django_db
class TestInKindSubstepCompleteness:
    def test_no_items_is_incomplete(self, setup):
        analysis, _ = setup
        assert not in_kind_step(analysis).is_complete

    def test_complete_split_is_complete(self, setup):
        analysis, instance = setup
        add_in_kind_item(analysis, instance, split={"0": "40", "1": "60"})
        assert in_kind_step(analysis).is_complete

    @pytest.mark.parametrize(
        "split",
        [None, {}, {"0": "100"}, {"0": "40", "1": "50"}],
        ids=["no row", "empty row", "missing component", "under 100"],
    )
    def test_incomplete_split_is_incomplete(self, setup, split):
        analysis, instance = setup
        add_in_kind_item(analysis, instance, split=split)
        step = in_kind_step(analysis)
        assert not step.is_complete
        assert [item.id for item in step.items_needing_subcomponent_split()] == [
            analysis.in_kind_contributions_cost_line_items.get().id
        ]

    def test_zero_allocation_needs_no_split(self, setup):
        analysis, instance = setup
        add_in_kind_item(analysis, instance, allocation=Decimal("0"))
        assert in_kind_step(analysis).is_complete

    def test_intervention_without_subcomponents_needs_no_split(self, defaults):
        analysis = AnalysisFactory(in_kind_contributions=True)
        instance = analysis.add_intervention(InterventionFactory())
        add_in_kind_item(analysis, instance)
        assert in_kind_step(analysis).is_complete

    def test_one_incomplete_item_among_complete_ones(self, setup):
        analysis, instance = setup
        add_in_kind_item(analysis, instance, split={"0": "40", "1": "60"})
        bad = add_in_kind_item(analysis, instance, split={"0": "40"})
        step = in_kind_step(analysis)
        assert not step.is_complete
        assert [item.id for item in step.items_needing_subcomponent_split()] == [bad.id]


@pytest.mark.django_db
class TestInKindListAndWorkflow:
    def _in_kind_url(self, analysis):
        return reverse(
            "analysis-add-other-costs-detail",
            kwargs={"pk": analysis.pk, "cost_type": int(AnalysisCostType.IN_KIND)},
        )

    def test_list_marks_items_needing_a_split(
        self, client_with_admin, analysis_workflow_with_all_cost_lines_allocated_to_subcomponents
    ):
        analysis = analysis_workflow_with_all_cost_lines_allocated_to_subcomponents.analysis
        analysis.in_kind_contributions = True
        analysis.save()
        instance = analysis.interventioninstance_set.select_related("subcomponent_cost_analysis").first()
        needing = add_in_kind_item(analysis, instance, split={"0": "100"})
        labels = instance.subcomponent_cost_analysis.subcomponent_labels
        complete = add_in_kind_item(analysis, instance, split={str(i): "20" for i in range(len(labels))})

        response = client_with_admin.get(self._in_kind_url(analysis))

        assert response.status_code == 200
        content = response.content.decode()
        assert "sub-component" in content.lower()
        assert f'data-needs-subcomponent-split="{needing.id}"' in content
        assert f'data-needs-subcomponent-split="{complete.id}"' not in content

    def test_insights_is_blocked_until_the_split_is_complete(
        self, analysis_workflow_with_all_cost_lines_allocated_to_subcomponents
    ):
        analysis = analysis_workflow_with_all_cost_lines_allocated_to_subcomponents.analysis
        analysis.in_kind_contributions = True
        analysis.save()
        instance = analysis.interventioninstance_set.select_related("subcomponent_cost_analysis").first()
        item = add_in_kind_item(analysis, instance, split={"0": "100"})

        assert not AnalysisWorkflow(analysis).get_step("insights").dependencies_met

        labels = instance.subcomponent_cost_analysis.subcomponent_labels
        row = item.config.subcomponent_cost_allocations.get()
        row.allocations = {str(i): "20" for i in range(len(labels))}
        row.save()

        assert AnalysisWorkflow(analysis).get_step("insights").dependencies_met
