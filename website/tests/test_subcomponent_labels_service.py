"""
Feature 86, Issue 1: editing an intervention's sub-component labels keeps every saved
percentage attached to the component it was entered for.
"""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from website.models import AnalysisCostType, SubcomponentCostAllocation, SubcomponentCostAnalysis
from website.subcomponent_labels import (
    Component,
    remap_allocations,
    update_subcomponent_labels,
    validate_sources,
)
from website.tests.factories import (
    AnalysisFactory,
    CostLineItemConfigFactory,
    CostLineItemFactory,
    CostLineItemInterventionAllocationFactory,
    InterventionInstanceFactory,
    SubcomponentCostAllocationFactory,
    SubcomponentCostAnalysisFactory,
)


def components(*pairs):
    return [Component(label=label, source=source) for label, source in pairs]


@pytest.fixture
def subcomponent_analysis(defaults):
    return SubcomponentCostAnalysisFactory(subcomponent_labels=["A", "B", "C"])


def add_row(subcomponent_analysis, allocations, skipped=False, analysis_cost_type=None):
    analysis = subcomponent_analysis.analysis
    config = CostLineItemConfigFactory(
        cost_line_item=CostLineItemFactory(analysis=analysis),
        analysis_cost_type=analysis_cost_type,
    )
    CostLineItemInterventionAllocationFactory(
        cli_config=config,
        intervention_instance=subcomponent_analysis.intervention_instance,
        allocation=Decimal("100"),
    )
    return SubcomponentCostAllocationFactory(
        subcomponent_analysis=subcomponent_analysis,
        cli_config=config,
        allocations=allocations,
        skipped=skipped,
    )


class TestRemapAllocations:
    def test_reorder_moves_each_value_with_its_component(self):
        assert remap_allocations({"0": "20", "1": "30", "2": "50"}, [2, 0, 1]) == {
            "0": "50",
            "1": "20",
            "2": "30",
        }

    @pytest.mark.parametrize(
        "sources, expected",
        [
            ([1, 2], {"0": "30", "1": "50"}),  # remove first
            ([0, 2], {"0": "20", "1": "50"}),  # remove middle
            ([0, 1], {"0": "20", "1": "30"}),  # remove last
        ],
    )
    def test_remove_drops_only_that_component(self, sources, expected):
        assert remap_allocations({"0": "20", "1": "30", "2": "50"}, sources) == expected

    def test_new_component_is_left_blank(self):
        assert remap_allocations({"0": "60", "1": "40"}, [0, 1, None]) == {"0": "60", "1": "40"}

    def test_partial_row_stays_partial(self):
        assert remap_allocations({"0": "50"}, [1, 0]) == {"1": "50"}

    def test_empty_and_null_rows_stay_empty(self):
        assert remap_allocations({}, [1, 0]) == {}
        assert remap_allocations(None, [1, 0]) == {}

    def test_number_values_are_written_as_strings(self):
        assert remap_allocations({"0": 50.0, "1": 50}, [0, 1]) == {"0": "50", "1": "50"}
        assert remap_allocations({"0": 33.5}, [0]) == {"0": "33.5"}


class TestValidateSources:
    def test_accepts_unique_in_range_positions_and_new_components(self):
        validate_sources([2, None, 0], existing_count=3)

    @pytest.mark.parametrize("sources", [[0, 0], [3], [-1], ["0"], [1.5]])
    def test_rejects_duplicate_or_invalid_positions(self, sources):
        with pytest.raises(ValidationError):
            validate_sources(sources, existing_count=3)


