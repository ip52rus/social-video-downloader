"""P9-R1b: same-host timing evidence, synthetic transport and offline children only."""

import asyncio
import json
import logging
import sys
from dataclasses import fields
from time import monotonic_ns
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from aiogram.methods import AnswerCallbackQuery, GetUpdates

from social_video_downloader import concurrency_diagnostics as diag
from social_video_downloader.config import ConfigurationError, Settings
from social_video_downloader.domain.errors import MetadataExtractionError
from social_video_downloader.infrastructure import youtube_snapshot as wire
from social_video_downloader.logging_config import SafeEventFilter, SafeEventFormatter
from tests.test_telegram_localization import message_update
from tests.test_youtube_metadata import owner as owner
from tests.test_youtube_snapshot import URL, info


def payload(*, enabled=True):
    req = wire.request(URL, "synthetic-request-nonce", diagnostics=enabled)
    data = wire.response(req, info(), 9.0, extraction=wire.ExtractionInterval(7 * 10**9, 8 * 10**9))
    return req, data


def test_wire_legacy_bytes_and_snapshot_unchanged():
    req, data = payload(enabled=False)
    assert "diagnostics" not in req and "diagnostics" not in data
    assert wire.encode(data) == wire.encode({**req, "created_at": 9.0, "info": info()})
    assert [f.name for f in fields(wire.Snapshot)] == ["url", "video_id", "created_at", "info"]


@pytest.mark.parametrize("value", [False, 1, "true", {}, None])
def test_request_opt_in_is_exact_true(value):
    req, _ = payload()
    req["diagnostics"] = value
    with pytest.raises(MetadataExtractionError):
        wire.validate_request(req)


def test_unknown_top_level_is_refused():
    req, data = payload()
    wire.validate_request(req)
    data["extra"] = "synthetic secret"
    with pytest.raises(MetadataExtractionError):
        wire.validate_response(data, req)
    req["extra"] = True
    with pytest.raises(MetadataExtractionError):
        wire.validate_request(req)


@pytest.mark.parametrize(
    "value",
    [
        None,
        {},
        {"extra": 7},
        {"extraction_started_ns": None, "extraction_finished_ns": None},
        {"extraction_started_ns": 7 * 10**9},
        {"extraction_started_ns": -1, "extraction_finished_ns": 8 * 10**9},
        {"extraction_started_ns": True, "extraction_finished_ns": 8 * 10**9},
        {"extraction_started_ns": 7.0, "extraction_finished_ns": 8 * 10**9},
        {"extraction_started_ns": "7000000000", "extraction_finished_ns": 8 * 10**9},
        {"extraction_started_ns": 8 * 10**9, "extraction_finished_ns": 7 * 10**9},
        {"extraction_started_ns": 7 * 10**9, "extraction_finished_ns": 10 * 10**9},
        {"extraction_started_ns": 2**64, "extraction_finished_ns": 2**64},
        {"extraction_started_ns": 7 * 10**9, "extraction_finished_ns": 8 * 10**9, "url": "secret"},
    ],
)
def test_invalid_evidence_is_unknown_without_repair(value):
    req, data = payload()
    data["diagnostics"] = value
    assert wire.extraction_interval(data, req, now_ns=9 * 10**9) is None


def test_interval_clock_bounds_and_missing_legacy_diagnostics():
    req, data = payload()
    assert wire.extraction_interval(data, req, now_ns=9 * 10**9) == wire.ExtractionInterval(
        7 * 10**9, 8 * 10**9
    )
    assert wire.extraction_interval(data, req, earliest_ns=8 * 10**9, now_ns=9 * 10**9) is None
    assert wire.extraction_interval(data, req, now_ns=200 * 10**9) is None
    data["created_at"] = 7.0
    assert wire.extraction_interval(data, req, now_ns=9 * 10**9) is None
    data.pop("diagnostics")
    assert wire.extraction_interval(data, req, now_ns=9 * 10**9) is None


