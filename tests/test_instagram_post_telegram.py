"""Network-forbidden checks for opt-in Telegram /p/ routing."""

import asyncio
import io
import shutil
import socket
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from yt_dlp.networking.common import Response

import social_video_downloader.telegram_instagram_posts as posts
from social_video_downloader.domain.carousel import (
    CarouselIssue,
    CarouselPlanState,
    DownloadedCarousel,
    DownloadedCarouselVideo,
)
from social_video_downloader.domain.models import DownloadedMedia, MediaMetadata, Platform
from social_video_downloader.handlers import handle_text
from social_video_downloader.infrastructure.telegram_carousel import (
    CarouselDeliveryCancelled,
    CarouselDeliveryError,
    CarouselDeliveryProgress,
)
from social_video_downloader.services.instagram_acquisition import InstagramCarouselAcquisition
from social_video_downloader.services.instagram_carousel import InstagramCarouselService
from social_video_downloader.telegram_instagram import InstagramReelHandler
from social_video_downloader.telegram_instagram_posts import (
    _ACQUISITION_LIMITS,
    _DELIVERY_LIMITS,
    TelegramCarouselDelivery,
)
from tests.integration.test_video_preparation import generate
from tests.test_instagram_carousel import (
    INVALID_CAROUSEL_SOURCES,
    ITEM_REFERENCE_SUFFIXES,
    PHOTO,
    SOURCE_MUTATIONS,
    VIDEO,
    Runtime,
    corrupt_upstream_collection,
    mutate_upstream_source,
)
from tests.test_instagram_provider import INFO
from tests.test_telegram_carousel import collection, response

URL = "https://www.instagram.com/p/Synthetic_01/"


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Network calls are forbidden in post routing tests")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)


@pytest.fixture
def message():
    result = MagicMock(text=URL)
    result.answer = AsyncMock()
    result.answer_video = AsyncMock(return_value=response(1))
    result.chat.id = 1
    result.bot = MagicMock()
    return result


def owner():
    def no_extraction(*args, **kwargs):
        raise AssertionError("Unexpected external Instagram extraction")

    return InstagramReelHandler(ydl_factory=no_extraction)


@pytest.mark.asyncio
async def test_three_video_carousel_is_routed_in_original_order_and_cleaned(
    message, monkeypatch, tmp_path
):
    expected, plan = collection(tmp_path, 3)
    handler = owner()
    inspected = []

    def inspect(self, raw):
        inspected.append(raw)
        return plan

    async def acquire(self, selection, output_dir):
        assert selection == plan
        assert 0 < self.limits.max_seconds <= _ACQUISITION_LIMITS.max_seconds
        assert (
            replace(self.limits, max_seconds=_ACQUISITION_LIMITS.max_seconds) == _ACQUISITION_LIMITS
        )
        videos = []
        for item in expected.videos:
            p = Path(output_dir) / item.media.file_path.name
            p.write_bytes(item.media.file_path.read_bytes())
            videos.append(
                DownloadedCarouselVideo(
                    item.position,
                    item.item_id,
                    DownloadedMedia(p, item.media.metadata),
                )
            )
        return DownloadedCarousel(
            plan.publication_url,
            tuple(videos),
            sum(v.media.file_path.stat().st_size for v in videos),
        )

    async def deliver(self, acquired, *, plan, workspace, chat_id):
        assert plan == expected_plan
        assert chat_id == 1
        assert self.limits == _DELIVERY_LIMITS
        assert [x.position for x in acquired.videos] == [1, 2, 3]
        assert all(x.media.file_path.is_file() for x in acquired.videos)
        inspected.append(Path(workspace))
        return CarouselDeliveryProgress(3, (1, 2, 3), (), 1)

    expected_plan = plan
    monkeypatch.setattr(InstagramCarouselService, "inspect_publication", inspect)
    monkeypatch.setattr(InstagramCarouselAcquisition, "acquire", acquire)
    monkeypatch.setattr(TelegramCarouselDelivery, "deliver", deliver)
    await handle_text(message, instagram_reels=handler)
    assert inspected[0] == URL
    assert not inspected[1].exists()
    assert message.answer_video.await_count == 0
    assert not handler._active


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "suffix",
    ITEM_REFERENCE_SUFFIXES,
)
async def test_unsafe_post_reference_never_extracts_or_sends(message, monkeypatch, suffix):
    handler = owner()
    acquire, deliver = AsyncMock(), AsyncMock()
    monkeypatch.setattr(InstagramCarouselAcquisition, "acquire", acquire)
    monkeypatch.setattr(TelegramCarouselDelivery, "deliver", deliver)
    prepare = MagicMock()
    monkeypatch.setattr(handler, "_prepare", prepare)
    message.text += suffix
    await handle_text(message, instagram_reels=handler)
    acquire.assert_not_awaited()
    deliver.assert_not_awaited()
    prepare.assert_not_called()
    assert message.answer_video.await_count == 0
    assert not message.bot.mock_calls
    assert "Некорректный или неоднозначный" in message.answer.call_args.args[0]
    assert not handler._active


