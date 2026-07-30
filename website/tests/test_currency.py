from types import SimpleNamespace
from unittest.mock import patch

from django.test import override_settings

from website.currency import currency_name


@override_settings(ISO_CURRENCY_CODE="USD")
def test_currency_name_uses_explicit_locale_when_babel_locale_is_missing():
    with patch("babel.numbers.LC_MONETARY", None):
        assert currency_name() == "US Dollar"


@override_settings(ISO_CURRENCY_CODE="USD")
def test_currency_name_uses_analysis_currency_with_explicit_locale():
    analysis = SimpleNamespace(currency_code="EUR")

    with patch("babel.numbers.LC_MONETARY", None):
        assert currency_name(analysis) == "Euro"