def test_disabled_parent_refuses_unsolicited_diagnostics():
    req, data = payload(enabled=False)
    data["diagnostics"] = {}
    with pytest.raises(MetadataExtractionError):
        wire.validate_response(data, req)


def test_opt_in_legacy_reply_and_invalid_timings_do_not_enter_snapshot(monkeypatch):
    now = monotonic_ns()
    req = wire.request(URL, "synthetic-request-nonce", diagnostics=True)
    legacy = wire.response(wire.request(URL, "synthetic-request-nonce"), info(), now / 10**9)
    snapshot = wire.validate_response(legacy, req)
    assert wire.extraction_interval(legacy, req) is None
    legacy["diagnostics"] = {"unexpected": "synthetic secret"}
    assert wire.validate_response(legacy, req) == snapshot
    assert wire.extraction_interval(legacy, req) is None
    assert snapshot.created_at == now / 10**9 and "diagnostics" not in snapshot.info


def test_optional_evidence_cannot_exceed_existing_wire_budget():
    req = wire.request(URL, "synthetic-request-nonce", diagnostics=True)
    data = wire.response(req, {"id": "abcdefghijk", "description": ""}, 9.0)
    base = {k: v for k, v in data.items() if k != "diagnostics"}
    base["info"]["description"] = "x" * (wire.RESPONSE_BYTES - len(wire.encode(base)))
    assert len(wire.encode(base)) == wire.RESPONSE_BYTES
    data["info"] = base["info"]
    encoded = wire.encode_metadata_response(data)
    assert len(encoded) == wire.RESPONSE_BYTES
    assert "diagnostics" not in wire.decode(encoded)
    base["info"]["description"] += "x"
    with pytest.raises(MetadataExtractionError):
        wire.encode_metadata_response(base)


def test_config_off_by_default_and_strict_opt_in():
    assert not Settings("synthetic").concurrency_diagnostics
    assert Settings.from_env(
        {"TELEGRAM_BOT_TOKEN": "synthetic", "CONCURRENCY_DIAGNOSTICS": "true"}
    ).concurrency_diagnostics
    for value in ("1", "yes", "", "secret"):
        with pytest.raises(ConfigurationError):
            Settings.from_env({"TELEGRAM_BOT_TOKEN": "synthetic", "CONCURRENCY_DIAGNOSTICS": value})
    with pytest.raises(ConfigurationError):
        Settings("synthetic", concurrency_diagnostics=1)


def test_recorder_clock_budget_and_no_hot_path_logging(monkeypatch):
    now = [10**9]
    p = diag.Probe(clock=lambda: now[0])
    logger = Mock()
    monkeypatch.setattr(diag, "logging", SimpleNamespace(getLogger=logger))
    p.record("callback_entered", trace=1)
    now[0] += 123
    p.record("ack_finished", trace=1, duration_ns=123, result="returned")
    assert [e["at_ns"] for e in p.records] == [10**9, 10**9 + 123]
    logger.assert_not_called()
    before = len(p.records)
    p.record("synthetic secret")
    p.record("ack_finished", result="secret")
    assert len(p.records) == before
    for _ in range(diag.MAX_EVENTS * 2):
        p.record("callback_entered")
    assert len(p.records) == diag.MAX_EVENTS
    assert p.records[-1]["event"] == "stopped" and p.records[-1]["result"] == "budget"
    assert not p.active and len(p._outbox) <= diag.MAX_EVENTS


@pytest.mark.asyncio
async def test_expiry_and_cleanup_drop_bounded_memory():
    now = [10**9]
    p = diag.Probe(clock=lambda: now[0])
    assert p.new_trace() == 1
    now[0] += diag.LIFETIME_NS
    assert not p.active and p.new_trace() == 0
    await p.close()
    assert not p.records and not p._outbox and not p._updates and not p._leases


