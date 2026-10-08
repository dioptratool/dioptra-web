"""Intervention metadata: current definitions resolved against stored values, numeric rules, draft
validation, and the transactional reconciliation of an intervention's definitions.

Values are stored on ``InterventionInstance.metadata`` keyed by field key (``str(uuid)``), as the
text or exact numeric string, or as a list of option keys. Consumers only ever see values through
``resolve_metadata``, which walks the *current* definitions, so a deleted field or option, or a
field whose key was rotated by a type change, disappears everywhere at once while the stored
orphan waits for a save of that instance or the cleanup command. An analysis that was showing such
a value has its ``updated`` timestamp set when the definitions change (see ``save_draft``).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import prefetch_related_objects
from django.utils import timezone
from django.utils.translation import gettext as _

from website.currency import currency_symbol
from website.models import (
    Analysis,
    InterventionInstance,
    InterventionMetadataField,
    InterventionMetadataOption,
)
from website.models.intervention_metadata import (
    MAX_FIELDS_PER_INTERVENTION,
    MAX_OPTIONS_PER_FIELD,
    NAME_MAX_LENGTH,
    NUMBER_MAX_DIGITS,
    MetadataFieldType,
    MetadataNumberType,
)

DECIMAL_PATTERN = re.compile(r"^-?[0-9]+(?:\.[0-9]+)?$")
INTEGER_PATTERN = re.compile(r"^-?[0-9]+$")

DEFINITION_PREFETCHES = ("metadata_fields", "metadata_fields__options")


class MetadataDraftError(Exception):
    """A validated definition draft could not be persisted; nothing was written."""


def _conflict_error() -> MetadataDraftError:
    return MetadataDraftError(
        _("The metadata could not be saved because another change conflicts with it. Reload and try again.")
    )


def _still_present(records: dict, pk):
    """The record with that pk, or the conflict error when another editor deleted it meanwhile."""
    record = records.get(pk)
    if record is None:
        raise _conflict_error()
    return record


# ---- numbers -------------------------------------------------------------------------------------


def validate_number(value: str, number_type: str) -> str:
    """
    The trimmed numeric string, or a ValidationError.

    Digits, an optional leading minus and (except for Integer) one decimal point; at most
    NUMBER_MAX_DIGITS digit characters counted as entered, so leading and trailing zeros count.
    No range, sign or scale limits beyond that.
    """
    text = (value or "").strip()
    if number_type == MetadataNumberType.INTEGER:
        if not INTEGER_PATTERN.match(text):
            raise ValidationError(_number_error(_("Enter a whole number."), text), code="invalid")
    elif not DECIMAL_PATTERN.match(text):
        raise ValidationError(
            _number_error(_("Enter a number, using a period as the decimal separator."), text), code="invalid"
        )
    if sum(character.isdigit() for character in text) > NUMBER_MAX_DIGITS:
        raise ValidationError(
            _("Enter at most %(max)s digits.") % {"max": NUMBER_MAX_DIGITS}, code="max_digits"
        )
    return text


def _number_error(message: str, text: str) -> str:
    """The invalid-number message, naming the comma when one was typed: "1,000" is the usual slip."""
    if "," in text:
        return f"{message} {_('Commas are not allowed.')}"
    return message


def format_number(value: str, number_type: str, analysis=None) -> str:
    """The stored numeric string for display: grouped digits, exact precision, unit affixes."""
    text = f"{Decimal(value):,}"
    if number_type == MetadataNumberType.PERCENTAGE:
        return f"{text}%"
    if number_type == MetadataNumberType.CURRENCY:
        return f"{currency_symbol(analysis) or ''}{text}"
    return text


# ---- definitions and values -----------------------------------------------------------------------


@dataclass(frozen=True)
class MetadataRow:
    key: str
    name: str
    field_type: str
    number_type: str | None
    raw: str | list[str]
    display: str
    items: tuple[str, ...]


def definitions_for(intervention) -> list[InterventionMetadataField]:
    """The intervention's current fields, with options, in configured order."""
    if intervention is None:
        return []
    return list(intervention.metadata_fields.all())


def resolve_metadata(instance: InterventionInstance, definitions=None, analysis=None) -> list[MetadataRow]:
    """
    The instance's nonblank values for its intervention's current definitions, in order.

    Retired fields and options are left out; "0" is a value. Pass ``definitions`` when they were
    prefetched for several instances.
    """
    values = instance.metadata or {}
    if definitions is None:
        definitions = definitions_for(instance.intervention)
    rows = []
    for definition in definitions:
        row = _row_for(definition, values.get(definition.storage_key), analysis)
        if row is not None:
            rows.append(row)
    return rows


