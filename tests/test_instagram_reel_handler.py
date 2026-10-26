"""Reel-only vertical integration, using synthetic acquisition and local media."""

import asyncio
import io
import shutil
import socket
from copy import deepcopy
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import SendVideo
from aiogram.types import Update
from yt_dlp.networking.common import Response

import social_video_downloader.telegram_instagram as integration
from social_video_downloader.bot import create_dispatcher
from social_video_downloader.config import ConfigurationError, Settings
from social_video_downloader.domain.errors import (
    DownloadFailedError,
    InvalidMediaURLError,
    MediaProcessingError,
)
from social_video_downloader.handlers import handle_text
from tests.integration.test_video_preparation import generate
from tests.localization_fixtures import russian_presentation as russian_presentation
from tests.test_instagram_provider import INFO, Factory
from tests.test_telegram_carousel import response

URL = "https://www.instagram.com/reel/Fixture_01/"


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def forbidden(*a, **kw):
        raise AssertionError("No network permitted")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)


@pytest.fixture
def message():
    value = MagicMock(text=URL)
    value.answer = AsyncMock()
    value.answer_video = AsyncMock(return_value=response(1))
    return value


def runtime(monkeypatch, source=None, info=INFO, failure=None):
    fixture = Factory(info)
    paths = []

    def factory(options):
        ydl = fixture(options)

        def forbidden(*a):
            raise AssertionError("No network permitted")

        ydl.urlopen = forbidden

        def acquire(raw, *, download):
            assert download is True
            fixture.processed.append(deepcopy(raw))
            path = Path(options["outtmpl"])
            paths.append(path)
            if failure:
                path.write_bytes(b"partial")
                raise DownloadFailedError("synthetic acquisition failure")
            if source is None:
                path.write_bytes(b"synthetic")
            else:
                shutil.copyfile(source, path)
            return raw

        ydl.process_ie_result = acquire
        return ydl

    if source is None:
        monkeypatch.setattr(integration, "prepare_telegram_video", lambda p, **kw: p)
        monkeypatch.setattr(
            integration,
            "inspect_telegram_video",
            lambda *a, **kw: {"streams": [{"codec_type": "video", "width": 64, "height": 96}]},
        )
    return integration.InstagramReelHandler(ydl_factory=factory), fixture, paths


@pytest.mark.asyncio
async def test_disabled_remains_unsupported_and_never_invokes_injection(message):
    injected = MagicMock()
    dispatcher = create_dispatcher(Settings("test-token"), instagram_reels=injected)
    assert "instagram_reels" not in dispatcher.workflow_data
    await handle_text(message)
    message.answer_video.assert_not_awaited()
    assert "пока не подключено" in message.answer.call_args.args[0]
    injected.handle.assert_not_called()


def test_flag_and_dependencies_are_explicit_and_dispatcher_local():
    enabled = Settings.from_env(
        {"TELEGRAM_BOT_TOKEN": "test-token", "INSTAGRAM_TELEGRAM_ENABLED": "true"}
    )
    first, second = create_dispatcher(enabled), create_dispatcher(enabled)
    assert first["instagram_reels"] is not second["instagram_reels"]
    assert first.sub_routers[0] is not second.sub_routers[0]
    assert (
        Settings.from_env(
            {"TELEGRAM_BOT_TOKEN": "test-token", "APP_ENV": "production"}
        ).instagram_telegram_enabled
        is False
    )


@pytest.mark.asyncio
async def test_dispatcher_injects_enabled_reel_handler_without_network():
    injected = SimpleNamespace(handle=AsyncMock())
    dispatcher = create_dispatcher(
        Settings("test-token", instagram_telegram_enabled=True), instagram_reels=injected
    )
    bot = Bot("123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi")
    update = Update.model_validate(
        {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "date": 0,
                "chat": {"id": 1, "type": "private"},
                "text": URL,
                "from": {"id": 1, "is_bot": False, "first_name": "Synthetic"},
            },
        }
    )
    try:
        await dispatcher.feed_update(bot, update)
        injected.handle.assert_awaited_once()
        assert injected.handle.call_args.args[1] == URL
    finally:
        await bot.session.close()


