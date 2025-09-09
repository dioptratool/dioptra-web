from collections.abc import Iterable
from typing import TypeVar

from .ident import ident

T = TypeVar("T")


def unique(seq: Iterable[T], key=ident) -> Iterable[T]:
    """
    Remove duplicates while preserving order
    https://www.peterbe.com/plog/uniqifiers-benchmark

    If key is given, use it to produce the unique key by which to compare results.
    """
    seen = set()
    seen_add = seen.add
    for x in seq:
        k = key(x)
        if k in seen:
            continue
        seen_add(k)
        yield x
