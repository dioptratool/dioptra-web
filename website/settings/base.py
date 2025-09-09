import copy
import logging
import os
import sys
from decimal import Decimal

from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _l

ENVIRONMENT_TYPE = os.getenv("ENVIRONMENT_TYPE", "base")

INSTANCE_NAME = "default"

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(BASE_DIR)

# Add the /lib directory to the path.
sys.path.append(os.path.join(PROJECT_DIR, "lib"))

# Static files (CSS, JavaScript, Images)
STATIC_ROOT = os.path.join(PROJECT_DIR, "static/")
STATIC_URL = "/static/"
MEDIA_ROOT = os.path.join(PROJECT_DIR, "media/")
MEDIA_URL = "/media/"
SITE_ID = 1
DOMAIN = os.getenv("DOMAIN", "localhost:8000")

BASE_URL = ""

# Custom User model
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-user-model
AUTH_USER_MODEL = "users.User"

DEBUG = False

DATA_UPLOAD_MAX_NUMBER_FIELDS = None

AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "us-west-2")

# To configure databases, use environment variables,
# or the settings files can configure individual pieces of the dict.
# Something will always need to set the host and port.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DATABASE_NAME", "dioptra"),
        "USER": os.getenv("DATABASE_USER", "dioptra"),
        "PASSWORD": os.getenv("DATABASE_PASSWORD", None),
        "HOST": os.getenv("DATABASE_ENDPOINT", None),
        "PORT": os.getenv("DATABASE_PORT", None),
    },
    "transaction_store": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("TRANSACTION_STORE_DATABASE_NAME", "dioptra_transactions"),
        "USER": os.getenv("TRANSACTION_STORE_USER", "dioptra"),
        "PASSWORD": os.getenv("TRANSACTION_STORE_PASSWORD"),
        "HOST": os.getenv("TRANSACTION_STORE_HOST"),
        "PORT": os.getenv("TRANSACTION_STORE_PORT"),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", None)

ROOT_URLCONF = "website.urls"

INSTALLED_APPS = [
    "website.apps.WebsiteConfig",
    "ombucore.admin",
    "ombucore.imagewidget",
    "ombucore.assets",
    "app_log.apps.AppLogConfig",
    "website.users.apps.UsersAppConfig",
    "website.help.apps.HelpAppConfig",
    "django.forms",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.sites",
    # Third party apps
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "any_urlfield",
    "ckeditor",
    "rules",
    "imagekit",
    "polymorphic_tree",
    "polymorphic",
    "mptt",
    "django_otp",
    "website.email_2fa",
    "django_otp.plugins.otp_email",
    "django_otp.plugins.otp_hotp",
    "taggit_autosuggest",
]

# Support legacy environment variable by mapping it to the modern/current one
if os.getenv("AUTHENTICATION_PROVIDER"):
    os.environ.setdefault("AUTH_PROVIDERS", os.getenv("AUTHENTICATION_PROVIDER"))
# Our oauth backends enabled by environment variables
AUTH_PROVIDERS = [s.strip() for s in os.getenv("AUTH_PROVIDERS", "").lower().split(",") if s]

INCLUDE_USERNAME_AND_PASSWORD_LOGIN_FORM = False

if "dioptra" in AUTH_PROVIDERS or not AUTH_PROVIDERS:
    INCLUDE_USERNAME_AND_PASSWORD_LOGIN_FORM = True

# "dioptra" is not a valid auth provider but instead a placeholder for the Username/Password field
if "dioptra" in AUTH_PROVIDERS:
    AUTH_PROVIDERS.remove("dioptra")

INSTALLED_APPS += [f"website.oauth_providers.{p}" for p in AUTH_PROVIDERS]

MIDDLEWARE = [
    "website.stopwatch.RequestMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "website.email_2fa.middleware.EmailTwoFactorMiddleware",
    "website.sessions.SessionIdleMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "website.context_processors.account_code_descriptions",
                "website.context_processors.dioptra_settings",
                "website.context_processors.include_login",
                "website.help.context_processors.help_context",
                "django.template.context_processors.media",
            ],
        },
    },
]
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

X_FRAME_OPTIONS = "SAMEORIGIN"


DATE_FORMAT = "d-M-Y"  # Dioptra format
DATE_INPUT_FORMATS = [
    "%d-%b-%Y",  # Dioptra format, according to
    # https://docs.python.org/3/library/datetime.html#strftime-and-strptime-behavior
    "%Y-%m-%d",  # Default Django format.
]
TIME_ZONE = "America/Los_Angeles"
USE_TZ = True

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

AUTHENTICATION_BACKENDS = [
    "rules.permissions.ObjectPermissionBackend",
    "django.contrib.auth.backends.ModelBackend",
    "website.permissions.SiteRolePermissionBackend",
    "website.auth_backends.DioptraUserAuthenticationBackend",
]