@pytest.mark.parametrize("value", ["1", "yes", "", "enabled"])
def test_invalid_flag_fails_closed(value):
    with pytest.raises(ConfigurationError):
        Settings.from_env({"TELEGRAM_BOT_TOKEN": "test-token", "INSTAGRAM_TELEGRAM_ENABLED": value})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "suffix",
    [
        "",
        "?utm_source=fixture",
        "?utm_source=ig_web_copy_link&psln=fixture==",
        "?dlrf=fixture&unrecognized=ignored",
        "?flag&empty=",
        "#share",
        "?psln=fixture#watch",
        "?note=img_index#note=slide",
        "?tracking=100%25#progress%25",
    ],
)
async def test_enabled_reel_uses_provider_and_one_send_then_cleans(message, monkeypatch, suffix):
    handler, fixture, paths = runtime(monkeypatch)
    downloaded_urls = []
    download = integration.InstagramProvider.download

    def traced_download(self, url, *args, **kwargs):
        downloaded_urls.append(url)
        return download(self, url, *args, **kwargs)

    monkeypatch.setattr(integration.InstagramProvider, "download", traced_download)
    prepare = MagicMock(side_effect=lambda p, **kw: p)
    monkeypatch.setattr(integration, "prepare_telegram_video", prepare)
    message.text += suffix
    await handle_text(message, instagram_reels=handler)
    assert len(fixture.extractions) == len(fixture.processed) == 1
    assert fixture.extractions[0][0] == URL
    assert downloaded_urls == [URL]
    assert prepare.call_args.kwargs["allow_silent"] is True
    message.answer_video.assert_awaited_once()
    assert message.answer_video.call_args.kwargs["supports_streaming"] is True
    assert message.answer_video.call_args.kwargs["width"] == 64
    method = response(1).answer_video(
        *message.answer_video.call_args.args, **message.answer_video.call_args.kwargs
    )
    assert "request_timeout" not in method.model_dump(exclude_none=True)
    assert message.answer_video.call_args.args[0].path.name.endswith(".mp4")
    assert all(not p.parent.parent.exists() for p in paths)
    assert not handler._active


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "suffix",
    [
        "?img_index=2",
        "?media_id=fixture",
        "?item_id=fixture",
        "?carousel_index=2",
        "?index=1",
        "?slide=2",
        "?psln=fixture&IMG_INDEX=2",
        "?%69mg_index=2",
        "?%2569mg_index=2",
        "?img_index=",
        "#slide",
        "#slide=2",
        "#slide/2",
        "#slide:2",
        "#?img_index=2",
        "#share&item_id=fixture",
        "#%69mg_index=2",
        "#%2569mg_index=2",
    ],
)
async def test_raw_reference_is_rejected_before_extraction(message, monkeypatch, suffix):
    handler, fixture, _ = runtime(monkeypatch)
    message.text += suffix
    await handle_text(message, instagram_reels=handler)
    assert not fixture.extractions
    message.answer_video.assert_not_awaited()


@pytest.mark.parametrize(
    "raw",
    [
        "http://m.instagram.com/reel/Fixture_01/?psln=fixture",
        "https://instagram.com/reel/Fixture_01?other=ignored#share",
        "https://www.instagram.com:443/reel/Fixture_01/?psln=fixture",
    ],
)
def test_share_links_reuse_provider_canonicalization(raw):
    assert integration._reel_url(raw) == URL


@pytest.mark.parametrize(
    "raw",
    [
        "https://www.instagram.com/p/Fixture_01/?psln=fixture",
        "https://www.instagram.com/stories/Fixture_01/",
        "https://www.instagram.com/reel/Fixture_01/extra/",
        "https://www.instagram.com/reel/",
        "ftp://www.instagram.com/reel/Fixture_01/",
        "https://instagram.com.evil.invalid/reel/Fixture_01/",
        "https://evil.instagram.com/reel/Fixture_01/",
        "https://www.instagram.com@evil.invalid/reel/Fixture_01/",
        "https://user@www.instagram.com/reel/Fixture_01/",
        "https://www.instagram.com:8443/reel/Fixture_01/",
        "https://www.instagram.com:invalid/reel/Fixture_01/",
        "https://[malformed/reel/Fixture_01/",
        URL + "?bad%XX=fixture",
        URL + "?=fixture",
        URL + "?" + "&".join(f"key{i}=value" for i in range(33)),
    ],
)
def test_invalid_or_unsupported_share_links_fail_closed(raw):
    with pytest.raises(InvalidMediaURLError):
        integration._reel_url(raw)


