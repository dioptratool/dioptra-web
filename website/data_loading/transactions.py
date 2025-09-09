import contextlib
import datetime
import logging
from collections import defaultdict
from decimal import Decimal
from itertools import chain, islice, zip_longest
from typing import AnyStr, IO

import django
from django.db import connection, connections
from psycopg import sql
from psycopg.rows import dict_row

from website import betterdb, stopwatch
from website.models import Analysis
from website.models.transaction import Transaction, TransactionLike
from .utils import BulkInserter, cast_and_handle_numeric_strings, excel_file_to_array
from .validation import validate_transaction_row
from .validation.error_messages import ERROR_MESSAGES

logger = logging.getLogger(__name__)


def transaction_filter(
    data,
    grant_codes: list[str] | str,
    date_start: str | datetime.date,
    date_end: str | datetime.date,
    country_codes: list[str] | None = None,
    batch_size: int = 1000,
):
    """
    We expect an iterable in the structure that is imported into the transaction_db

    This means a file without headers but has rows in this format:
        0 transaction_date date,
        1 country_code text,
        2 grant_code text,
        3 budget_line_code text,
        4 account_code text,
        5 site_code text,
        6 sector_code text,
        7 transaction_code text,
        8 transaction_description text,
        9 currency_code character varying(4),
        10 budget_line_description text,
        11 amount numeric,
        12 dummy_field_1 text,
        13 dummy_field_2 text,
        14 dummy_field_3 text,
        15 dummy_field_4 text,
        16 dummy_field_5 text
    """

    headers = [
        "transaction_date",
        "country_code",
        "grant_code",
        "budget_line_code",
        "account_code",
        "site_code",
        "sector_code",
        "transaction_code",
        "transaction_description",
        "currency_code",
        "budget_line_description",
        "amount",
        "dummy_field_1",
        "dummy_field_2",
        "dummy_field_3",
        "dummy_field_4",
        "dummy_field_5",
    ]

    if isinstance(grant_codes, str):
        grant_codes = [grant_code.strip().upper() for grant_code in grant_codes.split(",")]

    def selected_rows():
        for i, each_row in enumerate(data):
            # This transaction filter needs to be consolidated into the
            # budget cost line item logic above
            each_row[2] = cast_and_handle_numeric_strings(each_row[2])
            each_row[3] = cast_and_handle_numeric_strings(each_row[3])
            each_row[4] = cast_and_handle_numeric_strings(each_row[4])
            each_row[5] = cast_and_handle_numeric_strings(each_row[5])
            each_row[6] = cast_and_handle_numeric_strings(each_row[6])
            each_row[10] = cast_and_handle_numeric_strings(each_row[10])

            each_row[2] = str(each_row[2]).upper()
            if str(each_row[2]) not in grant_codes:
                continue

            if country_codes:
                if each_row[1] not in country_codes:
                    continue
            if isinstance(each_row[0], str):
                date = datetime.datetime.strptime(each_row[0], "%Y-%m-%d").date()
            elif isinstance(each_row[0], datetime.date):
                date = each_row[0]
            else:
                raise ValueError(f"Invalid date on row {i}: {each_row[0]}")

            if date_start > date:
                continue

            if date_end < date:
                continue

            each_row[11] = Decimal(each_row[11])
            yield zip_longest(headers, each_row, fillvalue=None)

    def chunks(iterable, size):
        for first in iterable:
            yield chain([first], islice(iterable, size - 1))

    return chunks(selected_rows(), batch_size)


def transactions_batcher(
    analysis: Analysis,
    from_datastore: bool = False,
    file_data: IO[AnyStr] | None = None,
):
    if from_datastore:
        # We want to query for all transactions, regardless of country
        # Later, we will persist only those in relevant countries (if filtering by country)

        with _transactions_cursor(
            grant_codes=analysis.grants,
            date_start=analysis.start_date,
            date_end=analysis.end_date,
        ) as transactions_cur:
            while True:
                rows = transactions_cur.fetchmany(500)
                if len(rows) > 0:
                    yield rows
                else:
                    break
    else:
        yield from transaction_filter(
            file_data,
            grant_codes=analysis.grants,
            date_start=analysis.start_date,
            date_end=analysis.end_date,
            batch_size=500,
        )


