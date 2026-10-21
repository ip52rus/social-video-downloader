"""Synthetic lifecycle events and privacy; no external sockets or real Telegram."""

import asyncio
import json
import logging
import socket
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import SendVideo

from social_video_downloader import handlers as yt
from social_video_downloader import operation_logging as events
from social_video_downloader import telegram_instagram as ig
from social_video_downloader import telegram_tiktok as tt
from social_video_downloader.domain.errors import MetadataExtractionError
from social_video_downloader.domain.models import DownloadOptions
from social_video_downloader.providers.youtube import YouTubeProvider
from tests.test_handlers import FakeDownloadService
from tests.test_telegram_carousel import response

PRIVATE = "SECRET_cookie_token_signed_URL_user_1234567_<html>_/private/file"


@pytest.fixture(autouse=True)
def offline(monkeypatch, caplog):
    def deny(*a, **kw):
        raise AssertionError("External socket forbidden")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    caplog.set_level(logging.INFO, logger=events.LOGGER_NAME)


def payloads(caplog):
    result = [json.loads(r.getMessage()) for r in caplog.records if r.name == events.LOGGER_NAME]
    assert PRIVATE not in caplog.text
    assert all(r.exc_info is None for r in caplog.records if r.name == events.LOGGER_NAME)
    return result


def test_measured_duration_and_fixed_error_category(monkeypatch, caplog):
    ticks = iter([7.0, 7.125])
    monkeypatch.setattr(events, "monotonic", lambda: next(ticks))
    with events.Operation("youtube", "metadata") as operation:
        operation.fail(MetadataExtractionError(PRIVATE))
    start, end = payloads(caplog)
    assert start["event"] == "operation_started"
    assert end == dict(
        platform="youtube",
        event="operation_failed",
        phase="metadata",
        category="metadata_unavailable",
        elapsed_ms=125.0,
    )


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), -1, PRIVATE, True, 10**1000],
    ids=["nan", "infinity", "negative", "string", "bool", "huge_int"],
)
def test_invalid_duration_cannot_become_private_or_unbounded(value, caplog):
    events.emit("tiktok", "operation_completed", "cleanup", elapsed_ms=value)
    assert payloads(caplog)[0]["elapsed_ms"] is None


def test_library_stderr_errors_are_suppressed(capsys):
    logger = YouTubeProvider._base_options()["logger"]
    for method in ("debug", "info", "warning", "error"):
        getattr(logger, method)(PRIVATE)
    assert capsys.readouterr() == ("", "")


