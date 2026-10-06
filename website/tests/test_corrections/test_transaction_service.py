"""
Feature 91 -- transaction correction service (spec sections 7-10).

Analyses are built the way Load Data builds them: transactions are inserted and grouped into cost
items by ``create_cost_line_items_from_transactions``, then auto-categorised and given their
Cost Type / Category bookkeeping objects. Nothing is mocked.
"""

from decimal import Decimal

import pytest
from django.conf import settings as django_settings

from website.corrections import (
    CorrectionError,
    CorrectionPatch,
    apply_transaction_correction,
    plan_transaction_correction,
)
from website.corrections.transactions import CREATE, MERGE, MOVE, UNCHANGED
from website.models import (
    Category,
    CostLineItem,
    CostLineItemConfig,
    CostLineItemInterventionAllocation,
    CostType,
    Transaction,
)
from website.models.cost_type import Support
from website.models.subcomponent import SubcomponentCostAllocation
from website.tests.factories import (
    AnalysisFactory,
    CategoryFactory,
    CostLineItemConfigFactory,
    CostLineItemFactory,
    CostLineItemInterventionAllocationFactory,
    SubcomponentCostAllocationFactory,
    SubcomponentCostAnalysisFactory,
    TransactionFactory,
)
from .helpers import (
    TX_DEFAULTS,
    allocate,
    allocations_of,
    group,
    item_defaults,
    item_for,
    make_analysis,
    tx,
)


def correct(analysis, transactions, **patch_kwargs):
    plan = plan_transaction_correction(
        analysis, [t.id for t in transactions], CorrectionPatch(**patch_kwargs)
    )
    return plan, apply_transaction_correction(plan)


@pytest.fixture
def analysis(defaults):
    return make_analysis()


@pytest.mark.django_db
class TestNonStructuralEdits:
    def test_amount_edit_recomputes_the_total_and_keeps_allocations(self, analysis):
        t1, t2 = tx(analysis), tx(analysis)
        group(analysis)
        item = item_for(analysis, site_code="S1")
        allocate(item, "40")

        plan, result = correct(analysis, [t1], amount=Decimal("250.5"))

        t1.refresh_from_db()
        item.refresh_from_db()
        assert t1.amount_in_instance_currency == Decimal("250.5")
        assert t1.amount_in_source_currency == Decimal("250.5")
        assert item.total_cost == Decimal("350.5")
        assert allocations_of(item) == [Decimal("40")]
        assert not plan.is_structural
        assert not plan.needs_allocation_warning
        assert plan.destinations[0].outcome == UNCHANGED
        assert result.changed_fields == ["amount"]
        assert result.regrouped_count == 0
        assert result.cleared_count == 0
        assert analysis.cost_line_items.count() == 1

    def test_zero_and_negative_amounts_are_allowed(self, analysis):
        t1, t2 = tx(analysis), tx(analysis)
        group(analysis)

        correct(analysis, [t1], amount=Decimal("-100"))
        correct(analysis, [t2], amount=Decimal("0"))

        item = item_for(analysis, site_code="S1")
        assert item.total_cost == Decimal("-100")
        assert item.transactions.count() == 2

    def test_date_description_and_custom_fields_are_patched_in_place(self, analysis):
        t1, t2 = tx(analysis), tx(analysis)
        group(analysis)
        item = item_for(analysis, site_code="S1")

        plan, result = correct(
            analysis,
            [t1, t2],
            date=analysis.start_date,
            transaction_description="Corrected payroll",
            custom_fields={"dummy_field_2": "CC-9"},
        )

        for each in (t1, t2):
            each.refresh_from_db()
            assert each.date == analysis.start_date
            assert each.transaction_description == "Corrected payroll"
            assert each.dummy_field_2 == "CC-9"
            assert each.cost_line_item_id == item.id
        assert result.changed_fields == ["transaction_description", "date", "dummy_field_2"]
        assert not plan.is_structural

    def test_a_prefilled_value_saved_unchanged_is_a_no_op(self, analysis):
        t1 = tx(analysis)
        group(analysis)

        plan, result = correct(analysis, [t1], site_code="S1", grant_code="G1", amount=Decimal("100"))

        assert result.changed_fields == []
        assert plan.destinations[0].outcome == UNCHANGED
        assert analysis.cost_line_items.count() == 1

    def test_blank_patch_changes_nothing(self, analysis):
        t1 = tx(analysis)
        group(analysis)
        item = item_for(analysis, site_code="S1")

        plan, result = correct(analysis, [t1])

        item.refresh_from_db()
        assert item.total_cost == Decimal("100")
        assert result.changed_fields == []
        assert result.record_count == 1

    def test_explicit_description_replaces_the_destination_and_its_transactions(self, analysis):
        t1, t2 = tx(analysis), tx(analysis)
        group(analysis)
        item = item_for(analysis, site_code="S1")

        # Edit Cost Item on a transaction-based analysis: every transaction of the item is selected.
        correct(analysis, [t1, t2], description="Staff salaries")

        item.refresh_from_db()
        assert item.budget_line_description == "Staff salaries"
        assert set(item.transactions.values_list("budget_line_description", flat=True)) == {"Staff salaries"}

    def test_description_from_a_partial_selection_applies_to_the_whole_item(self, analysis):
        # Budget Line Description on a transaction panel is the cost item's description: entering
        # it for one of three transactions renames the item and every transaction in it.
        t1, t2, t3 = tx(analysis), tx(analysis), tx(analysis)
        group(analysis)
        item = item_for(analysis, site_code="S1")

        plan, result = correct(analysis, [t1], description="Renamed")

        assert plan.destinations[0].outcome == UNCHANGED
        assert not plan.is_structural
        assert result.changed_fields == ["description"]
        item.refresh_from_db()
        assert item.budget_line_description == "Renamed"
        assert set(item.transactions.values_list("budget_line_description", flat=True)) == {"Renamed"}
        assert item.transactions.count() == 3


