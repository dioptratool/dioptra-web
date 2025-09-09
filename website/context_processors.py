from django.conf import settings

from website.currency import currency_code, currency_name, currency_symbol
from website.models import AccountCodeDescription, Settings


def account_code_descriptions(request):
    return {
        "account_code_descriptions": AccountCodeDescription.as_map(),
    }


def dioptra_settings(request):
    return {
        "dioptra_settings": Settings.objects.first(),
        "currency_config": {
            "symbol": currency_symbol(),
            "code": currency_code(),
            "name": currency_name(),
        },
    }


def include_login(request):
    return {
        "INCLUDE_USERNAME_AND_PASSWORD_LOGIN_FORM": settings.INCLUDE_USERNAME_AND_PASSWORD_LOGIN_FORM,
    }
