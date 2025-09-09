from .local import *

ENVIRONMENT_TYPE = os.environ.get("ENVIRONMENT_TYPE", "test")

DATABASES["transaction_store"]["NAME"] = "dioptra_transactions"
DATABASES["transaction_store"]["USER"] = "dioptra"
DATABASES["transaction_store"]["PASSWORD"] = os.getenv("DATABASE_PASSWORD")
DATABASES["transaction_store"]["PORT"] = "9005"

MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"
