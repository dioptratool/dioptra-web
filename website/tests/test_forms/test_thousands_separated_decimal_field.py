"""
`ThousandsSeparatedDecimalField` accepts the thousands separators amounts are
displayed with, so a value copied out of the table validates in an edit panel.
"""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from website.forms.fields import ThousandsSeparatedDecimalField


@pytest.mark.parametrize(
    ("entered", "expected"),
    [
        ("1,000", Decimal("1000")),
        ("1,000.50", Decimal("1000.50")),
        ("12,345,678.9012", Decimal("12345678.9012")),
        ("-1,000", Decimal("-1000")),
        (" 1,000 ", Decimal("1000")),
        ("1000", Decimal("1000")),
        ("0", Decimal("0")),
        ("-0.5", Decimal("-0.5")),
    ],
)
def test_separators_are_accepted_and_the_sign_is_kept(entered, expected):
    field = ThousandsSeparatedDecimalField(max_digits=14, decimal_places=4)
    assert field.clean(entered) == expected


@pytest.mark.parametrize("entered", ["1,00o", "abc", "1,000.5.5", "--1,000"])
def test_values_that_are_not_numbers_are_still_rejected(entered):
    field = ThousandsSeparatedDecimalField(max_digits=14, decimal_places=4)
    with pytest.raises(ValidationError):
        field.clean(entered)


def test_decimal_places_are_still_enforced():
    field = ThousandsSeparatedDecimalField(max_digits=14, decimal_places=4)
    with pytest.raises(ValidationError):
        field.clean("1,000.12345")


def test_blank_stays_blank_when_not_required():
    # A blank Amount means "make no change" on a correction panel.
    field = ThousandsSeparatedDecimalField(max_digits=14, decimal_places=4, required=False)
    assert field.clean("") is None
