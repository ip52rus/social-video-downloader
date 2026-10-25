"""Offline original-position policy, private worker scope and bound one-shot callbacks."""

import asyncio
import json
import socket
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message

from social_video_downloader.domain.carousel import CarouselScope
from social_video_downloader.domain.errors import (
    DownloadCleanupError,
    DownloadFailedError,
    DownloadTimeoutError,
    InvalidMediaURLError,
)
from social_video_downloader.domain.urls import instagram_item_position
from social_video_downloader.infrastructure import telegram_carousel as transport
from social_video_downloader.infrastructure.telegram_carousel import (
    CarouselDeliveryError,
    TelegramCarouselDelivery,
)
from social_video_downloader.infrastructure.workspace import quarantinable_workspace
from social_video_downloader.operation_logging import LOGGER_NAME
from social_video_downloader.services.instagram_acquisition import (
    CarouselAcquisitionLimits,
    InstagramCarouselAcquisition,
    plan_from_payload,
    plan_payload,
    validate_plan,
)
from social_video_downloader.services.instagram_carousel import InstagramCarouselService
from social_video_downloader.telegram_instagram import InstagramReelHandler
from social_video_downloader.telegram_instagram_interactions import (
    InstagramChoiceStore,
    parse_instagram_callback,
)
from social_video_downloader.telegram_instagram_posts import InstagramPostHandler
from tests import test_instagram_acquisition as acquisition
from tests.localization_fixtures import russian_presentation as russian_presentation
from tests.test_instagram_carousel import PHOTO, URL, VIDEO, Runtime
from tests.test_telegram_carousel import Sender, collection, install_preparation, response

media_files = acquisition.media_files


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("External network forbidden")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)


@pytest.mark.parametrize(
    "suffix,expected",
    [
        ("", None),
        ("?img_index=1", 1),
        ("?img_index=2", 2),
        ("?img_index=21", 21),
        ("?%69mg_index=%32&rpxt=fixture&utm_source=x&psln=x", 2),
        ("?utm_source=x#watch", None),
    ],
)
def test_url_positions(suffix, expected):
    assert instagram_item_position(URL + suffix) == expected


@pytest.mark.parametrize(
    "suffix",
    [
        "?img_index=0",
        "?img_index=-1",
        "?img_index=+2",
        "?img_index=02",
        "?img_index=2.0",
        "?img_index=",
        "?img_index=2&img_index=2",
        "?img_index=2&media_id=x",
        "?item_id=x",
        "?carousel_index=2",
        "?index=2",
        "?slide=2",
        "?img_index=%",
        "?img_index=2#img_index=2",
        "#?img_index=2",
        "?%2569mg_index=2",
        "?img_index=%2532",
        "?img_index%3D2=x",
        "?img_index=2#%FF",
        "?img_index=%FF",
        "?=value",
        "?img_index=9999999999",
        "?" + "&".join(f"x{i}=1" for i in range(33)),
    ],
)
def test_ambiguous_reference_refused(suffix):
    with pytest.raises(InvalidMediaURLError):
        instagram_item_position(URL + suffix)


def plans():
    full = Runtime([VIDEO, PHOTO, {**VIDEO, "pk": 103}]).service().create_selection_plan(URL)
    return full, InstagramCarouselService.select_video(full, 3)


@pytest.mark.parametrize("position", [1, 3])
def test_source_position_and_wire(position):
    full, _ = plans()
    selected = InstagramCarouselService.select_video(full, position)
    assert selected.items == full.items and selected.parent_identity == full.parent_identity
    assert selected.selected_videos == (full.items[position - 1],)
    assert plan_from_payload(json.loads(json.dumps(plan_payload(selected)))) == selected
    assert len(selected.items) == 3 and selected.scope is CarouselScope.SINGLE_VIDEO


@pytest.mark.parametrize("position", [0, 2, 4, True, -1])
def test_photo_or_bad_position_never_selects_neighbour(position):
    full, _ = plans()
    with pytest.raises(InvalidMediaURLError):
        InstagramCarouselService.select_video(full, position)