def _row_for(definition, raw, analysis) -> MetadataRow | None:
    common = dict(
        key=definition.storage_key,
        name=definition.name,
        field_type=definition.field_type,
        number_type=definition.number_type,
    )
    if definition.field_type == MetadataFieldType.MULTIPLE_CHOICE:
        if not isinstance(raw, list):
            return None
        selected = set(raw)
        live = [option for option in definition.options.all() if option.storage_key in selected]
        if not live:
            return None
        labels = tuple(option.label for option in live)
        return MetadataRow(
            raw=[option.storage_key for option in live], display=", ".join(labels), items=labels, **common
        )
    if definition.field_type == MetadataFieldType.SINGLE_CHOICE:
        if not isinstance(raw, str):
            return None
        for option in definition.options.all():
            if option.storage_key == raw:
                return MetadataRow(raw=raw, display=option.label, items=(option.label,), **common)
        return None
    if not isinstance(raw, str) or raw == "":
        return None
    if definition.is_number:
        try:
            display = format_number(raw, definition.number_type, analysis)
        except (InvalidOperation, ValueError):
            return None
        return MetadataRow(raw=raw, display=display, items=(display,), **common)
    return MetadataRow(raw=raw, display=raw, items=(raw,), **common)


def metadata_lookup(analysis) -> dict[int, list[MetadataRow]]:
    """Resolved rows for every intervention instance of the analysis, keyed by instance id."""
    instances = list(analysis.interventioninstance_set.all())
    prefetch_related_objects(instances, "intervention__metadata_fields__options")
    return {instance.id: resolve_metadata(instance, analysis=analysis) for instance in instances}


EXCEL_MAX_SIGNIFICANT_DIGITS = 15


def significant_digits(value: str) -> int:
    """Digits of a stored number from its first to its last nonzero digit; zero counts as one."""
    return len(Decimal(value).normalize().as_tuple().digits)


def excel_number(value: str) -> float | None:
    """
    The float to put in a spreadsheet cell when it carries the stored number exactly, else None.

    A number with more than 15 significant digits, or one that does not survive the float round
    trip, is written as text instead so no precision is silently lost.
    """
    try:
        exact = Decimal(value)
    except (InvalidOperation, ValueError):
        return None
    if significant_digits(value) > EXCEL_MAX_SIGNIFICANT_DIGITS:
        return None
    try:
        as_float = float(value)
    except (OverflowError, ValueError):
        return None
    if as_float != as_float or as_float in (float("inf"), float("-inf")):
        return None
    if Decimal(str(as_float)) != exact:
        return None
    return as_float


def excel_number_format(value: str, number_type: str | None, symbol: str | None = None) -> str:
    """
    The cell format that shows a stored number as Insights does: grouped, with exactly the entered
    decimal places (trailing zeros included), and the unit affix of its number type.
    """
    fraction = value.strip().partition(".")[2]
    pattern = "#,##0" + (f".{'0' * len(fraction)}" if fraction else "")
    if number_type == MetadataNumberType.PERCENTAGE:
        return f'{pattern}"%"'
    if number_type == MetadataNumberType.CURRENCY and symbol:
        return f'"{symbol}"{pattern}'
    return pattern


def prune_metadata(definitions, metadata: dict) -> dict:
    """``metadata`` restricted to the given definitions and their live options, blanks dropped."""
    pruned = {}
    for definition in definitions:
        raw = (metadata or {}).get(definition.storage_key)
        if definition.field_type == MetadataFieldType.MULTIPLE_CHOICE:
            if isinstance(raw, list):
                live_keys = {option.storage_key for option in definition.options.all()}
                selected = [key for key in raw if key in live_keys]
                if selected:
                    pruned[definition.storage_key] = selected
        elif definition.field_type == MetadataFieldType.SINGLE_CHOICE:
            if isinstance(raw, str) and any(option.storage_key == raw for option in definition.options.all()):
                pruned[definition.storage_key] = raw
        elif isinstance(raw, str) and raw != "":
            pruned[definition.storage_key] = raw
    return pruned


def metadata_usage(intervention) -> tuple[set[str], set[str]]:
    """Field keys and option keys that hold a value on any instance of the intervention."""
    definitions = {definition.storage_key: definition for definition in definitions_for(intervention)}
    field_keys, option_keys = set(), set()
    for metadata in InterventionInstance.objects.filter(intervention=intervention).values_list(
        "metadata", flat=True
    ):
        for key, value in (metadata or {}).items():
            if value in ("", [], None):
                continue
            field_keys.add(key)
            definition = definitions.get(key)
            if definition is None or not definition.is_choice:
                continue
            if isinstance(value, list):
                option_keys.update(value)
            else:
                option_keys.add(value)
    return field_keys, option_keys


# ---- definition drafts ------------------------------------------------------------------------------


