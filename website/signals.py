from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from website.models import FieldLabelOverrides
from website.models.utils import _get_overrides


@receiver([post_save, post_delete], sender=FieldLabelOverrides)
def _clear_cache(sender, **kwargs):
    _get_overrides.cache_clear()
