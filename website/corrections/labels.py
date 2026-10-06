"""
Displayed labels for correctable fields.

Labels resolve through the organization-configured Field Label Overrides exactly as the table
headers do (spec section 5), so the panels and the application log name fields the way the user
sees them.
"""

from __future__ import annotations

from django.utils.translation import gettext as _

from website.models.field_label import FieldLabelOverrides
from .patch import CUSTOM_FIELD_NAMES

# What kind of record a panel edits. It decides which override keys name Site and Amount.
COST_ITEM = "cost_item"
TRANSACTION = "transaction"

# Which family of custom fields a panel offers (section 5): Budget Custom Fields on
# budget-analysis cost-item panels, Transaction Custom Fields everywhere else.
BUDGET_CUSTOM_FIELDS = "ci"
TRANSACTION_CUSTOM_FIELDS = "tr"

CUSTOM_FIELD_DEFAULT_LABELS = {
    BUDGET_CUSTOM_FIELDS: "Budget Custom Field",
    TRANSACTION_CUSTOM_FIELDS: "Transaction Custom Field",
}

# Steps a correction can be made from, with the names the log uses for them.
STEP_LABELS = {
    "categorize": "Confirm Categories",
    "allocate": "Allocate Intervention Costs",
}


def custom_field_label(family: str, name: str) -> str:
    """The displayed label of ``dummy_field_N`` in the given family, honouring overrides."""
    number = name.rsplit("_", 1)[-1]
    default = f"{CUSTOM_FIELD_DEFAULT_LABELS[family]} {number}"
    return FieldLabelOverrides.label_for(f"{family}_{name}", default) or default


def field_labels(record_kind: str, custom_family: str) -> dict[str, str]:
    """Internal field name -> displayed label, for every field a correction can carry."""
    prefix = "ci" if record_kind == COST_ITEM else "tr"
    labels = {
        "cost_type": _("Cost Type"),
        "category": _("Category"),
        # The cost item's description; a transaction panel names it the way the import does.
        "description": FieldLabelOverrides.label_for(
            "ci_budget_line_description",
            _("Budget Line Description") if record_kind == TRANSACTION else _("Cost Item Description"),
        ),
        "transaction_description": _("Transaction Description"),
        "grant_code": FieldLabelOverrides.label_for("ci_grant_code", _("Grant")),
        "site_code": FieldLabelOverrides.label_for(f"{prefix}_site_code", _("Site")),
        "sector_code": FieldLabelOverrides.label_for("ci_sector_code", _("Sector Code")),
        "account_code": FieldLabelOverrides.label_for("ci_account_code", _("Account Code")),
        "date": FieldLabelOverrides.label_for("tr_date", _("Date")),
        "amount": FieldLabelOverrides.label_for(
            "tr_amount" if record_kind == TRANSACTION else "ci_total_cost", _("Amount")
        ),
    }
    for name in CUSTOM_FIELD_NAMES:
        labels[name] = custom_field_label(custom_family, name)
    return labels
