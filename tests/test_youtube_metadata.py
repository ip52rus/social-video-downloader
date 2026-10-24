"""Real offline children, cancellation, group cleanup and event-loop responsiveness."""

import asyncio
import gc
import json
import os
import signal
import statistics
import sys
import threading
import time
from contextlib import suppress
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from social_video_downloader.domain.errors import MetadataBusyError, MetadataExtractionError
from social_video_downloader.infrastructure import youtube_snapshot as wire
from social_video_downloader.providers.youtube import YouTubeProvider
from social_video_downloader.services import youtube_metadata as service
from social_video_downloader.services.choice_model import build_choice_plan
from tests.test_youtube_snapshot import URL, info


@pytest_asyncio.fixture
async def owner(monkeypatch):
    supervisor = service.YouTubeMetadata(seconds=8, cleanup_seconds=3)
    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()
    loop_errors = []
    loop.set_exception_handler(lambda _, context: loop_errors.append(context))
    state = SimpleNamespace(
        processes=[], mode="production", spawning=asyncio.Event(), spawned=asyncio.Event()
    )
    original = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        state.spawning.set()
        kwargs["stderr"] = asyncio.subprocess.PIPE
        process = await original(*args, **kwargs)
        state.processes.append(process)
        state.spawned.set()
        return process

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(
        service,
        "_command",
        lambda: [
            sys.executable,
            "-c",
            f"from tests.youtube_metadata_fixtures import child;child({state.mode!r})",
        ],
    )
    for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_API_ID", "TELEGRAM_API_HASH", "HTTPS_PROXY"):
        monkeypatch.setenv(key, "synthetic-secret-not-for-child")
    try:
        yield supervisor, state
    finally:
        # Rescue only test-owned groups if an assertion fails, then reap direct children.
        for process in state.processes:
            await service.YouTubeMetadata._stop_group(
                supervisor, process, time.monotonic() + 5, [False]
            )
        for task in list(supervisor._late_spawns):
            with suppress(Exception):
                await asyncio.wait_for(asyncio.shield(task), 5)
        supervisor.close()
        gc.collect()
        await asyncio.sleep(0)
        loop.set_exception_handler(previous_handler)
        assert not supervisor.active
        assert all(process.returncode is not None for process in state.processes)
        assert all(not thread.is_alive() for thread in supervisor._executor._threads)
        assert not loop_errors


def assert_reaped(state):
    for process in state.processes:
        assert process.returncode is not None
        with pytest.raises(ProcessLookupError):
            os.killpg(process.pid, 0)


@pytest.mark.asyncio
async def test_production_worker_metadata_only_cache_and_private_plan(owner):
    supervisor, state = owner
    provider = YouTubeProvider()
    before = time.monotonic()
    plan = await supervisor.plan(provider, URL)
    assert plan == build_choice_plan(_fixture_provider(), URL)
    assert before <= provider._inspection_cache[URL][0] <= time.monotonic()
    assert len(state.processes) == 1
    assert await supervisor.plan(provider, URL) == plan
    assert len(state.processes) == 1
    assert_reaped(state)


def _fixture_provider():
    provider = YouTubeProvider()
    provider._remember_info(URL, info())
    return provider