@pytest.mark.django_db
class TestOneToOneMove:
    def test_moving_all_transactions_to_an_unused_identity_keeps_the_row_and_allocations(self, analysis):
        t1, t2 = tx(analysis), tx(analysis)
        group(analysis)
        item = item_for(analysis, site_code="S1")
        item.note = "kept"
        item.save()
        allocate(item, "40")

        plan, result = correct(analysis, [t1, t2], grant_code="G2", site_code="S9")

        assert plan.destinations[0].outcome == MOVE
        assert not plan.is_structural
        assert not plan.needs_allocation_warning
        item.refresh_from_db()
        assert item.grant_code == "G2"
        assert item.site_code == "S9"
        assert item.note == "kept"
        assert allocations_of(item) == [Decimal("40")]
        assert set(item.transactions.values_list("site_code", flat=True)) == {"S9"}
        assert set(item.transactions.values_list("grant_code", flat=True)) == {"G2"}
        assert analysis.cost_line_items.count() == 1
        assert result.existing_count == 1
        assert result.created_count == 0
        assert result.cleared_count == 0
        assert result.changed_fields == ["grant_code", "site_code"]
        # The per-grant Allocate bookkeeping followed the move.
        assert set(analysis.cost_type_category_grants.values_list("grant", flat=True)) == {"G2"}

    def test_cost_type_change_on_a_whole_item_moves_it_and_unconfirms_only_the_destination(self, analysis):
        t1, t2 = tx(analysis), tx(analysis)
        t3 = tx(analysis, site_code="S2")
        group(analysis)
        analysis.cost_type_categories.update(confirmed=True)
        item = item_for(analysis, site_code="S1")
        other = item_for(analysis, site_code="S2")
        support = CostType.objects.get(type=Support.id)
        original = (item.config.cost_type_id, item.config.category_id)

        plan, result = correct(analysis, [t1, t2], cost_type=support)

        item.refresh_from_db()
        assert item.config.cost_type == support
        assert plan.destinations[0].outcome == MOVE
        assert plan.unconfirm_combinations == {(support.id, original[1])}
        destination_combo = analysis.cost_type_categories.get(cost_type=support, category_id=original[1])
        assert destination_combo.confirmed is False
        source_combo = analysis.cost_type_categories.get(cost_type_id=original[0], category_id=original[1])
        assert source_combo.confirmed is True  # ``other`` still lives there
        assert result.changed_fields == ["cost_type"]

    def test_regrouping_within_the_same_combination_never_changes_confirmation(self, analysis):
        t1 = tx(analysis)
        t2 = tx(analysis, site_code="S2")
        group(analysis)
        analysis.cost_type_categories.update(confirmed=True)

        plan, _result = correct(analysis, [t1], site_code="S2")

        assert plan.unconfirm_combinations == set()
        assert list(analysis.cost_type_categories.values_list("confirmed", flat=True)) == [True]


