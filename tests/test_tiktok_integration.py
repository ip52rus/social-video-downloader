"""Native worker + fake Telegram; every external socket is forbidden."""

import asyncio
import json
import os
import signal
import sys
from contextlib import suppress
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import SendVideo
from aiogram.types import Update

from social_video_downloader import telegram_tiktok as t
from social_video_downloader.bot import create_dispatcher
from social_video_downloader.config import ConfigurationError, Settings
from social_video_downloader.domain.errors import (
    DownloadCleanupError,
    DownloadFailedError,
    DownloadTimeoutError,
    UnsupportedDownloadModeError,
    UnsupportedQualityError,
)
from social_video_downloader.domain.models import DownloadedMedia, DownloadMode, DownloadOptions
from social_video_downloader.handlers import handle_text
from social_video_downloader.infrastructure import tiktok_native as n
from social_video_downloader.providers.tiktok import TikTokProvider
from social_video_downloader.services.choice_model import ChoicePlanState
from social_video_downloader.services.download import DownloadService
from tests.integration.test_video_preparation import generate
from tests.localization_fixtures import russian_presentation as russian_presentation
from tests.test_telegram_carousel import response
from tests.test_tiktok_native import MEDIA, A
from tests.test_tiktok_native import offline as offline
from tests.test_tiktok_native import workers as workers


def message(user=7):
    value = MagicMock(text=A, from_user=SimpleNamespace(id=user), chat=SimpleNamespace(id=1))
    value.answer = AsyncMock()
    value.answer_video = AsyncMock(return_value=response(1))
    return value


def synthetic_worker(monkeypatch, fixture, failure=None, *, public_page=False):
    original = n._command

    def command(workspace):
        argv = original(workspace)
        media = (
            "(403,b'PRIVATE_HTML',{})"
            if failure == "403"
            else "(200,b'abcdftyp',{'Content-Type':'video/mp4','Content-Length':'16'})"
            if failure == "incomplete"
            else f"(200,b'',{{'Content-Type':'video/mp4','Content-Length':'{n.FILE_BYTES + 1}'}})"
            if failure == "size"
            else f"response(Path({str(fixture)!r}).read_bytes(),'video/mp4')"
        )
        bootstrap = (
            "import socket,sys; from pathlib import Path; "
            "socket.socket.connect=socket.socket.connect_ex=lambda *a,**k: "
            "(_ for _ in ()).throw(AssertionError('No sockets')); "
            "from tests.test_tiktok_native import install,key,A,EMBED,MEDIA,page,response; "
            "from tests.test_tiktok_public_page import html; "
            f"wire=install({{key({'A' if public_page else 'EMBED'}):"
            f"response({'html' if public_page else 'page'}()),key(MEDIA):{media}}}); "
            + argv[2]
            + "; assert len(wire.requests)==2"
        )
        return [*argv[:2], bootstrap, *argv[3:]]

    monkeypatch.setattr(n, "_command", command)


class FixtureProvider(TikTokProvider):
    def __init__(self):
        self.paths = []

    def download_prepared(self, url, workspace, options=None, *, cancelled=None):
        path = workspace / "tiktok.mp4"
        path.write_bytes(b"local fixture")
        self.paths.append(path)
        return DownloadedMedia(path, self.extract_metadata(url)), {
            "width": 64,
            "height": 96,
            "duration": 1,
        }


def test_provider_local_capabilities_and_modes_need_no_http(monkeypatch, tmp_path):
    provider = TikTokProvider()
    monkeypatch.setattr(n, "download_video", lambda *a, **k: pytest.fail("Unexpected acquisition"))
    assert provider.can_handle(A) and provider.can_handle("https://vm.tiktok.com/Synthetic01/")
    assert provider.extract_metadata(A + "?tracking=1").source_url == A
    plan = DownloadService((provider,)).create_choice_plan(A)
    assert plan.state is ChoicePlanState.DIRECT_DOWNLOAD
    with pytest.raises(UnsupportedDownloadModeError):
        provider.download(A, tmp_path, DownloadOptions(DownloadMode.AUDIO_ONLY))
    with pytest.raises(UnsupportedQualityError):
        provider.download(A, tmp_path, DownloadOptions(quality_id="unproved"))


