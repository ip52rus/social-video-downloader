"""Opt-in, bounded same-host evidence. Never a client-click or wire-arrival clock."""

import asyncio
import logging
import re
import secrets
import weakref
from collections import deque
from contextlib import suppress
from contextvars import ContextVar
from dataclasses import dataclass
from time import monotonic_ns

from aiogram import BaseMiddleware
from aiogram.methods import AnswerCallbackQuery, GetUpdates, SendAudio, SendMediaGroup, SendVideo

LOGGER_NAME = "social_video_downloader.concurrency"
MAX_EVENTS = 512
MAX_TRACES = 128
LIFETIME_NS = 600 * 10**9
EVENTS = {
    "updates_received",
    "update_entered",
    "update_finished",
    "callback_entered",
    "admission",
    "lease_left",
    "metadata_started",
    "metadata_finished",
    "extraction_started",
    "extraction_finished",
    "ack_started",
    "ack_finished",
    "acquisition_started",
    "delivery_started",
    "delivery_finished",
    "loop_lag",
    "stopped",
}
RESULTS = {
    "none",
    "known",
    "unknown",
    "busy",
    "admitted",
    "stale",
    "failed",
    "returned",
    "cancelled",
    "expired",
    "cache",
    "budget",
    "closed",
}
FIELDS = {
    "schema",
    "run",
    "seq",
    "trace",
    "request",
    "event",
    "at_ns",
    "result",
    "duration_ns",
    "pending",
    "working",
    "quarantined",
    "contexts",
    "active_leases",
    "work_leases",
}


def safe_payload(value):
    if type(value) is not dict or set(value) != FIELDS:
        return None
    if type(value["schema"]) is not int or value["schema"] != 1:
        return None
    if type(value["run"]) is not str or re.fullmatch(r"[0-9a-f]{16}", value["run"]) is None:
        return None
    for name, limit in (
        ("seq", MAX_EVENTS),
        ("trace", MAX_TRACES),
        ("request", MAX_TRACES),
        ("at_ns", 2**63 - 1),
    ):
        if type(value[name]) is not int or not 0 <= value[name] <= limit:
            return None
    if type(value["event"]) is not str or value["event"] not in EVENTS:
        return None
    if type(value["result"]) is not str or value["result"] not in RESULTS:
        return None
    for name, limit in (
        ("duration_ns", LIFETIME_NS),
        ("contexts", 128),
        ("active_leases", 1024),
        ("work_leases", 8),
    ):
        number = value[name]
        if number is not None and (type(number) is not int or not 0 <= number <= limit):
            return None
    if any(
        value[k] is not None and type(value[k]) is not bool
        for k in ("pending", "working", "quarantined")
    ):
        return None
    return dict(value)


@dataclass(slots=True)
class Span:
    probe: "Probe"
    trace: int
    request: int | None = None


_current: ContextVar[Span | None] = ContextVar("concurrency_probe", default=None)


def current():
    with suppress(Exception):
        span = _current.get()
        return span if span is not None and span.probe.active else None
    return None


def observe(event, **fields):
    if (span := current()) is not None:
        fields.setdefault("request", span.request if span.request is not None else span.trace)
        span.probe.record(event, trace=span.trace, **fields)


def observe_lease(admission, lease, **fields):
    with suppress(Exception):
        if (span := current()) is not None:
            span.probe.lease(admission, lease, **fields)


