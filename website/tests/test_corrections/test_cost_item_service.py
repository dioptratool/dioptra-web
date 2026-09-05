"""
Feature 91 -- budget cost-item correction service (spec section 6).
"""

from decimal import Decimal

import pytest

from website.corrections import (
    CorrectionError,
    CorrectionPatch,
    apply_cost_item_correction,
    plan_cost_item_correction,
)
from website.models import CostLineItem, CostType
from website.models.cost_type import Support
from website.tests.factories import (
    AnalysisFactory,
    CategoryFactory,
    CostLineItemConfigFactory,
    CostLineItemFactory,
    CostLineItemInterventionAllocationFactory,
    CountryFactory,
    InterventionFactory,
    TransactionFactory,
)

ROW_DEFAULTS = dict(
    country_code="JO",
    grant_code="G1",
    budget_line_code="BL1",
    account_code="4100",
    site_code="S1",
    sector_code="SEC",
    budget_line_description="Salaries",
)


def row(analysis, amount="100", **overrides):
    values = {**ROW_DEFAULTS, **overrides}
    return CostLineItemFactory(analysis=analysis, total_cost=Decimal(amount), **values)


def categorize(analysis):
    analysis.auto_categorize_cost_line_items()
    analysis.ensure_cost_type_category_objects()


def correct(analysis, rows, **patch_kwargs):
    plan = plan_cost_item_correction(analysis, [r.id for r in rows], CorrectionPatch(**patch_kwargs))
    return plan, apply_cost_item_correction(plan)


@pytest.fixture
def analysis(defaults):
    analysis = AnalysisFactory(country=CountryFactory(name="Jordan", code="JO"), grants="G1,G2")
    analysis.add_intervention(
        InterventionFactory(output_metrics=["NumberOfTeacherDaysOfTraining"]),
        parameters={"number_of_teachers": 1, "number_of_days_of_training": 1},
    )
    return analysis


@pytest.mark.django_db
class TestDirectEdit:
    def test_every_supplied_field_is_written_and_blank_fields_left_alone(self, analysis):
        r1 = row(analysis, dummy_field_1="keep")
        r2 = row(analysis, site_code="S2", dummy_field_1="keep")
        categorize(analysis)

        plan, result = correct(
            analysis,
            [r1, r2],
            grant_code="G2",
            sector_code="NEW",
            account_code="9999",
            description="Renamed",
            amount=Decimal("12.3456"),
            custom_fields={"dummy_field_3": "CC-3"},
        )

        for each in (r1, r2):
            each.refresh_from_db()
            assert each.grant_code == "G2"
            assert each.sector_code == "NEW"
            assert each.account_code == "9999"
            assert each.budget_line_description == "Renamed"
            assert each.total_cost == Decimal("12.3456")
            assert each.dummy_field_3 == "CC-3"
            assert each.dummy_field_1 == "keep"  # not supplied: unchanged
        r2.refresh_from_db()
        assert r2.site_code == "S2"  # not supplied: unchanged
        assert result.record_count == 2
        assert result.changed_fields == [
            "description",
            "grant_code",
            "sector_code",
            "account_code",
            "amount",
            "dummy_field_3",
        ]
        assert not result.structural
        assert result.regrouped_count == 0
        assert result.cleared_count == 0
        # The per-grant Allocate bookkeeping followed the grant change.
        assert set(analysis.cost_type_category_grants.values_list("grant", flat=True)) == {"G2"}

    def test_rows_whose_fields_become_equal_stay_separate(self, analysis):
        r1 = row(analysis)
        r2 = row(analysis, site_code="S2")
        categorize(analysis)

        correct(analysis, [r2], site_code="S1")

        assert analysis.cost_line_items.count() == 2
        assert CostLineItem.objects.filter(id__in=[r1.id, r2.id]).count() == 2

    def test_a_prefilled_value_saved_unchanged_is_a_no_op(self, analysis):
        r1 = row(analysis)
        categorize(analysis)

        plan, result = correct(analysis, [r1], site_code="S1", amount=Decimal("100"), description="Salaries")

        assert result.changed_fields == []

    def test_transaction_only_fields_are_ignored(self, analysis):
        r1 = row(analysis)
        categorize(analysis)

        plan, result = correct(
            analysis, [r1], transaction_description="ignored", date=analysis.start_date, site_code="S3"
        )

        assert result.changed_fields == ["site_code"]

    def test_allocations_survive_a_direct_edit(self, analysis):
        r1 = row(analysis)
        categorize(analysis)
        for instance in analysis.interventioninstance_set.all():
            CostLineItemInterventionAllocationFactory(
                cli_config=r1.config, intervention_instance=instance, allocation=Decimal("55")
            )

        correct(analysis, [r1], amount=Decimal("500"), grant_code="G2")

        assert list(r1.config.allocations.values_list("allocation", flat=True)) == [Decimal("55")]