@pytest.mark.django_db
class TestSplits:
    def test_part_of_a_source_moving_to_a_new_destination_clears_the_source(self, analysis):
        t1, t2 = tx(analysis), tx(analysis)
        group(analysis)
        source = item_for(analysis, site_code="S1")
        source.note = "from source"
        source.save()
        allocate(source, "40")

        plan = plan_transaction_correction(analysis, [t2.id], CorrectionPatch(site_code="S2"))
        assert plan.is_structural
        assert plan.needs_allocation_warning
        assert plan.split_source_ids == {source.id}
        assert plan.affected_config_ids == {source.config.id}
        assert plan.destinations[0].outcome == CREATE

        result = apply_transaction_correction(plan)

        source.refresh_from_db()
        assert source.total_cost == Decimal("100")
        assert source.transactions.count() == 1
        assert allocations_of(source) == []
        created = item_for(analysis, site_code="S2")
        assert created.transactions.count() == 1
        assert created.total_cost == Decimal("100")
        assert created.budget_line_description == "Salaries"  # inherited
        assert created.note == "from source"  # inherited
        assert created.config.cost_type_id == source.config.cost_type_id
        assert created.config.category_id == source.config.category_id
        assert allocations_of(created) == []
        assert result.created_count == 1
        assert result.cleared_count == 1
        assert result.removed_count == 0
        assert result.structural

    def test_part_of_a_source_moving_into_an_existing_destination_clears_both(self, analysis):
        t1, t2 = tx(analysis), tx(analysis)
        t3 = tx(analysis, site_code="S2")
        group(analysis)
        source = item_for(analysis, site_code="S1")
        destination = item_for(analysis, site_code="S2")
        source.note = "source note"
        source.save()
        destination.note = "destination note"
        destination.save()
        allocate(source, "40")
        allocate(destination, "60")

        plan, result = correct(analysis, [t2], site_code="S2")

        assert plan.destinations[0].outcome == MERGE
        assert plan.affected_config_ids == {source.config.id, destination.config.id}
        source.refresh_from_db()
        destination.refresh_from_db()
        assert source.transactions.count() == 1
        assert destination.transactions.count() == 2
        assert destination.total_cost == Decimal("200")
        assert allocations_of(source) == []
        assert allocations_of(destination) == []
        assert destination.note == "destination note\nsource note"
        assert source.note == "source note"
        assert result.existing_count == 1
        assert result.cleared_count == 2

    def test_no_warning_when_the_affected_items_carry_no_allocation_data(self, analysis):
        t1, t2 = tx(analysis), tx(analysis)
        group(analysis)
        source = item_for(analysis, site_code="S1")
        # A null percentage and an all-blank sub-component row are not allocation data ...
        for instance in analysis.interventioninstance_set.all():
            CostLineItemInterventionAllocationFactory(
                cli_config=source.config, intervention_instance=instance, allocation=None
            )
        subcomponent_analysis = SubcomponentCostAnalysisFactory(analysis=analysis)
        SubcomponentCostAllocationFactory(
            subcomponent_analysis=subcomponent_analysis, cli_config=source.config, allocations={}
        )

        plan, result = correct(analysis, [t2], site_code="S2")

        assert plan.is_structural
        assert not plan.needs_allocation_warning
        # ... but clearing still removes every allocation row of the affected item.
        assert not CostLineItemInterventionAllocation.objects.filter(cli_config=source.config).exists()
        assert not SubcomponentCostAllocation.objects.filter(cli_config=source.config).exists()
        assert result.cleared_count == 1

    @pytest.mark.parametrize(
        "row_kwargs",
        [
            {"allocations": {}, "skipped": True},
            {"allocations": {"0": "100"}, "skipped": False},
        ],
    )
    def test_sub_component_rows_count_as_allocation_data(self, analysis, row_kwargs):
        t1, t2 = tx(analysis), tx(analysis)
        group(analysis)
        source = item_for(analysis, site_code="S1")
        SubcomponentCostAllocationFactory(
            subcomponent_analysis=SubcomponentCostAnalysisFactory(analysis=analysis),
            cli_config=source.config,
            **row_kwargs,
        )

        plan = plan_transaction_correction(analysis, [t2.id], CorrectionPatch(site_code="S2"))

        assert plan.needs_allocation_warning

    def test_a_zero_sum_source_is_kept_while_it_has_transactions(self, analysis):
        t1 = tx(analysis, amount="100")
        t2 = tx(analysis, amount="-100")
        t3 = tx(analysis, amount="50")
        group(analysis)
        source = item_for(analysis, site_code="S1")
        assert source.total_cost == Decimal("50")

        correct(analysis, [t3], site_code="S2")

        source.refresh_from_db()
        assert source.total_cost == Decimal("0")
        assert source.transactions.count() == 2


