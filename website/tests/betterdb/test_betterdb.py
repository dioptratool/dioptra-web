from collections import namedtuple

import pytest
from django import db
from django.db import connection
from django.test import TestCase

from website.betterdb import (
    bulk_delete,
    delete,
)
from website.betterdb.bulk_create_manytomany import bulk_create_manytomany
from website.betterdb.bulk_update_dicts import build_update_sql
from website.betterdb.bulk_upsert import build_upsert_sql
from website.betterdb.transactions import Rollback, transaction
from website.tests.betterdb.models import ExampleM2M, ExampleTree


def dbcalls():
    return len(connection.queries)


class FakeBase:
    pk = None

    _meta = namedtuple("fakemeta", ["concrete_fields"])([])

    def save(self, *args, **kwargs):
        self.pk = 1

    def delete(self, *args, **kwargs):
        self.pk = None

    def refresh_from_db(self, *args, **kwargs):
        pass


class UpsertTests(TestCase):
    def setUp(self):
        self.cursor = db.connection.cursor().__enter__()

    def build(self, *args, **kwargs):
        safe, rows = build_upsert_sql(self.cursor, *args, **kwargs)
        return safe.as_string(self.cursor.cursor)

    def test_generates_sql(self):
        assert (
            self.build("tbl", [{"x": 1, "y": 2}, {"x": 3, "y": 4}])
            == 'INSERT INTO "tbl" ("x", "y") VALUES %s ON CONFLICT DO NOTHING'
        )

        assert (self.build("tbl", [{"x": 1}, {"x": 3}])) == (
            'INSERT INTO "tbl" ("x") VALUES %s ON CONFLICT DO NOTHING'
        )
        assert (self.build("tbl", [{"x": 1}, {"x": 3}], constraint="x")) == (
            'INSERT INTO "tbl" ("x") VALUES %s ON CONFLICT ("x") DO NOTHING'
        )
        assert (self.build("tbl", [{"x": 1}, {"x": 3}], constraint="uniq")) == (
            'INSERT INTO "tbl" ("x") VALUES %s ON CONFLICT ON CONSTRAINT "uniq" DO NOTHING'
        )
        assert (self.build("tbl", [{"x": 1, "y": 2}, {"x": 3, "y": 4}], update=True)) == (
            'INSERT INTO "tbl" ("x", "y") VALUES %s ON CONFLICT DO UPDATE SET ("x", "y") = (EXCLUDED."x", EXCLUDED."y")'
        )
        assert (self.build("tbl", [{"x": 1, "y": 2}, {"x": 3, "y": 4}], constraint="x", update=True)) == (
            'INSERT INTO "tbl" ("x", "y") VALUES %s ON CONFLICT ("x") DO UPDATE SET ("y") = (EXCLUDED."y")'
        )
        assert (self.build("tbl", [{"x": 1}, {"x": 3}], constraint="uniq", update=True)) == (
            'INSERT INTO "tbl" ("x") VALUES %s ON CONFLICT ON CONSTRAINT "uniq" DO UPDATE SET ("x") = (EXCLUDED."x")'
        )
        assert (self.build("tbl", [{"x": 1, "y": 2}, {"x": 3, "y": 4}], update=["x"])) == (
            'INSERT INTO "tbl" ("x", "y") VALUES %s ON CONFLICT DO UPDATE SET ("x") = (EXCLUDED."x")'
        )

    def test_errors_for_mismatched_keys(self):
        with pytest.raises(KeyError):
            self.build("tbl", [{"x": 1}, {"y": 2}])

    def test_orders_rows(self):
        _, rows = build_upsert_sql(self.cursor, "tbl", [{"z": 1, "x": 2}, {"x": 3, "z": 4}])
        assert rows == [[2, 1], [3, 4]]


class BulkCreateManyToManyTests(TestCase):
    def test_creates(self):
        a, b, c, d = (ExampleM2M.objects.create() for _ in range(4))
        bulk_create_manytomany(
            ExampleM2M,
            "others",
            "from_examplem2m",
            "to_examplem2m",
            [(a, b), (a, c), (b, c), (b, d)],
        )
        assert a.others.count() == 2
        assert b.others.count() == 2
        assert c.others.count() == 0