def validate_uploaded_transaction_file(file_data: list[list[str]], analysis: Analysis | None) -> list[str]:
    errors = []
    if len(file_data) > 200_000:
        errors.append(ERROR_MESSAGES["file_too_large_transactions"]())
        # If the file is too large we leave immediately.
        return errors

    for i, row in enumerate(file_data):
        results = validate_transaction_row(i, row, analysis)
        if results.full_message():
            errors.append(results.full_message())
    return errors


@stopwatch.trace()
def load_transactions(
    analysis: Analysis,
    f: IO[AnyStr] | None = None,
    from_datastore: bool = False,
    filter_by_country: bool = False,
) -> tuple[bool, dict]:
    """
    If transactions are being loaded from a file `fp` can be populated with a Path
    If transactions are being loaded from the datastore set `from_datastore` to be true

    Both fields cannot be populated at the same time

    """
    if f and from_datastore:
        raise ValueError(
            "load_transactions works from either a file or the datastore.  Not both.  Check the values you are passing."
        )

    # If we are using a file we need to validate before we begin any loading.
    file_data = None
    if f:
        file_data = excel_file_to_array(f)

        fixed_data = []

        # Excel stores all numbers as floats.   This causes grants with values like "9116"
        #  to be save as "9116.0" in Excel.  This attempts to remedy the issue.   This
        #  could lead to a bug if there are ever grants that should be in the
        #  format "9116.0".   If that is ever the case we will need to enforce the Cell Format
        #  in excel.
        for row in file_data:
            try:
                row[2] = str(int(float(row[2])))
            except ValueError:
                pass
            fixed_data.append(row)

        file_data = fixed_data
        # Validate the file data
        errors = validate_uploaded_transaction_file(file_data, analysis)
        if errors:
            return False, {"errors": errors}

    # Use bulk inserting, it's quite a bit faster: http://stefano.dissegna.me/django-pg-bulk-insert.html
    # Using django models was about 4.5s for 15k rows, this is 1.3s.
    # It should be refactored into something more reusable as we need to build more bulk inserts.

    country_codes = analysis.get_all_countries_values("code") if filter_by_country else None
    total_costs_by_grant = defaultdict(Decimal)
    xactions = []
    try:
        with connection.cursor() as cursor:
            # We need to bulk insert with the ID so we can easily associate transactions and cost line items later.
            with betterdb.manual_sequence_lock(cursor, Transaction._meta.db_table) as seq:
                with BulkInserter(connection, Transaction._meta.db_table) as inserter:
                    for rows in transactions_batcher(analysis, from_datastore, file_data):
                        for row in rows:
                            row = dict(row)
                            row["id"] = seq.nextval()
                            # Remove extra whitespace. There's a couple micro-optimization here:
                            # - Use try/except since most values are strings,
                            #   and it's much faster than a type/hasattr check.
                            # - Compare the stripped and original values,
                            #   and only update the dict if they are not equal.
                            #   This is much faster than unconditionally setting a dict,
                            #   which requires both a hash lookup and a memory mutation.
                            for field, value in row.items():
                                try:
                                    new_value = value.strip()
                                    if value != new_value:
                                        row[field] = value.strip()
                                except AttributeError:
                                    pass
                            amount = row.pop("amount", 0)
                            total_costs_by_grant[row["grant_code"]] += amount
                            # If we are filtering by country, and the Transaction's
                            # country is not among the filtered countries,
                            # we should not persist the Transaction
                            if country_codes is not None:
                                if row["country_code"] not in country_codes:
                                    continue
                            row["amount_in_source_currency"] = Decimal(amount)
                            row["amount_in_instance_currency"] = Decimal(amount)
                            row["date"] = row.pop("transaction_date")
                            row["analysis_id"] = analysis.id
                            xactions.append(TransactionLike(**row))
                            inserter.add_row(row)
        analysis.source = Analysis.DATA_STORE_NAME

        # Convert the total_costs_by_grant dict to a comma separated string, where the index of the cost value matches
        # up with the index of its corresponding Grant in the Analysis "grants" parameter
        total_cost_list = []
        analysis_grant_list = analysis.grants.split(",")
        for grant in analysis_grant_list:
            cost = total_costs_by_grant[grant]
            total_cost_list.append(str(round(cost, 4)))
        analysis.all_transactions_total_cost = ",".join(total_cost_list)

        analysis.save()
    except Exception as e:
        logger.exception(e)
        return False, {"errors": [ERROR_MESSAGES["error_importing_from_transaction_store"]()]}
    return True, {"imported_count": len(xactions), "imported_transactions": xactions}


