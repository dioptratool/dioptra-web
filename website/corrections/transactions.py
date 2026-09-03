"""
In-app correction of transactions (Feature 91, spec sections 7-10).

A correction is planned first and applied second:

- ``plan_transaction_correction`` reads the current data and works out, without writing anything,
  where every selected transaction ends up, which cost items split or merge and which allocations
  would be cleared. The panel uses the plan to decide whether a confirmation step is needed.
- ``apply_transaction_correction`` writes the plan inside one atomic operation and runs the same
  post-save bookkeeping as the existing single-row categorisation path.

The existing ``Analysis.sync_cost_line_items`` routine is deliberately not reused: its grouping key
ignores Cost Type and Category, it drops zero-total groups, and it deletes parents before their
transactions are reassigned (spec section 13).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal

from django.db import transaction as db_transaction
from django.db.models import Count, Sum
from django.utils.translation import gettext as _

from website.models import (
    Analysis,
    CostLineItem,
    CostLineItemConfig,
    CostLineItemInterventionAllocation,
    Transaction,
)
from website.models.subcomponent import SubcomponentCostAllocation
from website.workflows import AnalysisWorkflow
from .errors import CorrectionError
from .patch import CUSTOM_FIELD_NAMES, FIELD_ORDER, GROUPING_FIELDS, CorrectionPatch

NOTE_MAX_LENGTH = CostLineItem._meta.get_field("note").max_length

# Raw grouping key followed by Cost Type id and Category id (spec section 2).
Identity = tuple

# How a destination comes to hold its transactions after the correction.
UNCHANGED = "unchanged"  # Transactions stay in the cost item they already belong to.
MOVE = "move"  # One-to-one move: the source row takes on a new identity; allocations survive.
MERGE = "merge"  # Transactions join an existing cost item that also holds other transactions.
CREATE = "create"  # A new cost item is created for the transactions.


@dataclasses.dataclass
class Destination:
    identity: Identity
    transactions: list[Transaction]
    # Distinct source cost items of ``transactions``, ascending id.
    sources: list[CostLineItem]
    existing: CostLineItem | None = None
    outcome: str = UNCHANGED
    # Description to write (new rows always; existing rows only when explicitly supplied).
    description: str | None = None
    # Whether ``description`` is also written to the destination's transactions.
    rewrite_transaction_descriptions: bool = False
    # Merged note to write on an existing or new row; None leaves the note alone.
    note: str | None = None

    @property
    def is_structural(self) -> bool:
        return self.outcome in (MERGE, CREATE)


@dataclasses.dataclass
class TransactionCorrectionPlan:
    analysis: Analysis
    patch: CorrectionPatch
    transactions: list[Transaction]
    sources: dict[int, CostLineItem]
    destinations: list[Destination]
    changed_fields: list[str]
    split_source_ids: set[int]
    removed_source_ids: set[int]
    # Configurations whose intervention and sub-component allocations are cleared.
    affected_config_ids: set[int]
    needs_allocation_warning: bool
    # (cost_type_id, category_id) combinations that must be confirmed again (section 10).
    unconfirm_combinations: set[tuple[int, int]]

    @property
    def is_structural(self) -> bool:
        return any(destination.is_structural for destination in self.destinations)

    @property
    def needs_confirmation(self) -> bool:
        """Whether the save must pass through the confirmation step (section 9)."""
        return self.needs_allocation_warning

    def fingerprint(self) -> str:
        """
        Identifies the confirmation the user is being asked for.

        The apply step recomputes the plan; if the warning condition changed since the preview,
        the confirmation step is shown again (section 13).
        """
        payload = {"warning": self.needs_allocation_warning}
        # An identity token for the confirmation step, not a security measure.
        return hashlib.sha1(json.dumps(payload, sort_keys=True).encode(), usedforsecurity=False).hexdigest()


@dataclasses.dataclass
class CorrectionResult:
    record_count: int
    changed_fields: list[str]
    # Cost items the moved transactions now belong to, split by how they came to exist.
    created_count: int
    existing_count: int
    removed_count: int
    cleared_count: int
    structural: bool

    @property
    def regrouped_count(self) -> int:
        return self.created_count + self.existing_count


def cost_line_item_identity(cost_line_item: CostLineItem) -> Identity:
    config = cost_line_item.config
    return (
        *(getattr(cost_line_item, name) for name in GROUPING_FIELDS),
        config.cost_type_id,
        config.category_id,
    )


def plan_transaction_correction(
    analysis: Analysis,
    transaction_ids: Iterable[int],
    patch: CorrectionPatch,
) -> TransactionCorrectionPlan:
    """
    Preview a correction of the given transactions without writing anything.

    Ids outside the analysis, and transactions whose cost item is a special-country lump sum or an
    Add Other Costs row, are dropped from the selection (section 14) - the same guard the existing
    bulk panels apply to forged ids.
    """
    transactions = list(
        Transaction.objects.filter(
            analysis=analysis,
            id__in=list(transaction_ids),
            cost_line_item__isnull=False,
            cost_line_item__is_special_lump_sum=False,
            cost_line_item__config__analysis_cost_type__isnull=True,
        )
        .select_related("cost_line_item", "cost_line_item__config")
        .order_by("id")
    )
    if not transactions:
        raise CorrectionError(_("None of the selected transactions can be edited."))

    sources: dict[int, CostLineItem] = {}
    for each in transactions:
        sources.setdefault(each.cost_line_item_id, each.cost_line_item)

    # Every ordinary cost item is a candidate destination. With duplicate identities (a legacy of
    # the sync routine's raw-key grouping) the lowest id wins, so the choice never depends on
    # database iteration order.
    candidates: dict[Identity, CostLineItem] = {}
    for candidate in (
        analysis.cost_line_items.cost_type_category_items().select_related("config").order_by("id")
    ):
        candidates.setdefault(cost_line_item_identity(candidate), candidate)

    # Effective identity: the cost item's current key overlaid with the edit. Reading the key from
    # the parent rather than the transaction's own columns keeps an amount-only or description-only
    # edit from regrouping a transaction whose columns drifted from its parent's.
    grouped: dict[Identity, list[Transaction]] = defaultdict(list)
    for each in transactions:
        grouped[_effective_identity(each.cost_line_item, patch)].append(each)

    # Transaction counts of every source and every existing destination, to tell a partial move
    # (split) from a whole one and an existing destination that keeps its own rows from one that
    # does not.
    selected_by_source: dict[int, int] = defaultdict(int)
    for each in transactions:
        selected_by_source[each.cost_line_item_id] += 1

    destinations: list[Destination] = []
    for identity, members in grouped.items():
        member_sources = sorted({m.cost_line_item for m in members}, key=lambda c: c.id)
        home = next((s for s in member_sources if cost_line_item_identity(s) == identity), None)
        existing = home if home is not None else candidates.get(identity)
        destinations.append(Destination(identity, members, member_sources, existing=existing))

    existing_ids = {d.existing.id for d in destinations if d.existing is not None}
    total_by_item = dict(
        Transaction.objects.filter(cost_line_item_id__in=set(sources) | existing_ids)
        .values_list("cost_line_item_id")
        .annotate(n=Count("id"))
        .values_list("cost_line_item_id", "n")
    )

    for destination in destinations:
        existing = destination.existing
        if existing is None:
            source = destination.sources[0] if len(destination.sources) == 1 else None
            whole_source = source is not None and selected_by_source[source.id] == total_by_item.get(
                source.id, 0
            )
            if whole_source and source.id not in existing_ids:
                destination.outcome = MOVE
            else:
                destination.outcome = CREATE
            continue

        own_remaining = total_by_item.get(existing.id, 0) - selected_by_source.get(existing.id, 0)
        contributors = {s.id for s in destination.sources}
        if own_remaining > 0:
            contributors.add(existing.id)
        destination.outcome = UNCHANGED if contributors == {existing.id} else MERGE

    # Sources: which ones split, which ones end up empty.
    landing: dict[int, set[Identity]] = defaultdict(set)
    for destination in destinations:
        for member in destination.transactions:
            landing[member.cost_line_item_id].add(destination.identity)
    split_source_ids: set[int] = set()
    removed_source_ids: set[int] = set()
    moved_rows = {d.sources[0].id for d in destinations if d.outcome == MOVE}
    for source_id, source in sources.items():
        remaining = total_by_item.get(source_id, 0) - selected_by_source[source_id]
        if remaining > 0:
            landing[source_id].add(cost_line_item_identity(source))
        if len(landing[source_id]) > 1:
            split_source_ids.add(source_id)
        if remaining == 0 and source_id not in existing_ids and source_id not in moved_rows:
            removed_source_ids.add(source_id)

    merge_destination_ids = {d.existing.id for d in destinations if d.outcome == MERGE}
    affected_item_ids = (split_source_ids - removed_source_ids) | merge_destination_ids
    items_by_id = {**sources, **{d.existing.id: d.existing for d in destinations if d.existing}}
    affected_config_ids = {items_by_id[item_id].config.id for item_id in affected_item_ids}

    _resolve_notes(destinations, sources, removed_source_ids)
    _resolve_descriptions(destinations, patch)

    unconfirm_combinations: set[tuple[int, int]] = set()
    if patch.changes_categorization:
        for each in transactions:
            config = each.cost_line_item.config
            previous = (config.cost_type_id, config.category_id)
            effective = _effective_categorization(config, patch)
            if effective != previous and None not in effective:
                unconfirm_combinations.add(effective)

    return TransactionCorrectionPlan(
        analysis=analysis,
        patch=patch,
        transactions=transactions,
        sources=sources,
        destinations=destinations,
        changed_fields=_changed_fields(transactions, patch),
        split_source_ids=split_source_ids,
        removed_source_ids=removed_source_ids,
        affected_config_ids=affected_config_ids,
        needs_allocation_warning=_has_allocation_data(affected_config_ids),
        unconfirm_combinations=unconfirm_combinations,
    )


def apply_transaction_correction(plan: TransactionCorrectionPlan) -> CorrectionResult:
    """
    Write a planned correction: every selected transaction is updated or none are.

    Empty source cost items are deleted only after their transactions have been reassigned
    (Transaction.cost_line_item cascades on delete). A cost item is removed only when it has no
    transactions left; a group whose transactions sum to zero remains.
    """
    with db_transaction.atomic():
        # A fresh instance: the caller's may carry prefetch caches that the bookkeeping below
        # (grants_list, special_country_cost_line_items) would otherwise read stale.
        analysis = Analysis.objects.get(pk=plan.analysis.pk)
        selected_ids = [t.id for t in plan.transactions]

        values = plan.patch.transaction_values()
        if values:
            Transaction.objects.filter(id__in=selected_ids).update(**values)

        created_count = 0
        existing_count = 0
        for destination in plan.destinations:
            member_ids = [t.id for t in destination.transactions]
            if destination.outcome == CREATE:
                row = _create_cost_line_item(analysis, destination)
                Transaction.objects.filter(id__in=member_ids).update(cost_line_item=row)
                created_count += 1
            elif destination.outcome == MOVE:
                row = destination.sources[0]
                _move_cost_line_item(row, destination, plan.patch)
                existing_count += 1
            else:
                row = destination.existing
                if destination.outcome == MERGE:
                    Transaction.objects.filter(id__in=member_ids).update(cost_line_item=row)
                    existing_count += 1
                update_fields = []
                if destination.description is not None:
                    row.budget_line_description = destination.description
                    update_fields.append("budget_line_description")
                if destination.note is not None:
                    row.note = destination.note
                    update_fields.append("note")
                if update_fields:
                    row.save(update_fields=update_fields)
            if destination.rewrite_transaction_descriptions:
                row.transactions.update(budget_line_description=destination.description)

        # Totals from the transactions as they now stand (every destination, created rows
        # included, is registered as ``existing`` by now); an item missing from the aggregate has
        # no transactions left.
        touched_ids = set(plan.sources) | {d.existing.id for d in plan.destinations if d.existing is not None}
        totals = dict(
            Transaction.objects.filter(cost_line_item_id__in=touched_ids)
            .values_list("cost_line_item_id")
            .annotate(total=Sum("amount_in_instance_currency"))
            .values_list("cost_line_item_id", "total")
        )
        empty_ids = [item_id for item_id in plan.sources if item_id not in totals]
        removed_count = len(empty_ids)
        if empty_ids:
            CostLineItem.objects.filter(analysis=analysis, id__in=empty_ids).delete()
        CostLineItem.objects.bulk_update(
            [CostLineItem(id=item_id, total_cost=total) for item_id, total in totals.items()],
            ["total_cost"],
        )

        cleared_count = 0
        if plan.affected_config_ids:
            surviving = list(
                CostLineItemConfig.objects.filter(id__in=plan.affected_config_ids).values_list(
                    "id", flat=True
                )
            )
            cleared_count = len(surviving)
            CostLineItemInterventionAllocation.objects.filter(cli_config_id__in=surviving).delete()
            SubcomponentCostAllocation.objects.filter(cli_config_id__in=surviving).delete()

        analysis.ensure_cost_type_category_objects()
        for cost_type_id, category_id in plan.unconfirm_combinations:
            analysis.cost_type_categories.filter(cost_type_id=cost_type_id, category_id=category_id).update(
                confirmed=False
            )

        workflow = AnalysisWorkflow(analysis)
        workflow.invalidate_step("insights")
        workflow.calculate_if_possible()

    return CorrectionResult(
        record_count=len(plan.transactions),
        changed_fields=list(plan.changed_fields),
        created_count=created_count,
        existing_count=existing_count,
        removed_count=removed_count,
        cleared_count=cleared_count,
        structural=plan.is_structural,
    )


# --- planning helpers -------------------------------------------------------------------------


def _effective_identity(cost_line_item: CostLineItem, patch: CorrectionPatch) -> Identity:
    key = [getattr(cost_line_item, name) for name in GROUPING_FIELDS]
    for index, name in enumerate(GROUPING_FIELDS):
        value = getattr(patch, name, None)
        if value is not None:
            key[index] = value
    return (*key, *_effective_categorization(cost_line_item.config, patch))


def _effective_categorization(config: CostLineItemConfig, patch: CorrectionPatch) -> tuple:
    cost_type_id = patch.cost_type.id if patch.cost_type is not None else config.cost_type_id
    category_id = patch.category.id if patch.category is not None else config.category_id
    return cost_type_id, category_id


def _changed_fields(transactions: list[Transaction], patch: CorrectionPatch) -> list[str]:
    """
    The supplied fields whose value differs on at least one selected record, so that a prefilled
    value saved unchanged is a no-op (section 5).
    """
    changed = []
    for name in patch.supplied_fields():
        if name == "cost_type":
            differs = any(t.cost_line_item.config.cost_type_id != patch.cost_type.id for t in transactions)
        elif name == "category":
            differs = any(t.cost_line_item.config.category_id != patch.category.id for t in transactions)
        elif name == "description":
            differs = any(t.cost_line_item.budget_line_description != patch.description for t in transactions)
        elif name == "amount":
            differs = any(t.amount_in_instance_currency != patch.amount for t in transactions)
        elif name in CUSTOM_FIELD_NAMES:
            differs = any(getattr(t, name) != patch.custom_fields[name] for t in transactions)
        else:
            differs = any(getattr(t, name) != getattr(patch, name) for t in transactions)
        if differs:
            changed.append(name)
    return changed


def _merge_notes(notes: Iterable[str]) -> str:
    """Distinct non-empty notes in the given order, newline-separated (section 9)."""
    seen: list[str] = []
    for note in notes:
        if note and note not in seen:
            seen.append(note)
    return "\n".join(seen)


def _resolve_notes(
    destinations: list[Destination], sources: dict[int, CostLineItem], removed_source_ids: set[int]
) -> None:
    for destination in destinations:
        if destination.outcome == MERGE:
            existing = destination.existing
            contributors = [s for s in destination.sources if s.id != existing.id]
            merged = _merge_notes([existing.note, *(s.note for s in contributors)])
            if merged != existing.note:
                destination.note = merged
        elif destination.outcome == CREATE:
            destination.note = _merge_notes(s.note for s in destination.sources)
        else:
            continue
        if len(destination.note or "") > NOTE_MAX_LENGTH:
            raise CorrectionError(
                _(
                    "The notes of the cost items being merged are too long to combine "
                    "(limit {limit} characters). Shorten them before making this change."
                ).format(limit=NOTE_MAX_LENGTH)
            )


def _resolve_descriptions(destinations: list[Destination], patch: CorrectionPatch) -> None:
    """
    Section 9: an explicit description (from either panel kind) is used everywhere and written to
    the destination's transactions. A new cost item inherits its description when every
    contributing source cost item agrees; when they differ it is created blank for the user to
    name afterwards, and its transactions keep their own descriptions. The choice is never made by
    database iteration order.
    """
    for destination in destinations:
        if patch.description is not None:
            destination.description = patch.description
            destination.rewrite_transaction_descriptions = True
            continue
        if destination.outcome != CREATE:
            continue
        contributed = {s.budget_line_description for s in destination.sources}
        destination.description = contributed.pop() if len(contributed) == 1 else ""


def _has_allocation_data(config_ids: set[int]) -> bool:
    """
    Allocation data exists for a cost item when it has an intervention allocation with a non-null,
    non-zero percentage, or a sub-component row that is skipped or holds at least one value
    (section 9). A sub-component row saved with every value blank is stored as an empty dict.
    """
    if not config_ids:
        return False
    if (
        CostLineItemInterventionAllocation.objects.filter(
            cli_config_id__in=config_ids, allocation__isnull=False
        )
        .exclude(allocation=0)
        .exists()
    ):
        return True
    for skipped, allocations in SubcomponentCostAllocation.objects.filter(
        cli_config_id__in=config_ids
    ).values_list("skipped", "allocations"):
        if skipped or allocations:
            return True
    return False


# --- apply helpers ----------------------------------------------------------------------------


def _create_cost_line_item(analysis: Analysis, destination: Destination) -> CostLineItem:
    country, grant, budget_line, account, site, sector, cost_type_id, category_id = destination.identity
    row = CostLineItem.objects.create(
        analysis=analysis,
        country_code=country,
        grant_code=grant,
        budget_line_code=budget_line,
        account_code=account,
        site_code=site,
        sector_code=sector,
        budget_line_description=destination.description or "",
        total_cost=Decimal(0),
        note=destination.note or "",
        is_special_lump_sum=False,
    )
    CostLineItemConfig.objects.create(
        cost_line_item=row,
        cost_type_id=cost_type_id,
        category_id=category_id,
    )
    # Let the caller find the new row through the destination like an existing one.
    destination.existing = row
    return row


def _move_cost_line_item(row: CostLineItem, destination: Destination, patch: CorrectionPatch) -> None:
    """A one-to-one move keeps the row (and so its allocations, note and id) under a new identity."""
    country, grant, budget_line, account, site, sector, cost_type_id, category_id = destination.identity
    row.grant_code = grant
    row.account_code = account
    row.site_code = site
    row.sector_code = sector
    update_fields = ["grant_code", "account_code", "site_code", "sector_code"]
    if destination.description is not None:
        row.budget_line_description = destination.description
        update_fields.append("budget_line_description")
    row.save(update_fields=update_fields)
    if patch.changes_categorization:
        CostLineItemConfig.objects.filter(id=row.config.id).update(
            cost_type_id=cost_type_id, category_id=category_id
        )
    destination.existing = row