@pytest.mark.asyncio
async def test_posts_are_dispatched_to_separate_post_flow(message, monkeypatch):
    from social_video_downloader.telegram_instagram_posts import InstagramPostHandler

    post_handle = AsyncMock()
    monkeypatch.setattr(InstagramPostHandler, "handle", post_handle)
    handler, fixture, _ = runtime(monkeypatch)
    message.text = URL.replace("/reel/", "/p/")
    await handle_text(message, instagram_reels=handler)
    post_handle.assert_awaited_once()
    assert post_handle.call_args.args == (message, message.text, message.text)
    assert not fixture.extractions


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw",
    [
        {"_type": "playlist", "entries": []},
        {"formats": []},
        {**INFO, "is_private": True},
        {"_type": "url"},
    ],
)
async def test_unsupported_content_never_acquires_or_sends(message, monkeypatch, raw):
    handler, fixture, _ = runtime(monkeypatch, info=raw)
    await handle_text(message, instagram_reels=handler)
    assert len(fixture.extractions) == 1 and not fixture.processed
    message.answer_video.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["acquisition", "preparation"])
async def test_failure_has_no_send_and_cleans(message, monkeypatch, stage):
    handler, fixture, paths = runtime(monkeypatch, failure=stage == "acquisition")
    if stage == "preparation":

        def fail(*a, **kw):
            raise MediaProcessingError("synthetic preparation failure")

        monkeypatch.setattr(integration, "prepare_telegram_video", fail)
    await handle_text(message, instagram_reels=handler)
    message.answer_video.assert_not_awaited()
    assert len(fixture.processed) == 1
    assert all(not p.parent.parent.exists() for p in paths)
    assert not handler._active


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["api_error", "timeout", "missing_response"])
async def test_send_failure_is_not_retried(message, monkeypatch, outcome):
    handler, fixture, _ = runtime(monkeypatch)
    if outcome == "api_error":
        message.answer_video.side_effect = TelegramNetworkError(
            method=SendVideo(chat_id=1, video="fixture"), message="synthetic"
        )
    elif outcome == "timeout":
        message.answer_video.side_effect = TimeoutError
    else:
        message.answer_video.return_value = None
    await handle_text(message, instagram_reels=handler)
    message.answer_video.assert_awaited_once()
    assert len(fixture.processed) == 1
    assert "Автоматического повтора не будет" in message.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_cancellation_keeps_admission_and_workspace_until_worker_exits(message, monkeypatch):
    handler = integration.InstagramReelHandler()
    started, release = Event(), Event()
    workspaces = []

    def slow(url, workspace, guard):
        workspaces.append(workspace)
        started.set()
        assert release.wait(5)
        assert workspace.exists()
        guard.check()

    monkeypatch.setattr(handler, "_prepare", slow)
    task = asyncio.create_task(handle_text(message, instagram_reels=handler))
    try:
        while not started.is_set():
            await asyncio.sleep(0.005)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        second = MagicMock(text=URL, answer=AsyncMock(), answer_video=AsyncMock())
        await handle_text(second, instagram_reels=handler)
        assert "Уже обрабатываю" in second.answer.call_args.args[0]
        assert not task.done() and workspaces[0].exists()
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert not workspaces[0].exists() and not handler._active
    message.answer_video.assert_not_awaited()


def test_received_body_limit_does_not_trust_content_length():
    guard = integration._Guard(Event(), max_bytes=5)
    wrapped = guard.wrap(
        Response(io.BytesIO(b"123456789"), "https://media.invalid/fixture.mp4", {})
    )
    assert wrapped.read(999999) == b"12345"
    with pytest.raises(DownloadFailedError):
        wrapped.read(1)
    assert guard.received == 5