@pytest.mark.asyncio
async def test_unclassifiable_carousel_is_blocked_not_partially_sent(
    message, monkeypatch, tmp_path
):
    _, ready = collection(tmp_path, 3)
    blocked = replace(
        ready,
        state=CarouselPlanState.BLOCKED,
        selected_videos=(),
        issue=CarouselIssue.UNKNOWN_ITEM,
    )
    monkeypatch.setattr(InstagramCarouselService, "inspect_publication", lambda self, url: blocked)
    handler = owner()
    await handle_text(message, instagram_reels=handler)
    assert "Невозможно безопасно" in message.answer.call_args.args[0]
    message.answer_video.assert_not_awaited()
    assert not handler._active


@pytest.mark.asyncio
async def test_large_carousel_is_refused_without_truncation_or_acquisition(
    message, monkeypatch, tmp_path
):
    _, plan = collection(tmp_path, 11)
    monkeypatch.setattr(InstagramCarouselService, "inspect_publication", lambda self, url: plan)
    handler = owner()
    await handle_text(message, instagram_reels=handler)
    assert "лимит — 10" in message.answer.call_args.args[0]
    assert "пропускать остальные не будем" in message.answer.call_args.args[0]
    message.answer_video.assert_not_awaited()
    assert not handler._active


@pytest.mark.asyncio
async def test_single_video_post_uses_existing_single_file_worker(message, monkeypatch):
    metadata = MediaMetadata("Synthetic", URL, Platform.INSTAGRAM)
    monkeypatch.setattr(InstagramCarouselService, "inspect_publication", lambda self, url: metadata)
    handler = owner()
    created = []

    def prepare(url, workspace, guard, *, provider):
        assert url == URL
        source = Path(workspace) / "single.mp4"
        source.write_bytes(b"synthetic")
        created.append(source)
        return source, {"width": 64, "height": 96, "duration": 1}

    monkeypatch.setattr(handler, "_prepare", prepare)
    await handle_text(message, instagram_reels=handler)
    message.answer_video.assert_awaited_once()
    assert created and not created[0].exists()
    assert not handler._active


@pytest.mark.asyncio
async def test_uncertain_album_send_does_not_retry_or_claim_success(message, monkeypatch, tmp_path):
    acquired, plan = collection(tmp_path, 3)
    handler = owner()
    sends = []

    monkeypatch.setattr(InstagramCarouselService, "inspect_publication", lambda self, url: plan)

    async def acquire(self, selection, workspace):
        return acquired

    async def deliver(self, media, *, plan, workspace, chat_id):
        sends.append(1)
        raise CarouselDeliveryError("delivery", CarouselDeliveryProgress(3, (1,), (2, 3), 1))

    monkeypatch.setattr(InstagramCarouselAcquisition, "acquire", acquire)
    monkeypatch.setattr(TelegramCarouselDelivery, "deliver", deliver)
    await handle_text(message, instagram_reels=handler)
    assert sends == [1]
    assert "могла быть доставлена" in message.answer.call_args.args[0]
    assert "автоматического повтора не будет" in message.answer.call_args.args[0]
    assert not handler._active


@pytest.mark.asyncio
async def test_post_respects_single_active_instagram_slot(message):
    handler = owner()
    handler._active = True
    await handle_text(message, instagram_reels=handler)
    assert "Уже обрабатываю Instagram-ссылку" in message.answer.call_args.args[0]
    message.answer_video.assert_not_awaited()
    assert handler._active


