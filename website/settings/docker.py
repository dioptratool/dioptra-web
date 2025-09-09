from .base import *

DEBUG_TOOLBAR_PATCH_SETTINGS = False

ENVIRONMENT_TYPE = os.environ.get("ENVIRONMENT_TYPE", "docker")

DEBUG = True

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", None)

DATABASES["default"]["HOST"] = "db"
DATABASES["default"]["PORT"] = "5432"
DATABASES["transaction_store"]["HOST"] = "transaction_db"
DATABASES["transaction_store"]["PORT"] = "5432"

ALLOWED_HOSTS = ["localhost"]

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
    # 'debug_toolbar.panels.sql.SQLPanel',
    # 'debug_toolbar.panels.staticfiles.StaticFilesPanel',
    "debug_toolbar.panels.templates.TemplatesPanel",
    # 'debug_toolbar.panels.cache.CachePanel',
    # 'debug_toolbar.panels.signals.SignalsPanel',
    # 'debug_toolbar.panels.logging.LoggingPanel',
    # 'debug_toolbar.panels.redirects.RedirectsPanel',
]

BASE_URL = "http://localhost:8000"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

if "okta" in SOCIALACCOUNT_PROVIDERS:
    SOCIALACCOUNT_PROVIDERS["okta"]["PROTOCOL"] = "http"

AUTH_2FA = False
# ISO_CURRENCY_CODE = 'USD'
ISO_CURRENCY_CODE = "EUR"