@pytest.mark.asyncio
@pytest.mark.parametrize("same_url", [True, False])
async def test_busy_rejected_before_spawn_or_external_work(owner, same_url):
    supervisor, state = owner
    state.mode = "slow"
    provider = YouTubeProvider()
    task = asyncio.create_task(supervisor.plan(provider, URL))
    try:
        await state.spawned.wait()
        with pytest.raises(MetadataBusyError):
            await supervisor.plan(provider, URL if same_url else "https://youtu.be/lmnopqrstuv")
        assert len(state.processes) == 1
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert_reaped(state)
    assert not supervisor.blocked and not provider._inspection_cache


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["silent", "stubborn", "descendant"])
@pytest.mark.parametrize("repeated", [False, True])
async def test_cancel_and_repeat_kill_whole_group_before_release(owner, mode, repeated):
    supervisor, state = owner
    state.mode = mode
    task = asyncio.create_task(supervisor.plan(YouTubeProvider(), URL))
    await state.spawned.wait()
    marker = await asyncio.wait_for(state.processes[-1].stderr.readline(), 3)
    assert marker == b"ready\n"  # Descendant/TERM behavior is established before cancellation.
    task.cancel()
    if repeated:
        for _ in range(5):
            await asyncio.sleep(0.01)
            task.cancel()
            if not task.done():
                assert supervisor.active
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not supervisor.active and not supervisor.blocked
    assert_reaped(state)


@pytest.mark.asyncio
async def test_cancel_during_unresolved_spawn_is_owned(owner, monkeypatch):
    supervisor, state = owner
    real = service.asyncio.create_subprocess_exec
    release = asyncio.Event()

    async def delayed(*args, **kwargs):
        state.spawning.set()
        await release.wait()
        return await real(*args, **kwargs)

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", delayed)
    state.mode = "silent"
    task = asyncio.create_task(supervisor.plan(YouTubeProvider(), URL))
    try:
        await state.spawning.wait()
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        assert supervisor.active and not task.done()
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert_reaped(state)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode", ["malformed", "partial", "oversize", "crash", "wrong_id", "unsupported", "silent"]
)
async def test_faults_refuse_without_cache_or_fallback(owner, mode):
    supervisor, state = owner
    supervisor.seconds = 4
    supervisor.cleanup_seconds = 2
    state.mode = mode
    provider = YouTubeProvider(lambda _: pytest.fail("parent extraction forbidden"))
    with pytest.raises(MetadataExtractionError):
        await supervisor.plan(provider, URL)
    assert not provider._inspection_cache
    assert not supervisor.active and not supervisor.blocked
    assert len(state.processes) == 1
    assert_reaped(state)


@pytest.mark.asyncio
async def test_spawn_failure_releases_slot(owner, monkeypatch):
    supervisor, state = owner

    async def failed(*args, **kwargs):
        raise OSError("synthetic private spawn error")

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", failed)
    with pytest.raises(MetadataExtractionError):
        await supervisor.plan(YouTubeProvider(), URL)
    assert not supervisor.active and not supervisor.blocked and not state.processes


@pytest.mark.asyncio
async def test_unknown_cleanup_quarantines_only_metadata(owner, monkeypatch):
    supervisor, state = owner

    async def unconfirmed(*args):
        raise OSError("synthetic cleanup failure")

    monkeypatch.setattr(supervisor, "_stop_group", unconfirmed)
    with pytest.raises(MetadataExtractionError):
        await supervisor.plan(YouTubeProvider(), URL)
    assert supervisor.blocked
    with pytest.raises(MetadataBusyError):
        await supervisor.plan(YouTubeProvider(), URL)
    assert len(state.processes) == 1
    # No shared Instagram/TikTok admission object is involved.


@pytest.mark.asyncio
async def test_cancelled_late_spawn_keeps_quarantine_and_eventual_owner(owner, monkeypatch):
    supervisor, state = owner
    supervisor.seconds, supervisor.cleanup_seconds = 0.2, 0.1
    real = service.asyncio.create_subprocess_exec
    release = asyncio.Event()

    async def delayed(*args, **kwargs):
        await release.wait()
        return await real(*args, **kwargs)

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", delayed)
    state.mode = "silent"
    try:
        with pytest.raises(MetadataExtractionError):
            await supervisor.plan(YouTubeProvider(), URL)
        assert supervisor.blocked and supervisor._late_spawns
    finally:
        release.set()
        for task in list(supervisor._late_spawns):
            await asyncio.wait_for(asyncio.shield(task), 5)
    assert supervisor.blocked
    assert_reaped(state)