@pytest.mark.parametrize("mutation", ["subset", "position", "child", "scope", "parent", "photo"])
def test_forged_plan_and_ipc(mutation):
    full, single = plans()
    if mutation == "subset":
        with pytest.raises(DownloadFailedError):
            validate_plan(
                replace(full, selected_videos=single.selected_videos), CarouselAcquisitionLimits()
            )
        return
    data = plan_payload(single)
    if mutation == "position":
        data["requested_position"] = 1
    elif mutation == "child":
        data["selected_child_id"] = "different"
    elif mutation == "scope":
        data["scope"] = "publication"
    elif mutation == "parent":
        data["parent_identity"]["pk"] = "1"
    else:
        data["requested_position"] = 2
        data["selected_child_id"] = full.items[1].item_id
    with pytest.raises(DownloadFailedError):
        plan_from_payload(data)


def test_exactly_one_acquisition_with_photo_between_videos(tmp_path, media_files):
    runtime = acquisition.Runtime(acquisition.product(3, photos=(2,)), media_files["video"])
    runtime.data["carousel_media"][2]["video_versions"][0]["url"] = (
        "https://media.invalid/selected.mp4"
    )
    original = runtime.factory
    seen = []

    def factory(options):
        ydl = original(options)
        open_media = ydl.urlopen

        def record(request):
            seen.append(request.url)
            return open_media(request)

        ydl.urlopen = record
        return ydl

    runtime.provider._ydl_factory = factory
    selected = InstagramCarouselService.select_video(runtime.plan(), 3)
    result = acquisition.acquire(runtime, selected, tmp_path)
    assert len(result["durations"]) == 1 and runtime.requests == 1
    assert runtime.processed == ["video-3"]
    assert seen == ["https://media.invalid/selected.mp4"]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("mutation", ["parent", "child", "order", "kind", "count"])
def test_single_refresh_rejects_entire_changed_manifest(tmp_path, media_files, mutation):
    runtime = acquisition.Runtime(acquisition.product(3), media_files["video"])
    selected = InstagramCarouselService.select_video(runtime.plan(), 3)
    if mutation == "parent":
        runtime.data["pk"] += 1
    elif mutation == "child":
        runtime.data["carousel_media"][0]["pk"] += 20
    elif mutation == "order":
        runtime.data["carousel_media"].reverse()
    elif mutation == "kind":
        runtime.data["carousel_media"][0] = {**PHOTO, "pk": 1001}
    else:
        runtime.data["carousel_media"].pop(0)
    with pytest.raises(DownloadFailedError):
        acquisition.acquire(runtime, selected, tmp_path)
    assert runtime.requests == 0 and not runtime.processed and not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_single_process_scope_and_reap(tmp_path, media_files, monkeypatch):
    runtime = acquisition.Runtime(acquisition.product(3), media_files["silent"])
    selected = InstagramCarouselService.select_video(runtime.plan(), 3)
    original = asyncio.create_subprocess_exec
    processes = []

    async def launch(executable, *args, **kwargs):
        if args == ("-m", "social_video_downloader.infrastructure.instagram_acquisition"):
            args = ("-c", acquisition.subprocess_script(runtime.media, count=3))
        process = await original(executable, *args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", launch)
    got = await InstagramCarouselAcquisition().acquire(selected, tmp_path)
    assert [(x.position, x.item_id) for x in got.videos] == [(3, selected.items[2].item_id)]
    assert got.total_bytes == runtime.media.stat().st_size
    assert all(p.returncode == 0 for p in processes)


def ui(monkeypatch, items=None):
    runtime = Runtime(items or [VIDEO, PHOTO, {**VIDEO, "pk": 103}])
    owner = InstagramReelHandler(ydl_factory=runtime.factory)
    bot = AsyncMock()
    prompt = response(17).as_(bot)
    monkeypatch.setattr(Message, "edit_text", AsyncMock())
    message = MagicMock(
        text=URL + "?img_index=3", from_user=SimpleNamespace(id=7), chat=SimpleNamespace(id=1)
    )
    message.answer = AsyncMock(return_value=prompt)
    message.answer_video = AsyncMock()
    return owner, message, prompt, runtime


def callback(prompt, data, user=7):
    return SimpleNamespace(
        message=prompt, data=data, from_user=SimpleNamespace(id=user), answer=AsyncMock()
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("action", [0, 1])
async def test_buttons_download_only_after_valid_choice(monkeypatch, action):
    owner, msg, prompt, runtime = ui(monkeypatch)
    send = AsyncMock()
    monkeypatch.setattr(InstagramPostHandler, "_send_carousel", send)
    await owner.handle(msg, msg.text)
    assert not owner._active and len(runtime.extractions) == 1
    send.assert_not_awaited()
    msg.answer_video.assert_not_awaited()
    keyboard = msg.answer.call_args.kwargs["reply_markup"]
    data = keyboard.inline_keyboard[action][0].callback_data
    assert len(data.encode()) <= 64 and URL not in data and parse_instagram_callback(data)
    cb = callback(prompt, data)
    await owner._post_handler.handle_callback(cb)
    await owner._post_handler.handle_callback(cb)
    assert send.await_count == 1 and not owner._active
    plan = send.call_args.args[1]
    assert [x.position for x in plan.selected_videos] == ([1, 3] if action == 0 else [3])
    assert len(runtime.extractions) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("position", [2, 4])
async def test_photo_offer_or_out_of_range(monkeypatch, position):
    owner, msg, _, _ = ui(monkeypatch)
    msg.text = URL + f"?img_index={position}"
    await owner.handle(msg, msg.text)
    if position == 2:
        assert "фотография" in msg.answer.call_args.args[0]
        assert len(msg.answer.call_args.kwargs["reply_markup"].inline_keyboard) == 1
    else:
        assert "Такого элемента" in msg.answer.call_args.args[0]
    assert not owner._active


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["user", "chat", "message", "action", "restart", "expired"])
async def test_wrong_stale_callback_never_downloads(monkeypatch, bad):
    owner, msg, prompt, _ = ui(monkeypatch)
    send = AsyncMock()
    monkeypatch.setattr(InstagramPostHandler, "_send_carousel", send)
    await owner.handle(msg, msg.text)
    data = msg.answer.call_args.kwargs["reply_markup"].inline_keyboard[1][0].callback_data
    if bad == "chat":
        prompt = response(17, chat_id=9)
    if bad == "message":
        prompt = response(18)
    if bad == "action":
        data = data[:-1] + "2"
    handler = owner._post_handler
    if bad == "restart":
        handler = InstagramPostHandler(owner)
    if bad == "expired":
        handler._choices._clock = lambda: datetime.now(UTC) + timedelta(hours=1)
    await handler.handle_callback(callback(prompt, data, user=8 if bad == "user" else 7))
    send.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["busy", "ack", "edit"])