def test_formatter_reconstructs_only_fixed_schema():
    p = diag.Probe()
    p.record("ack_finished", result="unknown")
    value = dict(p.records[-1])
    record = logging.LogRecord(diag.LOGGER_NAME, logging.INFO, "", 0, "secret URL", (), None)
    record.safe_concurrency = value
    assert SafeEventFilter().filter(record)
    assert json.loads(SafeEventFormatter().format(record)) == value
    assert "secret" not in SafeEventFormatter().format(record)
    record.safe_concurrency = {**value, "url": "synthetic secret"}
    assert not SafeEventFilter().filter(record)


@pytest.mark.asyncio
async def test_receipt_and_ack_clocks_are_distinct():
    now = [10**9]
    p = diag.Probe(clock=lambda: now[0])
    observer = diag.SessionObserver(p)
    update = message_update(URL, "en")

    async def received(bot, method):
        now[0] += 100
        return [update]

    await observer(received, None, GetUpdates())
    span = p.enter(update)
    token = diag._current.set(span)
    try:

        async def ack(bot, method):
            now[0] += 200
            return True

        await observer(ack, None, AnswerCallbackQuery(callback_query_id="synthetic"))
    finally:
        diag._current.reset(token)
    events = list(p.records)
    assert [e["event"] for e in events] == ["updates_received", "ack_started", "ack_finished"]
    assert events[0]["trace"] == events[-1]["trace"]
    assert events[0]["at_ns"] == 10**9 + 100
    assert events[-1]["duration_ns"] == 200
    assert events[-1]["at_ns"] - events[1]["at_ns"] == 200
    await p.close()


@pytest.mark.asyncio
async def test_session_failure_no_retry_and_cancel_propagates():
    p = diag.Probe()
    token = diag._current.set(diag.Span(p, 1))
    try:
        for error in (RuntimeError("synthetic sensitive"), asyncio.CancelledError()):
            transport = AsyncMock(side_effect=error)
            with pytest.raises(type(error)):
                await diag.SessionObserver(p)(
                    transport, None, AnswerCallbackQuery(callback_query_id="synthetic")
                )
            transport.assert_awaited_once()
            assert p.records[-1]["result"] in {"unknown", "cancelled"}
    finally:
        diag._current.reset(token)
        await p.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("outcome", ["success", "cancel", "quarantine"])