def publication_runtime(product, *, source=None, mutate=None):
    """Use the installed extractor/adapter with the existing synthetic JSON runtime."""
    runtime = Runtime([])
    runtime.product = deepcopy(product)
    if mutate is not None:
        runtime.mutate = mutate
    processed, repeated_extractions = [], []

    def factory(options):
        output = options.get("outtmpl")
        ydl = runtime.factory(options)
        extract = ydl.extract_info

        def inspect(url, **kwargs):
            if runtime.extractions:
                # The former fallback would see permissive metadata on re-extraction.
                # A blocked source must never reach this branch.
                repeated_extractions.append(url)
                return deepcopy(INFO)
            return extract(url, **kwargs)

        def acquire(raw, *, download):
            assert download is True
            processed.append(deepcopy(raw))
            assert source is not None, "Forbidden source reached acquisition"
            assert "_carousel_item_evidence" not in raw
            shutil.copyfile(source, output)
            return raw

        ydl.extract_info = inspect
        ydl.process_ie_result = acquire
        return ydl

    return InstagramReelHandler(ydl_factory=factory), runtime, processed, repeated_extractions


@pytest.mark.asyncio
@pytest.mark.parametrize("audio", [False, True])
@pytest.mark.parametrize(
    "suffix", ["", "?utm_source=fixture&psln=fixture&dlrf=fixture", "?share#watch"]
)
async def test_positive_single_post_consumes_same_snapshot_and_validates_local_media(
    message, tmp_path, audio, suffix
):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("Local FFmpeg/ffprobe unavailable")
    source = tmp_path / "local.mp4"
    generate(source, audio=audio)
    original = source.read_bytes()
    # Incomplete codec/dimension fields remain admissible, with explicit VIDEO evidence.
    product = {**VIDEO, "video_versions": [{"url": "https://media.invalid/video.mp4"}]}
    handler, runtime, processed, repeated = publication_runtime(product, source=source)
    message.text += suffix
    sent_paths = []

    async def send(file, **kwargs):
        sent_paths.append(Path(file.path))
        assert Path(file.path).read_bytes() == original
        assert kwargs == {"width": 64, "height": 96, "duration": 1, "supports_streaming": True}
        return response(1)

    message.answer_video.side_effect = send
    await handle_text(message, instagram_reels=handler)
    assert runtime.extractions == [URL]
    assert len(processed) == 1 and not repeated
    message.answer_video.assert_awaited_once()
    assert sent_paths and not sent_paths[0].parent.exists()
    assert source.read_bytes() == original and not handler._active


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "product",
    [
        {**VIDEO, "is_private": True},
        {**VIDEO, "needs_auth": True},
        {**VIDEO, "has_drm": True},
        {**VIDEO, "availability": "needs_auth"},
        {**VIDEO, "media_type": 1},
        {"pk": 101, "media_type": 2},
        {**VIDEO, "pk": False},
        {**VIDEO, "video_versions": [{"url": "https://media.invalid/video.m3u8"}]},
        PHOTO,
        {"pk": 1386527023699267419445, "carousel_media": [{**VIDEO, "is_private": True}]},
        {"pk": 1386527023699267419445, "carousel_media": [{**VIDEO, "needs_auth": True}]},
        {"pk": 1386527023699267419445, "carousel_media": [{**VIDEO, "has_drm": True}]},
        {"pk": 1386527023699267419445, "carousel_media": [{"pk": 101, "media_type": 2}]},
        {
            "pk": 1386527023699267419445,
            "carousel_media": [
                {**VIDEO, "video_versions": [{"url": "https://media.invalid/video.m3u8"}]}
            ],
        },
        {"pk": 1386527023699267419445, "is_private": True, "carousel_media": [VIDEO]},
    ],
)
async def test_blocked_source_never_reextracts_acquires_or_sends(message, monkeypatch, product):
    message.text += "?utm_source=fixture&psln=fixture&dlrf=fixture#watch"
    handler, runtime, processed, repeated = publication_runtime(product)
    acquire, deliver = AsyncMock(), AsyncMock()
    monkeypatch.setattr(InstagramCarouselAcquisition, "acquire", acquire)
    monkeypatch.setattr(TelegramCarouselDelivery, "deliver", deliver)
    await handle_text(message, instagram_reels=handler)
    assert runtime.extractions == [URL]
    assert not processed and not repeated
    acquire.assert_not_awaited()
    deliver.assert_not_awaited()
    message.answer_video.assert_not_awaited()
    assert not message.bot.mock_calls and not handler._active