async def test_busy_or_api_failure_is_safe(monkeypatch, failure):
    owner, msg, prompt, _ = ui(monkeypatch)
    send = AsyncMock()
    monkeypatch.setattr(InstagramPostHandler, "_send_carousel", send)
    await owner.handle(msg, msg.text)
    data = msg.answer.call_args.kwargs["reply_markup"].inline_keyboard[1][0].callback_data
    cb = callback(prompt, data)
    if failure == "busy":
        owner._active = True
    elif failure == "ack":
        cb.answer.side_effect = TimeoutError
    else:
        monkeypatch.setattr(Message, "edit_text", AsyncMock(side_effect=TimeoutError))
    await owner._post_handler.handle_callback(cb)
    if failure != "edit":
        send.assert_not_awaited()
        owner._active = False
        cb.answer.side_effect = None
        await owner._post_handler.handle_callback(cb)
    assert send.await_count == 1


@pytest.mark.asyncio
async def test_early_and_concurrent_clicks_and_reel_admission(monkeypatch):
    owner, msg, prompt, _ = ui(monkeypatch)
    send = AsyncMock()
    monkeypatch.setattr(InstagramPostHandler, "_send_carousel", send)

    async def offer(text, **kwargs):
        data = kwargs["reply_markup"].inline_keyboard[1][0].callback_data
        await owner._post_handler.handle_callback(callback(prompt, data))
        send.assert_not_awaited()
        return prompt

    msg.answer.side_effect = offer
    await owner.handle(msg, msg.text)
    data = msg.answer.call_args.kwargs["reply_markup"].inline_keyboard[1][0].callback_data
    cb = callback(prompt, data)
    entered, release = asyncio.Event(), asyncio.Event()

    async def acknowledge(*args):
        entered.set()
        await release.wait()

    cb.answer.side_effect = acknowledge
    task = asyncio.create_task(owner._post_handler.handle_callback(cb))
    await entered.wait()
    await owner._post_handler.handle_callback(callback(prompt, data))
    reel = MagicMock()
    reel.answer = AsyncMock()
    await owner.handle(reel, "https://www.instagram.com/reel/Synthetic/")
    assert "Дождись" in reel.answer.call_args.args[0]
    release.set()
    await task
    assert send.await_count == 1 and not owner._active