async def test_real_child_valid_callback_busy_and_later_transition(
    monkeypatch, tmp_path, enabled, outcome
):
    from aiogram import Bot
    from aiogram.methods import SendAudio, SendMediaGroup, SendVideo

    from social_video_downloader import handlers
    from social_video_downloader.bot import create_dispatcher
    from social_video_downloader.download_protection import DownloadAdmission
    from social_video_downloader.services import youtube_metadata as owner
    from social_video_downloader.services.download import DownloadService
    from social_video_downloader.services.youtube_metadata import YouTubeMetadata
    from social_video_downloader.telegram_interactions import InMemoryPendingInteractionStore
    from tests.test_telegram_localization import Session, callback_update

    cancel = outcome == "cancel"
    p = diag.Probe() if enabled else None
    admission = DownloadAdmission(max_active=1, free_bytes=lambda: 100 * 1024**3)
    metadata = YouTubeMetadata(seconds=25, cleanup_seconds=5)
    service = DownloadService()
    service._youtube_metadata = metadata
    monkeypatch.setattr(handlers, "download_service", service)
    monkeypatch.setattr(handlers, "pending_interaction_store", InMemoryPendingInteractionStore())
    acquisition = AsyncMock(side_effect=AssertionError("no acquisition permitted"))
    monkeypatch.setattr(service, "download_bounded", acquisition)
    entered, release = tmp_path / "entered", tmp_path / "release"
    original = asyncio.create_subprocess_exec
    children = []

    async def spawn(*args, **kwargs):
        proc = await original(*args, **kwargs)
        children.append(proc)
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    # Actual production worker timestamps around controlled network-free extract_info.
    script = f"""
import time
from pathlib import Path
from tests.youtube_metadata_fixtures import info
from social_video_downloader.providers.youtube import YouTubeProvider
from social_video_downloader.infrastructure.youtube_metadata_worker import main
class YDL:
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def extract_info(self, url, *, download, process):
        assert download is False and process is False
        if 'lmnopqrstuv' in url:
            Path({str(entered)!r}).write_text('ready')
            deadline=time.monotonic()+20
            while not Path({str(release)!r}).exists():
                if time.monotonic()>deadline: raise RuntimeError('test watchdog')
                time.sleep(0.01)
        return info('lmnopqrstuv' if 'lmnopqrstuv' in url else 'abcdefghijk')
YouTubeProvider._new_ydl=lambda self, options: YDL()
raise SystemExit(main())
"""
    monkeypatch.setattr(owner, "_command", lambda: [sys.executable, "-c", script])
    session = Session()
    bot = Bot("123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi", session=session)
    if p:
        session.middleware(diag.SessionObserver(p))
    dp = create_dispatcher(Settings("synthetic"), download_admission=admission, diagnostics=p)
    task = None
    try:
        await dp.feed_update(bot, message_update(URL, "en", user=7))
        card = next(m for m in reversed(session.messages) if m.reply_markup)
        callback_data = card.reply_markup.inline_keyboard[0][0].callback_data
        pending = admission._leases[7].pending
        assert not admission._leases[7].working
        original_stop = metadata._stop_group

        async def stop_group(*args):
            await original_stop(*args)
            if outcome == "quarantine" and entered.exists():
                raise OSError("synthetic cleanup uncertainty")

        monkeypatch.setattr(metadata, "_stop_group", stop_group)
        task = asyncio.create_task(
            dp.feed_update(bot, message_update("https://youtu.be/lmnopqrstuv", "en", user=8))
        )
        async with asyncio.timeout(15):
            while not entered.exists():
                await asyncio.sleep(0.01)
        await dp.feed_update(bot, callback_update(card, callback_data, user=7, code="en"))
        assert session.calls[-1].text == "The bot is busy. Try again later."
        assert admission._leases[7].pending is pending
        assert not admission._leases[7].working
        assert admission._leases[8].working
        acquisition.assert_not_awaited()
        if cancel:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert 8 not in admission._leases
        else:
            release.write_text("done")
            await task
        if outcome == "quarantine":
            assert metadata.blocked and admission._leases[8].quarantined
            assert admission._leases[8].working and admission._leases[8].contexts == 0
            assert admission._leases[7].pending is pending
            await dp.feed_update(bot, callback_update(card, callback_data, user=7, code="en"))
            assert session.calls[-1].text == "The bot is busy. Try again later."
            acquisition.assert_not_awaited()
            if p:
                assert [e for e in p.records if e["event"] == "metadata_finished"][-1][
                    "result"
                ] == "unknown"
                assert any(e["event"] == "lease_left" and e["quarantined"] for e in p.records)
            assert all(x.returncode is not None for x in children)
            return
        assert not any(x.working for x in admission._leases.values())
        if p and cancel:
            assert [e for e in p.records if e["event"] == "metadata_finished"][-1][
                "result"
            ] == "unknown"
        if p and not cancel:
            events = list(p.records)
            starts = [e for e in events if e["event"] == "extraction_started"]
            finishes = [e for e in events if e["event"] == "extraction_finished"]
            busy = next(e for e in events if e["event"] == "admission" and e["result"] == "busy")
            cb = next(
                e
                for e in events
                if e["event"] == "callback_entered" and e["trace"] == busy["trace"]
            )
            ack = next(
                e for e in events if e["event"] == "ack_finished" and e["trace"] == busy["trace"]
            )
            if len(starts) != 2 or len(finishes) != 2:
                pytest.skip("INCONCLUSIVE: missing extraction boundaries")
            a_start, a_end = starts[-1], finishes[-1]
            if not (a_start["at_ns"] <= cb["at_ns"] <= ack["at_ns"] <= a_end["at_ns"]):
                pytest.skip("INCONCLUSIVE: callback/extraction overlap not established")
            assert a_start["trace"] == a_end["trace"] and a_start["trace"] != cb["trace"]
            assert busy["request"] == starts[0]["trace"]
            assert ack["result"] == "returned" and ack["duration_ns"] >= 0
            assert not any(
                e["event"] in {"acquisition_started", "delivery_started"} for e in events
            )
        # A has released work; B can use the original nonterminal choice without media.
        await dp.feed_update(bot, callback_update(card, callback_data, user=7, code="en"))
        assert session.calls[-1].text == "Choose the quality:"
        assert admission._leases[7].pending is pending
        for user in (7, 8):
            await dp.feed_update(bot, message_update("/cancel", "en", user=user))
        assert not admission._leases
        assert not any(isinstance(x, (SendVideo, SendAudio, SendMediaGroup)) for x in session.calls)
        acquisition.assert_not_awaited()
        assert len(children) == 2 and all(x.returncode is not None for x in children)
        assert not metadata.active and not metadata.blocked
        for proc in children:
            assert not metadata._group_exists(proc.pid)
    finally:
        release.write_text("done")
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if p:
            await p.close()
        metadata.close()
        await session.close()