@pytest.mark.asyncio
async def test_insufficient_disk_fails_before_extraction(message, monkeypatch):
    handler, fixture, _ = runtime(monkeypatch)
    monkeypatch.setattr(integration.shutil, "disk_usage", lambda _: SimpleNamespace(free=0))
    await handle_text(message, instagram_reels=handler)
    assert not fixture.extractions
    message.answer_video.assert_not_awaited()


def test_explicit_production_activation_is_rejected():
    with pytest.raises(ConfigurationError, match="isolated"):
        Settings("test-token", app_env="production", instagram_telegram_enabled=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("audio", [False, True])
async def test_actual_local_silent_and_audio_passthrough(message, monkeypatch, tmp_path, audio):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("Local FFmpeg/ffprobe unavailable")
    source = tmp_path / "source.mp4"
    generate(source, audio=audio)
    handler, fixture, _ = runtime(monkeypatch, source=source)
    calls = []
    run = integration._Guard.run

    def traced(self, command, **kw):
        calls.append(command[0])
        return run(self, command, **kw)

    monkeypatch.setattr(integration._Guard, "run", traced)
    original = source.read_bytes()

    async def send(file, **kw):
        assert Path(file.path).read_bytes() == original
        assert kw["width"] == 64 and kw["height"] == 96 and kw["duration"] == 1
        return response(1)

    message.answer_video.side_effect = send
    await handle_text(message, instagram_reels=handler)
    message.answer_video.assert_awaited_once()
    assert len(fixture.processed) == 1 and calls == ["ffprobe", "ffprobe"]


@pytest.mark.asyncio
async def test_actual_conversion_uses_existing_helper_and_preserves_silence(
    message, monkeypatch, tmp_path
):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("Local FFmpeg/ffprobe unavailable")
    source = tmp_path / "source.mp4"
    generate(source, video="mpeg4")
    handler, _, _ = runtime(monkeypatch, source=source)

    async def send(file, **kw):
        data = integration.inspect_telegram_video(Path(file.path))
        assert [s["codec_name"] for s in data["streams"]] == ["h264"]
        return response(1)

    message.answer_video.side_effect = send
    await handle_text(message, instagram_reels=handler)
    message.answer_video.assert_awaited_once()


def test_one_media_open_and_cooperative_deadline(monkeypatch):
    opened = []

    def factory(options):
        assert options["max_filesize"] == 5
        assert options["continuedl"] is False and options["fixup"] == "never"
        assert options["progress_hooks"]

        def open_response(request):
            opened.append(True)
            return Response(io.BytesIO(b"123456"), "https://media.invalid/fixture.mp4", {})

        return SimpleNamespace(urlopen=open_response)

    guard = integration._Guard(Event(), max_bytes=5)
    ydl = guard.ydl(factory, {"outtmpl": "fixture.mp4"})
    response = ydl.urlopen(None)
    assert response.read(100) == b"12345"
    with pytest.raises(DownloadFailedError):
        ydl.urlopen(None)
    assert len(opened) == 1
    guard.deadline = 0
    with pytest.raises(integration.DownloadTimeoutError):
        response.read(1)


def test_preparation_write_limit_and_timeout_are_terminal(tmp_path, monkeypatch):
    guard = integration._Guard(Event(), max_bytes=32)
    output = tmp_path / "output.mp4"
    # Real exec'd child inherits the file cap; it cannot leave an unbounded output.
    with pytest.raises(integration._PreparationStopped):
        guard.run(
            ["ffmpeg", "-f", "lavfi", "-i", "color=s=64x96", "-t", "1", str(output)],
            check=True,
            capture_output=True,
            text=True,
        )
    assert not output.exists() or output.stat().st_size <= 32
    guard.deadline = 0
    with pytest.raises(integration._PreparationStopped):
        guard.run(["ffprobe", str(output)], check=True, capture_output=True, text=True)
