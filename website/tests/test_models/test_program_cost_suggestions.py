from decimal import Decimal
from types import SimpleNamespace

import pytest

from website.models import CostType
from website.models.cost_type import ProgramCost, Support
from website.tests.factories import (
    AnalysisFactory,
    CategoryFactory,
    CostLineItemInterventionAllocationFactory,
    InterventionInstanceFactory,
)


pytestmark = pytest.mark.django_db


@pytest.fixture
def calculator(make_program_cost_item):
    """Build a Program Cost grant/category with saved peer rows and a blank target item.

    ``rows`` are ``(amount, allocations)`` pairs saved before the target. The returned
    namespace exposes ``make_item`` (same grant/category/analysis unless overridden) and
    ``suggest(*items)``, which suggests for the given items or for the target by default.
    """

    def build(rows, n=3):
        analysis = AnalysisFactory(grants="G1,G2")
        interventions = [InterventionInstanceFactory(analysis=analysis) for _ in range(n)]
        category = CategoryFactory()
        program = CostType.objects.get(type=ProgramCost.id)

        def make_item(
            amount, allocations=(), *, analysis=analysis, grant="G1", category=category, cost_type=program
        ):
            return make_program_cost_item(
                analysis,
                amount,
                allocations,
                interventions=interventions,
                grant=grant,
                category=category,
                cost_type=cost_type,
            )

        for amount, allocations in rows:
            make_item(amount, allocations)
        target = make_item(200000)
        analysis.ensure_cost_type_category_objects()
        group = analysis.cost_type_category_grants.get(
            grant="G1", cost_type_category__category=category, cost_type_category__cost_type=program
        )

        def suggest(*selected):
            return group.program_cost_suggestion(
                excluded_config_ids=[item.config.pk for item in selected or (target,)]
            )

        return SimpleNamespace(
            analysis=analysis,
            interventions=interventions,
            target=target,
            make_item=make_item,
            suggest=suggest,
        )

    return build


@pytest.mark.parametrize(
    "rows, expected",
    [
        ([(100, [100, 0, 0]), (1000, [0, 100, 0])], ["9.09", "90.91", "0.00"]),
        ([(100, [100, 0, 0]), (1000, [0, 100, 0]), (1000, [25, 50, 25])], ["16.67", "71.43", "11.90"]),
        ([(100, [0, 0, 0]), (1000, [0, 0, 0])], ["0.00", "0.00", "0.00"]),
        ([(100, [50, 25, 0])], ["50.00", "25.00", "0.00"]),
        ([(100, [100, None, None]), (1000, [0, 100, 0])], ["9.09", "90.91", "0.00"]),
        ([(100, [100]), (100000, []), (100000, [None, None, None])], ["100.00", "0.00", "0.00"]),
        ([(100, [100]), (100000, [None, None, None]), (100, [0, None, None])], ["50.00", "0.00", "0.00"]),
        ([(100, [100, 0, 0]), (-20, [100, 0, 0])], ["100.00", "0.00", "0.00"]),
        ([(-100, [100, 0, 0]), (-300, [0, 100, 0])], ["25.00", "75.00", "0.00"]),
        ([(100, [100, 0, 0]), (100, [0, 100, 0]), (100, [0, 0, 100])], ["33.33", "33.33", "33.33"]),
        ([(1000000, [100, 0, 0]), (1, [0, 100, 0])], ["100.00", "0.00", "0.00"]),
        ([(100, [1.005, 0, 0])], ["1.01", "0.00", "0.00"]),
        ([(0, [100, 0, 0]), (100, [0, 100, 0])], ["0.00", "100.00", "0.00"]),
    ],
    ids=[
        "simple",
        "unequal-weights",
        "explicit-zero",
        "partial",
        "partial-blanks",
        "wholly-blank",
        "entered-zero-and-blanks",
        "valid-refund",
        "negative-denominator-valid",
        "thirds",
        "tiny-share",
        "half-up-rounding",
        "zero-dollar-peer",
    ],
)
def test_weighted_percentages(calculator, rows, expected):
    case = calculator(rows)
    result = case.suggest()
    assert result["allocations"] == dict(zip([i.pk for i in case.interventions], expected))
    assert result["warning"] is None


def test_scope_and_per_intervention_amounts(calculator):
    case = calculator([(100, [100, 0, 0]), (1000, [0, 100, 0])])
    case.make_item(900000, [0, 0, 100], grant="G2")
    case.make_item(900000, [0, 0, 100], category=CategoryFactory())
    case.make_item(900000, [0, 0, 100], cost_type=CostType.objects.get(type=Support.id))
    case.make_item(900000, [0, 0, 100], analysis=AnalysisFactory())
    result = case.suggest()
    assert result["denominator"] == 1100
    assert result["numerators"] == dict(zip([i.pk for i in case.interventions], [100, 1000, 0]))
    assert list(result["allocations"].values()) == ["9.09", "90.91", "0.00"]
    case.target.total_cost = Decimal(200000000)
    case.target.save()
    assert case.suggest() == result