@pytest.mark.django_db
class TestUpdateSubcomponentLabels:
    def test_reorder_keeps_percentages_with_their_components(self, subcomponent_analysis):
        row = add_row(subcomponent_analysis, {"0": "20", "1": "30", "2": "50"})

        update_subcomponent_labels(subcomponent_analysis, components(("C", 2), ("A", 0), ("B", 1)))

        subcomponent_analysis.refresh_from_db()
        row.refresh_from_db()
        assert subcomponent_analysis.subcomponent_labels == ["C", "A", "B"]
        assert row.allocations == {"0": "50", "1": "20", "2": "30"}

    def test_rename_and_reorder_in_one_save(self, subcomponent_analysis):
        row = add_row(subcomponent_analysis, {"0": "20", "1": "30", "2": "50"})

        update_subcomponent_labels(
            subcomponent_analysis, components(("B renamed", 1), ("A", 0), ("C renamed", 2))
        )

        subcomponent_analysis.refresh_from_db()
        row.refresh_from_db()
        assert subcomponent_analysis.subcomponent_labels == ["B renamed", "A", "C renamed"]
        assert row.allocations == {"0": "30", "1": "20", "2": "50"}

    def test_remove_then_add_same_name_starts_blank(self, subcomponent_analysis):
        row = add_row(subcomponent_analysis, {"0": "20", "1": "30", "2": "50"})

        update_subcomponent_labels(subcomponent_analysis, components(("A", 0), ("C", 2), ("B", None)))

        subcomponent_analysis.refresh_from_db()
        row.refresh_from_db()
        assert subcomponent_analysis.subcomponent_labels == ["A", "C", "B"]
        assert row.allocations == {"0": "20", "1": "50"}

    def test_skipped_and_partial_rows_are_preserved(self, subcomponent_analysis):
        skipped = add_row(subcomponent_analysis, {}, skipped=True)
        partial = add_row(subcomponent_analysis, {"2": "40"})

        update_subcomponent_labels(subcomponent_analysis, components(("C", 2), ("A", 0), ("B", 1)))

        skipped.refresh_from_db()
        partial.refresh_from_db()
        assert skipped.skipped and skipped.allocations == {}
        assert not partial.skipped and partial.allocations == {"0": "40"}

    def test_in_kind_rows_are_remapped_too(self, subcomponent_analysis):
        subcomponent_analysis.analysis.in_kind_contributions = True
        subcomponent_analysis.analysis.save()
        row = add_row(
            subcomponent_analysis,
            {"0": "20", "1": "30", "2": "50"},
            analysis_cost_type=AnalysisCostType.IN_KIND,
        )

        update_subcomponent_labels(subcomponent_analysis, components(("B", 1), ("C", 2)))

        row.refresh_from_db()
        assert row.allocations == {"0": "30", "1": "50"}

    def test_other_interventions_rows_are_untouched(self, subcomponent_analysis):
        analysis = subcomponent_analysis.analysis
        other = SubcomponentCostAnalysisFactory(
            intervention_instance=InterventionInstanceFactory(analysis=analysis),
            subcomponent_labels=["A", "B", "C"],
        )
        config = CostLineItemConfigFactory(cost_line_item=CostLineItemFactory(analysis=analysis))
        for instance in (subcomponent_analysis.intervention_instance, other.intervention_instance):
            CostLineItemInterventionAllocationFactory(
                cli_config=config, intervention_instance=instance, allocation=Decimal("50")
            )
        mine = SubcomponentCostAllocationFactory(
            subcomponent_analysis=subcomponent_analysis, cli_config=config, allocations={"0": "100"}
        )
        theirs = SubcomponentCostAllocationFactory(
            subcomponent_analysis=other, cli_config=config, allocations={"0": "100"}
        )

        update_subcomponent_labels(subcomponent_analysis, components(("B", 1), ("A", 0), ("C", 2)))

        mine.refresh_from_db()
        theirs.refresh_from_db()
        other.refresh_from_db()
        assert mine.allocations == {"1": "100"}
        assert theirs.allocations == {"0": "100"}
        assert other.subcomponent_labels == ["A", "B", "C"]

    def test_rows_holding_json_numbers_are_saved_as_strings(self, subcomponent_analysis):
        # Production data stores some values as JSON numbers; QuerySet.update bypasses the
        # field's type check, which is how they got there.
        row = add_row(subcomponent_analysis, {"0": "20", "1": "30", "2": "50"})
        SubcomponentCostAllocation.objects.filter(pk=row.pk).update(
            allocations={"0": 20.0, "1": 30.0, "2": 50.0}
        )

        update_subcomponent_labels(subcomponent_analysis, components(("A", 0), ("B", 1), ("C", 2)))

        row.refresh_from_db()
        assert row.allocations == {"0": "20", "1": "30", "2": "50"}

    def test_duplicate_existing_labels_are_told_apart_by_position(self, defaults):
        subcomponent_analysis = SubcomponentCostAnalysisFactory(subcomponent_labels=["test", "test"])
        row = add_row(subcomponent_analysis, {"0": "25", "1": "75"})

        update_subcomponent_labels(
            subcomponent_analysis,
            components(
                ("test", 1),
            ),
        )

        subcomponent_analysis.refresh_from_db()
        row.refresh_from_db()
        assert subcomponent_analysis.subcomponent_labels == ["test"]
        assert row.allocations == {"0": "75"}

    def test_invalid_sources_write_nothing(self, subcomponent_analysis):
        row = add_row(subcomponent_analysis, {"0": "20", "1": "30", "2": "50"})

        with pytest.raises(ValidationError):
            update_subcomponent_labels(subcomponent_analysis, components(("A", 0), ("A again", 0)))

        subcomponent_analysis.refresh_from_db()
        row.refresh_from_db()
        assert subcomponent_analysis.subcomponent_labels == ["A", "B", "C"]
        assert row.allocations == {"0": "20", "1": "30", "2": "50"}

    def test_creates_the_analysis_when_missing(self, defaults):
        instance = InterventionInstanceFactory()

        update_subcomponent_labels(None, components(("X", None), ("Y", None)), intervention_instance=instance)

        assert SubcomponentCostAnalysis.objects.get(intervention_instance=instance).subcomponent_labels == [
            "X",
            "Y",
        ]
