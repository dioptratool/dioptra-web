import re
from collections import abc
from collections.abc import Callable, Generator, Hashable, Iterable
from typing import Any, TypeVar

from ._legacy import *
from .filtering import Predicate, invert, pull_if, remove_if
from .ident import ident
from .stable_set import StableSet
from .unique import unique

_sentinel = object()

T = TypeVar("T")


class Comparable:
    def __lt__(self, other: Any) -> bool: ...


def dash_to_camel(match):
    group = match.group()
    if len(group) == 3:
        return group[0] + group[2].upper()
    else:
        return group[1].upper()


def columnify(inp: str):
    s = inp
    s = s.replace("ID", "Id")
    s = re.sub(r"^[^a-zA-Z0-9]+", "", s)
    s = re.sub(r"[^a-zA-Z0-9]+$", "", s)
    res = []
    for idx, c in enumerate(s):
        if c.islower():
            res.append(c)
            continue
        if res and res[-1] != "_":
            res.append("_")
        if c.isupper() or c.isnumeric():
            res.append(c.lower())

    return "".join(res)


def count(iterable: Iterable[T], f: Predicate | None = None) -> int:
    """Count items in generator. If you need a filter,
    provide a predicate or filter the generator yourself,
    like `x for x in y if f(x)`.
    """
    c = 0
    for o in iterable:
        if f is None or f(o):
            c += 1
    return c


def find(iterable: Iterable[T], f: Predicate, default=None) -> T:
    for o in iterable:
        if f(o):
            return o
    return default


def clamp(value, minv, maxv):
    v = value
    if maxv is not None:
        v = min(v, maxv)
    if minv is not None:
        v = max(v, minv)
    return v


def remove_prefix(text, prefix):
    if text.startswith(prefix):
        return text[len(prefix) :]
    return text


def get_index(coll: list[T], idx: int, default=None) -> T | None:
    try:
        return coll[idx]
    except IndexError:
        return default


def dig(d: dict, *keys: str, default=None) -> Any:
    if not d:
        return default
    for k in keys:
        if not isinstance(d, dict):
            raise ValueError(f"non-dict in dig chain")
        # noinspection PyUnresolvedReferences
        val = d.get(k, _sentinel)
        if val is _sentinel:
            return default
        d = val
    return d


def dig_obj(d: object, *keys: str, default=None) -> Any:
    if not d:
        return default
    for k in keys:
        val = getattr(d, k, _sentinel)
        if val is _sentinel:
            return default
        d = val
    return d


def flatten(iterables: Iterable[Iterable[T]]) -> list[T]:
    a = []
    for b in iterables:
        a.extend(b)
    return a


def first(iterable: Iterable[T], default=None) -> T:
    return next(iter(iterable), default)


def avg(v):
    return sum(v) / len(v)


def partition(seq: Iterable[T], predicate: Callable[[T], bool]) -> tuple[list[T], list[T]]:
    a, b = [], []

    for item in seq:
        (a if predicate(item) else b).append(item)

    return a, b


def merge(*dicts):
    """Return a dictionary of all dicts merged,
    such that values in later dicts override earlier ones."""
    m = {}
    for d in dicts:
        m.update(d)
    return m


def defaults(*dicts):
    """Like 'merge', but values in later dicts do not override earlier ones."""
    return merge(*reversed(dicts))


def flow(funcs: Iterable[Callable[[T], T]]) -> Callable[[T], T]:
    def flow_callback(t: T) -> T:
        for f in funcs:
            t = f(t)
        return t

    return flow_callback


def group_by(
    items: Iterable[T], key: Callable[[T], Hashable] = lambda x: x
) -> dict[Hashable, tuple[T, list[T]]]:
    result = {}
    for item in items:
        keyval = key(item)
        keyitems = result.setdefault(keyval, [])
        keyitems.append(item)
    return result


def group_and_count(items: Iterable[T], key: Callable[[T], Hashable] = lambda x: x) -> dict[Hashable, int]:
    result = {}
    for item in items:
        keyval = key(item)
        current = result.get(keyval, 0)
        result[keyval] = current + 1
    return result


def aggregate(function, iterable, initial):
    for o in iterable:
        function(initial, o)
    return initial


def flatlist(*args):
    """Something like JavaScript Array.concat.
    If any value in args is iterable, splat it into the result list.

    >>> flatlist([], 1, [2, 3, 4], *[[5, 6], [7, 8]], 9, *[[0]])
    [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]
    """
    result = []
    for arg in args:
        if isinstance(arg, abc.Iterable):
            result.extend(arg)
        else:
            result.append(arg)
    return result


def minmax(seq: Iterable[T], key: Callable[[T], Comparable] = None) -> tuple[T, T]:
    """Return the min and max value of the sequence.
    If no key is given, T must be comparable.
    If key is given, it will be called with each element of seq
    to get the comparable value (like `sorted(seq, key=key)`.
    """
    omin = omax = cmin = cmax = None
    for o in seq:
        if key is not None:
            c = key(o)
        else:
            c = o
        if omin is None or c < cmin:
            omin = o
            cmin = c
        if omax is None or c > cmax:
            omax = o
            cmax = c
    return omin, omax


class immutablemap(dict):
    """
    A dict instance preventing further modification to its key set.  Callers should be aware
    that values are not automatically made immutable.  A narrow use case for this is to
    prevent accidental modification to the dictionary container itself, such as those used
    to encode business rules.

    This isn't like https://www.python.org/dev/peps/pep-0603/ frozenmap.
    """

    def __hash__(self):
        return id(self)

    def __repr__(self):
        return f"immutablemap({super().__repr__()})"

    def _immutable(self, *args, **kws):
        raise TypeError("object is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    update = _immutable
    setdefault = _immutable
    pop = _immutable
    popitem = _immutable


def removeprefix(s: str, prefix: str) -> str:
    if s.startswith(prefix):
        return s[len(prefix) :]
    return s


def iremoveprefix(s: str, prefix: str) -> str:
    if s[: len(prefix)].casefold() == prefix.casefold():
        return s[len(prefix) :]
    return s


def removesuffix(s: str, suffix: str) -> str:
    if s.endswith(suffix):
        return s[: -len(suffix)]
    return s


def iremovesuffix(s: str, suffix: str) -> str:
    if s[-len(suffix) :].casefold() == suffix.casefold():
        return s[: -len(suffix)]
    return s


def chunks(lst: list[T], n) -> Generator[list[T]]:
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]
