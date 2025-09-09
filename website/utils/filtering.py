from collections.abc import Callable, Iterable
from typing import TypeVar

T = TypeVar("T")

Predicate = Callable[[T], bool]


def invert(f: Callable) -> Callable:
    return lambda *a, **kw: not f(*a, **kw)


def remove_if(seq: Iterable[T], predicate: Predicate) -> Iterable[T]:
    """Return a generator with values that predicate returns truthy for."""
    return (x for x in seq if not predicate(x))


def pull_if(seq: list[T], predicate: Predicate) -> list[T]:
    """Pop values from seq where predicate returns truthy for."""
    pulled = []
    # Walk the list backwards so we can pop indices reliably.
    for idx in reversed(range(len(seq))):
        if predicate(seq[idx]):
            pulled.append(seq.pop(idx))
    return pulled
