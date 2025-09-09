__doc__ = """
Stopwatch provides tools for assisting with benchmarking long-running activities.

To enable stopwatching, call `stopwatch.activate()`,
which will cause each call to `stopwatch.click` to log.
This should generally only be done by the outermost caller,
like a test or command.

If you want to stop the stopwatching,
and/or reset it back to its initial state, call `stopwatch.reset()`.

To get the current stopwatch, call `stopwatch.current()`.
However, generally you don't need to interact with a `Stopwatch` directly.
"""

import contextlib
import threading
import time
from collections import deque
from collections.abc import Callable
from contextlib import ContextDecorator, contextmanager

import structlog
from django.conf import settings
from django.db import connection

_default_logger = structlog.get_logger("stopwatch")


def _getlogger():
    return getattr(_tl, "logger", _default_logger)


@contextmanager
def use_logger(logger):
    last_logger = _getlogger()
    _tl.active_logger = logger
    try:
        yield
    finally:
        _tl.active_logger = last_logger


class StopwatchLike:
    def click(self, event, **kwargs):
        pass


def _log_time(**kwargs):
    _getlogger().bind(**kwargs).warning("stopwatch_click")


class Stopwatch(StopwatchLike):
    def __init__(self, *, record_time: Callable):
        self.start = time.perf_counter()
        self.last = self.start
        self.last_queries = len(connection.queries_log)
        self.record_time = record_time
        self.total_queries = 0

    def click(self, event, **kwargs):
        now = time.perf_counter()
        event = _traced_event_name(event)

        stage = now - self.last
        total = now - self.start
        self.last = now

        nowq = len(connection.queries_log)
        stageq = nowq - self.last_queries
        self.last_queries = nowq
        self.total_queries += stageq

        self.record_time(
            stopwatch_event=event,
            stage=round(stage, 4),
            total=round(total, 4),
            queries=stageq,
            total_queries=self.total_queries,
            **kwargs,
        )


class Noopwatch(StopwatchLike):
    def __init__(self, *args, **kwargs):
        pass

    def click(self, *args, **kwargs):
        pass


_orig_force_debug_cursor = False
_orig_queries_log = False
_activesw: Stopwatch | None = None
_tl = threading.local()
_noop = Noopwatch()


@contextlib.contextmanager
def silent():
    global _activesw
    orig = _activesw
    try:
        _activesw = _noop
        yield
    finally:
        _activesw = orig


def activate():
    """Activate the stopwatch so that clicks report via the record_time function."""
    if is_active():
        _getlogger().warn("stopwatch_already_active")
        return

    global _activesw, _orig_force_debug_cursor, _orig_queries_log

    _orig_force_debug_cursor = connection.force_debug_cursor
    connection.force_debug_cursor = True

    _orig_queries_log = connection.queries_log
    connection.queries_log = CountingDeque(connection.queries_log)

    _activesw = Stopwatch(record_time=_log_time)


def is_active() -> bool:
    return _activesw is not None


def current() -> StopwatchLike:
    return _activesw or _noop


def real_current() -> Stopwatch:
    return _activesw


def click(event, **kwargs):
    current().click(event, **kwargs)


def clickorlog(event, **kwargs):
    """If a real stopwatch is active, click, if not, log."""
    sw = current()
    if isinstance(sw, Noopwatch):
        _getlogger().bind(**kwargs).warning(_traced_event_name(event))
    else:
        sw.click(event, **kwargs)


def reset():
    global _activesw
    _activesw = None
    if _orig_queries_log is not None:
        connection.queries_log = _orig_queries_log
    if _orig_force_debug_cursor is not None:
        connection.force_debug_cursor = _orig_force_debug_cursor


def _traced_event_name(event):
    stack = getattr(_tl, "trace_stack", [])
    if stack:
        return ".".join(stack) + "." + event
    return event


class trace(ContextDecorator):
    def __init__(
        self,
        name=None,
        trace_enter=True,
        trace_exit=True,
        click_func=None,
        orlog=False,
        click_kwargs=None,
    ):
        self.name = name
        self.trace_enter = trace_enter
        self.trace_exit = trace_exit
        self.click_func = click_func
        if self.click_func is None:
            self.click_func = clickorlog if orlog else click
        self.click_kwargs = click_kwargs or {}

    def __call__(self, func):
        if self.name is None:
            self.name = func.__name__
        return super().__call__(func)

    def __enter__(self):
        if self.name is None:
            raise TypeError("__init__() missing required argument 'name' when used as a context manager")
        if not hasattr(_tl, "trace_stack"):
            _tl.trace_stack = []
        _tl.trace_stack.append(self.name)
        self._started = time.perf_counter()
        if self.trace_enter:
            self.click_func("enter", **self.click_kwargs)
        return self

    def __exit__(self, *exc):
        if self.trace_enter:
            self.click_func("exit", trace=time.perf_counter() - self._started, **self.click_kwargs)
        _tl.trace_stack.pop()
        return False


class CountingDeque:
    """CountingDeque mimics a Deque, so can be used as connection.queries_log.
    It records how many items have ever been appended in total_appended.
    """

    def __init__(self, d: deque):
        self.total_appended = len(d)
        self.d = d

    def __iter__(self):
        return self.d.__iter__()

    def __len__(self):
        return self.d.__len__()

    def append(self, x):
        self.total_appended += 1
        return self.d.append(x)

    def clear(self):
        self.d.clear()

    @property
    def maxlen(self):
        return self.d.maxlen


class RequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        level = settings.STOPWATCH_LEVEL
        if not level:
            return self.get_response(request)

        activate()

        with trace(name=request.get_full_path()):
            response = self.get_response(request)

        reset()
        return response
