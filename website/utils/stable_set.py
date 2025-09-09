from __future__ import annotations

from collections.abc import Iterable

from .unique import unique


class StableSet:
    """Set with stable ordering.
    Used when you need set operations on a list of unique values.

    Implemented by keeping everything in a list and using `unique` when needed.
    """

    def __init__(self, collection: Iterable):
        self._collection = list(collection)

    def add(self, element) -> StableSet:
        self._collection.append(element)
        return self

    def remove(self, element) -> StableSet:
        self._collection = list(unique(self._collection))
        try:
            self._collection.remove(element)
        except ValueError:
            pass
        return self

    def union(self, other: Iterable) -> StableSet:
        self._collection.extend(other)
        return self

    def difference(self, other: Iterable) -> StableSet:
        self._collection = list(unique(self._collection))
        for o in other:
            try:
                self._collection.remove(o)
            except ValueError:
                pass
        return self

    def __add__(self, other):
        return self.union(other)

    def __sub__(self, other):
        return self.difference(other)

    def to_list(self, sort=False) -> list:
        objs = unique(self._collection)
        if sort:
            objs = sorted(objs)
        objs = unique(objs)
        return list(objs)