@pytest.mark.asyncio
@pytest.mark.parametrize("source", INVALID_CAROUSEL_SOURCES)
async def test_invalid_source_collection_never_acquires_or_sends(message, monkeypatch, source):
    message.text += "?utm_source=fixture&psln=fixture&dlrf=fixture#watch"
    handler, runtime, processed, repeated = publication_runtime({**VIDEO, "carousel_media": source})
    acquire, deliver = AsyncMock(), AsyncMock()
    monkeypatch.setattr(InstagramCarouselAcquisition, "acquire", acquire)
    monkeypatch.setattr(TelegramCarouselDelivery, "deliver", deliver)
    # This guard makes an unsafe single-video permission fail visibly before IO.
    prepare = MagicMock(side_effect=AssertionError("Malformed collection reached single worker"))
    monkeypatch.setattr(handler, "_prepare", prepare)
    await handle_text(message, instagram_reels=handler)
    assert runtime.extractions == [URL] and not processed and not repeated
    prepare.assert_not_called()
    acquire.assert_not_awaited()
    deliver.assert_not_awaited()
    message.answer_video.assert_not_awaited()
    assert not message.bot.mock_calls and not handler._active


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["single", "missing_entries", "dropped_entry", "reordered"])
async def test_changed_upstream_collection_never_reaches_media(message, monkeypatch, change):
    corrupt_upstream_collection(monkeypatch, change)
    handler, runtime, processed, repeated = publication_runtime(
        {**VIDEO, "carousel_media": [VIDEO, {**VIDEO, "pk": 103}]}
    )
    acquire, deliver = AsyncMock(), AsyncMock()
    monkeypatch.setattr(InstagramCarouselAcquisition, "acquire", acquire)
    monkeypatch.setattr(TelegramCarouselDelivery, "deliver", deliver)
    prepare = MagicMock(side_effect=AssertionError("Changed collection reached single worker"))
    monkeypatch.setattr(handler, "_prepare", prepare)
    await handle_text(message, instagram_reels=handler)
    assert runtime.extractions == [URL] and not processed and not repeated
    prepare.assert_not_called()
    acquire.assert_not_awaited()
    deliver.assert_not_awaited()
    message.answer_video.assert_not_awaited()
    assert not message.bot.mock_calls and not handler._active


@pytest.mark.asyncio
@pytest.mark.parametrize("change", SOURCE_MUTATIONS)
async def test_mutated_source_never_acquires_sends_or_reextracts(message, monkeypatch, change):
    items = mutate_upstream_source(monkeypatch, change)
    handler, runtime, processed, repeated = publication_runtime({**VIDEO, "carousel_media": items})
    acquire, deliver = AsyncMock(), AsyncMock()
    monkeypatch.setattr(InstagramCarouselAcquisition, "acquire", acquire)
    monkeypatch.setattr(TelegramCarouselDelivery, "deliver", deliver)
    prepare = MagicMock(side_effect=AssertionError("Mutated collection reached single worker"))
    monkeypatch.setattr(handler, "_prepare", prepare)
    await handle_text(message, instagram_reels=handler)
    assert runtime.extractions == [URL] and not processed and not repeated
    prepare.assert_not_called()
    acquire.assert_not_awaited()
    deliver.assert_not_awaited()
    message.answer_video.assert_not_awaited()
    assert not message.bot.mock_calls and not handler._active


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        "missing_evidence",
        "missing_id",
        "changed_id",
        "missing_formats",
        "redirect",
        "unknown",
        "null",
    ],
)
async def test_incomplete_or_ambiguous_single_metadata_is_not_permission_to_fallback(
    message, change
):
    def mutate(raw):
        if change == "null":
            return None
        if change.startswith("missing_"):
            key = {
                "missing_evidence": "_carousel_item_evidence",
                "missing_id": "id",
                "missing_formats": "formats",
            }[change]
            raw.pop(key, None)
        elif change == "changed_id":
            raw["id"] = "different"
        else:
            raw["_type"] = "url" if change == "redirect" else "unclassified"
        return raw

    handler, runtime, processed, repeated = publication_runtime(VIDEO, mutate=mutate)
    await handle_text(message, instagram_reels=handler)
    assert runtime.extractions == [URL] and not repeated and not processed
    message.answer_video.assert_not_awaited()
    assert not message.bot.mock_calls and not handler._active


