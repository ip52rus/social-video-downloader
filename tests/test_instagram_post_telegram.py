"""Network-forbidden checks for opt-in Telegram /p/ routing."""

import socket
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from social_video_downloader.domain.carousel import (
    CarouselIssue,
    CarouselPlanState,
    CarouselScope,
    CarouselSelectionPlan,
    DownloadedCarousel,
    DownloadedCarouselVideo,
)
from social_video_downloader.domain.models import DownloadedMedia
from social_video_downloader.handlers import handle_text
from social_video_downloader.infrastructure.telegram_carousel import (
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
        assert self.limits == _ACQUISITION_LIMITS
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
    monkeypatch.setattr(InstagramCarouselService, "create_selection_plan", inspect)
    monkeypatch.setattr(InstagramCarouselAcquisition, "acquire", acquire)
    monkeypatch.setattr(TelegramCarouselDelivery, "deliver", deliver)
    await handle_text(message, instagram_reels=handler)
    assert inspected[0] == URL
    assert not inspected[1].exists()
    assert message.answer_video.await_count == 0
    assert not handler._active


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ["?img_index=2", "?unknown=ignored", "#slide/2"])
async def test_unsafe_post_reference_never_extracts_or_sends(message, suffix):
    handler = owner()
    message.text += suffix
    await handle_text(message, instagram_reels=handler)
    assert message.answer_video.await_count == 0
    assert "ссылка на публикацию целиком" in message.answer.call_args.args[0]
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
    monkeypatch.setattr(
        InstagramCarouselService, "create_selection_plan", lambda self, url: blocked
    )
    handler = owner()
    await handle_text(message, instagram_reels=handler)
    assert "Невозможно безопасно" in message.answer.call_args.args[0]
    message.answer_video.assert_not_awaited()
    assert not handler._active


@pytest.mark.asyncio
async def test_single_video_post_uses_existing_single_file_worker(message, monkeypatch):
    blocked = CarouselSelectionPlan(
        URL,
        None,
        (),
        (),
        CarouselScope.PUBLICATION,
        CarouselPlanState.BLOCKED,
        CarouselIssue.UNSUPPORTED_CONTENT,
    )
    monkeypatch.setattr(
        InstagramCarouselService, "create_selection_plan", lambda self, url: blocked
    )
    handler = owner()
    created = []

    def prepare(url, workspace, guard):
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

    monkeypatch.setattr(InstagramCarouselService, "create_selection_plan", lambda self, url: plan)

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