@pytest.mark.parametrize("audio", [False, True])
@pytest.mark.asyncio
async def test_real_native_worker_to_fake_telegram_keeps_file_until_response(
    monkeypatch, tmp_path, workers, audio
):
    source = tmp_path / "fixture.mp4"
    generate(source, audio=audio)
    synthetic_worker(monkeypatch, source, public_page=True)
    msg = message()
    paths = []

    async def upload(video, **kwargs):
        path = Path(video.path)
        paths.append(path)
        assert path.is_file() and path.read_bytes() == source.read_bytes()
        assert kwargs["width"] > 0 and kwargs["height"] > 0 and kwargs["supports_streaming"]
        assert not any(worker.returncode is None for worker in workers)
        await asyncio.sleep(0)
        assert path.is_file()
        return response(1)

    msg.answer_video.side_effect = upload
    handler = t.TelegramTikTokHandler()
    await handler.handle(msg, A)
    msg.answer_video.assert_awaited_once()
    assert all(not path.parent.exists() for path in paths) and not handler._active_users
    assert all(worker.returncode == 0 for worker in workers)
    assert len(msg.answer.await_args_list) == 1


@pytest.mark.parametrize(
    "failure,error",
    [("403", "http_403"), ("incomplete", "incomplete_response"), ("size", "byte_limit")],
)
def test_export_wire_errors_remove_only_owned_files(monkeypatch, tmp_path, workers, failure, error):
    synthetic_worker(monkeypatch, None, failure)
    foreign = tmp_path / "foreign"
    foreign.write_text("keep")
    result = n.run([A], output_dir=tmp_path)
    assert not result["success"] and result["error"] == error and result["workspace_cleaned"]
    assert result["metadata_requests"] == result["media_requests"] == result["acquisitions"] == 1
    assert sorted(path.name for path in tmp_path.iterdir()) == ["foreign"]
    assert foreign.read_text() == "keep" and all(worker.returncode == 0 for worker in workers)
    assert "PRIVATE" not in json.dumps(result)


def test_export_never_overwrites_existing_destination(monkeypatch, tmp_path, workers):
    fixture = tmp_path / "fixture.mp4"
    generate(fixture, audio=True)
    synthetic_worker(monkeypatch, fixture, public_page=True)
    foreign = tmp_path / "tiktok.mp4"
    foreign.write_text("keep")
    with pytest.raises(DownloadFailedError):
        TikTokProvider().download(A, tmp_path)
    assert foreign.read_text() == "keep" and not list(tmp_path.glob("tiktok-native-*"))


@pytest.mark.parametrize(
    "category",
    [
        "http_403",
        "byte_limit",
        "incomplete_response",
        "source_identity_mismatch",
        "separate_streams_unsupported",
        "deadline",
        "preparation_requires_conversion",
    ],
)
@pytest.mark.asyncio
async def test_handler_safe_errors_without_upload_or_private_diagnostics(monkeypatch, category):
    paths = []

    def fail(url, workspace, **kwargs):
        path = workspace / "partial.mp4"
        path.write_bytes(b"partial")
        paths.append(path)
        raise n.Refusal(category)

    monkeypatch.setattr(n, "download_video", fail)
    msg = message()
    await t.TelegramTikTokHandler().handle(msg, A)
    msg.answer_video.assert_not_awaited()
    assert all(not path.parent.exists() for path in paths)
    text = " ".join(call.args[0] for call in msg.answer.await_args_list)
    assert all(secret not in text for secret in (A, MEDIA, "11111111", category))


@pytest.mark.parametrize("user", [None, True, 0, -1, "7"])
@pytest.mark.asyncio
async def test_invalid_user_identity_denies_before_provider(user):
    provider = MagicMock()
    msg = message(user)
    await t.TelegramTikTokHandler(provider=provider).handle(msg, A)
    provider.download_prepared.assert_not_called()
    msg.answer_video.assert_not_awaited()


@pytest.mark.parametrize(
    "url",
    [
        "https://www.tiktok.com/@fixture",
        "https://vm.tiktok.com/invalid/extra/",
        "http://www.tiktok.com/@fixture/video/11111111",
        A.replace("/video/", "/photo/"),
        A + "?img_index=1",
    ],
)
@pytest.mark.asyncio
async def test_invalid_or_unsupported_url_no_download(url):
    provider = FixtureProvider()
    msg = message()
    await t.TelegramTikTokHandler(provider=provider).handle(msg, url)
    assert not provider.paths
    msg.answer_video.assert_not_awaited()


@pytest.mark.parametrize("kind", ["exception", "unconfirmed", "wrong_chat", "timeout"])
@pytest.mark.asyncio
async def test_upload_failure_and_timeout_keep_file_until_await_finishes(monkeypatch, kind):
    provider = FixtureProvider()
    msg = message()
    seen = []

    async def upload(video, **kwargs):
        path = Path(video.path)
        try:
            assert path.is_file()
            if kind == "exception":
                raise TelegramNetworkError(
                    method=SendVideo(chat_id=1, video="fixture"), message=MEDIA
                )
            if kind == "timeout":
                await asyncio.Event().wait()
            return None if kind == "unconfirmed" else response(1, chat_id=2)
        finally:
            seen.append(path.is_file())

    if kind == "timeout":
        monkeypatch.setattr(t, "SEND_SECONDS", 0.01)
    msg.answer_video.side_effect = upload
    await t.TelegramTikTokHandler(provider=provider).handle(msg, A)
    assert seen == [True] and all(not p.parent.exists() for p in provider.paths)
    msg.answer_video.assert_awaited_once()
    assert "Автоматического повтора" in msg.answer.await_args_list[-1].args[0]