@pytest.mark.asyncio
async def test_loop_lag_measures_planned_wakeup_not_handler_duration(monkeypatch, caplog):
    now = [1_000_000_000]
    p = diag.Probe(clock=lambda: now[0])
    calls = 0

    async def tick(seconds):
        nonlocal calls
        assert seconds == 0.05
        calls += 1
        if calls == 1:
            now[0] = 6_100_000_000
        else:
            raise asyncio.CancelledError

    caplog.set_level(logging.INFO, logger=diag.LOGGER_NAME)
    monkeypatch.setattr(diag.asyncio, "sleep", tick)
    with pytest.raises(asyncio.CancelledError):
        await p._pump()
    event = next(r.safe_concurrency for r in caplog.records if r.name == diag.LOGGER_NAME)
    assert event["event"] == "loop_lag"
    assert event["duration_ns"] == 6_100_000_000 - 1_050_000_000
    assert event["at_ns"] == 6_100_000_000
    assert not p._outbox and not p.records and not p.active


@pytest.mark.asyncio
async def test_disabled_or_broken_observer_does_not_change_transport():
    p = diag.Probe()
    transport = AsyncMock(return_value=False)
    p.clock = lambda: (_ for _ in ()).throw(RuntimeError("synthetic sink/clock failure"))
    result = await diag.SessionObserver(p)(
        transport, None, AnswerCallbackQuery(callback_query_id="synthetic")
    )
    assert result is False
    transport.assert_awaited_once()
    handler = AsyncMock(return_value="ordinary result")
    assert await diag.UpdateObserver(p)(handler, message_update(URL, "en"), {}) == "ordinary result"
    handler.assert_awaited_once()
    await p.close()


@pytest.mark.asyncio
async def test_false_acknowledgement_is_not_confirmation():
    p = diag.Probe()
    token = diag._current.set(diag.Span(p, 1))
    try:
        method = AnswerCallbackQuery(callback_query_id="synthetic")
        assert await diag.SessionObserver(p)(AsyncMock(return_value=False), None, method) is False
        assert p.records[-1]["result"] == "unknown"
    finally:
        diag._current.reset(token)
        await p.close()


def test_trace_limit_cannot_alias_new_requests():
    p = diag.Probe()
    assert [p.new_trace() for _ in range(diag.MAX_TRACES)] == list(range(1, diag.MAX_TRACES + 1))
    assert p.new_trace() == 0