def scenario(platform, monkeypatch, *, error=None):
    msg = MagicMock()
    msg.from_user = SimpleNamespace(id=7)
    msg.chat = SimpleNamespace(id=1)
    msg.answer = AsyncMock()
    msg.answer_video = AsyncMock(return_value=response(1))
    msg.answer_audio = AsyncMock()
    paths = []
    handler = None
    if platform == "youtube":
        service = FakeDownloadService(error=error)
        monkeypatch.setattr(yt, "download_service", service)
        monkeypatch.setattr(yt, "prepare_telegram_video", lambda path: path)
        monkeypatch.setattr(
            yt,
            "inspect_telegram_video",
            lambda path: {
                "streams": [{"codec_type": "video", "width": 64, "height": 96, "private": PRIVATE}]
            },
        )

        async def run():
            await yt._download_and_deliver_media(
                msg, "https://youtu.be/Synthetic", DownloadOptions()
            )
            paths.extend(call[1] for call in service.calls)

        attempts = service.calls
    else:
        handler = tt.TelegramTikTokHandler() if platform == "tiktok" else ig.InstagramReelHandler()
        attempts = []

        def prepare(url, workspace, cancelled):
            attempts.append(True)
            paths.append(workspace)
            path = workspace / "fixture.mp4"
            path.write_bytes(b"synthetic")
            if error is not None:
                raise error
            return path, {"width": 64, "height": 96}

        monkeypatch.setattr(handler, "_prepare", prepare)
        url = (
            "https://www.tiktok.com/@synthetic/video/7000000000000000001"
            if platform == "tiktok"
            else "https://www.instagram.com/reel/Synthetic/"
        )

        async def run():
            await handler.handle(msg, url)

    return msg, run, attempts, paths, handler


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["youtube", "instagram", "tiktok"])
@pytest.mark.parametrize("kind", ["success", "expected", "unexpected", "upload", "logging"])
async def test_real_handler_lifecycle_without_sensitive_logs(monkeypatch, caplog, platform, kind):
    error = (
        MetadataExtractionError(PRIVATE)
        if kind == "expected"
        else (RuntimeError(PRIVATE) if kind == "unexpected" else None)
    )
    msg, run, attempts, paths, _ = scenario(platform, monkeypatch, error=error)
    if kind == "upload":
        msg.answer_video.side_effect = TelegramNetworkError(
            method=SendVideo(chat_id=1, video=PRIVATE), message=PRIVATE
        )
    if kind == "logging":

        def broken(*a, **kw):
            raise OSError(PRIVATE)

        monkeypatch.setattr(logging.getLogger(events.LOGGER_NAME), "log", broken)
    if kind == "unexpected" and platform == "instagram":
        with pytest.raises(RuntimeError):
            await run()
    else:
        await run()
    assert len(attempts) == 1
    assert msg.answer_video.await_count == (0 if error else 1)
    assert all(not p.exists() for p in paths)
    if kind != "logging":
        data = payloads(caplog)
        assert len(data) == 2
        assert data[-1]["event"] == (
            "operation_completed" if kind == "success" else "operation_failed"
        )
        assert (
            data[-1]["category"]
            == {
                "success": "none",
                "expected": "metadata_unavailable",
                "unexpected": "unexpected",
                "upload": "telegram_network",
            }[kind]
        )
        if kind == "upload":
            assert data[-1]["phase"] == "upload"


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["youtube", "instagram", "tiktok"])
async def test_upload_cancellation_keeps_cleanup_and_logs_cancelled(monkeypatch, caplog, platform):
    msg, run, attempts, paths, handler = scenario(platform, monkeypatch)
    entered = asyncio.Event()

    async def send(*a, **kw):
        entered.set()
        await asyncio.Event().wait()

    msg.answer_video.side_effect = send
    task = asyncio.create_task(run())
    await asyncio.wait_for(entered.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(attempts) == 1 and msg.answer_video.await_count == 1
    assert all(not p.exists() for p in paths)
    if platform == "tiktok":
        assert not handler._active_users
    elif platform == "instagram":
        assert not handler._active
    assert payloads(caplog)[-1]["category"] == "cancelled"


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, RuntimeError(PRIVATE)])
async def test_service_lifecycle_closes_session_without_logging_bot_identity(
    monkeypatch, caplog, failure
):
    from social_video_downloader import bot as app
    from social_video_downloader.config import Settings

    bot = SimpleNamespace(session=SimpleNamespace(close=AsyncMock()))
    dispatcher = SimpleNamespace(start_polling=AsyncMock(side_effect=failure))
    monkeypatch.setattr(app, "create_bot", lambda settings: bot)
    monkeypatch.setattr(app, "create_dispatcher", lambda settings: dispatcher)
    if failure:
        with pytest.raises(RuntimeError):
            await app.run_bot(Settings("SECRET_TOKEN"))
    else:
        await app.run_bot(Settings("SECRET_TOKEN"))
    bot.session.close.assert_awaited_once()
    data = payloads(caplog)
    assert data[0]["platform"] == "service"
    assert data[-1]["event"] == ("operation_failed" if failure else "operation_completed")
    if failure:
        assert data[-1]["phase"] == "polling"


@pytest.mark.asyncio
async def test_cleanup_failure_logs_quarantine_and_keeps_reservation(monkeypatch, caplog):
    from tempfile import TemporaryDirectory

    msg, run, attempts, paths, handler = scenario("tiktok", monkeypatch)
    original = TemporaryDirectory.cleanup

    def failure(directory):
        raise OSError(PRIVATE)

    monkeypatch.setattr(tt.TemporaryDirectory, "cleanup", failure)
    try:
        await run()
        assert handler._blocked and handler._active_users == {7}
        assert paths[0].exists()
        data = payloads(caplog)
        assert data[-1]["phase"] == "cleanup"
        assert data[-1]["category"] == "cleanup_failed"
        assert data[-1]["event"] == "operation_failed"
        await handler.handle(msg, "https://www.tiktok.com/@synthetic/video/7000000000000000001")
        assert len(attempts) == 1
    finally:
        monkeypatch.setattr(tt.TemporaryDirectory, "cleanup", original)
        # The synthetic worker has returned; this test owns the quarantined directory.
        import shutil

        for path in paths:
            shutil.rmtree(path)


def test_startup_failure_exits_without_raw_traceback(monkeypatch, caplog):
    from social_video_downloader import bot as app

    def broken():
        raise RuntimeError(PRIVATE)

    monkeypatch.setattr(app.Settings, "from_env", broken)
    with pytest.raises(SystemExit) as stopped:
        app.main()
    assert stopped.value.code == 1
    assert payloads(caplog)[-1]["category"] == "unexpected"
