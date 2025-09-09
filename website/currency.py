from __future__ import annotations

from babel.numbers import get_currency_name, get_currency_symbol
from django.conf import settings

from website.models import Analysis

ISO_CURRENCY_CODE_NOT_SET = True

if settings.ISO_CURRENCY_CODE == "none":
    ISO_CURRENCY_CODE_NOT_SET = False

if settings.ISO_CURRENCY_CODE is None:
    ISO_CURRENCY_CODE_NOT_SET = False


def currency_code(analysis: Analysis = None) -> str | None:
    if ISO_CURRENCY_CODE_NOT_SET:
        return None
    elif analysis is not None and analysis.currency_code:
        return analysis.currency_code
    else:
        return settings.ISO_CURRENCY_CODE


def currency_name(analysis: Analysis = None):
    if ISO_CURRENCY_CODE_NOT_SET:
        return None
    elif analysis is not None and analysis.currency_code:
        return get_currency_name(analysis.currency_code)
    else:
        return get_currency_name(settings.ISO_CURRENCY_CODE)


def currency_symbol(analysis: Analysis = None) -> str | None:
    if ISO_CURRENCY_CODE_NOT_SET:
        return None
    elif analysis is not None and analysis.currency_code:
        return get_currency_symbol(analysis.currency_code, locale=get_currency_locale())
    else:
        return get_currency_symbol(settings.ISO_CURRENCY_CODE, locale=get_currency_locale())


def get_currency_locale(currency_code: str = "en_US") -> str:
    """
    Currency is always formatted as if we are in America per the client
    """

    return "en_US"