class BulkUpdateDictsTests(TestCase):
    def setUp(self):
        self.cursor = db.connection.cursor().__enter__()

    def build(self, *args, **kwargs):
        safe, rows = build_update_sql(self.cursor, *args, **kwargs)
        return safe.as_string(self.cursor.cursor)

    def test_generates_sql(self):
        assert (self.build("tbl", [{"x": 1, "y": 2, "z": 3}, {"x": 3, "y": 4, "z": 5}], ["x"])) == (
            'UPDATE "tbl" AS t1 SET "y" = t2."y", "z" = t2."z" '
            'FROM (VALUES %s) AS t2("x", "y", "z") WHERE t1."x" = t2."x"'
        )
        assert (self.build("tbl", [{"x": 1, "y": 2, "z": 3}, {"x": 3, "y": 4, "z": 5}], ["x", "y"])) == (
            'UPDATE "tbl" AS t1 SET "z" = t2."z" '
            'FROM (VALUES %s) AS t2("x", "y", "z") WHERE t1."x" = t2."x" AND t1."y" = t2."y"'
        )
        assert (self.build("tbl", [{"x": 1, "y": 2}, {"x": 3, "y": 4}], "x")) == (
            'UPDATE "tbl" AS t1 SET "y" = t2."y" ' 'FROM (VALUES %s) AS t2("x", "y") WHERE t1."x" = t2."x"'
        )
        assert (
            self.build(
                "tbl",
                [{"x": 1, "y": 2}, {"x": 3, "y": 4}],
                ["x"],
                expressions={"y": lambda lhs, rhs: f"{lhs} || {rhs}"},
            )
        ) == (
            'UPDATE "tbl" AS t1 SET "y" = t1."y" || t2."y" '
            'FROM (VALUES %s) AS t2("x", "y") WHERE t1."x" = t2."x"'
        )

    def test_errors_on_only_pk(self):
        with pytest.raises(ValueError):
            self.build("tbl", [{"x": 1}], "x")

    def test_errors_on_missing_pk(self):
        with pytest.raises(ValueError):
            self.build("tbl", [{"y": 2}], "x")

    def test_errors_for_mismatched_keys(self):
        with pytest.raises(KeyError):
            self.build("tbl", [{"x": 1, "z": 2}, {"x": 1, "y": 2}], "x")

    def test_orders_rows(self):
        _, rows = build_update_sql(self.cursor, "tbl", [{"z": 1, "x": 2}, {"x": 3, "z": 4}], "x")
        assert rows == ([[2, 1], [3, 4]])


class DeleteTests(TestCase):
    def test_bulk_deletes_multiple_querysets(self):
        t1, t2, t3, t4 = (ExampleTree.objects.create(name=str(i)) for i in range(4))
        q1, q2, q3, q4 = (ExampleTree.objects.filter(name=str(i)) for i in range(4))
        assert bulk_delete([q1, q3]) == 2
        assert ExampleTree.objects.count() == 2
        assert t2 in ExampleTree.objects.all()
        assert t4 in ExampleTree.objects.all()
        assert delete(q2) == 1
        assert ExampleTree.objects.count() == 1
        assert t4 in ExampleTree.objects.all()

    def test_works_with_empty_set(self):
        assert bulk_delete([]) == 0
        assert delete(ExampleTree.objects.none()) == 0


@pytest.mark.django_db(transaction=True)
class TestTransaction:
    @pytest.fixture(autouse=True)
    def setup_class(self, django_db_setup, django_db_blocker):
        with django_db_blocker.unblock():
            ExampleTree.objects.all().delete()

    @pytest.fixture(autouse=True)
    def teardown_class(self, django_db_setup, django_db_blocker):
        with django_db_blocker.unblock():
            ExampleTree.objects.all().delete()

    def test_transaction_propagates_error(self):
        assert ExampleTree.objects.all().count() == 0
        with pytest.raises(ZeroDivisionError):
            with transaction():
                ExampleTree.objects.create(name="x")
                _ = 1 / 0
        assert ExampleTree.objects.all().count() == 0

    def test_transaction_propagates_rollbacks(self):
        assert ExampleTree.objects.all().count() == 0
        with pytest.raises(Rollback):
            with transaction():
                ExampleTree.objects.create(name="x")
                raise Rollback()
        assert ExampleTree.objects.all().count() == 0

    def test_transaction_can_ignore_rollback(self):
        assert ExampleTree.objects.all().count() == 0
        with transaction(reraise_rollback=False):
            ExampleTree.objects.create(name="x")
            raise Rollback()
        assert ExampleTree.objects.all().count() == 0

    def test_invokes_callback_on_rollback(self):
        ExampleTree.objects.all().delete()

        assert ExampleTree.objects.all().count() == 0
        x = []
        with transaction(reraise_rollback=False, on_rollback=lambda: x.append(1)):
            ExampleTree.objects.create(name="x")
            raise Rollback()
        assert ExampleTree.objects.all().count() == 0
        assert x == [1]
        ExampleTree.objects.all().delete()

    def test_can_use_savepoint(self):
        with transaction():
            ExampleTree.objects.create(name="x")
            with pytest.raises(ZeroDivisionError):
                with transaction(savepoint=True):
                    ExampleTree.objects.create(name="y")
                    _ = 1 / 0
        assert ExampleTree.objects.all().count() == 1
        ExampleTree.objects.all().delete()
