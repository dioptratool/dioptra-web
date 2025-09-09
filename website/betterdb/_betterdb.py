import contextlib

import django.core.files
from django.core.exceptions import EmptyResultSet
from django.db import connections, models
from django.db.models import QuerySet
from django.utils import timezone
from psycopg import sql

_IGNORE = object()
_ignore_fields = {"associations"}


def _list2arr(v):
    if v:
        assert isinstance(
            v[0], int
        ), "bulk insert only supported for int arrays, need to add escaping support"
    return "{" + ",".join(map(str, v)) + "}"


_adapters = {
    models.Model: _IGNORE,
    django.core.files.File: lambda f: f.name,
    django.core.files.base.ContentFile: lambda f: f.name,
    list: _list2arr,
}


def to_bulk_dicts(instances: list[models.Model]) -> list[dict]:
    """Turn a list of unsaved models into dictionaries that can be used for
    a postgres-extras bulk upsert.
    Dictionaries cannot have different keys but we also want to avoid passing None where possible,
    so cannot use the entire object dict.
    """
    if not instances:
        return []

    slim_dicts = []
    key_superset = set()
    constant_fields = {}
    now = timezone.now()
    for field in instances[0]._meta.fields:
        if field.null:
            # We don't need constant fields if we allow null
            continue
        needs_now = getattr(field, "auto_now", None) or getattr(field, "auto_now_add", None)
        if needs_now:
            constant_fields[field.db_column or field.name] = now
    for m in instances:
        d = dict(constant_fields)
        for k, v in m.__dict__.items():
            if v is None or k.startswith("_") or k in _ignore_fields:
                continue
            adapter = _adapters.get(type(v))
            if adapter:
                v = adapter(v)
                if v == _IGNORE:
                    continue
            key_superset.add(k)

            d[k] = v

        slim_dicts.append(d)
    full_dicts = []
    for slim in slim_dicts:
        full = {k: None for k in key_superset}
        full.update(slim)
        full_dicts.append(full)
    return full_dicts


def build_dynamic_column_strings(cursor, column_names: list[str]) -> tuple[sql.SQL, str]:
    """Given a series of column names,
    return an escaped string value that can be formatted into an SQL statement as a seires of colum names,
    and the '%s' placeholders that can be used in a VALUES statement.
    """
    col_str = format_identifiers(cursor, column_names)
    value_placeholders = ", ".join(["%s"] * len(column_names))
    return col_str, value_placeholders


def format_identifiers(cursor, names: list[str], qualifier=None) -> sql.SQL:
    if not qualifier:
        qualifier = ""
    elif not qualifier.endswith("."):
        qualifier += "."
    return (
        sql.SQL(", ".join([f"{qualifier}{{}}"] * len(names)))
        .format(*[sql.Identifier(c) for c in names])
        .as_string(cursor)
    )


@contextlib.contextmanager
def django_cursor(model_cls):
    with connections[model_cls.objects.db].cursor() as cur:
        yield cur


@contextlib.contextmanager
def psyco_cursor(model_cls):
    with django_cursor(model_cls) as cur:
        yield cur.cursor


def delete(qs: QuerySet) -> int:
    """Delete a queryset by going directly to the database.

    This totally bypasses Django, which means:

    - It's fast and executes just one query
    - No signals or hooks are called
    - It is limited to a delete that can be expressed in one query.
      Django actually lets you do qs._raw_delete() and it will split your query
      into multiple tables if needed. But it also does not work with UNION,
      as per https://code.djangoproject.com/ticket/32333
    """
    model = qs.model
    pk = model._meta.pk.name
    conn = connections[model.objects.db]

    qs = qs.values(pk)
    query = qs.query
    try:
        stmt, params = query.as_sql(query.get_compiler(connection=conn), conn)
    except EmptyResultSet:
        # This is absurd: https://code.djangoproject.com/ticket/22973
        return 0
    with conn.cursor() as cur:
        # Security Note (09/27/2021) [B608]:
        #  We have to jump through some hoops to use Django to compile a QuerySet to SQL,
        # and then use that query in our DELETE.
        # The only user-derived input here is from `qs` (`query`),
        # which is compiled properly/safely using an SQL compiler.
        # We need to use this verbatim. The other values are absolutely safe for interpolation
        # (table name and an integer PK). Doing this without string interpolation would require
        # using literal/unsafe SQL placeholders (since we already compiled our subselect),
        # so we just use interpolation.
        cur.execute(
            f"DELETE FROM {model._meta.db_table} WHERE {pk} IN ({stmt})",  #  nosec: B608
            params,
        )
        return cur.rowcount


def bulk_delete(querysets: list[QuerySet]) -> int:
    """Delete a UNION of the given querysets. Querysets MUST all refer to the same model."""
    if not querysets:
        return 0
    assert len({qs.model for qs in querysets}) == 1, "Querysets models must all match"
    unioned = querysets[0].union(*querysets[1:])
    return delete(unioned)


def offset_limit(qs, offset, limit):
    """qs[offset:offset + limit] but in a way that doesn't twist your brain if you think in SQL and not Django."""
    assert offset is not None, "offset cannot be None"
    assert limit is not None, "limit cannot be None"
    return qs[offset : (offset + limit)]


def scalar(cursor, q, args=None):
    cursor.execute(q, args)
    return cursor.fetchone()[0]


def select_all(cursor, q, args=None):
    cursor.execute(q, args)
    return cursor.fetchall()
