from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from functools import partial
from itertools import islice
from typing import Any, ContextManager

import psycopg
from psycopg.adapt import Dumper
from psycopg.sql import Composable, Composed, Identifier, SQL

# See https://www.postgresql.org/docs/9.6/datatype-numeric.html
MAX_PG_INT = 2147483647
MIN_PG_INT = -2147483648


class Cursor:
    arraysize: int
    itersize: int  # pg extension

    def execute(self, statement, params: tuple | list = None): ...

    def fetchone(self) -> list: ...

    def fetchall(self) -> list[list]: ...

    def fetchmany(self, chunk_size: int) -> list[list]: ...


def unwrap_cursor(cursor: Cursor) -> Cursor:
    if hasattr(cursor, "cursor"):
        return cursor.cursor
    return cursor


class Connection:
    def cursor(self) -> ContextManager[Cursor]: ...


class DjangoConnection(Connection):
    class features:
        empty_fetchmany_value: Any

    def chunked_cursor(self) -> ContextManager[Cursor]: ...


TServerSideCursorProvider = DjangoConnection


@contextmanager
def new_server_side_cursor(
    con: TServerSideCursorProvider,
) -> ContextManager[tuple[Cursor, Any]]:
    # Creating named cursors from psycopg Connection objects is not implemented
    with con.chunked_cursor() as cursor:
        yield cursor, con.features.empty_fetchmany_value


class SqlUnsafe(Composable):
    """There is no sql.Composable subclass for keywords,
    which are not identifiers or literals. So if you need ASC or whatever,
    you can use this. Note it is UNSAFE! Never pass in user-defined code
    (in the future, we can validate this to only Postgres keywords).
    """

    def as_string(self, context):
        return self._wrapped


@contextmanager
def set_search_path(cursor: Cursor, path):
    cursor.execute("select current_setting('search_path')")
    existing = cursor.fetchone()[0]
    try:
        cursor.execute("SET SEARCH_PATH TO " + path)
        yield
    finally:
        cursor.execute("SET SEARCH_PATH TO " + existing)


class Schema(Identifier):
    pass


class Table(Identifier):
    pass


_public_schema = Schema("public")
_temp_schema = Schema("pg_temp")


class FQN(Identifier):
    def __init__(self, schema: Schema | str, table: Table | str):
        if not isinstance(schema, Schema):
            schema = Schema(schema)
        if not isinstance(table, Table):
            table = Table(table)
        self.schema = schema
        self.table = table
        super().__init__(schema.string, table.string)

    @classmethod
    def parse(cls, s: str):
        sch, tbl = s.split(".")
        return cls(Schema(sch), tbl)

    @classmethod
    def public(cls, t: Table | str):
        return cls(_public_schema, t)

    @classmethod
    def temp(cls, t: Table | str):
        return cls(_temp_schema, t)


class Column(Identifier):
    pass


class Keyword(SqlUnsafe):
    pass


class OrderByExpr(Composed):
    """Represents an ORDER BY column / direction pair expression

    `column` may either be a column name, or a Column instance.
    `direction` may either be a direction keyword ("ASC", "DESC"), or a Keyword instance.
    """

    def __init__(
        self,
        column: Column | str,
        direction: Keyword | str | None = None,
    ):
        if not isinstance(column, Column):
            column = Column(column)

        if not isinstance(direction, Keyword):
            direction = Keyword(direction if direction else "ASC")

        sql = SQL("{} {}").format(column, direction)
        super().__init__(sql)


class PGIntArray:
    def __init__(self, items=None):
        self.items = items or []


class PGIntArrayDumper(Dumper):
    oid = psycopg.adapters.types["integer"].array_oid

    def dump(self, obj: PGIntArray) -> bytes:
        inner = ",".join(str(x) for x in obj.items)
        return f"{{{inner}}}".encode()

    def quote(self, obj: PGIntArray) -> bytes:
        data = self.dump(obj)
        return b"'" + data + b"'" + b"::integer[]"


psycopg.adapters.register_dumper(PGIntArray, PGIntArrayDumper)


def map_as_dict(
    row_it: Iterable[list[Any]], columns: Iterable[str] | Iterable[Identifier]
) -> Iterator[dict[str, Any]]:
    """Maps row tuples to a dictionary keyed by column name"""
    if isinstance(columns[0], Identifier):
        columns = [col.string for col in columns]

    yield from map(partial(_zip_row, columns=columns), row_it)


def _zip_row(cells, columns):
    assert len(cells) == len(columns)
    return {columns[i]: cell for i, cell in enumerate(cells)}


def _chunked(it, size):
    """
    Yield successive chunks (as lists) of length `size` from the iterable `it`.
    """
    it = iter(it)
    while True:
        chunk = list(islice(it, size))
        if not chunk:
            break
        yield chunk


def execute_values_with_template(
    cur,
    base_query: str | Composed,
    argslist: list[tuple],
    *,
    template: str | None = None,
    page_size: int = 500,
):
    """
    Emulate psycopg2.extras.execute_values, honoring `value_template`.

    - `base_query` should be the SQL up to the VALUES, e.g.
        "UPDATE my_table AS t SET col1 = v.col1, col2 = v.col2
         FROM (VALUES %s) AS v(col1, col2) WHERE v.pk = t.pk"
      where the `%s` is the placeholder for your VALUES list.

    - `value_template` is a string like "(%s,CAST(%s AS jsonb),%s)" or "(%s, %s, NOW())".
    - `argslist` is a list of tuples, one tuple per row.
    """

    if not argslist:
        return

    # Convert Composed to string if needed
    if isinstance(base_query, Composed):
        base_query = base_query.as_string(unwrap_cursor(cur))

    # Generate default placeholder-template if none provided
    if template is None:
        num_fields = len(argslist[0])
        template = "(" + ",".join("%s" for _ in range(num_fields)) + ")"

    for chunk in _chunked(argslist, page_size):
        # build "(%s,%s),(%s,%s),…"
        values_sql = ",".join(template for _ in chunk)
        # plug it into the query (replace first %s with VALUES list)
        sql = base_query.replace("%s", values_sql, 1)
        # flatten arguments
        flat_args = [elem for row in chunk for elem in row]
        cur.execute(sql, flat_args)
