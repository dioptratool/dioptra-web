import contextlib
import re
import time

import structlog
from django.conf import settings
from django.db.backends import utils

logger = structlog.get_logger("stopwatch.sql")

if settings.DEBUG or settings.STOPWATCH_LOG_SQL:
    orig_class = utils.CursorDebugWrapper
    re_select = re.compile("^SELECT (.*) FROM (.*)$")
    re_squashspace = re.compile(r"\s+")

    class Wrapper(orig_class):
        """Stick breakpoints in execute so you can see when requests are made in real-time.
        Eventually we should add this to real-time logging, and remove what's in stopwatch.
        """

        def execute(self, sql, params=None):
            with self._logit(sql):
                return super().execute(sql, params)

        def executemany(self, sql, params):
            with self._logit(sql):
                return super().executemany(sql, params)

        @contextlib.contextmanager
        def _logit(self, sql):
            if not settings.STOPWATCH_LOG_SQL:
                yield
            else:
                start = time.perf_counter()
                try:
                    yield
                finally:
                    elap = time.perf_counter() - start
                    fsql = self._fmt_sql(sql)
                    should_log = (
                        fsql.startswith("UPDATE")
                        or fsql.startswith("DELETE")
                        or elap > settings.STOPWATCH_SLOW_SQL
                        or not settings.STOPWATCH_SLOW_SQL
                    )
                    if should_log:
                        logger.bind(ms=round(elap * 1000, 4), sql=fsql).info("sql_query")

        def _fmt_sql(self, s):
            s = s or ""  # query can be None, not really sure when though...
            s = re_squashspace.sub(" ", s)
            match = re_select.match(s)
            if match and len(match.groups()) == 2:
                col_count = match.group(1).count('", "')
                # Security Note (07/16/2025) [B608]: No portion of the raw SQL string is user-provided
                s = f"SELECT <{col_count}> FROM {match.group(2)}"  # nosec B608
            s = s.replace("\n", " ")
            return s[:1000]

    utils.CursorDebugWrapper = Wrapper
