"""Offline ownership checks for YouTube threads using the Telegram workspace."""

import asyncio
import gc
import threading
from contextvars import ContextVar
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from social_video_downloader import handlers
from social_video_downloader.domain.models import (
    DownloadedMedia,
    DownloadMode,
    DownloadOptions,
    MediaMetadata,
    Platform,
)
from social_video_downloader.infrastructure.telegram_audio import PreparedAudio

STAGES = ("download", "audio_prepare", "video_prepare", "probe")
URL = "https://www.youtube.com/watch?v=abcdefghijk"


@pytest_asyncio.fixture
async def pipeline(monkeypatch):
    loop = asyncio.get_running_loop()
    state = SimpleNamespace(
        block=None,
        fail=False,
        entered=asyncio.Event(),
        release=threading.Event(),
        finished=threading.Event(),
        active=False,
        workspace=None,
        calls=[],
        timeline=[],
        loop_errors=[],
        threads=set(),
    )
    previous_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda _, context: state.loop_errors.append(context))

    class TrackedDirectory(TemporaryDirectory):
        def cleanup(self):
            state.timeline.append(("cleanup", state.active))
            super().cleanup()

    def work(stage, path, result):
        state.threads.add(threading.current_thread())
        state.calls.append(stage)
        if stage != state.block:
            return result()
        state.active = True
        state.timeline.append(("started", stage))
        try:
            with (path.parent / "held.part").open("wb") as output:
                output.write(b"synthetic media")
                output.flush()
                loop.call_soon_threadsafe(state.entered.set)
                if not state.release.wait(5):
                    raise AssertionError("test worker was not released")
                assert path.parent.is_dir()
                output.write(b"finished")
                if state.fail:
                    raise RuntimeError("synthetic private worker detail")
                return result()
        finally:
            state.active = False
            state.timeline.append(("finished", stage))
            state.finished.set()

    def download(url, directory, options):
        state.workspace = directory
        path = directory / "source.mp4"

        def result():
            path.write_bytes(b"synthetic source")
            return DownloadedMedia(
                file_path=path,
                metadata=MediaMetadata(
                    title="Synthetic",
                    source_url=url,
                    platform=Platform.YOUTUBE,
                    duration_seconds=1,
                ),
            )

        return work("download", path, result)

    def prepare_audio(path, duration):
        return work("audio_prepare", path, lambda: PreparedAudio(path, 1))

    monkeypatch.setattr(handlers, "TemporaryDirectory", TrackedDirectory)
    monkeypatch.setattr(handlers, "download_service", SimpleNamespace(download=download))
    monkeypatch.setattr(handlers, "prepare_telegram_audio", prepare_audio)
    monkeypatch.setattr(
        handlers, "prepare_telegram_video", lambda path: work("video_prepare", path, lambda: path)
    )
    monkeypatch.setattr(
        handlers, "inspect_telegram_video", lambda path: work("probe", path, lambda: {})
    )
    monkeypatch.setattr(handlers, "telegram_video_upload_parameters", lambda _: {})
    state.message = SimpleNamespace(
        answer=AsyncMock(),
        answer_audio=AsyncMock(),
        answer_video=AsyncMock(return_value=SimpleNamespace(video=object())),
    )
    try:
        yield state
    finally:
        state.release.set()
        # All file workers must finish, including after an assertion failure.
        await loop.shutdown_default_executor()
        gc.collect()
        await asyncio.sleep(0)
        loop.set_exception_handler(previous_handler)
        assert not state.active
        assert all(not thread.is_alive() for thread in state.threads)
        assert not state.loop_errors


def options(stage):
    mode = DownloadMode.AUDIO_ONLY if stage == "audio_prepare" else DownloadMode.VIDEO_WITH_AUDIO
    return DownloadOptions(mode=mode)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", [DownloadMode.AUDIO_ONLY, DownloadMode.VIDEO_WITH_AUDIO])
