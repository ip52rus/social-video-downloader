"""Bounded public admission and independent ownership, without external sockets."""

import asyncio
import shutil
from pathlib import Path
from threading import Event

import pytest

from social_video_downloader import telegram_tiktok as t
from social_video_downloader.domain.errors import DownloadTimeoutError
from tests.integration.test_video_preparation import generate
from tests.test_telegram_carousel import response
from tests.test_tiktok_integration import FixtureProvider, message, synthetic_worker
from tests.test_tiktok_native import A, B
from tests.test_tiktok_native import offline as offline
from tests.test_tiktok_native import workers as workers


@pytest.mark.parametrize("user", [7, 8, 912345])
@pytest.mark.asyncio
async def test_any_user_can_download_without_test_list(user):
    provider = FixtureProvider()
    msg = message(user)
    handler = t.TelegramTikTokHandler(provider=provider)
    await handler.handle(msg, A)
    msg.answer_video.assert_awaited_once()
    assert not handler._active_users
    assert all(not path.parent.exists() for path in provider.paths)


@pytest.mark.asyncio
async def test_two_real_workers_saturation_duplicate_and_slot_reuse(monkeypatch, tmp_path, workers):
    source = tmp_path / "source.mp4"
    generate(source, audio=True)
    synthetic_worker(monkeypatch, source, public_page=True)
    handler = t.TelegramTikTokHandler()
    started = [asyncio.Event(), asyncio.Event()]
    release = [asyncio.Event(), asyncio.Event()]
    paths = {}

    def upload(index):
        async def send(video, **kwargs):
            path = Path(video.path)
            paths[index] = path
            assert path.read_bytes() == source.read_bytes()
            started[index].set()
            await release[index].wait()
            assert path.is_file()
            return response(1)

        return send

    messages = [message(7), message(8)]
    for index, msg in enumerate(messages):
        msg.answer_video.side_effect = upload(index)
    tasks = [asyncio.create_task(handler.handle(msg, A)) for msg in messages]
    try:
        await asyncio.wait_for(asyncio.gather(*(event.wait() for event in started)), 10)
        assert handler._active_users == {7, 8}
        assert len(workers) == 2 and all(p.returncode == 0 for p in workers)
        assert paths[0].parent != paths[1].parent
        for user in (7, 9):
            excess = message(user)
            await handler.handle(excess, A)
            excess.answer_video.assert_not_awaited()
            assert excess.answer.call_args.args == ("Бот занят, попробуйте позже.",)
        assert len(workers) == 2
        release[0].set()
        await asyncio.wait_for(tasks[0], 3)
        assert handler._active_users == {8} and not paths[0].parent.exists()
        # The same user can reserve the freed slot while the other upload remains live.
        again = message(7)
        await asyncio.wait_for(handler.handle(again, A), 10)
        again.answer_video.assert_awaited_once()
        assert len(workers) == 3 and handler._active_users == {8}
    finally:
        for event in release:
            event.set()
        await asyncio.gather(*tasks, return_exceptions=True)
    assert all(msg.answer.await_count == 1 for msg in messages)
    assert not handler._active_users and all(not path.parent.exists() for path in paths.values())
    assert all(p.returncode == 0 for p in workers)