@pytest.mark.django_db
class TestMerges:
    def test_a_whole_source_merging_into_an_existing_destination_removes_the_source(self, analysis):
        t1 = tx(analysis)
        t2 = tx(analysis, site_code="S2")
        group(analysis)
        source = item_for(analysis, site_code="S1")
        destination = item_for(analysis, site_code="S2")
        source.note = "moved"
        source.save()
        destination.note = "kept"
        destination.save()
        allocate(source, "40")
        allocate(destination, "60")

        plan, result = correct(analysis, [t1], site_code="S2")

        assert plan.destinations[0].outcome == MERGE
        assert plan.removed_source_ids == {source.id}
        assert plan.affected_config_ids == {destination.config.id}
        assert not CostLineItem.objects.filter(id=source.id).exists()
        assert not CostLineItemConfig.objects.filter(id=source.config.id).exists()
        destination.refresh_from_db()
        assert destination.transactions.count() == 2
        assert destination.total_cost == Decimal("200")
        assert destination.note == "kept\nmoved"
        assert allocations_of(destination) == []
        assert result.removed_count == 1
        assert result.existing_count == 1
        assert result.cleared_count == 1
        assert analysis.cost_line_items.count() == 1

    def test_identical_notes_are_deduplicated_and_blank_notes_skipped(self, analysis):
        t1 = tx(analysis)
        t2 = tx(analysis, site_code="S2")
        t3 = tx(analysis, site_code="S3")
        group(analysis)
        item_for(analysis, site_code="S1")  # blank note
        s2 = item_for(analysis, site_code="S2")
        s3 = item_for(analysis, site_code="S3")
        s2.note = "same"
        s2.save()
        s3.note = "same"
        s3.save()

        correct(analysis, [t1, t2, t3], site_code="S9")

        created = item_for(analysis, site_code="S9")
        assert created.note == "same"
        assert created.transactions.count() == 3
        assert analysis.cost_line_items.count() == 1

    def test_multiple_sources_combining_into_one_new_destination_start_unallocated(self, analysis):
        t1 = tx(analysis)
        t2 = tx(analysis, site_code="S2")
        group(analysis)
        s1 = item_for(analysis, site_code="S1")
        s2 = item_for(analysis, site_code="S2")
        s1.note = "one"
        s1.save()
        s2.note = "two"
        s2.save()
        allocate(s1, "40")
        allocate(s2, "60")

        plan, result = correct(analysis, [t1, t2], site_code="S3")

        assert plan.destinations[0].outcome == CREATE
        assert plan.destinations[0].sources == [s1, s2]
        # Both sources end up empty, so nothing survives to warn about.
        assert not plan.needs_allocation_warning
        assert plan.removed_source_ids == {s1.id, s2.id}
        created = item_for(analysis, site_code="S3")
        assert created.transactions.count() == 2
        assert created.total_cost == Decimal("200")
        assert created.note == "one\ntwo"
        assert created.budget_line_description == "Salaries"
        assert allocations_of(created) == []
        assert analysis.cost_line_items.count() == 1
        assert result.created_count == 1
        assert result.removed_count == 2

    def test_partial_contributors_to_a_new_destination_are_cleared(self, analysis):
        t1, t1b = tx(analysis), tx(analysis)
        t2, t2b = tx(analysis, site_code="S2"), tx(analysis, site_code="S2")
        group(analysis)
        s1 = item_for(analysis, site_code="S1")
        s2 = item_for(analysis, site_code="S2")
        allocate(s1, "40")
        allocate(s2, "60")

        plan, result = correct(analysis, [t1, t2], site_code="S3")

        assert plan.needs_allocation_warning
        assert plan.affected_config_ids == {s1.config.id, s2.config.id}
        assert allocations_of(s1) == []
        assert allocations_of(s2) == []
        assert item_for(analysis, site_code="S3").transactions.count() == 2
        assert result.cleared_count == 2

    def test_differing_descriptions_leave_the_new_item_untitled(self, analysis):
        # Sources disagree and nothing was entered: the new item is created blank rather than
        # taking whichever description the database returned first; its transactions keep theirs.
        t1 = tx(analysis, budget_line_description="Salaries")
        t2 = tx(analysis, site_code="S2", budget_line_description="Wages")
        group(analysis)

        plan, _result = correct(analysis, [t1, t2], site_code="S3")

        assert not plan.needs_confirmation
        created = item_for(analysis, site_code="S3")
        assert created.budget_line_description == ""
        assert set(created.transactions.values_list("budget_line_description", flat=True)) == {
            "Salaries",
            "Wages",
        }
        assert created.transactions.count() == 2
        assert analysis.cost_line_items.count() == 1

    def test_an_explicit_description_is_used_for_the_new_item(self, analysis):
        t1 = tx(analysis, budget_line_description="Salaries")
        t2 = tx(analysis, site_code="S2", budget_line_description="Wages")
        group(analysis)

        plan, _result = correct(analysis, [t1, t2], site_code="S3", description="Explicit")

        created = item_for(analysis, site_code="S3")
        assert created.budget_line_description == "Explicit"
        assert set(created.transactions.values_list("budget_line_description", flat=True)) == {"Explicit"}

    def test_inherited_description_does_not_rewrite_transactions(self, analysis):
        t1 = tx(analysis, budget_line_description="Salaries")
        t2 = tx(analysis, budget_line_description="Salaries (Q2)")  # same item, drifted text
        group(analysis)

        correct(analysis, [t2], site_code="S3")

        t2.refresh_from_db()
        assert t2.budget_line_description == "Salaries (Q2)"
        assert item_for(analysis, site_code="S3").budget_line_description == "Salaries"

    def test_note_overflow_is_rejected_before_anything_is_written(self, analysis):
        t1 = tx(analysis)
        t2 = tx(analysis, site_code="S2")
        group(analysis)
        s1 = item_for(analysis, site_code="S1")
        s2 = item_for(analysis, site_code="S2")
        s1.note = "a" * 1500
        s1.save()
        s2.note = "b" * 1000
        s2.save()

        with pytest.raises(CorrectionError, match="too long"):
            plan_transaction_correction(analysis, [t1.id], CorrectionPatch(site_code="S2"))

        s1.refresh_from_db()
        s2.refresh_from_db()
        assert s1.transactions.count() == 1
        assert s2.transactions.count() == 1
        assert s2.note == "b" * 1000

    def test_transactions_with_different_effective_categories_get_separate_destinations(self, analysis):
        t1 = tx(analysis)
        t2 = tx(analysis, site_code="S2")
        group(analysis)
        s2 = item_for(analysis, site_code="S2")
        other_category = CategoryFactory()
        s2.config.category = other_category
        s2.config.save()
        analysis.ensure_cost_type_category_objects()

        plan, _result = correct(analysis, [t1, t2], site_code="S3")

        assert len(plan.destinations) == 2
        assert {d.outcome for d in plan.destinations} == {MOVE}
        created = analysis.cost_line_items.filter(site_code="S3").select_related("config")
        assert created.count() == 2
        assert {c.config.category_id for c in created} == {
            Category.get_default().id,
            other_category.id,
        }