@pytest.mark.asyncio
async def test_cancellation_during_upload_does_not_delete_live_input():
    provider = FixtureProvider()
    msg = message()
    started = asyncio.Event()
    held = []

    async def upload(video, **kwargs):
        path = Path(video.path)
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            held.append(path.is_file())

    msg.answer_video.side_effect = upload
    handler = t.TelegramTikTokHandler(provider=provider)
    task = asyncio.create_task(handler.handle(msg, A))
    await asyncio.wait_for(started.wait(), 3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert (
        held == [True]
        and not handler._active_users
        and all(not p.parent.exists() for p in provider.paths)
    )


@pytest.mark.parametrize("leader_exits", [False, True])
@pytest.mark.asyncio
async def test_repeated_cancel_owns_real_process_group_workspace_and_busy_slot(
    monkeypatch, tmp_path, workers, leader_exits
):
    pidfile = tmp_path / "child.pid"
    code = (
        "import subprocess,sys,time; from pathlib import Path; "
        "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
        f"Path({str(pidfile)!r}).write_text(str(p.pid)); "
        + ("pass" if leader_exits else "time.sleep(30)")
    )
    monkeypatch.setattr(n, "_command", lambda workspace: [sys.executable, "-c", code])
    killpg = n.os.killpg
    cleaning, release = Event(), Event()

    def delayed(group, sig):
        if sig == signal.SIGKILL:
            cleaning.set()
            release.wait(3)
        return killpg(group, sig)

    monkeypatch.setattr(n.os, "killpg", delayed)
    directories = []
    temporary = t.TemporaryDirectory

    def track(*args, **kwargs):
        directory = temporary(*args, **kwargs)
        directories.append(Path(directory.name))
        return directory

    monkeypatch.setattr(t, "TemporaryDirectory", track)
    handler = t.TelegramTikTokHandler()
    task = asyncio.create_task(handler.handle(message(), A))
    try:
        async with asyncio.timeout(4):
            while not pidfile.exists():
                await asyncio.sleep(0.01)
        second = message()
        await handler.handle(second, A)
        assert len(workers) == 1 and "Бот занят" in second.answer.call_args.args[0]
        task.cancel()
        async with asyncio.timeout(4):
            while not cleaning.is_set():
                await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.sleep(0.02)
        assert not task.done() and handler._active_users and directories[0].exists()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 4)
        assert not handler._active_users and all(not p.exists() for p in directories)
        assert all(worker.returncode is not None for worker in workers)
        async with asyncio.timeout(3):
            while True:
                try:
                    os.kill(int(pidfile.read_text()), 0)
                except ProcessLookupError:
                    break
                await asyncio.sleep(0.01)
    finally:
        release.set()
        if not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await asyncio.wait_for(task, 5)
        if pidfile.exists():
            with suppress(ProcessLookupError):
                os.kill(int(pidfile.read_text()), signal.SIGKILL)


def test_export_deadline_reaps_worker_and_removes_private_workspace(monkeypatch, tmp_path, workers):
    monkeypatch.setattr(n, "SECONDS", 0.15)
    monkeypatch.setattr(
        n, "_command", lambda workspace: [sys.executable, "-c", "import time; time.sleep(30)"]
    )
    with pytest.raises(DownloadTimeoutError):
        TikTokProvider().download(A, tmp_path)
    assert not list(tmp_path.iterdir()) and all(p.returncode is not None for p in workers)


