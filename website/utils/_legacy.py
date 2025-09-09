from collections import namedtuple


def list_dedupe(l):
    """
    Takes a list of items and removes duplicates, maintaining order.

    A `set` won't work because order isn't guaranteed.
    """
    return list(dict.fromkeys(l))


Choice = namedtuple("Choice", "name value label")


class Choices:
    @classmethod
    def names(cls):
        return [name for name in vars(cls) if name.isupper()]

    @classmethod
    def values(cls):
        return [getattr(cls, n) for n in cls.names()]

    @classmethod
    def items(cls):
        return [(n, getattr(cls, n)) for n in cls.names()]

    @classmethod
    def choices(cls):
        return [(value, cls.label(name)) for name, value in cls.items()]

    @classmethod
    def label(cls, name):
        return (
            cls.labels.get(name)
            if hasattr(cls, "labels") and name in cls.labels
            else name.replace("_", " ").title()
        )

    @classmethod
    def as_dict(cls):
        return dict(cls.choices())

    @classmethod
    def as_named(cls):
        return [Choice(name, value, cls.label(name)) for name, value in cls.items()]
