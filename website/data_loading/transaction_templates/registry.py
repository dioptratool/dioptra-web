from __future__ import annotations

import importlib
import pkgutil

from django.core.exceptions import ImproperlyConfigured
from django.db.utils import OperationalError, ProgrammingError

from .base import TransactionTemplate

DEFAULT_TRANSACTION_TEMPLATE_ID = "dioptra_default"
TRANSACTION_TEMPLATE_PACKAGE = "website.data_loading.transaction_templates"


def get_active_transaction_template_id() -> str:
    from website.models import Settings

    try:
        configured_id = Settings.objects.values_list("transaction_data_template", flat=True).first()
    except (OperationalError, ProgrammingError):
        configured_id = None

    configured_id = str(configured_id or "").strip().lower()
    return configured_id or DEFAULT_TRANSACTION_TEMPLATE_ID


def get_enabled_transaction_template_ids() -> list[str]:
    return [get_active_transaction_template_id()]


def get_available_transaction_template_ids() -> list[str]:
    package = importlib.import_module(TRANSACTION_TEMPLATE_PACKAGE)
    template_ids = [
        module_info.name
        for module_info in pkgutil.iter_modules(package.__path__)
        if module_info.ispkg and not module_info.name.startswith("_")
    ]
    return sorted(
        template_ids,
        key=lambda template_id: (template_id != DEFAULT_TRANSACTION_TEMPLATE_ID, template_id),
    )


def get_transaction_template_choices() -> list[tuple[str, str]]:
    return [
        (template.id, template.label)
        for template in (
            _load_template_class(template_id)() for template_id in get_available_transaction_template_ids()
        )
    ]


def get_transaction_template(template_id: str | None = None) -> TransactionTemplate:
    active_id = get_active_transaction_template_id()
    selected_id = (template_id or active_id).strip().lower()

    if selected_id != active_id:
        raise ImproperlyConfigured(
            f'Transaction data template "{selected_id}" is not active. ' f'Active template: "{active_id}".'
        )

    template_cls = _load_template_class(selected_id)
    template = template_cls()
    if template.id != selected_id:
        raise ImproperlyConfigured(
            f'Transaction data template "{selected_id}" has mismatched id "{template.id}".'
        )
    return template


def get_enabled_transaction_templates() -> list[TransactionTemplate]:
    return [get_transaction_template()]


def _load_template_class(template_id: str) -> type[TransactionTemplate]:
    module_path = f"{TRANSACTION_TEMPLATE_PACKAGE}.{template_id}"
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as e:
        if e.name == module_path:
            raise ImproperlyConfigured(
                f'Transaction data template "{template_id}" was not found. '
                f"Create {module_path} or select a different transaction data template."
            ) from e
        raise

    template_cls = getattr(module, "Template", None)
    if template_cls is None:
        raise ImproperlyConfigured(
            f'Transaction data template "{template_id}" does not expose a Template class.'
        )
    if not issubclass(template_cls, TransactionTemplate):
        raise ImproperlyConfigured(
            f'Transaction data template "{template_id}" Template must extend TransactionTemplate.'
        )
    return template_cls
