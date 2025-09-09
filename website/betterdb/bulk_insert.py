import contextlib
import csv
import io
import json

from django.db import models

from website import stopwatch
from ._betterdb import psyco_cursor, scalar, to_bulk_dicts
from .sql import Cursor


def bulk_insert(
    model_cls: type[models.Model],
    dicts_or_instances: list[dict] | list[models.Model],
):
    if not dicts_or_instances:
        return
    dicts = dicts_or_instances
    if not isinstance(dicts_or_instances[0], dict):
        dicts = to_bulk_dicts(dicts_or_instances)

    with psyco_cursor(model_cls) as cursor:
        with BulkInserter(cursor, model_cls._meta.db_table) as bi:
            stopwatch.click(f"bulk_insert_adding_rows", row_count=len(dicts))
            for d in dicts:
                bi.add_row(d)


class BulkInserter(contextlib.AbstractContextManager):
    # The character used to represent a null value. If we use the default,
    # we get empty strings converted to NULLs, which we don't want.
    # But in some cases, we do want NULLs- we can replace their None value in a CSV or whatever string
    # with this control character.
    null = "\u0001"

    def __init__(self, cursor, table, debug=False):
        self.debug = debug
        self.cursor = cursor
        self.table = table
        self.stream = io.StringIO()
        self.writer = None
        self.rows = []

    def add_row(self, row: dict, flush=False):
        if self.writer is None:
            self.writer = csv.DictWriter(
                self.stream,
                delimiter="\t",
                fieldnames=row.keys(),
                # This makes it about 30% faster
                extrasaction="ignore",
            )
            self.writer.writeheader()
        self.rows.append({k: self._value_to_csv(v) for k, v in row.items()})
        if flush:
            self._flushrows()

    def _flushrows(self):
        stopwatch.click(f"bulk_insert_flushing_rows", row_count=len(self.rows))
        self.writer.writerows(self.rows)
        self.rows.clear()

    def _value_to_csv(self, v):
        if hasattr(v, "to_csv"):
            return v.to_csv()
        if isinstance(v, (list, tuple)):
            return "{" + ",".join(f"{x}" for x in v) + "}"
        if isinstance(v, dict):
            return json.dumps(v)
        if v is None:
            return self.null
        return v

    def __enter__(self) -> "BulkInserter":
        return self

    def __exit__(self, *args):
        self.insert_written()
        return super().__exit__(*args)

    def insert_written(self):
        """Insert all rows written to CSV buffer.
        Only do this once (like on context exit).
        """
        if self.writer is None:
            return
        self._flushrows()
        self.stream.flush()
        self.stream.seek(0)
        if self.debug:
            print(f"Inserting {self.rows} rows")
            print(self.stream.getvalue())
            self.stream.seek(0)
        fieldnames = [f'"{f}"' for f in self.writer.fieldnames]
        fieldnames = ", ".join(fieldnames)
        stopwatch.click("starting_copy_from")
        sql = (
            f"COPY {self.table} ({fieldnames}) "
            # We do not want nulls, so instead of an empty string being turned to NULL,
            # use something that won't match anything.
            f"FROM STDIN WITH HEADER DELIMITER '\t' NULL '{self.null}' CSV"
        )

        with self.cursor.copy(sql) as copy:
            chunk = self.stream.read(8192)
            # continue until EOF (read() returns b'' or '')
            while chunk:
                copy.write(chunk)
                chunk = self.stream.read(8192)

        stopwatch.click("finished_copy_from")


@contextlib.contextmanager
def manual_sequence_lock(cursor: Cursor, table: str, sequence=None):
    """Allow manual management of a sequence. Only use this in cases where you are doing bulk inserts or updates
    and have no other choice.

    This procedure entails:

    - Taking an EXCLUSIVE lock (blocking all other writes) on the table.
    - Incrementing the given sequence, which defaults to the PK sequence for the table.
    - Yielding to the block. Calling code should use the `nextval()` method to
      return the next suitable value to use.
    - 'Committing' the latest sequence value so that the sequence
      picks up where it left off.

    WARNING: There is no way to take a lock on a sequence in PG,
    so we have to take a lock on the table.
    This is potentially brittle and slow if there are many writes,
    or anything is manually working with the sequence.

    There is a potential for race condition, but since sequence value changes
    are visible outside of a transaction, we should not run into it during
    the common case of inserting new rows.
    """
    sequence = sequence or f"{table}_id_seq"
    cursor.execute(f"LOCK TABLE {table} IN EXCLUSIVE MODE")
    current_id = scalar(cursor, "SELECT nextval(%s)", (sequence,)) - 1
    msc = ManualSequence(current_id)
    yield msc
    cursor.execute(f"SELECT setval(%s, %s, false)", (sequence, msc.nextval()))


class ManualSequence:
    def __init__(self, current_id):
        self._current_id = current_id

    def nextval(self):
        self._current_id += 1
        return self._current_id