@pytest.mark.asyncio
async def test_planning_copy_survives_concurrent_cache_consumption(owner):
    supervisor, state = owner
    provider = _fixture_provider()
    stamp, copy = await supervisor._cpu(provider._planning_snapshot, URL)
    consumed = await asyncio.to_thread(provider._take_cached_info, URL)
    consumed["formats"].clear()
    req = wire.request(URL, "synthetic-request-nonce")
    plan = await supervisor._cpu(supervisor._cached_plan, req, stamp, copy)
    assert plan == build_choice_plan(_fixture_provider(), URL)
    assert not state.processes


async def _measure(operation):
    from social_video_downloader.handlers import handle_choice_callback

    running = [True]
    lags = []
    callback = SimpleNamespace(data="invalid", answer=AsyncMock())
    due = time.monotonic() + 0.05

    async def callback_event():
        await asyncio.sleep(0.05)
        await handle_choice_callback(callback)
        return max(0, time.monotonic() - due)

    async def ticker():
        while running[0]:
            planned = time.monotonic() + 0.01
            await asyncio.sleep(0.01)
            lags.append(max(0, time.monotonic() - planned))

    heartbeat = asyncio.create_task(ticker())
    independent = asyncio.create_task(callback_event())
    start = time.monotonic()
    try:
        await asyncio.sleep(0)  # Register both timers before the blocking legacy call.
        await operation()
    finally:
        running[0] = False
        latency = await independent
        await heartbeat
    callback.answer.assert_awaited_once()
    return latency, max(lags), time.monotonic() - start


@pytest.mark.asyncio
async def test_latency_two_seconds_child_preserves_callback_and_heartbeat(owner):
    from social_video_downloader.services.download import DownloadService

    supervisor, state = owner
    state.mode = "slow"
    baseline, after = [], []

    class SlowYDL:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def extract_info(self, *args, **kwargs):
            assert kwargs == dict(download=False, process=False)
            time.sleep(2)
            return info()

    for _ in range(3):
        legacy = DownloadService([YouTubeProvider(lambda _: SlowYDL())])

        async def old_path(legacy=legacy):
            legacy.create_choice_plan(URL)

        baseline.append(await _measure(old_path))
        after.append(await _measure(lambda: supervisor.plan(YouTubeProvider(), URL)))
    metrics = {}
    for name, samples in (("before", baseline), ("after", after)):
        metrics[name] = {
            "callback_p50_ms": statistics.median(x[0] for x in samples) * 1000,
            "callback_max_ms": max(x[0] for x in samples) * 1000,
            "heartbeat_p50_max_lag_ms": statistics.median(x[1] for x in samples) * 1000,
            "heartbeat_max_lag_ms": max(x[1] for x in samples) * 1000,
            "operation_p50_ms": statistics.median(x[2] for x in samples) * 1000,
        }
    print("offline metadata latency", json.dumps(metrics, sort_keys=True))
    assert metrics["before"]["callback_p50_ms"] >= 1800
    assert metrics["after"]["callback_max_ms"] < 500
    assert metrics["after"]["heartbeat_max_lag_ms"] < 500
    assert_reaped(state)


@pytest.mark.asyncio
async def test_cancel_before_spawn_does_not_claim_or_launch(owner):
    supervisor, state = owner
    task = asyncio.create_task(supervisor.plan(YouTubeProvider(), URL))
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not supervisor.active and not state.processes


@pytest.mark.asyncio
async def test_ipc_write_failure_cleans_real_child(owner, monkeypatch):
    supervisor, state = owner
    real = service.asyncio.create_subprocess_exec

    async def broken(*args, **kwargs):
        process = await real(*args, **kwargs)
        writer = process.stdin

        def fail(_):
            raise BrokenPipeError("synthetic private payload")

        process.stdin = SimpleNamespace(write=fail, close=writer.close)
        return process

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", broken)
    with pytest.raises(MetadataExtractionError):
        await supervisor.plan(YouTubeProvider(), URL)
    assert not supervisor.blocked
    assert_reaped(state)


