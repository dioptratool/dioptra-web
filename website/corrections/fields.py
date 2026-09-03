"""
What the correction panels show: which custom fields are visible, the closed lists for the code
fields, and the prefill values computed over a selection.
"""

from __future__ import annotations

from collections.abc import Iterable

from website.models import AccountCodeDescription, Analysis, CostLineItem, Transaction
from website.models.field_label import FieldLabelOverrides
from .labels import BUDGET_CUSTOM_FIELDS
from .patch import CUSTOM_FIELD_NAMES, EDITABLE_GROUPING_FIELDS


class _Multiple:
    """The selected records disagree on a field's value (spec section 5)."""

    def __repr__(self):
        return "<multiple values>"


MULTIPLE = _Multiple()


def visible_custom_fields(analysis: Analysis, family: str) -> list[str]:
    """
    A panel shows a custom field when it is populated somewhere in the analysis or its label has
    been overridden in Field Label Overrides (section 5).
    """
    if family == BUDGET_CUSTOM_FIELDS:
        populated = {column["field"] for column in analysis.cost_item_custom_fields}
    else:
        populated = {column["field"] for column in analysis.transaction_custom_fields}
    overrides = FieldLabelOverrides.get()
    named = {
        name
        for name in CUSTOM_FIELD_NAMES
        if getattr(overrides, f"{family}_{name}_overridden", False)
        and getattr(overrides, f"{family}_{name}", None)
    }
    return [name for name in CUSTOM_FIELD_NAMES if name in populated or name in named]


def code_suggestions(analysis: Analysis, field: str) -> list[str]:
    """Distinct values of a code field across the analysis's cost items and transactions."""
    if field not in EDITABLE_GROUPING_FIELDS:
        raise ValueError(field)
    values = set(analysis.cost_line_items.values_list(field, flat=True).distinct())
    values |= set(analysis.transactions.values_list(field, flat=True).distinct())
    return sorted(value for value in values if value)


def grant_choices(analysis: Analysis) -> list[str]:
    """
    The grants a correction may choose: every grant code present on the analysis's cost items and
    transactions, plus the grants the analysis was defined with (section 5).

    The two lists can disagree either way: a budget upload is not validated against the defined
    grants, and a defined grant may have no rows yet. They can also differ only in case, because
    the transaction import upper-cases grant codes while the defined list is stored as typed; then
    the spelling present in the data wins, since choosing the other spelling would start a separate
    grant table.
    """
    present = code_suggestions(analysis, "grant_code")
    seen = {grant.casefold() for grant in present}
    choices = list(present)
    for grant in analysis.query_grants():
        if grant and grant.casefold() not in seen:
            choices.append(grant)
            seen.add(grant.casefold())
    return sorted(choices, key=str.casefold)


def account_code_choices(analysis: Analysis) -> list[tuple[str, str]]:
    """
    (code, label) pairs for the Account Code list: the codes present on the analysis's rows plus
    every code in the organisation's Account Code Description lookup, so rows can be moved to a
    known account code the import never carried. Options display as "code — description" where
    the lookup has a mapping and as the raw code otherwise; the value is always the code
    (section 5).
    """
    descriptions = AccountCodeDescription.as_map()
    codes = set(code_suggestions(analysis, "account_code")) | set(descriptions)
    choices = []
    for code in sorted(codes):
        description = descriptions.get(code)
        label = f"{code} — {description.account_description}" if description else code
        choices.append((code, label))
    return choices


def uniform(values: Iterable) -> object:
    """The one value every record shares, ``MULTIPLE`` when they differ, None for no records."""
    distinct = set(values)
    if not distinct:
        return None
    if len(distinct) == 1:
        return distinct.pop()
    return MULTIPLE


def transaction_prefill(transactions: list[Transaction]) -> dict[str, object]:
    """
    Per-field prefill for a transaction panel over the selected transactions.

    Cost Type, Category and the cost item description come from the parent cost items, where
    they live (section 5).
    """
    values = {
        "cost_type": uniform(t.cost_line_item.config.cost_type_id for t in transactions),
        "category": uniform(t.cost_line_item.config.category_id for t in transactions),
        "description": uniform(t.cost_line_item.budget_line_description for t in transactions),
        "transaction_description": uniform(t.transaction_description for t in transactions),
        "date": uniform(t.date for t in transactions),
        "amount": uniform(t.amount_in_instance_currency for t in transactions),
    }
    for name in EDITABLE_GROUPING_FIELDS:
        values[name] = uniform(getattr(t, name) for t in transactions)
    for name in CUSTOM_FIELD_NAMES:
        values[name] = uniform(getattr(t, name) for t in transactions)
    return values


def cost_item_prefill(
    cost_line_items: list[CostLineItem], transactions: list[Transaction] | None = None
) -> dict[str, object]:
    """
    Per-field prefill for a cost-item panel over the selected cost items.

    On a transaction-based analysis the custom fields come from the items' transactions (the panel
    batch-edits them and Budget Custom Fields are always empty); pass those transactions.
    """
    values = {
        "cost_type": uniform(c.config.cost_type_id for c in cost_line_items),
        "category": uniform(c.config.category_id for c in cost_line_items),
        "description": uniform(c.budget_line_description for c in cost_line_items),
        "amount": uniform(c.total_cost for c in cost_line_items),
    }
    for name in EDITABLE_GROUPING_FIELDS:
        values[name] = uniform(getattr(c, name) for c in cost_line_items)
    records = transactions if transactions is not None else cost_line_items
    for name in CUSTOM_FIELD_NAMES:
        values[name] = uniform(getattr(r, name) for r in records)
    return values