@pytest.mark.django_db
class TestDestinationMatching:
    def test_same_raw_key_with_a_different_category_stays_separate(self, analysis):
        t1, t2 = tx(analysis), tx(analysis)
        group(analysis)
        item = item_for(analysis, site_code="S1")
        other_category = CategoryFactory()
        # A sibling with the same raw key but a different category (as a categorisation edit can
        # leave behind).
        sibling = CostLineItemFactory(analysis=analysis, total_cost=Decimal("100"), **item_defaults())
        CostLineItemConfigFactory(cost_line_item=sibling, category=other_category)
        TransactionFactory(
            analysis=analysis,
            cost_line_item=sibling,
            amount_in_instance_currency=Decimal("100"),
            amount_in_source_currency=Decimal("100"),
            **TX_DEFAULTS,
        )

        plan, _result = correct(analysis, [t1], amount=Decimal("5"))
        assert plan.destinations[0].outcome == UNCHANGED
        assert plan.destinations[0].existing == item

        # Changing the category to the sibling's makes them the same identity: merge.
        plan, _result = correct(analysis, [t1, t2], category=other_category)
        assert plan.destinations[0].outcome == MERGE
        assert plan.destinations[0].existing == sibling
        assert not CostLineItem.objects.filter(id=item.id).exists()
        sibling.refresh_from_db()
        assert sibling.transactions.count() == 3

    def test_duplicate_identities_resolve_to_the_lowest_id(self, analysis):
        t1 = tx(analysis)
        group(analysis)
        # Two rows with the same identity as each other (a legacy of raw-key syncing).
        rows = []
        for _ in range(2):
            row = CostLineItemFactory(
                analysis=analysis, total_cost=Decimal("100"), **item_defaults(site_code="S2")
            )
            CostLineItemConfigFactory(cost_line_item=row, category=Category.get_default())
            TransactionFactory(
                analysis=analysis,
                cost_line_item=row,
                amount_in_instance_currency=Decimal("100"),
                amount_in_source_currency=Decimal("100"),
                **{**TX_DEFAULTS, "site_code": "S2"},
            )
            rows.append(row)

        plan, _result = correct(analysis, [t1], site_code="S2")

        assert plan.destinations[0].existing == min(rows, key=lambda r: r.id)
        assert min(rows, key=lambda r: r.id).transactions.count() == 2
        assert max(rows, key=lambda r: r.id).transactions.count() == 1

    def test_a_row_whose_own_identity_still_matches_stays_home_despite_a_duplicate(self, analysis):
        # An older (lower id) duplicate of the identity must not pull an unrelated edit away
        # from the row the transactions already belong to.
        older = CostLineItemFactory(analysis=analysis, total_cost=Decimal("1"), **item_defaults())
        CostLineItemConfigFactory(cost_line_item=older, category=Category.get_default())
        t1, t2 = tx(analysis), tx(analysis)
        group(analysis)
        t1.refresh_from_db()
        home = t1.cost_line_item
        assert older.id < home.id

        plan, _result = correct(analysis, [t1], amount=Decimal("7"))

        assert plan.destinations[0].outcome == UNCHANGED
        assert plan.destinations[0].existing.id == home.id
        t1.refresh_from_db()
        assert t1.cost_line_item_id == home.id