def test_store_bound_capacity_ttl_and_restart():
    clock = [datetime.now(UTC)]
    store = InstagramChoiceStore(clock=lambda: clock[0], capacity=1, ttl=timedelta(seconds=1))
    choice = store.create(7, 1, plans())
    assert choice is not None and store.create(8, 1, plans()) is None
    assert store.resolve(choice.token, 1, 7, 1, 17) is None
    assert store.bind(choice.token, 17)
    assert store.resolve(choice.token, 1, 7, 1, 17, consume=True) == choice.plans[1]
    assert store.resolve(choice.token, 1, 7, 1, 17) is None
    choice = store.create(7, 1, plans())
    assert store.bind(choice.token, 17)
    clock[0] += timedelta(seconds=1)
    assert store.resolve(choice.token, 1, 7, 1, 17) is None
    assert parse_instagram_callback("ig:v2:bad:1") is None


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, "wrong_collection", "timeout", "unconfirmed"])
async def test_single_delivery_exact_file_and_uncertainty(tmp_path, monkeypatch, failure):
    files, full = collection(tmp_path, 3, photos=(2,))
    selected = InstagramCarouselService.select_video(full, 3)
    files = replace(files, videos=tuple(x for x in files.videos if x.position == 3))
    if failure == "wrong_collection":
        files = replace(files, videos=())
    install_preparation(monkeypatch)
    sender = Sender(
        error_at=1 if failure == "timeout" else None,
        malformed=(lambda r: []) if failure == "unconfirmed" else None,
    )
    task = TelegramCarouselDelivery(sender).deliver(
        files, plan=selected, workspace=tmp_path, chat_id=1
    )
    if failure:
        with pytest.raises(CarouselDeliveryError):
            await task
    else:
        progress = await task
        assert progress.complete and progress.confirmed_positions == (3,)
        assert sender.calls[0][0] == "video"
    assert len(sender.calls) == (0 if failure == "wrong_collection" else 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("action", [0, 1])
@pytest.mark.parametrize("media_kind", ["video", "silent"])
async def test_url_to_worker_to_confirmed_delivery_and_cleanup(
    monkeypatch, media_files, action, media_kind, caplog
):
    import logging

    caplog.set_level(logging.INFO, logger=LOGGER_NAME)
    runtime = acquisition.Runtime(acquisition.product(3), media_files[media_kind])
    original = asyncio.create_subprocess_exec
    processes = []

    async def launch(executable, *args, **kwargs):
        if args == ("-m", "social_video_downloader.infrastructure.instagram_acquisition"):
            args = ("-c", acquisition.subprocess_script(runtime.media, count=3))
        process = await original(executable, *args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", launch)
    owner, msg, _, _ = ui(monkeypatch)
    owner._ydl_factory = runtime.factory
    sender = Sender()
    prompt = response(17).as_(sender)
    msg.answer.return_value = prompt
    await owner.handle(msg, msg.text)
    assert runtime.requests == 0 and not processes and not sender.calls
    data = msg.answer.call_args.kwargs["reply_markup"].inline_keyboard[action][0].callback_data
    await owner._post_handler.handle_callback(callback(prompt, data))
    await owner._post_handler.handle_callback(callback(prompt, data))
    assert len(processes) == 2 and all(p.returncode == 0 for p in processes)
    assert len(sender.calls) == 1 and sender.calls[0][0] == ("album" if action == 0 else "video")
    assert len(sender.seen_paths) == (3 if action == 0 else 1)
    assert all(not path.exists() for path in sender.seen_paths)
    assert not owner._active
    for private in (URL, data, "Fixture_Carousel", str(runtime.data["pk"])):
        assert private not in caplog.text
    assert "operation_completed" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_single_deadline_cancellation_reap(tmp_path, media_files, monkeypatch, cancel):
    runtime = acquisition.Runtime(acquisition.product(3), media_files["video"])
    selected = InstagramCarouselService.select_video(runtime.plan(), 3)
    processes = acquisition.install_child(
        monkeypatch, acquisition.subprocess_script(runtime.media, count=3, mode="hang")
    )
    service = InstagramCarouselAcquisition(
        CarouselAcquisitionLimits(max_seconds=10 if cancel else 0.5)
    )
    task = asyncio.create_task(service.acquire(selected, tmp_path))
    if cancel:
        async with asyncio.timeout(5):
            while not list(tmp_path.glob("*/partial.mp4")):
                await asyncio.sleep(0.01)
        task.cancel()
    with pytest.raises(asyncio.CancelledError if cancel else DownloadTimeoutError):
        await task
    assert processes and all(p.returncode is not None for p in processes)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_cleanup_failure_preserves_worker_workspace(tmp_path, monkeypatch):
    from pathlib import Path

    from social_video_downloader.services import instagram_acquisition as boundary

    _, selected = plans()

    class FailedChild:
        async def communicate(self, payload):
            private = json.loads(payload)["workspace"]
            Path(private, "partial.mp4").write_bytes(b"synthetic")
            raise DownloadFailedError("synthetic")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=FailedChild()))
    monkeypatch.setattr(boundary, "_kill", AsyncMock(side_effect=OSError("private-sentinel")))
    with pytest.raises(DownloadCleanupError):
        await InstagramCarouselAcquisition().acquire(selected, tmp_path)
    assert len(list(tmp_path.glob("*/partial.mp4"))) == 1


