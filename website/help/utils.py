from functools import lru_cache

from .models import HelpItem


@lru_cache(maxsize=1)
def get_helpitems() -> dict[str, HelpItem]:
    return {t.identifier: t for t in HelpItem.objects.all()}