@pytest.mark.django_db
class TestScope:
    def test_ids_outside_the_analysis_and_out_of_scope_parents_are_dropped(self, analysis, defaults):
        t1 = tx(analysis)
        group(analysis)
        foreign_analysis = AnalysisFactory(country=analysis.country, grants="G1")
        foreign = tx(foreign_analysis)
        group(foreign_analysis)
        lump = CostLineItemFactory(analysis=analysis, is_special_lump_sum=True, grant_code="G1")
        CostLineItemConfigFactory(cost_line_item=lump, cost_type=None, category=None)
        lump_tx = TransactionFactory(analysis=analysis, cost_line_item=lump, **TX_DEFAULTS)

        plan, result = correct(analysis, [t1, foreign, lump_tx], site_code="S5")

        assert [t.id for t in plan.transactions] == [t1.id]
        assert result.record_count == 1
        foreign.refresh_from_db()
        lump_tx.refresh_from_db()
        assert foreign.site_code == "S1"
        assert lump_tx.site_code == "S1"

    def test_nothing_in_scope_is_an_error(self, analysis):
        t1 = tx(analysis)
        group(analysis)
        foreign = tx(AnalysisFactory(country=analysis.country, grants="G1"))

        with pytest.raises(CorrectionError):
            plan_transaction_correction(analysis, [foreign.id], CorrectionPatch(site_code="S5"))


