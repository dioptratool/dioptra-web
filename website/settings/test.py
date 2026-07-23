from .local import *

ENVIRONMENT_TYPE = os.environ.get("ENVIRONMENT_TYPE", "test")

DATABASES["transaction_store"]["NAME"] = os.getenv("TRANSACTION_STORE_DATABASE_NAME", "dioptra_transactions")
DATABASES["transaction_store"]["USER"] = os.getenv("TRANSACTION_STORE_USER", "dioptra")
DATABASES["transaction_store"]["PASSWORD"] = os.getenv(
    "TRANSACTION_STORE_PASSWORD", os.getenv("DATABASE_PASSWORD")
)
DATABASES["transaction_store"]["PORT"] = os.getenv("TRANSACTION_STORE_PORT", "9005")

MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"