async def test_success_preserves_delivery_and_cleans_workspace(pipeline, mode):
    await handlers._download_and_deliver_media(pipeline.message, URL, DownloadOptions(mode=mode))

    assert pipeline.calls.count("download") == 1
    assert not pipeline.workspace.exists()
    assert pipeline.timeline == [("cleanup", False)]
    assert pipeline.message.answer_audio.await_count == (mode is DownloadMode.AUDIO_ONLY)
    assert pipeline.message.answer_video.await_count == (mode is DownloadMode.VIDEO_WITH_AUDIO)


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("repeat_cancel", [False, True])
@pytest.mark.parametrize("worker_fails", [False, True])
async def test_cancel_drains_file_worker_before_cleanup(
    pipeline, stage, repeat_cancel, worker_fails, caplog
):
    pipeline.block = stage
    pipeline.fail = worker_fails
    task = asyncio.create_task(
        handlers._download_and_deliver_media(pipeline.message, URL, options(stage))
    )
    try:
        await asyncio.wait_for(pipeline.entered.wait(), 3)
        task.cancel()
        # Independent event-loop work must progress while the real thread is held.
        ticks = []
        for tick in range(10):
            await asyncio.sleep(0)
            ticks.append(tick)
            if repeat_cancel:
                task.cancel()
            assert not task.done()
            assert pipeline.workspace.is_dir()
            assert not pipeline.finished.is_set()
            assert not any(event == "cleanup" for event, _ in pipeline.timeline)
        assert len(ticks) == 10
    finally:
        pipeline.release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)

    assert pipeline.finished.is_set()
    assert not pipeline.workspace.exists()
    assert pipeline.timeline == [("started", stage), ("finished", stage), ("cleanup", False)]
    expected = list(STAGES[:2]) if stage == "audio_prepare" else ["download"]
    if stage == "video_prepare":
        expected += ["video_prepare"]
    elif stage == "probe":
        expected += ["video_prepare", "probe"]
    assert pipeline.calls == expected
    pipeline.message.answer_audio.assert_not_awaited()
    pipeline.message.answer_video.assert_not_awaited()
    pipeline.message.answer.assert_not_awaited()
    assert "synthetic private worker detail" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", STAGES)
async def test_worker_failure_without_cancel_preserves_existing_error_behavior(pipeline, stage):
    pipeline.block = stage
    pipeline.fail = True
    pipeline.release.set()
    await handlers._download_and_deliver_media(pipeline.message, URL, options(stage))

    assert pipeline.finished.is_set()
    assert not pipeline.workspace.exists()
    assert pipeline.calls.count(stage) == 1
    # Video probing remains best effort; the other stages retain the error response.
    assert pipeline.message.answer_video.await_count == (stage == "probe")
    assert pipeline.message.answer.await_count == (stage != "probe")
    pipeline.message.answer_audio.assert_not_awaited()


@pytest.mark.asyncio
async def test_local_helper_preserves_to_thread_context_and_keyword_arguments():
    context = ContextVar("synthetic", default="missing")
    token = context.set("copied")
    try:
        result = await handlers._run_workspace_thread(
            lambda *, value: (context.get(), value), value=7
        )
        assert result == ("copied", 7)
    finally:
        context.reset(token)
        await asyncio.get_running_loop().shutdown_default_executor()


@pytest.mark.asyncio
async def test_shutdown_style_cancellation_has_no_independently_cancelled_worker_task(pipeline):
    pipeline.block = "download"
    task = asyncio.create_task(
        handlers._download_and_deliver_media(pipeline.message, URL, options("download"))
    )
    try:
        await asyncio.wait_for(pipeline.entered.wait(), 3)
        owned_tasks = asyncio.all_tasks() - {asyncio.current_task()}
        assert owned_tasks == {task}
        for owned in owned_tasks:
            owned.cancel()
        for _ in range(5):
            await asyncio.sleep(0)
            assert not task.done()
            assert pipeline.workspace.is_dir()
    finally:
        pipeline.release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
    assert pipeline.finished.is_set()
    assert not pipeline.workspace.exists()
