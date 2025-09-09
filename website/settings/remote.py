import http.client

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

from website.settings.base import *

ENVIRONMENT_TYPE = os.environ.get("ENVIRONMENT_TYPE", "remote")

INSTANCE_NAME = os.environ.get("INSTANCE_NAME")


def get_local_ip():
    try:
        get_token_headers = {"X-aws-ec2-metadata-token-ttl-seconds": 21600}
        get_token = http.client.HTTPConnection("169.254.169.254", timeout=2)
        get_token.request("PUT", "/latest/api/token", headers=get_token_headers)
        response_get_token = get_token.getresponse()
        token = response_get_token.read().decode("utf-8")

        headers = {"X-aws-ec2-metadata-token": token}
        connection = http.client.HTTPConnection("169.254.169.254", timeout=2)
        connection.request("GET", "/latest/meta-data/local-ipv4", headers=headers)
        response = connection.getresponse()
        return response.read().decode("utf-8")
    except Exception:
        return None


# BASE_URL = os.environ.get('BASE_URL')
BASE_URL = f"https://{DOMAIN}"

ALLOWED_HOSTS = ["", "localhost", get_local_ip(), DOMAIN]
STATIC_ROOT = "/var/www/static/"
STATIC_URL = "/static/"
MEDIA_ROOT = "/var/www/media/"
MEDIA_URL = "/media/"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 15768000  # Trigger Strict-Transport-Security header.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True


def sentry_before_send(event, hint):
    if event.get("logger") == "django.security.DisallowedHost":
        return None
    event["release"] = os.environ.get("APPLICATION_VERSION", "unknown")
    event["environment"] = os.environ.get("ENVIRONMENT_TYPE", "production")
    return event


if os.environ.get("SENTRY_DSN", None):
    sentry_sdk.init(
        dsn=os.environ.get("SENTRY_DSN", None),
        integrations=[DjangoIntegration()],
        before_send=sentry_before_send,
    )

# #### AWS SES Email #### #
EMAIL_BACKEND = "django_ses.SESBackend"
AWS_SES_REGION_NAME = os.environ.get("SES_REGION", AWS_DEFAULT_REGION)
AWS_SES_REGION_ENDPOINT = f"email.{AWS_SES_REGION_NAME}.amazonaws.com"

# Security settings
CSRF_COOKIE_SECURE = True
# Only allow cookies on HTTPS # https://docs.djangoproject.com/en/2.2/ref/settings/#csrf-cookie-secure
SESSION_COOKIE_SECURE = True


if "ISO_CURRENCY_CODE" not in os.environ:
    raise ImproperlyConfigured("The environment variable ISO_CURRENCY_CODE is not set")

ISO_CURRENCY_CODE = os.environ.get("ISO_CURRENCY_CODE")

PDF_EXPORT_COMMAND = ["/usr/bin/chromium-browser"]

# Security Stuff
SILENCED_SYSTEM_CHECKS = ["security.W019"]
# W019 - Ombucore uses frames for all it's panels

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_SSL_REDIRECT = True
X_FRAME_OPTIONS = "SAMEORIGIN"
SECURE_HSTS_PRELOAD = True
