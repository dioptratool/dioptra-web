"""
Structural edits to an intervention's sub-component labels.

Sub-component percentages are stored per cost item as a dict keyed by label position
(``{"0": "60", "1": "40"}``). Saving a new label list on its own would leave those keys
pointing at whichever label now sits at each position, so a reorder or removal would move
percentages between components. Every save therefore goes through
:func:`update_subcomponent_labels`, which takes each component's *source* (its position in
the saved list, or ``None`` for a new component) and remaps every allocation row of the
sub-component analysis in the same transaction.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils.translation import gettext_lazy as _

from website.models import InterventionInstance, SubcomponentCostAllocation, SubcomponentCostAnalysis

STALE_MESSAGE = _(
    "The sub-components for this intervention changed after this form was opened. "
    "Reload it and enter the values again."
)


@dataclass(frozen=True)
class Component:
    label: str
    source: int | None = None
    """Position of this component in the saved label list; ``None`` for a new component."""


def is_stale(subcomponent_analysis: SubcomponentCostAnalysis | None, posted_id, posted_revision) -> bool:
    """
    True when a form's posted (analysis id, revision) no longer describes the saved analysis:
    the components were added to, removed from or reordered since the form was opened, or
    the analysis was deleted and recreated, or created after a form that expected none.
    """
    if subcomponent_analysis is None:
        return posted_id not in (None, "")
    try:
        return (
            int(posted_id) != subcomponent_analysis.id
            or int(posted_revision) != subcomponent_analysis.revision
        )
    except (TypeError, ValueError):
        return True


def validate_sources(sources: Sequence[int | None], existing_count: int) -> None:
    """
    Each source must be ``None`` or a position within the saved label list, used at most once.
    """
    seen = set()
    for source in sources:
        if source is None:
            continue
        if isinstance(source, bool) or not isinstance(source, int):
            raise ValidationError(_("Invalid sub-component reference."), code="invalid")
        if not 0 <= source < existing_count or source in seen:
            raise ValidationError(_("Invalid sub-component reference."), code="invalid")
        seen.add(source)


def _allocation_str(value) -> str:
    """
    Stored values should be strings, but production holds some JSON numbers (``50.0``), which
    the field's type check rejects on save. Normalise to the shortest exact string.
    """
    if isinstance(value, str):
        return value
    try:
        text = f"{Decimal(str(value)):f}"
    except InvalidOperation:
        return str(value)
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def remap_allocations(allocations: dict | None, sources: Sequence[int | None]) -> dict:
    """
    Move each stored percentage to its component's new position. Removed components are
    dropped; new components (``None``) stay absent, which is how a blank is stored.
    """
    old = allocations or {}
    new = {}
    for new_idx, source in enumerate(sources):
        if source is None:
            continue
        key = str(source)
        if key in old:
            new[str(new_idx)] = _allocation_str(old[key])
    return new


def update_subcomponent_labels(
    subcomponent_analysis: SubcomponentCostAnalysis | None,
    components: Sequence[Component],
    *,
    intervention_instance: InterventionInstance | None = None,
) -> SubcomponentCostAnalysis:
    """
    Save the labels and remap every allocation row of this sub-component analysis in one
    transaction. Pass ``intervention_instance`` to create the analysis when it doesn't exist
    yet; every component is then new.
    """
    labels = [component.label for component in components]
    sources = [component.source for component in components]

    if subcomponent_analysis is None:
        if intervention_instance is None:
            raise ValueError("intervention_instance is required when creating a sub-component analysis")
        validate_sources(sources, existing_count=0)
        return SubcomponentCostAnalysis.objects.create(
            intervention_instance=intervention_instance, subcomponent_labels=labels
        )

    existing = subcomponent_analysis.subcomponent_labels or []
    validate_sources(sources, existing_count=len(existing))
    # A rename keeps every position; anything else moves stored percentages.
    structure_changed = sources != list(range(len(existing)))

    with transaction.atomic():
        subcomponent_analysis.subcomponent_labels = labels
        update_fields = ["subcomponent_labels"]
        if structure_changed:
            subcomponent_analysis.revision = F("revision") + 1
            update_fields.append("revision")
        subcomponent_analysis.save(update_fields=update_fields)
        if structure_changed:
            subcomponent_analysis.refresh_from_db(fields=["revision"])

        changed = []
        for row in subcomponent_analysis.allocations.all():
            remapped = remap_allocations(row.allocations, sources)
            if remapped != (row.allocations or {}):
                row.allocations = remapped
                changed.append(row)
        if changed:
            SubcomponentCostAllocation.objects.bulk_update(changed, ["allocations"], batch_size=500)

    return subcomponent_analysis