@pytest.mark.asyncio
async def test_cancel_while_finite_decoder_runs_retains_slot_and_does_not_publish(
    owner, monkeypatch
):
    supervisor, state = owner
    entered = asyncio.Event()
    release = threading.Event()
    original = supervisor._decode_plan
    loop = asyncio.get_running_loop()

    def held(*args):
        loop.call_soon_threadsafe(entered.set)
        assert release.wait(5)
        return original(*args)

    monkeypatch.setattr(supervisor, "_decode_plan", held)
    provider = YouTubeProvider()
    task = asyncio.create_task(supervisor.plan(provider, URL))
    try:
        await asyncio.wait_for(entered.wait(), 4)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        assert supervisor.active and not task.done()
        assert_reaped(state)
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert not provider._inspection_cache and not supervisor.active


@pytest.mark.asyncio
async def test_group_probe_permission_is_unknown_until_proven_absent(owner, monkeypatch):
    supervisor, state = owner
    real = os.killpg
    errors = []

    def probe(pid, sig):
        if sig == 0 and not errors:
            errors.append("transient EPERM")
            raise PermissionError("zombie-only group")
        return real(pid, sig)

    monkeypatch.setattr(os, "killpg", probe)
    await supervisor.plan(YouTubeProvider(), URL)
    assert errors and not supervisor.blocked
    assert_reaped(state)


@pytest.mark.asyncio
@pytest.mark.parametrize("same_url", [True, False])
async def test_sequential_users_keep_separate_bound_snapshots(owner, same_url):
    supervisor, state = owner
    provider = YouTubeProvider()
    await supervisor.plan(provider, URL)
    other = URL if same_url else "https://youtu.be/lmnopqrstuv"
    await supervisor.plan(provider, other)
    assert len(state.processes) == (1 if same_url else 2)
    assert provider._cached_info(other)["id"] == wire.target(other)[1]
    assert_reaped(state)


@pytest.mark.asyncio
async def test_real_handler_uses_async_service_and_produces_only_choices(owner, monkeypatch):
    from unittest.mock import MagicMock

    from social_video_downloader import handlers
    from social_video_downloader.services.download import DownloadService

    supervisor, state = owner
    configured = DownloadService()
    configured._youtube_metadata = supervisor
    monkeypatch.setattr(handlers, "download_service", configured)
    msg = MagicMock()
    msg.text = URL
    card = SimpleNamespace(message_id=789, edit_text=AsyncMock())
    msg.answer = AsyncMock(return_value=card)
    msg.answer_video = AsyncMock()
    msg.answer_audio = AsyncMock()
    msg.chat.id, msg.from_user.id = 2, 1
    await handlers.handle_text(msg)
    msg.answer.assert_awaited_once()
    assert msg.answer.call_args.kwargs.get("reply_markup") is None
    card.edit_text.assert_awaited_once()
    assert card.edit_text.call_args.kwargs["reply_markup"] is not None
    msg.answer_video.assert_not_awaited()
    msg.answer_audio.assert_not_awaited()
    assert len(state.processes) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url,argument",
    [
        ("https://www.instagram.com/reel/Fixture/", "instagram_reels"),
        ("https://www.tiktok.com/@fixture/video/12345678", "tiktok_videos"),
    ],
)
async def test_quarantined_youtube_does_not_block_other_routes(owner, monkeypatch, url, argument):
    from social_video_downloader import handlers
    from social_video_downloader.services.download import DownloadService

    supervisor, state = owner
    supervisor.blocked = True
    configured = DownloadService()
    configured._youtube_metadata = supervisor
    monkeypatch.setattr(handlers, "download_service", configured)
    route = SimpleNamespace(handle=AsyncMock())
    msg = SimpleNamespace(text=url)
    await handlers.handle_text(msg, **{argument: route})
    route.handle.assert_awaited_once()
    assert not state.processes


