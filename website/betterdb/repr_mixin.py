from datetime import datetime


class ReprMixin:
    """Mixin that overrides the repr method to
    display all non-empty public fields.
    """

    def __repr__(self):
        kvps = [f"{k}={_fmt_value(k, v)}" for (k, v) in _public_fields(self) if v]
        valuestr = ", ".join(kvps)
        return f"{type(self).__name__}({valuestr})"


def _public_fields(m):
    f = [(k, v) for (k, v) in m.__dict__.items() if not k.startswith("_")]
    return f


def _fmt_value(k, v):
    if isinstance(v, datetime):
        return v.isoformat()
    return repr(v)
