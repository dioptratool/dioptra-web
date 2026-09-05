"""
In-app correction of budget cost items (Feature 91, spec section 6).

A budget cost item is edited directly. It remains the same source row when its fields change and
never merges with another row merely because their fields become equal, so there is no regrouping,
no note merging and no allocation clearing here; the only bookkeeping is the Cost Type / Category
combination upkeep and the confirmation rule of section 10.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable

from django.db import transaction as db_transaction
from django.utils.translation import gettext as _

from website.models import Analysis, CostLineItem, CostLineItemConfig
from website.workflows import AnalysisWorkflow
from .errors import CorrectionError
from .patch import CUSTOM_FIELD_NAMES, CorrectionPatch
from .transactions import CorrectionResult

# Patch fields that do not exist on a cost item and are ignored by this service.
TRANSACTION_ONLY_FIELDS = ("transaction_description", "date")


@dataclasses.dataclass
class CostItemCorrectionPlan:
    analysis: Analysis
    patch: CorrectionPatch
    cost_line_items: list[CostLineItem]
    changed_fields: list[str]
    # (cost_type_id, category_id) combinations that must be confirmed again (section 10).
    unconfirm_combinations: set[tuple[int, int]]
    # A direct edit never splits or merges, so it never needs the confirmation step; these mirror
    # the transaction plan so the panels can treat both plans alike.
    needs_allocation_warning: bool = False

    @property
    def needs_confirmation(self) -> bool:
        return False

    def fingerprint(self) -> str:
        return "direct"


def plan_cost_item_correction(
    analysis: Analysis, cost_line_item_ids: Iterable[int], patch: CorrectionPatch
) -> CostItemCorrectionPlan:
    """
    Preview a direct correction of budget cost items.

    Ids outside the analysis and rows outside the editable tables (special-country lump sums, Add
    Other Costs rows) are dropped, as in the transaction service. A cost item that is derived from
    transactions is refused outright: its values belong to its transactions (section 7).
    """
    cost_line_items = list(
        analysis.cost_line_items.cost_type_category_items()
        .filter(id__in=list(cost_line_item_ids))
        .select_related("config")
        .order_by("id")
    )
    if not cost_line_items:
        raise CorrectionError(_("None of the selected cost items can be edited."))
    derived = CostLineItem.objects.filter(
        id__in=[c.id for c in cost_line_items], transactions__isnull=False
    ).exists()
    if derived:
        raise CorrectionError(
            _("Cost items in a transaction-based analysis are edited through their transactions.")
        )

    unconfirm_combinations: set[tuple[int, int]] = set()
    if patch.changes_categorization:
        for cost_line_item in cost_line_items:
            config = cost_line_item.config
            previous = (config.cost_type_id, config.category_id)
            effective = (
                patch.cost_type.id if patch.cost_type is not None else config.cost_type_id,
                patch.category.id if patch.category is not None else config.category_id,
            )
            if effective != previous and None not in effective:
                unconfirm_combinations.add(effective)

    return CostItemCorrectionPlan(
        analysis=analysis,
        patch=patch,
        cost_line_items=cost_line_items,
        changed_fields=_changed_fields(cost_line_items, patch),
        unconfirm_combinations=unconfirm_combinations,
    )


def apply_cost_item_correction(plan: CostItemCorrectionPlan) -> CorrectionResult:
    """Write a planned cost-item correction: every selected row is updated or none are."""
    with db_transaction.atomic():
        analysis = Analysis.objects.get(pk=plan.analysis.pk)
        ids = [c.id for c in plan.cost_line_items]

        values = plan.patch.cost_line_item_values()
        if values:
            CostLineItem.objects.filter(id__in=ids).update(**values)

        config_values = {}
        if plan.patch.cost_type is not None:
            config_values["cost_type"] = plan.patch.cost_type
        if plan.patch.category is not None:
            config_values["category"] = plan.patch.category
        if config_values:
            CostLineItemConfig.objects.filter(cost_line_item_id__in=ids).update(**config_values)

        analysis.ensure_cost_type_category_objects()
        for cost_type_id, category_id in plan.unconfirm_combinations:
            analysis.cost_type_categories.filter(cost_type_id=cost_type_id, category_id=category_id).update(
                confirmed=False
            )

        workflow = AnalysisWorkflow(analysis)
        workflow.invalidate_step("insights")
        workflow.calculate_if_possible()

    return CorrectionResult(
        record_count=len(plan.cost_line_items),
        changed_fields=list(plan.changed_fields),
        created_count=0,
        existing_count=0,
        removed_count=0,
        cleared_count=0,
        structural=False,
    )


def _changed_fields(cost_line_items: list[CostLineItem], patch: CorrectionPatch) -> list[str]:
    changed = []
    for name in patch.supplied_fields():
        if name in TRANSACTION_ONLY_FIELDS:
            continue
        if name == "cost_type":
            differs = any(c.config.cost_type_id != patch.cost_type.id for c in cost_line_items)
        elif name == "category":
            differs = any(c.config.category_id != patch.category.id for c in cost_line_items)
        elif name == "description":
            differs = any(c.budget_line_description != patch.description for c in cost_line_items)
        elif name == "amount":
            differs = any(c.total_cost != patch.amount for c in cost_line_items)
        elif name in CUSTOM_FIELD_NAMES:
            differs = any(getattr(c, name) != patch.custom_fields[name] for c in cost_line_items)
        else:
            differs = any(getattr(c, name) != getattr(patch, name) for c in cost_line_items)
        if differs:
            changed.append(name)
    return changed