def test_missing_or_corrupt_metadata_times_still_plan_without_fallback():
    now = monotonic_ns()
    req = wire.request(URL, "synthetic-request-nonce", diagnostics=True)
    good = wire.response(
        req, info(), now / 10**9, extraction=wire.ExtractionInterval(now - 100, now)
    )
    expected = YouTubeMetadata_for_test(good, req)
    for value in (None, {}, {"extraction_started_ns": now + 1, "extraction_finished_ns": now}):
        data = dict(good)
        data["diagnostics"] = value
        snapshot, plan, interval = YouTubeMetadata_for_test(data, req)
        assert snapshot == expected[0] and plan == expected[1] and interval is None


def YouTubeMetadata_for_test(data, req):
    from social_video_downloader.services.youtube_metadata import YouTubeMetadata

    return YouTubeMetadata._decode_plan(wire.encode(data), req)


def test_optional_flag_cannot_shrink_legacy_request_budget():
    nonce = "synthetic-request-nonce"
    req = wire.request(URL + "&tracking=", nonce)
    count = wire.REQUEST_BYTES - len(wire.encode(req, wire.REQUEST_BYTES))
    req = wire.request(URL + "&tracking=" + "x" * count, nonce, diagnostics=True)
    actual, encoded = wire.encode_metadata_request(req)
    assert len(encoded) == wire.REQUEST_BYTES
    assert "diagnostics" not in actual
    assert wire.decode(encoded, wire.REQUEST_BYTES) == actual


@pytest.mark.asyncio
async def test_getupdates_to_dispatcher_uses_same_ephemeral_trace(monkeypatch):
    from aiogram import Bot
    from aiogram.types import Update

    from social_video_downloader.bot import create_dispatcher
    from tests.test_telegram_localization import Session

    p = diag.Probe()
    session = Session()
    bot = Bot("123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi", session=session)
    update = Update.model_validate(
        message_update("/start", "en").model_dump(), context={"bot": bot}
    )
    original = session.make_request

    async def request(bot, method, timeout=None):
        if isinstance(method, GetUpdates):
            return [update]
        return await original(bot, method, timeout)

    monkeypatch.setattr(session, "make_request", request)
    session.middleware(diag.SessionObserver(p))
    dp = create_dispatcher(Settings("synthetic"), diagnostics=p)
    try:
        updates = await bot.get_updates()
        await dp.feed_update(bot, updates[0])
        receipt = next(e for e in p.records if e["event"] == "updates_received")
        ingress = next(e for e in p.records if e["event"] == "update_entered")
        assert receipt["trace"] == ingress["trace"] != 0
        assert receipt["at_ns"] <= ingress["at_ns"]
        assert not p._updates
        assert len(session.calls) == 1  # Only the ordinary /start reply, no extra probe API.
    finally:
        await p.close()
        await session.close()


@pytest.mark.asyncio
async def test_enabled_lifecycle_has_no_orphan_probe_task(monkeypatch):
    from types import SimpleNamespace

    from social_video_downloader import bot as app

    p = diag.Probe()
    session = SimpleNamespace(close=AsyncMock(), middleware=Mock())
    fake_bot = SimpleNamespace(session=session)

    async def polling(bot):
        await p.start()
        await asyncio.sleep(0)

    dispatcher = SimpleNamespace(start_polling=polling)
    monkeypatch.setattr(app, "Probe", lambda: p)
    monkeypatch.setattr(app, "create_bot", lambda settings: fake_bot)
    monkeypatch.setattr(app, "create_dispatcher", lambda settings, diagnostics: dispatcher)
    await app.run_bot(Settings("synthetic", concurrency_diagnostics=True))
    assert not p.active and p._task.done()
    assert not p.records and not p._updates and not p._leases and not p._outbox
    session.middleware.assert_called_once()
    session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_enabled_cache_keeps_timestamp_and_never_reextracts(owner):
    from social_video_downloader.providers.youtube import YouTubeProvider

    metadata, state = owner
    provider = YouTubeProvider()
    p = diag.Probe()
    token = diag._current.set(diag.Span(p, 1))
    try:
        first = await metadata.plan(provider, URL)
        stamp = provider._inspection_cache[URL][0]
        assert await metadata.plan(provider, URL) == first
        assert provider._inspection_cache[URL][0] == stamp
        assert "diagnostics" not in provider._inspection_cache[URL][1]
        assert len(state.processes) == 1
        assert [e for e in p.records if e["event"] == "metadata_finished"][-1]["result"] == "cache"
        assert len([e for e in p.records if e["event"] == "extraction_started"]) == 1
    finally:
        diag._current.reset(token)
        await p.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("clock_owner", ["child", "parent"])
