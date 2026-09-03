"""
Application log entries for corrections (Feature 91, spec section 15).

One entry per successful save, written by the view after the atomic correction has committed.
Messages name fields by their displayed labels and never carry values.
"""

from __future__ import annotations

from collections.abc import Mapping

from django.utils.translation import gettext as _, ngettext

from website.app_log import loggers
from website.models import Analysis
from .labels import COST_ITEM, STEP_LABELS, TRANSACTION
from .transactions import CorrectionResult


def correction_log_message(
    analysis: Analysis,
    result: CorrectionResult,
    step: str,
    record_kind: str,
    labels: Mapping[str, str],
) -> str:
    """
    For example:

        Corrected 12 transactions in Malnutrition Treatment in Iraq from Confirm Categories
        (Site, Sector Code); regrouped into 2 cost items (1 created, 1 existing), 1 cost item
        removed; cleared allocations on 2 cost items.

        Corrected 3 cost items in Malnutrition Treatment in Iraq from Allocate Intervention Costs
        (Grant).
    """
    if record_kind == TRANSACTION:
        records = ngettext("%d transaction", "%d transactions", result.record_count) % result.record_count
    else:
        records = _cost_items(result.record_count)
    message = _("Corrected {records} in {analysis} from {step}").format(
        records=records, analysis=analysis.title, step=STEP_LABELS[step]
    )
    if result.changed_fields:
        message += " ({fields})".format(fields=", ".join(labels[name] for name in result.changed_fields))

    structural = []
    if result.regrouped_count:
        structural.append(
            _("regrouped into {items} ({created} created, {existing} existing)").format(
                items=_cost_items(result.regrouped_count),
                created=result.created_count,
                existing=result.existing_count,
            )
        )
    if result.removed_count:
        structural.append(_("{items} removed").format(items=_cost_items(result.removed_count)))
    if structural:
        message += "; " + ", ".join(structural)
    if result.cleared_count:
        message += "; " + _("cleared allocations on {items}").format(items=_cost_items(result.cleared_count))
    return message + "."


def log_correction(
    analysis: Analysis,
    result: CorrectionResult,
    step: str,
    record_kind: str,
    labels: Mapping[str, str],
    user=None,
) -> None:
    message = correction_log_message(analysis, result, step, record_kind, labels)
    if record_kind == TRANSACTION:
        loggers.log_analysis_transactions_corrected(analysis, message, user)
    elif record_kind == COST_ITEM:
        loggers.log_analysis_cost_items_corrected(analysis, message, user)
    else:
        raise ValueError(f"Unknown record kind: {record_kind}")


def _cost_items(count: int) -> str:
    return ngettext("%d cost item", "%d cost items", count) % count
