"""
Feature 91 -- the Allocate country proportion follows in-app corrections (spec section 13, D-10).

The proportion is ordinary cost lines / all stored cost lines for the grant. It used to read the
per-grant total cached at import, which cannot be recomputed and went stale after any amount edit
or grant move.
"""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from website.corrections import CorrectionPatch, apply_transaction_correction, plan_transaction_correction
from website.tests.factories import CostLineItemConfigFactory, CostLineItemFactory
from website.views.analysis.steps.allocate import AllocateSupportingCosts
from .helpers import group, make_analysis, tx


def proportion_for(analysis, grant):
    view = AllocateSupportingCosts()
    view.analysis = analysis
    view.object = analysis
    view.grant_code = grant
    view.dioptra_settings = MagicMock()
    view.workflow = MagicMock()
    view.step = MagicMock()
    view.parent_step = MagicMock(is_complete=False)
    return view.calc_country_proportion()


@pytest.mark.django_db
def test_proportion_is_ordinary_over_all_stored_cost_lines_and_follows_an_amount_edit(defaults):
    analysis = make_analysis()
    t1 = tx(analysis, amount="300")
    group(analysis)
    lump = CostLineItemFactory(
        analysis=analysis, is_special_lump_sum=True, grant_code="G1", total_cost=Decimal("100")
    )
    CostLineItemConfigFactory(cost_line_item=lump, cost_type=None, category=None)
    # The stale import cache would claim far more than is stored; it must be ignored.
    analysis.all_transactions_total_cost = "9999,0"
    analysis.save()

    assert proportion_for(analysis, "G1") == Decimal("300") / Decimal("400")

    plan = plan_transaction_correction(analysis, [t1.id], CorrectionPatch(amount=Decimal("100")))
    apply_transaction_correction(plan)

    assert proportion_for(analysis, "G1") == Decimal("100") / Decimal("200")


@pytest.mark.django_db
def test_proportion_follows_a_grant_move_and_is_zero_for_an_empty_grant(defaults):
    analysis = make_analysis()
    t1 = tx(analysis, amount="300")
    group(analysis)

    assert proportion_for(analysis, "G1") == 1
    assert proportion_for(analysis, "G2") == 0

    plan = plan_transaction_correction(analysis, [t1.id], CorrectionPatch(grant_code="G2"))
    apply_transaction_correction(plan)

    assert proportion_for(analysis, "G1") == 0
    assert proportion_for(analysis, "G2") == 1