@pytest.mark.asyncio
@pytest.mark.parametrize("mixed", [False, True])
@pytest.mark.parametrize("silent", [False, True])
@pytest.mark.parametrize(
    "suffix", ["", "?utm_source=fixture&psln=fixture&dlrf=fixture", "?share#watch"]
)
async def test_real_metadata_plan_selects_every_video_and_only_confirmed_photos_are_skipped(
    message, monkeypatch, mixed, silent, suffix
):
    message.text += suffix
    items = [VIDEO, {**VIDEO, "pk": 103}]
    if silent:
        items = [{**item, "has_audio": False} for item in (*items, {**VIDEO, "pk": 104})]
    if mixed:
        items.insert(0, PHOTO)
    handler, runtime, processed, repeated = publication_runtime(
        {"pk": 1386527023699267419445, "carousel_media": items}
    )
    expected = list(range(2 if mixed else 1, len(items) + 1))
    outputs = []

    async def acquire(self, plan, output_dir):
        assert [x.position for x in plan.selected_videos] == expected
        videos = []
        for item in plan.selected_videos:
            path = Path(output_dir) / f"video-{item.position}.mp4"
            path.write_bytes(b"synthetic")
            videos.append(
                DownloadedCarouselVideo(
                    item.position,
                    item.item_id,
                    DownloadedMedia(path, MediaMetadata("Synthetic", URL, Platform.INSTAGRAM)),
                )
            )
        outputs.append(Path(output_dir))
        return DownloadedCarousel(
            URL, tuple(videos), sum(x.media.file_path.stat().st_size for x in videos)
        )

    async def deliver(self, acquired, *, plan, workspace, chat_id):
        assert [x.position for x in acquired.videos] == expected
        assert [x.item_id for x in acquired.videos] == [x.item_id for x in plan.selected_videos]
        assert all(x.kind.value == "video" for x in plan.selected_videos)
        return CarouselDeliveryProgress(len(expected), tuple(expected), (), 1)

    monkeypatch.setattr(InstagramCarouselAcquisition, "acquire", acquire)
    monkeypatch.setattr(TelegramCarouselDelivery, "deliver", deliver)
    await handle_text(message, instagram_reels=handler)
    assert runtime.extractions == [URL] and not processed and not repeated
    assert outputs and all(not p.exists() for p in outputs) and not handler._active


@pytest.mark.asyncio
@pytest.mark.parametrize("stop", ["cancel", "repeat_cancel", "deadline", "request_error"])
async def test_inspection_stop_prevents_next_request_and_retains_slot_until_thread_exits(
    message, monkeypatch, stop
):
    entered, release, finished = Event(), Event(), Event()
    requests, responses, guards, timeouts = [], [], [], []
    original_guard = posts._Guard

    class Guard(original_guard):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            guards.append(self)

    def timeout(delay):
        context = asyncio.timeout(delay)
        timeouts.append(context)
        return context

    monkeypatch.setattr(posts, "_Guard", Guard)
    monkeypatch.setattr(
        posts,
        "asyncio",
        SimpleNamespace(get_running_loop=asyncio.get_running_loop, timeout=timeout),
    )

    class MetadataOnly:
        def __init__(self, options):
            self.params = options

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def add_info_extractor(self, ie):
            pass

        def urlopen(self, request):
            requests.append(request)
            entered.set()
            assert release.wait(5)
            if stop == "request_error":
                raise OSError("Synthetic metadata failure")
            result = Response(io.BytesIO(b"{}"), "https://www.instagram.com/fixture", {})
            responses.append(result)
            return result

        def extract_info(self, *args, **kwargs):
            try:
                self.urlopen("first")
                self.urlopen("second")
                return {"_type": "playlist", "entries": [], "_carousel_source_count": 0}
            finally:
                finished.set()

    handler = InstagramReelHandler(ydl_factory=MetadataOnly)
    acquire, deliver = AsyncMock(), AsyncMock()
    monkeypatch.setattr(InstagramCarouselAcquisition, "acquire", acquire)
    monkeypatch.setattr(TelegramCarouselDelivery, "deliver", deliver)
    prepare = MagicMock()
    monkeypatch.setattr(handler, "_prepare", prepare)
    task = asyncio.create_task(handle_text(message, instagram_reels=handler))
    try:
        async with asyncio.timeout(3):
            while not entered.is_set():
                await asyncio.sleep(0.001)
        if stop == "deadline":
            guards[0].deadline = monotonic() - 1
            timeouts[0].reschedule(asyncio.get_running_loop().time())
        elif stop != "request_error":
            task.cancel()
        if stop != "request_error":
            async with asyncio.timeout(3):
                while not guards[0].cancelled.is_set():
                    await asyncio.sleep(0.001)
            if stop == "repeat_cancel":
                task.cancel()
                await asyncio.sleep(0)
        assert not task.done() and handler._active and not finished.is_set()
        assert requests == ["first"]
        busy = MagicMock(text=URL, answer=AsyncMock(), answer_video=AsyncMock())
        await handle_text(busy, instagram_reels=handler)
        assert "Уже обрабатываю" in busy.answer.call_args.args[0]
    finally:
        release.set()
        if stop in {"cancel", "repeat_cancel"}:
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            await task
    assert finished.is_set() and requests == ["first"] and not handler._active
    assert all(x.closed for x in responses)
    acquire.assert_not_awaited()
    deliver.assert_not_awaited()
    prepare.assert_not_called()
    message.answer_video.assert_not_awaited()