class Probe:
    """One bounded 10-minute window per process; no IDs, URLs, payloads or extra threads.

    Hot-path record only builds a fixed small dict in memory. The asyncio pump emits
    at most four small records per 50 ms through the existing sanitized logging sink.
    Logging is best effort, not a durable evidence store. Missing records mean UNKNOWN.
    """

    def __init__(self, *, clock=monotonic_ns):
        self.clock = clock
        self.started = clock()
        self.run = secrets.token_hex(8)
        self.records = deque(maxlen=MAX_EVENTS)
        self._outbox = deque(maxlen=MAX_EVENTS)
        self._updates = {}
        self._leases = {}
        self._traces = 0
        self._closed = False
        self._task = None
        self._sequence = 0

    @property
    def active(self):
        with suppress(Exception):
            return not self._closed and 0 <= self.clock() - self.started < LIFETIME_NS
        return False

    def new_trace(self):
        if not self.active or self._traces >= MAX_TRACES:
            return 0
        self._traces += 1
        return self._traces

    def record(
        self,
        event,
        *,
        trace=0,
        request=None,
        at_ns=None,
        result="none",
        duration_ns=None,
        pending=None,
        working=None,
        quarantined=None,
        contexts=None,
        active_leases=None,
        work_leases=None,
    ):
        with suppress(Exception):
            if not self.active:
                return
            if self._sequence >= MAX_EVENTS - 1:
                event, result = "stopped", "budget"
            value = safe_payload(
                dict(
                    schema=1,
                    run=self.run,
                    seq=self._sequence + 1,
                    trace=trace,
                    request=trace if request is None else request,
                    event=event,
                    at_ns=self.clock() if at_ns is None else at_ns,
                    result=result,
                    duration_ns=duration_ns,
                    pending=pending,
                    working=working,
                    quarantined=quarantined,
                    contexts=contexts,
                    active_leases=active_leases,
                    work_leases=work_leases,
                )
            )
            if value is None:
                return
            self._sequence += 1
            self.records.append(value)
            self._outbox.append(value)
            if event == "stopped":
                self._closed = True
                self._updates.clear()
                self._leases.clear()

    def received(self, updates):
        # Weak object identity is only a transient handoff, never a Telegram ID/hash.
        now = self.clock()
        self._updates = {
            k: v for k, v in self._updates.items() if v[0]() is not None and now - v[2] < 30 * 10**9
        }
        for update in updates[:MAX_TRACES]:
            if len(self._updates) >= MAX_TRACES:
                break
            trace = self.new_trace()
            if not trace:
                break
            self._updates[id(update)] = (weakref.ref(update), trace, now)
            self.record("updates_received", trace=trace, at_ns=now)

    def enter(self, update):
        previous = self._updates.pop(id(update), None)
        trace = (
            previous[1]
            if previous is not None
            and previous[0]() is update
            and 0 <= self.clock() - previous[2] < 30 * 10**9
            else self.new_trace()
        )
        return Span(self, trace)

    def lease(self, admission, lease, *, result, leaving=False):
        span = current()
        if span is None:
            return
        key = id(lease) if lease is not None else None
        self._leases = {k: v for k, v in self._leases.items() if v[0]() is not None}
        if key is not None and key not in self._leases and len(self._leases) < MAX_TRACES:
            self._leases[key] = (weakref.ref(lease), span.trace)
        span.request = self._leases[key][1] if key in self._leases else 0
        self.record(
            "lease_left" if leaving else "admission",
            trace=span.trace,
            request=self._leases[key][1] if key in self._leases else 0,
            result=result,
            pending=lease.pending is not None if lease is not None else None,
            working=lease.working if lease is not None else None,
            quarantined=lease.quarantined if lease is not None else None,
            contexts=lease.contexts if lease is not None else None,
            active_leases=len(admission._leases),
            work_leases=sum(x.working for x in admission._leases.values()),
        )
        if key is not None and leaving and all(x is not lease for x in admission._leases.values()):
            self._leases.pop(key, None)

    def flush(self, count=4):
        for _ in range(min(count, 4)):
            if not self._outbox:
                break
            value = self._outbox.popleft()
            with suppress(Exception):
                logging.getLogger(LOGGER_NAME).info(
                    "concurrency", extra={"safe_concurrency": value}
                )

    async def start(self, **_):
        if self._task is None and self.active:
            with suppress(Exception):
                self._task = asyncio.create_task(self._pump())

    async def _pump(self):
        try:
            due = self.clock() + 50_000_000
            report_due = due + 5 * 10**9
            maximum = 0
            while self.active:
                await asyncio.sleep(0.05)
                now = self.clock()
                maximum = max(maximum, max(0, now - due))
                if now >= report_due:
                    self.record("loop_lag", duration_ns=min(maximum, LIFETIME_NS))
                    maximum, report_due = 0, now + 5 * 10**9
                self.flush()
                # Include observer/flush work in the next scheduling-lag sample.
                due = now + 50_000_000
        except Exception:
            pass  # Diagnostic failures never fail polling/metadata or clear a lease.
        finally:
            self._closed = True
            self._updates.clear()
            self._leases.clear()
            # Drop unflushed records; no unbounded/synchronous shutdown drain.
            self._outbox.clear()
            self.records.clear()

    async def close(self, **_):
        self._closed = True
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await self._task
        self._updates.clear()
        self._leases.clear()
        self._outbox.clear()
        self.records.clear()


class UpdateObserver(BaseMiddleware):
    def __init__(self, probe):
        self.probe = probe

    async def __call__(self, handler, event, data):
        if not self.probe.active:
            return await handler(event, data)
        try:
            span = self.probe.enter(event)
        except Exception:
            return await handler(event, data)
        if not span.trace:
            return await handler(event, data)
        token = _current.set(span)
        self.probe.record("update_entered", trace=span.trace)
        try:
            return await handler(event, data)
        finally:
            observe("update_finished")
            _current.reset(token)


class SessionObserver:
    def __init__(self, probe):
        self.probe = probe

    async def __call__(self, make_request, bot, method):
        if not self.probe.active:
            return await make_request(bot, method)
        kind = (
            "ack"
            if isinstance(method, AnswerCallbackQuery)
            else "delivery"
            if isinstance(method, (SendVideo, SendAudio, SendMediaGroup))
            else None
        )
        try:
            start = self.probe.clock()
        except Exception:
            return await make_request(bot, method)
        if kind:
            observe(kind + "_started")
        try:
            result = await make_request(bot, method)
        except BaseException as error:
            if kind:
                observe(
                    kind + "_finished",
                    result="cancelled" if isinstance(error, asyncio.CancelledError) else "unknown",
                    duration_ns=self._duration(start),
                )
            raise
        if isinstance(method, GetUpdates):
            with suppress(Exception):
                self.probe.received(result)
        if kind:
            confirmed = result is True if kind == "ack" else result is not None
            observe(
                kind + "_finished",
                result="returned" if confirmed else "unknown",
                duration_ns=self._duration(start),
            )
        return result

    def _duration(self, start):
        with suppress(Exception):
            return self.probe.clock() - start
        return None