# #### AWS SES Email #### #
DEFAULT_FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@dioptratool.org")

# django-allauth
# https://django-allauth.readthedocs.io/en/latest/configuration.html
# ------------------------------------------------------------------------------
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"
ACCOUNT_USER_MODEL_USERNAME_FIELD = "email"
ACCOUNT_ALLOW_REGISTRATION = os.getenv("DJANGO_ACCOUNT_ALLOW_REGISTRATION", True)
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_ADAPTER = "website.users.adapters.AccountAdapter"
SOCIALACCOUNT_ADAPTER = "website.users.adapters.SocialAccountAdapter"
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_SUBJECT_PREFIX = ""
SOCIALACCOUNT_LOGIN_ON_GET = True

if str(os.getenv("AUTH_2FA")).lower() == "false":
    AUTH_2FA = False
else:
    AUTH_2FA = True

SOCIALACCOUNT_PROVIDERS = {}

OKTA_OAUTH2_PATH = os.getenv("OKTA_OAUTH2_PATH", None)
if "okta" in AUTH_PROVIDERS:
    if not os.getenv("OKTA_URL"):
        raise ImproperlyConfigured(f"OKTA_URL must be set to your Okta domain. See https://bit.ly/3iJHyuY")
    if not OKTA_OAUTH2_PATH:
        raise ImproperlyConfigured(
            f"OKTA_OAUTH2_PATH must be set like '/oauth2/default/v1'. See https://bit.ly/3iJHyuY"
        )
    SOCIALACCOUNT_PROVIDERS["okta"] = {
        "DEFAULT_URL": os.getenv("OKTA_URL"),
        "PROTOCOL": "https",
    }

ONELOGIN_APP = os.getenv("ONELOGIN_APP")
if "onelogin" in AUTH_PROVIDERS:
    if not ONELOGIN_APP:
        raise ImproperlyConfigured(f"ONELOGIN_APP must be set to your app name, like 'dioptra-dev'")
    SOCIALACCOUNT_PROVIDERS["onelogin"] = {"PROTOCOL": "https"}


MICROSOFT_TENANT_ID = os.getenv("MICROSOFT_TENANT_ID")
if "microsoft" in AUTH_PROVIDERS:
    if not MICROSOFT_TENANT_ID:
        raise ImproperlyConfigured(f"MICROSOFT_TENANT_ID must be set")
    SOCIALACCOUNT_PROVIDERS["microsoft"] = {
        "tenant": MICROSOFT_TENANT_ID,
        "PROTOCOL": "https",
    }


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 8,
        },
    },
    {
        "NAME": "website.validators.NumberValidator",
    },
    {
        "NAME": "website.validators.LetterValidator",
    },
    {
        "NAME": "website.validators.SymbolValidator",
    },
]

# CKEditor
# ------------------------------------------------------------------------------
help_text = {
    "theme": "default",
    "toolbar": [
        [
            "Bold",
            "Italic",
            "Underline",
            "BulletedList",
            "NumberedList",
            "Link",
            "Unlink",
            "Source",
        ],
    ],
    "format_tags": "p;h2;h3;h4;h5;h6;pre",
    "removeDialogTabs": "link:upload;link:advanced",
    "removeButtons": "BrowseServer",
    "forcePasteAsPlainText": True,
    "stylesSet": [],
    "extraPlugins": "autogrow,wordcount",
    "autoGrow_minHeight": 200,
    "autoGrow_maxHeight": 300,
    "bodyClass": "rte",
    "width": "100%",
    "disableNativeSpellChecker": False,
    "dialog_backgroundCoverColor": "rgb(160, 160, 160)",
    "contentsCss": "/static/wysiwyg.css",
    "wordcount": {
        "showParagraphs": False,
        "showWordCount": False,
        "showCharCount": True,
        "countSpacesAsChars": False,
        "countHTML": False,
        "maxWordCount": -1,
        "maxCharCount": 350,
    },
}

# Create one configuration of the help text with a nested "maxCharCount" and another without
help_text_limitless = copy.deepcopy(help_text)
del help_text_limitless["wordcount"]["maxCharCount"]

