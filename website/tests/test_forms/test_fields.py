from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from website.forms.fields import PositiveFixedDecimalField


class TestPositiveFixedDecimalField:
    def test_ignores_spurious_characters(self):
        field = PositiveFixedDecimalField(allow_zero=True)
        assert field.clean(" 40% ") == Decimal("40")
        assert field.clean("1,000") == Decimal("1000")
        assert field.clean("$50") == Decimal("50")
        assert field.clean("33.33") == Decimal("33.33")

    def test_rejects_value_with_no_digits(self):
        field = PositiveFixedDecimalField(allow_zero=True)
        with pytest.raises(ValidationError):
            field.clean("abc")

    def test_rejects_malformed_number(self):
        field = PositiveFixedDecimalField(allow_zero=True)
        with pytest.raises(ValidationError):
            field.clean("40.5.3")
