from typing import TypeVar

from django.db import models

from website.betterdb import sql
from ._betterdb import (
    build_dynamic_column_strings,
    format_identifiers,
    psyco_cursor,
    to_bulk_dicts,
)
from .sql import execute_values_with_template

T = TypeVar("T", bound=models.Model)


def bulk_upsert(model_cls: type[T], unique_column: str, instances: list[T], update=False) -> list[T]:
    bulk_upsert_dicts(model_cls, to_bulk_dicts(instances), constraint=unique_column, update=update)
    result = list(
        model_cls.objects.filter(**{f"{unique_column}__in": [getattr(r, unique_column) for r in instances]})
    )
    return result


def bulk_upsert_dicts(
    model_cls: type[models.Model],
    dicts: list[dict],
    constraint: str = None,
    update=False,
):
    if not dicts:
        return
    with psyco_cursor(model_cls) as cur:
        query, argslist = build_upsert_sql(
            cur, model_cls._meta.db_table, dicts, constraint=constraint, update=update
        )
        execute_values_with_template(cur, query, argslist, page_size=min(500, len(dicts)))


def build_upsert_sql(
    cursor,
    table: str,
    rows: list[dict],
    constraint=None,
    update: bool | list[str] = False,
) -> tuple[sql.Composed, list[list]]:
    """Build the upsert statement as psycopg compatible templates.

    :param cursor: psycopg cursor
    :param table: Name of the table to upsert against.
    :param rows: Array of rows to insert. Must all have same keys.
    :param constraint: Name of the column or constraint to perform the conflict action against.
      If constraint is present in row keys, assume it's a column; otherwise assume it's a constraint.
    :param update: If false, DO NOTHING. If True, DO UPDATE with all the keys, except 'constraint' if it is a key.
      If a list of strings, treat those as the columns to update.
    """
    if hasattr(cursor, "cursor"):
        # django.db.connection.cursor() is a wrapped cursor, we need to unwrap it
        cursor = cursor.cursor
    assert cursor
    if not rows:
        raise ValueError("cannot build sql for empty rows")
    keys = list(sorted(rows[0].keys()))

    value_rows = [[d[k] for k in keys] for d in rows]

    col_str, col_placeholders = build_dynamic_column_strings(cursor, keys)

    fmt_kw = dict(table=sql.Identifier(table))
    # Security Note (07/16/2025) [B608]: No portion of the raw SQL string is user-provided
    q = f"""INSERT INTO {{table}} ({col_str}) VALUES %s ON CONFLICT """  # nosec B608
    if constraint:
        q += "({constraint}) " if constraint in keys else "ON CONSTRAINT {constraint} "
        fmt_kw["constraint"] = sql.Identifier(constraint)
    keys_to_set = []
    if update is True:
        keys_to_set = list(keys)
        if constraint:
            try:
                keys_to_set.remove(constraint)
            except ValueError:
                # If constraint is a real constraint and not a column, it won't be present
                pass
    elif update:
        keys_to_set = update
    if keys_to_set:
        update_cols = format_identifiers(cursor, keys_to_set)
        excluded_cols = format_identifiers(cursor, keys_to_set, qualifier="EXCLUDED")
        # Security Note (07/16/2025) [B608]: No portion of the raw SQL string is user-provided
        q += f"DO UPDATE SET ({update_cols}) = ({excluded_cols})"  # nosec: B608
    else:
        q += "DO NOTHING"
    q = q.strip().replace("\n", " ")
    safe = sql.SQL(q).format(**fmt_kw)
    return safe, value_rows
