from contextlib import ContextDecorator

import django.db.transaction


def is_in_transaction(connection=None):
    connection = connection or django.db.transaction.get_connection()
    return connection.in_atomic_block


class transaction(ContextDecorator):
    _xact = None

    def __init__(self, reraise_rollback=True, on_rollback=None, savepoint=False):
        self.reraise_rollback = reraise_rollback
        self.on_rollback = on_rollback
        self.savepoint = savepoint
        super().__init__()

    def __enter__(self):
        if is_in_transaction() and not self.savepoint:
            return
        self._xact = django.db.transaction.atomic()
        self._xact.__enter__()

    def __exit__(self, *ex):
        if self._xact:
            self._xact.__exit__(*ex)
        if ex and ex[0] == Rollback:
            if self.on_rollback:
                self.on_rollback()
            if not self.reraise_rollback:
                return True


class Rollback(Exception):
    pass