@pytest.mark.asyncio
async def test_snapshot_publication_waits_for_confirmed_cleanup(owner, monkeypatch):
    supervisor, state = owner
    entered, release = asyncio.Event(), asyncio.Event()
    original = supervisor._stop_group

    async def held(*args):
        entered.set()
        await release.wait()
        return await original(*args)

    monkeypatch.setattr(supervisor, "_stop_group", held)
    provider = YouTubeProvider()
    task = asyncio.create_task(supervisor.plan(provider, URL))
    try:
        await asyncio.wait_for(entered.wait(), 4)
        assert supervisor.active and not provider._inspection_cache
    finally:
        release.set()
        await task
    assert provider._cached_info(URL) is not None
    assert_reaped(state)


@pytest.mark.asyncio
async def test_returncode_alone_is_not_group_completion(owner, monkeypatch):
    supervisor, _ = owner
    signals = []
    checks = []

    def group_probe(pid):
        checks.append(pid)
        return True  # A direct child's returncode cannot prove descendant absence.

    monkeypatch.setattr(supervisor, "_group_exists", group_probe)
    monkeypatch.setattr(os, "killpg", lambda pid, sig: signals.append(sig))
    process = SimpleNamespace(
        pid=123, returncode=0, stdin=SimpleNamespace(close=lambda: None), wait=AsyncMock()
    )
    with pytest.raises(MetadataExtractionError):
        await supervisor._stop_group(process, time.monotonic() + 0.02, [False])
    assert checks and signal.SIGTERM in signals and signal.SIGKILL in signals
    process.wait.assert_not_awaited()


@pytest.mark.asyncio
async def test_oversized_request_is_refused_before_child(owner):
    supervisor, state = owner
    with pytest.raises(MetadataExtractionError):
        await supervisor.plan(YouTubeProvider(), URL + "&tracking=" + "x" * 9000)
    assert not state.processes and not supervisor.active


def test_application_services_share_process_admission():
    from social_video_downloader.services.download import DownloadService

    assert DownloadService()._youtube_metadata is DownloadService()._youtube_metadata


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["malformed", "unsupported", "silent"])
async def test_fixed_events_never_include_ipc_or_upstream_details(owner, mode, caplog):
    import logging

    from social_video_downloader.operation_logging import LOGGER_NAME, Operation, safe_payload

    supervisor, state = owner
    state.mode = mode
    supervisor.seconds, supervisor.cleanup_seconds = 4, 2
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)
    with pytest.raises(MetadataExtractionError), Operation("youtube", "metadata"):
        await supervisor.plan(YouTubeProvider(), URL)
    events = [record for record in caplog.records if record.name == LOGGER_NAME]
    assert events and all(safe_payload(json.loads(record.message)) for record in events)
    assert all(record.exc_info is None for record in events)
    assert URL not in caplog.text and "abcdefghijk" not in caplog.text
    assert "synthetic-secret-not-for-child" not in caplog.text
    assert "synthetic private" not in caplog.text
    assert_reaped(state)


@pytest.mark.asyncio
async def test_already_reaped_child_still_drains_rejected_pipe_buffer(owner, monkeypatch):
    supervisor, _ = owner
    output = asyncio.StreamReader()
    output.feed_data(b"synthetic rejected reply")
    output.feed_eof()
    process = SimpleNamespace(
        pid=123,
        returncode=0,
        stdin=SimpleNamespace(close=lambda: None),
        stdout=output,
        stderr=None,
        wait=AsyncMock(),
    )
    monkeypatch.setattr(supervisor, "_group_exists", lambda _: False)
    await supervisor._stop_group(process, time.monotonic() + 1, [False])
    assert output.at_eof()
    process.wait.assert_awaited_once()