@pytest.mark.asyncio
async def test_unconfirmed_worker_cleanup_quarantines_and_blocks_handler(
    monkeypatch, tmp_path, workers
):
    # Inject an OS cleanup failure, then perform emergency cleanup ourselves.
    import shutil

    pidfile = tmp_path / "worker.pid"
    code = (
        "import os,time; from pathlib import Path; "
        f"Path({str(pidfile)!r}).write_text(str(os.getpid())); time.sleep(30)"
    )
    monkeypatch.setattr(n, "_command", lambda workspace: [sys.executable, "-c", code])
    monkeypatch.setattr(n, "SECONDS", 0.15)
    original = n.os.killpg

    def denied(group, sig):
        if sig == signal.SIGKILL:
            raise OSError("PRIVATE_ERROR")
        return original(group, sig)

    monkeypatch.setattr(n.os, "killpg", denied)
    directories = []
    temporary = t.TemporaryDirectory

    def track(*args, **kwargs):
        directory = temporary(*args, **kwargs)
        directories.append(Path(directory.name))
        return directory

    monkeypatch.setattr(t, "TemporaryDirectory", track)
    handler = t.TelegramTikTokHandler()
    msg = message()
    try:
        await asyncio.wait_for(handler.handle(msg, A), 8)
        assert handler._blocked and handler._active_users == {7} and directories[0].exists()
        assert "приостановлена" in msg.answer.call_args.args[0]
        assert all("PRIVATE" not in call.args[0] for call in msg.answer.await_args_list)
        await handler.handle(message(), A)
        assert len(workers) == 1
    finally:
        monkeypatch.setattr(n.os, "killpg", original)
        for process in workers:
            if process.returncode is None:
                with suppress(ProcessLookupError):
                    original(process.pid, signal.SIGKILL)
                process.wait(timeout=3)
        for directory in directories:
            shutil.rmtree(directory, ignore_errors=True)


def test_provider_classifies_unconfirmed_cleanup_without_details(monkeypatch, tmp_path):
    def failed(*a, **k):
        raise n.Refusal("workspace_cleanup_failed")

    monkeypatch.setattr(n, "download_video", failed)
    with pytest.raises(DownloadCleanupError) as error:
        TikTokProvider().download(A, tmp_path)
    assert "workspace_cleanup_failed" not in str(error.value)


@pytest.mark.parametrize(
    "flag,capacity",
    [
        ("yes", "2"),
        ("true", "0"),
        ("true", "abc"),
        ("true", "2.0"),
        ("true", "-1"),
        ("true", "9"),
        ("true", "２"),
        ("true", "2" * 5000),
    ],
)
def test_invalid_tiktok_config_fails_closed(flag, capacity):
    with pytest.raises(ConfigurationError):
        Settings.from_env(
            {
                "TELEGRAM_BOT_TOKEN": "fixture",
                "TIKTOK_TELEGRAM_ENABLED": flag,
                "TIKTOK_MAX_CONCURRENT_OPERATIONS": capacity,
            }
        )


@pytest.mark.parametrize("capacity", [True, 0, -1, 9, 2.0, "2"])
def test_direct_tiktok_settings_and_handler_reject_invalid_capacity(capacity):
    with pytest.raises(ConfigurationError):
        Settings("fixture", tiktok_max_concurrent_operations=capacity)
    with pytest.raises(ValueError):
        t.TelegramTikTokHandler(max_concurrent=capacity)


@pytest.mark.parametrize("capacity", [1, 2, 8])
def test_public_tiktok_flag_production_and_capacity_wiring(capacity):
    assert not Settings("fixture").tiktok_telegram_enabled
    assert Settings("fixture").tiktok_max_concurrent_operations == 2
    enabled = Settings.from_env(
        {
            "TELEGRAM_BOT_TOKEN": "fixture",
            "APP_ENV": "production",
            "TIKTOK_TELEGRAM_ENABLED": "true",
            "TIKTOK_MAX_CONCURRENT_OPERATIONS": str(capacity),
        }
    )
    with pytest.raises(ConfigurationError, match="Instagram"):
        Settings("fixture", app_env="production", instagram_telegram_enabled=True)
    assert not hasattr(enabled, "tiktok_test_user_ids")
    assert (
        create_dispatcher(Settings("fixture"), tiktok_videos=object()).workflow_data.get(
            "tiktok_videos"
        )
        is None
    )
    first, second = create_dispatcher(enabled), create_dispatcher(enabled)
    assert first["tiktok_videos"] is not second["tiktok_videos"]
    assert first["tiktok_videos"]._max_concurrent == capacity


@pytest.mark.asyncio
async def test_flag_off_keeps_original_tiktok_response():
    msg = message()
    await handle_text(msg)
    assert "пока не подключено" in msg.answer.call_args.args[0]
    msg.answer_video.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatcher_routes_enabled_public_tiktok():
    injected = SimpleNamespace(handle=AsyncMock())
    dispatcher = create_dispatcher(
        Settings("fixture", tiktok_telegram_enabled=True), tiktok_videos=injected
    )
    bot = Bot("123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi")
    update = Update.model_validate(
        {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "date": 0,
                "chat": {"id": 1, "type": "private"},
                "from": {"id": 7, "is_bot": False, "first_name": "Fixture"},
                "text": A,
            },
        }
    )
    try:
        await dispatcher.feed_update(bot, update)
        injected.handle.assert_awaited_once()
    finally:
        await bot.session.close()
