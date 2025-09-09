from collections.abc import Callable

from django.db import models

from . import sql
from ._betterdb import (
    format_identifiers,
    psyco_cursor,
)
from .sql import execute_values_with_template


def bulk_update_dicts(
    model_cls: type[models.Model],
    dicts: list[dict],
    expressions: dict[str, Callable[[str, str], str]] = None,
    pk: str | list[str] = None,
    value_template: str | None = None,
):
    """Bulk-update row dictionaries.

    Each row must have the same keys in it,
    and must include at least one column, in addition to any primary keys.

    If pk is given, use it to the identify the row;
    usually this is the primary key, but you may not have it,
    and only have parts of a unique constraint, for example.

    If expressions is given, it should be a mapping of column/key, to callback used
    to format the update expression. For example,
    {'x': lambda lhs, rhs: f"{lhs} || {rhs}"}
    would produce SQL like `x = x || incoming.x`.
    lhs and rhs are pre-quoted so should be used directly in the resulting string.
    """
    if not dicts:
        return
    with psyco_cursor(model_cls) as cur:
        if pk is None:
            pk = [model_cls._meta.pk.name]
        elif isinstance(pk, str):
            pk = [pk]
        query, argslist = build_update_sql(cur, model_cls._meta.db_table, dicts, pk, expressions)

        execute_values_with_template(
            cur,
            query,
            argslist=argslist,
            template=value_template,
            page_size=min(500, len(dicts)),
        )


def build_update_sql(cursor, table: str, rows, pks, expressions=None) -> tuple[sql.Composed, list[list]]:
    if hasattr(cursor, "cursor"):
        # django.db.connection.cursor() is a wrapped cursor, we need to unwrap it
        cursor = cursor.cursor
    assert cursor
    expressions = expressions or {}
    if not rows:
        raise ValueError("cannot build sql for empty rows")
    if not all(k in rows[0] for k in pks):
        raise ValueError(f"every row must have all pk keys: {pks}")
    if len(rows[0]) == len(pks):
        raise ValueError(f"rows must have value columns, not just pks")
    expressions = expressions or {}

    def fmt(ident):
        return format_identifiers(cursor, [ident])

    keys = list(sorted(rows[0].keys()))

    values_view_rows = [[d[k] for k in keys] for d in rows]
    safe_values_view_columns = [fmt(k) for k in keys]

    assignments = []
    for c in keys:
        if c in pks:
            continue
        safe_c = fmt(c)
        lhs = f"t1.{safe_c}"
        rhs = f"t2.{safe_c}"
        if c in expressions:
            expr = expressions[c](lhs, rhs)
        else:
            expr = rhs
        assignments.append(f"{safe_c} = {expr}")

    safe_pk_compares = []
    for pk in pks:
        safe_pk = fmt(pk)
        safe_pk_compares.append(f"t1.{safe_pk} = t2.{safe_pk}")
    # Security Note (07/16/2025) [B608]: No portion of the raw SQL string is user-provided
    sql_parts = [
        f"UPDATE {fmt(table)} AS t1 SET ",  # nosec B608
        ", ".join(assignments),
        " FROM (VALUES %s) AS t2(",
        ", ".join(safe_values_view_columns),
        ") WHERE ",
        " AND ".join(safe_pk_compares),
    ]

    q = "".join(sql_parts)
    q = q.strip().replace("\n", " ")
    return sql.SQL(q).format(), values_view_rows
