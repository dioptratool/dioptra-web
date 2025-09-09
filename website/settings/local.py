from .base import *

ENVIRONMENT_TYPE = os.getenv("ENVIRONMENT_TYPE", "local")

DEBUG = True

SECRET_KEY = "local-secret-key"

DATABASES["default"]["HOST"] = "localhost"
DATABASES["default"]["PORT"] = "12432"
DATABASES["default"]["PASSWORD"] = os.getenv("DATABASE_PASSWORD")

# Must match transaction-data-pipeline database service
DATABASES["transaction_store"]["NAME"] = "dioptra_transactions"
DATABASES["transaction_store"]["USER"] = "dioptra"
DATABASES["transaction_store"]["PASSWORD"] = os.getenv("DATABASE_PASSWORD")
DATABASES["transaction_store"]["HOST"] = "localhost"
DATABASES["transaction_store"]["PORT"] = "9005"

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

INTERNAL_IPS = ["localhost", "127.0.0.1"]

INSTALLED_APPS += [
    "django_extensions",
    "debug_toolbar",
]


if DEBUG and "debug_toolbar" in INSTALLED_APPS:
    MIDDLEWARE = [
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    ] + MIDDLEWARE

DEBUG_TOOLBAR_CONFIG = {"JQUERY_URL": None}

DEBUG_TOOLBAR_PANELS = [
    # 'debug_toolbar.panels.versions.VersionsPanel',
    "debug_toolbar.panels.timer.TimerPanel",
    "debug_toolbar.panels.settings.SettingsPanel",
    # 'debug_toolbar.panels.headers.HeadersPanel',
    "debug_toolbar.panels.request.RequestPanel",
    "debug_toolbar.panels.sql.SQLPanel",
    # 'debug_toolbar.panels.staticfiles.StaticFilesPanel',
    "debug_toolbar.panels.templates.TemplatesPanel",
    # 'debug_toolbar.panels.cache.CachePanel',
    # 'debug_toolbar.panels.signals.SignalsPanel',
    # 'debug_toolbar.panels.logging.LoggingPanel',
    # 'debug_toolbar.panels.redirects.RedirectsPanel',
]

BASE_URL = "http://localhost:8000"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

for _provider_fields in SOCIALACCOUNT_PROVIDERS.values():
    if "PROTOCOL" in _provider_fields:
        _provider_fields["PROTOCOL"] = "http"


AUTH_2FA = False
# ISO_CURRENCY_CODE = 'USD'
ISO_CURRENCY_CODE = "EUR"

if sys.platform == "darwin":
    PDF_EXPORT_COMMAND = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
elif sys.platform == "linux":
    PDF_EXPORT_COMMAND = ["/usr/bin/chromium"]