def test_excludes_all_selected_saved_allocations(calculator):
    case = calculator([(100, [100, 0, 0]), (1000, [0, 100, 0])])
    x = case.make_item(200000, [100, 0, 0])
    y = case.make_item(50000, [0, 100, 0])
    result = case.suggest(x, y)
    assert result["denominator"] == 1100
    assert list(result["allocations"].values()) == ["9.09", "90.91", "0.00"]
    assert list(case.suggest(x)["allocations"].values()) == ["0.20", "99.80", "0.00"]
    assert list(case.suggest(y)["allocations"].values()) == ["99.50", "0.50", "0.00"]


@pytest.mark.parametrize("invalid", [[70, 50, 0], [-1, 50, 0], [101, 0, 0]])
def test_excludes_entire_invalid_row(calculator, invalid):
    case = calculator([(100, [100, 0, 0]), (1000000, invalid)])
    result = case.suggest()
    assert result["denominator"] == 100
    assert list(result["allocations"].values()) == ["100.00", "0.00", "0.00"]


def test_allocation_to_another_analysis_intervention_is_ignored(calculator):
    # The application never writes such a row; if one exists the rest of the item still counts.
    case = calculator([(100, [100, 0, 0])])
    item = case.make_item(300, [0, 100, 0])
    CostLineItemInterventionAllocationFactory(
        cli_config=item.config, intervention_instance=InterventionInstanceFactory(), allocation=100
    )
    result = case.suggest()
    assert result["denominator"] == 400
    assert list(result["allocations"].values()) == ["25.00", "75.00", "0.00"]


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [(100, [])],
        [(100, [None, None, None])],
        [(0, [100, 0, 0])],
        [(100, [100, 0, 0]), (-100, [0, 100, 0])],
        [(100, [70, 50, 0])],
    ],
    ids=[
        "no-peers",
        "missing-allocations",
        "null-allocations",
        "zero-cost",
        "refund-cancellation",
        "invalid-only",
    ],
)
def test_zero_denominator_does_not_fall_back(calculator, rows):
    case = calculator(rows)
    case.make_item(1000, [0, 100, 0], category=CategoryFactory())
    case.make_item(1000, [0, 100, 0], grant="G2")
    result = case.suggest()
    assert result["denominator"] == 0
    assert result["allocations"] is None
    assert result["warning"] is None


@pytest.mark.parametrize("refund", [-20, "-99.99", -200, "-0.01"])
def test_negative_percentage_warns_before_rounding(calculator, refund):
    case = calculator([(100, [100, 0, 0]), (refund, [0, 100, 0])])
    result = case.suggest()
    assert result["allocations"] is None
    assert result["warning"] == (
        "Due to the refund allocations the application was unable to produce a suggested allocation"
    )


def test_tiny_negative_that_would_round_to_zero_is_unavailable(calculator):
    case = calculator([(1000000, [100, 0, 0]), ("-0.01", [0, 100, 0])])
    assert case.suggest()["allocations"] is None
    assert case.suggest()["warning"]


def test_true_overallocation_is_not_corrected_as_rounding(calculator):
    # Both rows are valid. A partially allocated refund yields 125% / 0% / 0%.
    case = calculator([(100, [100, 0, 0]), (-20, [0, 0, 0])])
    assert case.suggest()["allocations"] is None


@pytest.mark.parametrize("with_zero", [False, True])
def test_rounding_overflow_reduces_positive_allocations_only(calculator, with_zero):
    if with_zero:
        rows = [(100, [100, 0, 0, 0]), (100, [0, 100, 0, 0]), (400, [0, 0, 100, 0])]
        expected = ["16.66", "16.66", "66.66", "0.00"]
        total = Decimal("99.98")
    else:
        rows = [(100, [100 if i == j else 0 for j in range(6)]) for i in range(6)]
        expected = ["16.66"] * 6
        total = Decimal("99.96")
    case = calculator(rows, n=len(expected))
    allocations = list(case.suggest()["allocations"].values())
    assert allocations == expected
    assert sum(map(Decimal, allocations)) == total


def test_new_intervention_receives_zero(calculator):
    case = calculator([(100, [100, 0, 0])])
    new = InterventionInstanceFactory(analysis=case.analysis)
    assert case.suggest()["allocations"][new.pk] == "0.00"


def test_program_calculator_rejects_support_category(calculator):
    case = calculator([])
    support = CostType.objects.get(type=Support.id)
    case.make_item(100, [100, 0, 0], cost_type=support)
    case.analysis.ensure_cost_type_category_objects()
    group = case.analysis.cost_type_category_grants.get(cost_type_category__cost_type=support)
    with pytest.raises(ValueError, match="Program Cost"):
        group.program_cost_suggestion(excluded_config_ids=[])