@pytest.mark.asyncio
async def test_callback_cancellation_holds_slot_until_real_worker_reaped(monkeypatch, media_files):
    from social_video_downloader.services import instagram_acquisition as boundary

    runtime = acquisition.Runtime(acquisition.product(3), media_files["video"])
    owner, msg, prompt, _ = ui(monkeypatch)
    owner._ydl_factory = runtime.factory
    processes = acquisition.install_child(
        monkeypatch, acquisition.subprocess_script(runtime.media, count=3, mode="hang")
    )
    entered, release = asyncio.Event(), asyncio.Event()
    original = boundary._kill

    async def kill(process):
        entered.set()
        await release.wait()
        await original(process)

    monkeypatch.setattr(boundary, "_kill", kill)
    await owner.handle(msg, msg.text)
    data = msg.answer.call_args.kwargs["reply_markup"].inline_keyboard[1][0].callback_data
    task = asyncio.create_task(owner._post_handler.handle_callback(callback(prompt, data)))
    try:
        async with asyncio.timeout(5):
            while not processes:
                await asyncio.sleep(0.01)
        task.cancel()
        async with asyncio.timeout(5):
            await entered.wait()
        assert owner._active and not task.done()
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert not owner._active and all(p.returncode is not None for p in processes)


@pytest.mark.asyncio
async def test_cleanup_failure_propagates_and_blocks_instagram(tmp_path, monkeypatch):
    owner, msg, prompt, _ = ui(monkeypatch)
    send = AsyncMock(side_effect=DownloadCleanupError("private-sentinel"))
    monkeypatch.setattr(InstagramPostHandler, "_send_carousel", send)
    await owner.handle(msg, msg.text)
    data = msg.answer.call_args.kwargs["reply_markup"].inline_keyboard[1][0].callback_data
    await owner._post_handler.handle_callback(callback(prompt, data))
    assert owner._active and owner._blocked
    with pytest.raises(DownloadCleanupError), quarantinable_workspace(base_dir=tmp_path) as private:
        (private / "partial").write_bytes(b"synthetic")
        raise DownloadCleanupError("synthetic")
    assert (private / "partial").exists()
    files, full = collection(tmp_path, 2)
    monkeypatch.setattr(
        transport, "_prepare", AsyncMock(side_effect=DownloadCleanupError("synthetic"))
    )
    with pytest.raises(DownloadCleanupError):
        await TelegramCarouselDelivery(Sender()).deliver(
            files, plan=full, workspace=tmp_path, chat_id=1
        )
