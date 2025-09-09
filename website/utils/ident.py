from typing import TypeVar

T = TypeVar("T")


def ident(x: T) -> T:
    return x