@pytest.mark.asyncio
async def test_cancelled_worker_retains_slot_and_does_not_cancel_other_operation():
    entered, cancelled_seen, release_worker = Event(), Event(), Event()
    second_upload, release_upload = asyncio.Event(), asyncio.Event()
    provider = FixtureProvider()
    original = provider.download_prepared

    def prepare(url, workspace, options=None, *, cancelled=None):
        if url == A:
            entered.set()
            assert cancelled.wait(5)
            cancelled_seen.set()
            assert release_worker.wait(5)
            raise DownloadTimeoutError("PRIVATE_URL_COOKIE_HTML")
        assert not cancelled.is_set()
        return original(url, workspace, options, cancelled=cancelled)

    provider.download_prepared = prepare
    first, second = message(7), message(8)
    second.text = B

    async def upload(video, **kwargs):
        second_upload.set()
        await release_upload.wait()
        assert Path(video.path).is_file()
        return response(1)

    second.answer_video.side_effect = upload
    handler = t.TelegramTikTokHandler(provider=provider)
    tasks = [
        asyncio.create_task(handler.handle(first, A)),
        asyncio.create_task(handler.handle(second, B)),
    ]
    try:
        await asyncio.wait_for(second_upload.wait(), 3)
        assert entered.is_set()
        tasks[0].cancel()
        async with asyncio.timeout(3):
            while not cancelled_seen.is_set():
                await asyncio.sleep(0.005)
        tasks[0].cancel()
        await asyncio.sleep(0)
        assert not tasks[0].done() and handler._active_users == {7, 8}
        release_worker.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(tasks[0], 3)
        assert handler._active_users == {8} and not tasks[1].done()
        assert provider.paths[0].is_file()
        release_upload.set()
        await asyncio.wait_for(tasks[1], 3)
        first.answer_video.assert_not_awaited()
        second.answer_video.assert_awaited_once()
        assert second.answer.await_count == 1
    finally:
        release_worker.set()
        release_upload.set()
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    assert not handler._active_users and not handler._blocked
    assert all(not path.parent.exists() for path in provider.paths)


@pytest.mark.asyncio
async def test_concurrent_results_keep_their_own_files():
    provider = FixtureProvider()
    original = provider.download_prepared

    def prepare(url, *args, **kwargs):
        media, parameters = original(url, *args, **kwargs)
        media.file_path.write_bytes(url.encode())
        return media, parameters

    provider.download_prepared = prepare
    handler = t.TelegramTikTokHandler(provider=provider)
    ready, release = [asyncio.Event(), asyncio.Event()], asyncio.Event()
    messages = [message(7), message(8)]

    def send(index, url):
        async def upload(video, **kwargs):
            ready[index].set()
            await release.wait()
            assert Path(video.path).read_bytes() == url.encode()
            return response(1)

        return upload

    for index, (msg, url) in enumerate(zip(messages, (A, B), strict=True)):
        msg.answer_video.side_effect = send(index, url)
    tasks = [
        asyncio.create_task(handler.handle(msg, url))
        for msg, url in zip(messages, (A, B), strict=True)
    ]
    try:
        await asyncio.wait_for(asyncio.gather(*(event.wait() for event in ready)), 3)
        assert len({path.parent for path in provider.paths}) == 2
    finally:
        release.set()
        await asyncio.gather(*tasks)
    assert not handler._active_users
    assert all(msg.answer.await_count == 1 for msg in messages)
    assert all(not path.parent.exists() for path in provider.paths)


@pytest.mark.asyncio
async def test_cleanup_failure_quarantines_reservation_and_blocks_every_user(monkeypatch):
    provider = FixtureProvider()
    original = t.TemporaryDirectory
    directories = []

    def temporary(*args, **kwargs):
        directory = original(*args, **kwargs)
        directories.append(directory)

        def fail():
            raise OSError("PRIVATE_COOKIE_SIGNED_URL_HTML")

        directory.cleanup = fail
        return directory

    monkeypatch.setattr(t, "TemporaryDirectory", temporary)
    handler = t.TelegramTikTokHandler(provider=provider)
    first = message(7)
    try:
        await handler.handle(first, A)
        assert handler._blocked and handler._active_users == {7}
        assert provider.paths[0].is_file() and not directories[0]._finalizer.alive
        other = message(8)
        await handler.handle(other, B)
        other.answer_video.assert_not_awaited()
        assert len(provider.paths) == 1 and "приостановлена" in other.answer.call_args.args[0]
        assert "PRIVATE" not in repr(first.answer.await_args_list)
    finally:
        # Test-owned quarantine only: production deliberately leaves it for inspection.
        for directory in directories:
            shutil.rmtree(directory.name)
