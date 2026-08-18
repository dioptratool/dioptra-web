from __future__ import annotations

from babel.numbers import get_currency_name, get_currency_symbol
from django.conf import settings

from website.models import Analysis


def iso_currency_code_is_set() -> bool:
    return settings.ISO_CURRENCY_CODE not in [None, "none"]


def instance_currency_code() -> str | None:
    """The single currency this instance is configured for, or None when it has none."""

    if not iso_currency_code_is_set():
        return None
    return settings.ISO_CURRENCY_CODE


def currency_code(analysis: Analysis = None) -> str | None:
    if not iso_currency_code_is_set():
        return None
    if analysis is not None and analysis.currency_code:
        return analysis.currency_code
    return settings.ISO_CURRENCY_CODE


def currency_name(analysis: Analysis = None):
    if not iso_currency_code_is_set():
        return None
    if analysis is not None and analysis.currency_code:
        return get_currency_name(analysis.currency_code, locale=get_currency_locale())
    return get_currency_name(settings.ISO_CURRENCY_CODE, locale=get_currency_locale())


def currency_symbol(analysis: Analysis = None) -> str | None:
    if not iso_currency_code_is_set():
        return None
    if analysis is not None and analysis.currency_code:
        return get_currency_symbol(analysis.currency_code, locale=get_currency_locale())
    return get_currency_symbol(settings.ISO_CURRENCY_CODE, locale=get_currency_locale())


def get_currency_locale(currency_code: str = "en_US") -> str:
    """
    Currency is always formatted as if we are in America per the client
    """

    return "en_US"