CKEDITOR_CONFIGS = {
    "default": {
        "theme": "default",
        "toolbar": [
            [
                "Bold",
                "Italic",
                "JustifyLeft",
                "JustifyCenter",
                "JustifyRight",
                "BulletedList",
                "NumberedList",
                "Link",
                "Unlink",
                "Table",
                "HorizontalRule",
                "Format",
                "RemoveFormat",
                "Styles",
                "Source",
                "Ombuimage",
                "Ombudocument",
            ],
        ],
        "format_tags": "p;h2;h3;h4;h5;h6;pre",
        "removeDialogTabs": "link:upload;link:advanced",
        "removeButtons": "BrowseServer",
        "forcePasteAsPlainText": True,
        "stylesSet": [
            {
                "name": "Link - Primary",
                "element": "a",
                "attributes": {"class": "btn btn-primary"},
            },
            {
                "name": "Link - secondary",
                "element": "a",
                "attributes": {"class": "btn btn-secondary"},
            },
        ],
        "extraPlugins": "autogrow,ombuimage",
        "removePlugins": "exportpdf",
        "autoGrow_minHeight": 200,
        "autoGrow_maxHeight": 300,
        "bodyClass": "rte",
        "width": "100%",
        "disableNativeSpellChecker": False,
        "dialog_backgroundCoverColor": "rgb(160, 160, 160)",
        "contentsCss": "/static/wysiwyg.css",
    },
    "help_text": help_text,
    "help_text_limitless": help_text_limitless,
}
ASSET_IMAGE_EMBEDDED_GENERATOR = "assets:asset_embedded_image"

EMPTY_LABEL = _l("Choose one")

# Security Settings
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Strict"

# When using OAuth, the session cookie CANNOT be Strict (it must be Lax or less).
# When we 'log in with Okta', we generate a 'state' and store it in the session
# (which is stored in the DB). This 'state' value is passed through to Okta.
# (see https://auth0.com/docs/protocols/state-parameters for more details about the state param).
#
# Once we complete the OAuth login at, say, https://dioptra.okta.com,
# the browser follows a 302 redirect back to the app at a url like
# https://testing.dioptratool.org?code=xyz&state=whatwassentbefore.
#
# Because this navigation request originated at another site (not dioptratool.org),
# this is a **cross-site request**. The 'samesite=strict' means that
# the browser will NOT send the session cookie to Django;
# because we don't have a session, we cannot look up the 'state' we stored,
# and Django fails to verify the OAuth result.
#
# The solution is to use samesite=lax. This will pass the cookie for
# things like cross-site navigation requests (which OAuth user agent flow requires),
# but not expose it for other types of requests.
#
# For example, some embedded JS at evilsite.com that made a fetch to dioptratool.org
# would NOT include cookies.
#
# If samesite=strict is used, a login where you are not authed with the oauth provider
# will fail for the above reason. However, if you ARE already authed in the oauth provider,
# the login will work. This is because the browser is following a series of 302 redirects,
# so it does not actually change its host and is thus considered a same-site request.
#
# In other words, if you are not logged into Okta (or whatever OAuth), the requests are:
# - POST to dioptra
# - 302 from dioptra to okta
# - 200 from okta
# - POST to okta
# - 302 from okta to dioptra
# - dioptra handles navigation GET, coming from okta.com
#
# But if you are logged into Okta:
# - POST to dioptra
# - 302 to okta
# - 302 from okta to dioptra
# - dioptra handles navigation GET, coming from dioptratool.com
#
SESSION_COOKIE_SAMESITE = "Lax" if AUTH_PROVIDERS else "Strict"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_IDLE_TIMEOUT = 3600  # In seconds

ISO_CURRENCY_CODE = "USD"

COST_LINE_ITEMS_ROW_LIMIT = 5000
IMPORTED_TRANSACTION_LIMIT = 200_000

STOPWATCH_LEVEL = int(os.getenv("STOPWATCH_LEVEL", 0))
# Empty string to not log at all, 0 to log all, > 0 to only log slow stuff
STOPWATCH_LOG_SQL = bool(os.getenv("STOPWATCH_LOG_SQL"))
STOPWATCH_SLOW_SQL = float(os.getenv("STOPWATCH_LOG_SQL", "0.0"))

PDF_EXPORT_COMMAND = ["/usr/bin/google-chrome-stable"]

DEFAULT_CATEGORY = os.getenv("DEFAULT_CATEGORY", "Materials & Activities")
DEFAULT_COST_TYPE = os.getenv("DEFAULT_COST_TYPE", "Program Costs")

LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", "WARNING")
if LOG_LEVEL not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
    logging.warning(
        f"The envar DJANGO_LOG_LEVEL is not set to a valid level (Set to: {LOG_LEVEL}). Using WARNING instead."
    )
    LOG_LEVEL = "WARNING"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "root": {
        "level": LOG_LEVEL,
        "handlers": ["console"],
    },
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s",
        },
    },
    "handlers": {
        "console": {
            "level": LOG_LEVEL,
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "level": LOG_LEVEL,
            "handlers": ["console"],
            "propagate": True,
        },
        "django.template": {
            "level": LOG_LEVEL,
            "handlers": ["console"],
            "propagate": False,
        },
        "django.db": {
            "level": LOG_LEVEL,
            "handlers": ["console"],
            "propagate": False,
        },
    },
}


DECIMAL_PRECISION = Decimal("0.0001")
DECIMAL_PLACES = 4

# Transitional setting.  This can be removed for Django >=6
FORMS_URLFIELD_ASSUME_HTTPS = True
