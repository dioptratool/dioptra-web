from __future__ import annotations

import dataclasses
import datetime
from collections.abc import Mapping
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from website.models import Category, CostType

# The raw grouping key of a transaction-derived cost item, in key order (spec section 2).
GROUPING_FIELDS = (
    "country_code",
    "grant_code",
    "budget_line_code",
    "account_code",
    "site_code",
    "sector_code",
)

# Country and budget line code are part of the key but cannot be corrected in-app (section 14).
EDITABLE_GROUPING_FIELDS = ("grant_code", "site_code", "sector_code", "account_code")

CUSTOM_FIELD_NAMES = tuple(f"dummy_field_{n}" for n in range(1, 6))

# Every field a correction can carry, in the order of the section 5 matrix. Used for stable
# ordering of "fields changed" in the application log.
FIELD_ORDER = (
    "cost_type",
    "category",
    "description",
    "transaction_description",
    "grant_code",
    "site_code",
    "sector_code",
    "account_code",
    "date",
    "amount",
    *CUSTOM_FIELD_NAMES,
)


@dataclasses.dataclass(frozen=True)
class CorrectionPatch:
    """
    The values a correction applies to every selected record.

    ``None`` means "make no change to this field" (section 5); a custom field that is absent from
    ``custom_fields`` is likewise untouched. Text values are expected already trimmed by the form.
    """

    cost_type: CostType | None = None
    category: Category | None = None
    # Cost item description (CostLineItem.budget_line_description).
    description: str | None = None
    transaction_description: str | None = None
    grant_code: str | None = None
    site_code: str | None = None
    sector_code: str | None = None
    account_code: str | None = None
    date: datetime.date | None = None
    amount: Decimal | None = None
    custom_fields: Mapping[str, str] = dataclasses.field(default_factory=dict)

    def __post_init__(self):
        unknown = set(self.custom_fields) - set(CUSTOM_FIELD_NAMES)
        if unknown:
            raise ValueError(f"Unknown custom fields: {sorted(unknown)}")
        # Normalise so that a custom field explicitly passed as None is "no change" too.
        object.__setattr__(
            self,
            "custom_fields",
            {name: value for name, value in self.custom_fields.items() if value is not None},
        )

    @property
    def changes_grouping(self) -> bool:
        return any(getattr(self, name) is not None for name in EDITABLE_GROUPING_FIELDS)

    @property
    def changes_categorization(self) -> bool:
        return self.cost_type is not None or self.category is not None

    def supplied_fields(self) -> list[str]:
        """The field names this patch carries a value for, in matrix order."""
        supplied = []
        for name in FIELD_ORDER:
            if name in CUSTOM_FIELD_NAMES:
                if name in self.custom_fields:
                    supplied.append(name)
            elif getattr(self, name) is not None:
                supplied.append(name)
        return supplied

    def transaction_values(self) -> dict[str, object]:
        """
        The Transaction column values to write on every selected transaction.

        Amount is the single displayed analysis-currency amount and is written to both stored
        amount columns, preserving the import invariant that they are equal (section 8).
        """
        values: dict[str, object] = {}
        for name in EDITABLE_GROUPING_FIELDS:
            value = getattr(self, name)
            if value is not None:
                values[name] = value
        if self.transaction_description is not None:
            values["transaction_description"] = self.transaction_description
        if self.date is not None:
            values["date"] = self.date
        if self.amount is not None:
            values["amount_in_instance_currency"] = self.amount
            values["amount_in_source_currency"] = self.amount
        values.update(self.custom_fields)
        return values

    def cost_line_item_values(self) -> dict[str, object]:
        """The CostLineItem column values a budget cost item takes from this patch."""
        values: dict[str, object] = {}
        for name in EDITABLE_GROUPING_FIELDS:
            value = getattr(self, name)
            if value is not None:
                values[name] = value
        if self.description is not None:
            values["budget_line_description"] = self.description
        if self.amount is not None:
            values["total_cost"] = self.amount
        values.update(self.custom_fields)
        return values