def build_draft(intervention) -> dict:
    """The editor's draft for an intervention: its current definitions with usage flags."""
    if intervention is None or not intervention.pk:
        return {"fields": []}
    used_fields, used_options = metadata_usage(intervention)
    fields = []
    for definition in intervention.metadata_fields.prefetch_related("options"):
        fields.append(
            {
                "draft_id": uuid.uuid4().hex,
                "id": definition.pk,
                "key": definition.storage_key,
                "name": definition.name,
                "field_type": definition.field_type,
                "number_type": definition.number_type,
                "in_use": definition.storage_key in used_fields,
                "options": [
                    {
                        "draft_id": uuid.uuid4().hex,
                        "id": option.pk,
                        "key": option.storage_key,
                        "label": option.label,
                        "in_use": option.storage_key in used_options,
                    }
                    for option in definition.options.all()
                ],
            }
        )
    return {"fields": fields}


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _optional_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError({"id": [_("Invalid identifier.")]})


def normalize_field_row(row: dict) -> dict:
    """
    One draft field validated on its own content and returned normalized.

    Raises ValidationError with a dict keyed by "name", "field_type", "number_type" or "options".
    """
    if not isinstance(row, dict):
        raise ValidationError({"name": [_("Invalid field.")]})
    errors = {}
    name = _text(row.get("name"))
    if not name:
        errors["name"] = [_("Enter a name.")]
    elif len(name) > NAME_MAX_LENGTH:
        errors["name"] = [_("Use at most %(max)s characters.") % {"max": NAME_MAX_LENGTH}]

    field_type = row.get("field_type")
    if field_type not in MetadataFieldType.values:
        errors["field_type"] = [_("Choose a type.")]
    number_type = row.get("number_type") or None
    if field_type == MetadataFieldType.NUMBER:
        if number_type not in MetadataNumberType.values:
            errors["number_type"] = [_("Choose a number type.")]
    else:
        number_type = None

    options = []
    if field_type in (MetadataFieldType.MULTIPLE_CHOICE, MetadataFieldType.SINGLE_CHOICE):
        raw_options = row.get("options") or []
        if not isinstance(raw_options, list):
            raw_options = []
        for raw in raw_options:
            if not isinstance(raw, dict):
                continue
            label = _text(raw.get("label"))
            if not label:
                errors.setdefault("options", []).append(_("Every option needs a label."))
                continue
            if len(label) > NAME_MAX_LENGTH:
                errors.setdefault("options", []).append(
                    _("Option labels may use at most %(max)s characters.") % {"max": NAME_MAX_LENGTH}
                )
                continue
            options.append(
                {
                    "draft_id": _text(raw.get("draft_id")) or uuid.uuid4().hex,
                    "id": _optional_int(raw.get("id")),
                    "key": _text(raw.get("key")) or None,
                    "label": label,
                    "in_use": bool(raw.get("in_use")),
                }
            )
        if not options and "options" not in errors:
            errors["options"] = [_("Add at least one option.")]
        elif len(options) > MAX_OPTIONS_PER_FIELD:
            errors.setdefault("options", []).append(
                _("A field may have at most %(max)s options.") % {"max": MAX_OPTIONS_PER_FIELD}
            )
    if errors:
        raise ValidationError(errors)

    return {
        "draft_id": _text(row.get("draft_id")) or uuid.uuid4().hex,
        "id": _optional_int(row.get("id")),
        "key": _text(row.get("key")) or None,
        "name": name,
        "field_type": field_type,
        "number_type": number_type,
        "in_use": bool(row.get("in_use")),
        "options": options,
    }


def validate_draft(intervention, draft) -> list[dict]:
    """
    The whole draft validated against the intervention's persisted definitions.

    Returns the normalized rows in order. Raises ValidationError listing every problem, each
    naming the affected field.
    """
    fields = draft.get("fields") if isinstance(draft, dict) else None
    if not isinstance(fields, list):
        raise ValidationError(_("Invalid metadata draft."))
    if len(fields) > MAX_FIELDS_PER_INTERVENTION:
        raise ValidationError(
            _("An intervention may have at most %(max)s metadata fields.")
            % {"max": MAX_FIELDS_PER_INTERVENTION}
        )

    existing = {}
    if intervention is not None and intervention.pk:
        existing = {
            definition.pk: definition
            for definition in intervention.metadata_fields.prefetch_related("options")
        }

    rows, messages, seen_names = [], [], {}
    for position, raw in enumerate(fields, start=1):
        label = _text(raw.get("name")) if isinstance(raw, dict) else "" or _("field %(n)s") % {"n": position}
        try:
            row = normalize_field_row(raw)
        except ValidationError as error:
            for field_errors in error.message_dict.values():
                for message in field_errors:
                    messages.append(f"{label or _('Field %(n)s') % {'n': position}}: {message}")
            continue
        folded = row["name"].casefold()
        if folded in seen_names:
            messages.append(_("%(name)s: field names must be unique.") % {"name": row["name"]})
        seen_names[folded] = row
        if row["id"] is not None:
            definition = existing.get(row["id"])
            if definition is None:
                messages.append(_("%(name)s: this field no longer exists.") % {"name": row["name"]})
                continue
            option_ids = {option.pk for option in definition.options.all()}
            for option in row["options"]:
                if option["id"] is not None and option["id"] not in option_ids:
                    messages.append(_("%(name)s: an option no longer exists.") % {"name": row["name"]})
                    break
        rows.append(row)
    if messages:
        raise ValidationError(messages)
    return rows