@pytest.mark.asyncio
async def test_inspection_time_counts_against_acquisition_and_blocks_expired_delivery(
    message, monkeypatch, tmp_path
):
    import social_video_downloader.telegram_instagram as reels

    acquired, plan = collection(tmp_path, 3)
    clock = [10.0]
    monkeypatch.setattr(reels, "monotonic", lambda: clock[0])
    monkeypatch.setattr(posts, "monotonic", lambda: clock[0])

    def inspect(self, url):
        clock[0] += 100
        return plan

    outputs = []

    async def acquire(self, selection, output_dir):
        assert self.limits.max_seconds == _ACQUISITION_LIMITS.max_seconds - 100
        outputs.append(Path(output_dir))
        clock[0] += self.limits.max_seconds + 1
        return acquired

    monkeypatch.setattr(InstagramCarouselService, "inspect_publication", inspect)
    monkeypatch.setattr(InstagramCarouselAcquisition, "acquire", acquire)
    deliver = AsyncMock()
    monkeypatch.setattr(TelegramCarouselDelivery, "deliver", deliver)
    handler = owner()
    await handle_text(message, instagram_reels=handler)
    deliver.assert_not_awaited()
    message.answer_video.assert_not_awaited()
    assert outputs and not outputs[0].exists() and not handler._active


@pytest.mark.asyncio
async def test_single_post_work_deadline_is_not_reset_after_inspection(message, monkeypatch):
    import social_video_downloader.telegram_instagram as reels

    clock = [10.0]
    monkeypatch.setattr(reels, "monotonic", lambda: clock[0])
    monkeypatch.setattr(posts, "monotonic", lambda: clock[0])

    def inspected(raw):
        clock[0] += 100
        return raw

    handler, runtime, processed, repeated = publication_runtime(VIDEO, mutate=inspected)

    async def acknowledge(text):
        if text.startswith("Одиночное"):
            clock[0] += 81

    message.answer.side_effect = acknowledge
    await handle_text(message, instagram_reels=handler)
    assert runtime.extractions == [URL] and not repeated and not processed
    message.answer_video.assert_not_awaited()
    assert not handler._active


@pytest.mark.asyncio
async def test_single_worker_repeated_cancellation_keeps_workspace_until_exit(message, monkeypatch):
    monkeypatch.setattr(
        InstagramCarouselService,
        "inspect_publication",
        lambda self, url: MediaMetadata("Synthetic", URL, Platform.INSTAGRAM),
    )
    entered, release = Event(), Event()
    workspaces, guards = [], []
    handler = owner()

    def prepare(url, workspace, guard, *, provider):
        workspaces.append(workspace)
        guards.append(guard)
        entered.set()
        assert release.wait(5)
        assert workspace.is_dir()
        guard.check()

    monkeypatch.setattr(handler, "_prepare", prepare)
    task = asyncio.create_task(handle_text(message, instagram_reels=handler))
    try:
        async with asyncio.timeout(3):
            while not entered.is_set():
                await asyncio.sleep(0.001)
        task.cancel()
        async with asyncio.timeout(3):
            while not guards[0].cancelled.is_set():
                await asyncio.sleep(0.001)
        task.cancel()
        await asyncio.sleep(0)
        assert handler._active and not task.done() and workspaces[0].is_dir()
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert not handler._active and not workspaces[0].exists()
    message.answer_video.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["preparation", "upload"])