@pytest.mark.django_db
class TestFingerprint:
    def test_fingerprint_tracks_the_warning_and_the_prompts(self, analysis):
        t1, t2 = tx(analysis), tx(analysis)
        group(analysis)
        source = item_for(analysis, site_code="S1")

        before = plan_transaction_correction(analysis, [t2.id], CorrectionPatch(site_code="S2"))
        allocate(source, "40")
        after = plan_transaction_correction(analysis, [t2.id], CorrectionPatch(site_code="S2"))

        assert not before.needs_confirmation
        assert after.needs_confirmation
        assert before.fingerprint() != after.fingerprint()
        assert (
            after.fingerprint()
            == plan_transaction_correction(analysis, [t2.id], CorrectionPatch(site_code="S2")).fingerprint()
        )


@pytest.mark.django_db
class TestBookkeeping:
    def test_emptied_combination_is_removed_and_grant_tables_follow(self, analysis):
        t1 = tx(analysis)
        group(analysis)
        assert analysis.cost_type_categories.count() == 1
        support = CostType.objects.get(type=Support.id)

        correct(analysis, [t1], cost_type=support, grant_code="G2")

        combos = list(analysis.cost_type_categories.values_list("cost_type_id", "confirmed"))
        assert combos == [(support.id, False)]
        grants = analysis.cost_type_category_grants.values_list("cost_type_category__cost_type_id", "grant")
        assert list(grants) == [(support.id, "G2")]

    def test_decimal_precision_is_the_application_setting(self, analysis):
        t1 = tx(analysis)
        group(analysis)

        correct(analysis, [t1], amount=Decimal("12.3456"))

        t1.refresh_from_db()
        assert t1.amount_in_instance_currency == Decimal("12.3456")
        assert django_settings.DECIMAL_PLACES == 4
