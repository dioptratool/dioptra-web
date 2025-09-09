import inspect
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def require_prefetch(obj, name: str):
    """
    Helper that ensures prefetches are being done for performance-critical parts of code.
    Logs a warning if a prefetch is missing
    """

    cache = getattr(obj, "_prefetched_objects_cache", None)

    if not cache or name not in cache:
        caller_frame = inspect.stack()[1]
        if settings.DEBUG:
            logger.warning(
                f"Missing prefetch for `{name}` on {obj.__class__.__name__}(pk={obj.pk}) called from `{caller_frame.function} in {caller_frame.filename}:{caller_frame.lineno}`. "
                "Consider adding prefetch_related() to improve performance."
            )
        # Fall back to direct query
        return getattr(obj, name).all()

    return cache[name]