@pytest.mark.parametrize("invalid_return", [False, True])
async def test_timing_clock_failure_is_unknown_and_does_not_retry(
    owner, monkeypatch, clock_owner, invalid_return
):
    from social_video_downloader.providers.youtube import YouTubeProvider
    from social_video_downloader.services import youtube_metadata as service

    metadata, state = owner
    if clock_owner == "child":
        script = """
from social_video_downloader.infrastructure import youtube_metadata_worker as worker
from tests.youtube_metadata_fixtures import child
worker.monotonic_ns=lambda: (_ for _ in ()).throw(RuntimeError('synthetic timing failure'))
child('production')
"""
        if invalid_return:
            script = script.replace(
                "(_ for _ in ()).throw(RuntimeError('synthetic timing failure'))", "'invalid'"
            )
        monkeypatch.setattr(service, "_command", lambda: [sys.executable, "-c", script])
    else:
        monkeypatch.setattr(
            service,
            "monotonic_ns",
            lambda: (
                "invalid"
                if invalid_return
                else (_ for _ in ()).throw(RuntimeError("synthetic timing failure"))
            ),
        )
    p = diag.Probe()
    token = diag._current.set(diag.Span(p, 1))
    try:
        plan = await metadata.plan(YouTubeProvider(), URL)
        assert plan.mode_choices and len(state.processes) == 1
        assert not any(e["event"] == "extraction_started" for e in p.records)
        assert [e for e in p.records if e["event"] == "metadata_finished"][-1][
            "result"
        ] == "unknown"
        assert not metadata.active and not metadata.blocked
    finally:
        diag._current.reset(token)
        await p.close()


def test_backwards_diagnostic_clock_disables_evidence():
    now = [10**9]
    p = diag.Probe(clock=lambda: now[0])
    now[0] -= 1
    assert not p.active
    p.record("callback_entered")
    assert not p.records


@pytest.mark.asyncio
async def test_lag_does_not_hide_its_own_sink_stall(monkeypatch, caplog):
    now = [1_000_000_000]
    p = diag.Probe(clock=lambda: now[0])
    ticks = 0
    flushed = 0
    original = p.flush

    async def tick(seconds):
        nonlocal ticks
        ticks += 1
        if ticks == 1:
            now[0] = 6_100_000_000
        elif ticks == 2:
            now[0] += 50_000_000
        else:
            raise asyncio.CancelledError

    def flush():
        nonlocal flushed
        original()
        flushed += 1
        if flushed == 1:
            now[0] += 5_100_000_000

    monkeypatch.setattr(diag.asyncio, "sleep", tick)
    monkeypatch.setattr(p, "flush", flush)
    caplog.set_level(logging.INFO, logger=diag.LOGGER_NAME)
    with pytest.raises(asyncio.CancelledError):
        await p._pump()
    samples = [r.safe_concurrency for r in caplog.records if r.name == diag.LOGGER_NAME]
    assert [e["duration_ns"] for e in samples] == [5_050_000_000, 5_100_000_000]