@pytest.mark.django_db
class TestCategorization:
    def test_cost_type_change_unconfirms_only_the_destination_combination(self, analysis):
        r1 = row(analysis)
        r2 = row(analysis, site_code="S2")
        categorize(analysis)
        analysis.cost_type_categories.update(confirmed=True)
        support = CostType.objects.get(type=Support.id)
        category_id = r1.config.category_id
        program_id = r1.config.cost_type_id

        plan, result = correct(analysis, [r1], cost_type=support)

        r1.refresh_from_db()
        assert r1.config.cost_type == support
        assert plan.unconfirm_combinations == {(support.id, category_id)}
        assert analysis.cost_type_categories.get(cost_type=support).confirmed is False
        assert analysis.cost_type_categories.get(cost_type_id=program_id).confirmed is True
        assert result.changed_fields == ["cost_type"]

    def test_moving_the_last_row_out_removes_the_emptied_combination(self, analysis):
        r1 = row(analysis)
        categorize(analysis)
        support = CostType.objects.get(type=Support.id)
        other = CategoryFactory()

        correct(analysis, [r1], cost_type=support, category=other)

        combos = list(analysis.cost_type_categories.values_list("cost_type_id", "category_id", "confirmed"))
        assert combos == [(support.id, other.id, False)]

    def test_edits_within_the_same_combination_never_change_confirmation(self, analysis):
        r1 = row(analysis)
        categorize(analysis)
        analysis.cost_type_categories.update(confirmed=True)

        plan, _result = correct(analysis, [r1], site_code="S7", grant_code="G2", amount=Decimal("1"))

        assert plan.unconfirm_combinations == set()
        assert list(analysis.cost_type_categories.values_list("confirmed", flat=True)) == [True]

    def test_category_supplied_unchanged_does_not_unconfirm(self, analysis):
        r1 = row(analysis)
        categorize(analysis)
        analysis.cost_type_categories.update(confirmed=True)

        plan, result = correct(analysis, [r1], category=r1.config.category, cost_type=r1.config.cost_type)

        assert plan.unconfirm_combinations == set()
        assert result.changed_fields == []
        assert list(analysis.cost_type_categories.values_list("confirmed", flat=True)) == [True]


@pytest.mark.django_db
class TestScope:
    def test_transaction_derived_cost_items_are_refused(self, analysis):
        r1 = row(analysis)
        categorize(analysis)
        TransactionFactory(analysis=analysis, cost_line_item=r1, **{k: v for k, v in ROW_DEFAULTS.items()})

        with pytest.raises(CorrectionError, match="through their transactions"):
            plan_cost_item_correction(analysis, [r1.id], CorrectionPatch(site_code="S2"))

        r1.refresh_from_db()
        assert r1.site_code == "S1"

    def test_out_of_scope_rows_are_dropped(self, analysis):
        r1 = row(analysis)
        categorize(analysis)
        foreign = row(AnalysisFactory(country=analysis.country, grants="G1"))
        lump = CostLineItemFactory(analysis=analysis, is_special_lump_sum=True, grant_code="G1")
        CostLineItemConfigFactory(cost_line_item=lump, cost_type=None, category=None)

        plan, result = correct(analysis, [r1, foreign, lump], site_code="S5")

        assert [c.id for c in plan.cost_line_items] == [r1.id]
        assert result.record_count == 1
        foreign.refresh_from_db()
        lump.refresh_from_db()
        assert foreign.site_code == "S1"
        assert lump.site_code == ""

    def test_nothing_in_scope_is_an_error(self, analysis):
        foreign = row(AnalysisFactory(country=analysis.country, grants="G1"))

        with pytest.raises(CorrectionError):
            plan_cost_item_correction(analysis, [foreign.id], CorrectionPatch(site_code="S5"))