async def test_shared_deadline_cleans_outputs_and_preserves_delivery_uncertainty(
    message, monkeypatch, tmp_path, phase
):
    original, plan = collection(tmp_path, 3)
    monkeypatch.setattr(InstagramCarouselService, "inspect_publication", lambda self, url: plan)
    entered = asyncio.Event()
    outputs, timeouts = [], []

    def timeout(delay):
        context = asyncio.timeout(delay)
        timeouts.append(context)
        return context

    monkeypatch.setattr(
        posts,
        "asyncio",
        SimpleNamespace(get_running_loop=asyncio.get_running_loop, timeout=timeout),
    )

    async def acquire(self, selection, output_dir):
        videos = []
        for item in original.videos:
            path = Path(output_dir) / item.media.file_path.name
            path.write_bytes(item.media.file_path.read_bytes())
            videos.append(replace(item, media=replace(item.media, file_path=path)))
        outputs.append(Path(output_dir))
        return replace(original, videos=tuple(videos))

    async def send(**kwargs):
        entered.set()
        await asyncio.Event().wait()

    message.bot.send_media_group = AsyncMock(side_effect=send)

    async def deliver(self, media, **kwargs):
        try:
            if phase == "upload":
                await message.bot.send_media_group()
            else:
                entered.set()
                await asyncio.Event().wait()
        except asyncio.CancelledError:
            raise CarouselDeliveryCancelled(
                CarouselDeliveryProgress(3, (), (1, 2, 3) if phase == "upload" else (), 0)
            ) from None

    monkeypatch.setattr(InstagramCarouselAcquisition, "acquire", acquire)
    monkeypatch.setattr(TelegramCarouselDelivery, "deliver", deliver)
    handler = owner()
    task = asyncio.create_task(handle_text(message, instagram_reels=handler))
    async with asyncio.timeout(3):
        await entered.wait()
    assert handler._active and outputs[0].is_dir()
    timeouts[-1].reschedule(asyncio.get_running_loop().time())
    await task
    assert not handler._active and not outputs[0].exists()
    assert all(x.media.file_path.is_file() for x in original.videos)
    message.answer_video.assert_not_awaited()
    if phase == "upload":
        message.bot.send_media_group.assert_awaited_once()
        assert "могла быть доставлена" in message.answer.call_args.args[0]
    else:
        message.bot.send_media_group.assert_not_awaited()
        assert "Не удалось подготовить" in message.answer.call_args.args[0]
    assert "повтора не будет" in message.answer.call_args.args[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("single", [False, True])
async def test_acknowledgement_cannot_outlive_deadline_and_start_media_stages(
    message, monkeypatch, tmp_path, single
):
    _, plan = collection(tmp_path, 3)
    inspected = MediaMetadata("Synthetic", URL, Platform.INSTAGRAM) if single else plan
    monkeypatch.setattr(
        InstagramCarouselService, "inspect_publication", lambda self, url: inspected
    )
    contexts = []
    entered = asyncio.Event()

    def timeout(delay):
        context = asyncio.timeout(delay)
        contexts.append(context)
        return context

    monkeypatch.setattr(
        posts,
        "asyncio",
        SimpleNamespace(get_running_loop=asyncio.get_running_loop, timeout=timeout),
    )

    async def acknowledge(text):
        if text.startswith(("Одиночное", "Карусель распознана")):
            entered.set()
            await asyncio.Event().wait()

    message.answer.side_effect = acknowledge
    acquire, deliver = AsyncMock(), AsyncMock()
    monkeypatch.setattr(InstagramCarouselAcquisition, "acquire", acquire)
    monkeypatch.setattr(TelegramCarouselDelivery, "deliver", deliver)
    handler = owner()
    prepare = MagicMock()
    monkeypatch.setattr(handler, "_prepare", prepare)
    task = asyncio.create_task(handle_text(message, instagram_reels=handler))
    async with asyncio.timeout(3):
        await entered.wait()
    contexts[-1].reschedule(asyncio.get_running_loop().time())
    await task
    acquire.assert_not_awaited()
    deliver.assert_not_awaited()
    prepare.assert_not_called()
    message.answer_video.assert_not_awaited()
    assert not handler._active