def save_draft(intervention, rows: list[dict]) -> None:
    """
    Reconcile the intervention's definitions with validated draft rows, in one transaction.

    Removed records are deleted, kept ones updated (a real type or number-type change rotates the
    field's key, retiring its values), new ones created with new keys. Names are first moved to
    placeholders so two fields can swap names under the unique constraint. A conflict with what
    another editor saved meanwhile, including a submitted record they deleted, surfaces as
    MetadataDraftError after a full rollback.

    Every analysis that was showing a value this save retires (through a deleted field, a rotated
    key or a deleted option) gets its ``updated`` timestamp set, so its dashboard date reflects
    the change. The stored instance JSON is not touched here; see the module docstring.
    """
    try:
        with transaction.atomic():
            visible_before = _visible_values(intervention)
            existing = {definition.pk: definition for definition in intervention.metadata_fields.all()}
            submitted_ids = {row["id"] for row in rows if row["id"] is not None}
            for pk, definition in existing.items():
                if pk not in submitted_ids:
                    definition.delete()
            for row in rows:
                if row["id"] is not None:
                    definition = _still_present(existing, row["id"])
                    definition.name = f"__placeholder__{uuid.uuid4().hex}"
                    definition.save(update_fields=["name"])
            for order, row in enumerate(rows):
                if row["id"] is not None:
                    definition = _still_present(existing, row["id"])
                    if (definition.field_type, definition.number_type) != (
                        row["field_type"],
                        row["number_type"],
                    ):
                        definition.rotate_key()
                    definition.name = row["name"]
                    definition.field_type = row["field_type"]
                    definition.number_type = row["number_type"]
                    definition.order = order
                    definition.save()
                else:
                    definition = InterventionMetadataField.objects.create(
                        intervention=intervention,
                        name=row["name"],
                        field_type=row["field_type"],
                        number_type=row["number_type"],
                        order=order,
                    )
                _save_options(definition, row)
            _touch_analyses_showing_less(visible_before, _visible_values(intervention))
    except IntegrityError as error:
        raise _conflict_error() from error


def _visible_values(intervention) -> dict[int, tuple[int | None, dict]]:
    """Per instance of the intervention: its analysis id and the values its current definitions show."""
    definitions = list(
        InterventionMetadataField.objects.filter(intervention=intervention).prefetch_related("options")
    )
    return {
        pk: (analysis_id, prune_metadata(definitions, metadata))
        for pk, analysis_id, metadata in InterventionInstance.objects.filter(
            intervention=intervention
        ).values_list("pk", "analysis_id", "metadata")
    }


def _touch_analyses_showing_less(before: dict, after: dict) -> None:
    """
    Set ``updated`` on every analysis whose visible metadata shrank between the two snapshots.

    Pruning only ever removes, so any difference means the analysis now shows less. The timestamp is
    set explicitly because ``auto_now`` does not fire on a queryset update; nothing else on the
    analysis, its lifecycle fields included, is written.
    """
    analysis_ids = set()
    for pk, (analysis_id, visible) in before.items():
        remaining = after.get(pk)
        if analysis_id is not None and remaining is not None and remaining[1] != visible:
            analysis_ids.add(analysis_id)
    if analysis_ids:
        Analysis.objects.filter(pk__in=analysis_ids).update(updated=timezone.now())


def _save_options(definition, row):
    existing = {option.pk: option for option in InterventionMetadataOption.objects.filter(field=definition)}
    if not definition.is_choice:
        for option in existing.values():
            option.delete()
        return
    submitted_ids = {option["id"] for option in row["options"] if option["id"] is not None}
    for pk, option in existing.items():
        if pk not in submitted_ids:
            option.delete()
    for order, draft in enumerate(row["options"]):
        if draft["id"] is not None:
            option = _still_present(existing, draft["id"])
            option.label = draft["label"]
            option.order = order
            option.save()
        else:
            InterventionMetadataOption.objects.create(field=definition, label=draft["label"], order=order)