def get_transactions_data_store_count(
    grant_codes: list[str] | str,
    date_start: str | datetime.date,
    date_end: str | datetime.date,
    country_codes: list[str] | None = None,
) -> int:
    with connections["transaction_store"].cursor() as cursor:
        if isinstance(date_start, datetime.date):
            date_start = date_start.strftime("%Y-%m-%d")
        if isinstance(date_end, datetime.date):
            date_end = date_end.strftime("%Y-%m-%d")
        if isinstance(grant_codes, str):
            grant_codes = [grant_code.strip().upper() for grant_code in grant_codes.split(",")]
        try:
            if country_codes:
                cursor.execute(
                    """
               SELECT
                   count(*) 
                FROM
                   transactions 
                WHERE
                   upper(grant_code) = ANY (%s) 
                   AND upper(country_code) = ANY (%s) 
                   AND transaction_date BETWEEN SYMMETRIC %s AND %s;
                    """,
                    (
                        grant_codes,
                        country_codes,
                        date_start,
                        date_end,
                    ),
                )
            else:
                cursor.execute(
                    """
                   SELECT
                       count(*) 
                    FROM
                       transactions 
                    WHERE
                       upper(grant_code) = ANY (%s) 
                       AND transaction_date BETWEEN SYMMETRIC %s AND %s;
                        """,
                    (
                        grant_codes,
                        date_start,
                        date_end,
                    ),
                )
        except django.db.utils.DataError:
            # logger.info(f"Invalid query while getting count: {e}")
            return 0

        return cursor.fetchone()[0]


@contextlib.contextmanager
def _transactions_cursor(
    grant_codes: list[str] | str,
    date_start: str | datetime.date,
    date_end: str | datetime.date,
    country_codes: list[str] | None = None,
):
    if isinstance(date_start, datetime.date):
        date_start = date_start.strftime("%Y-%m-%d")
    if isinstance(date_end, datetime.date):
        date_end = date_end.strftime("%Y-%m-%d")
    if isinstance(grant_codes, str):
        grant_codes = [grant_code.strip().upper() for grant_code in grant_codes.split(",")]

    conn = connections["transaction_store"]
    conn.ensure_connection()

    with conn.connection.cursor(row_factory=dict_row) as cursor:
        fields = [
            "account_code",
            "amount",
            "budget_line_code",
            "budget_line_description",
            "country_code",
            "currency_code",
            "dummy_field_1",
            "dummy_field_2",
            "dummy_field_3",
            "dummy_field_4",
            "dummy_field_5",
            "grant_code",
            "sector_code",
            "site_code",
            "transaction_code",
            "transaction_date",
            "transaction_description",
        ]

        if country_codes is not None:
            query = sql.SQL(
                """SELECT 
                                 {} 
                               FROM 
                                 transactions 
                               WHERE
                                 upper(grant_code) = ANY (%s)
                                 AND upper(country_code) = ANY(%s) 
                                 AND transaction_date BETWEEN SYMMETRIC %s AND %s;"""
            ).format(sql.SQL(", ").join(map(sql.Identifier, fields)))
            cursor.execute(
                query,
                (
                    grant_codes,
                    country_codes,
                    date_start,
                    date_end,
                ),
            )

        else:
            query = sql.SQL(
                """SELECT 
                                 {} 
                               FROM 
                                 transactions 
                               WHERE
                                 upper(grant_code) = ANY (%s)
                                 AND transaction_date BETWEEN SYMMETRIC %s AND %s;"""
            ).format(sql.SQL(", ").join(map(sql.Identifier, fields)))
            cursor.execute(
                query,
                (
                    grant_codes,
                    date_start,
                    date_end,
                ),
            )

        yield cursor
