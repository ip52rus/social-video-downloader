"""E5 targeted UI gaps: available-platform guidance and restart/repeat journeys.

Real dispatchers, in-memory stores and callback handlers; fake Telegram transport
and delivery boundaries. This simulates state loss, not an OS/device LIVE restart.
"""

import asyncio

import pytest
from aiogram.methods import AnswerCallbackQuery, SendMessage

from social_video_downloader import handlers
from social_video_downloader.domain.models import DownloadMode
from social_video_downloader.download_protection import DownloadAdmission
from social_video_downloader.services.instagram_carousel import InstagramCarouselService
from social_video_downloader.telegram_i18n import get_i18n, resolve_locale
from social_video_downloader.telegram_instagram_posts import InstagramPostHandler
from social_video_downloader.telegram_interactions import InMemoryPendingInteractionStore
from tests.test_telegram_carousel import collection
from tests.test_telegram_localization import (
    IG,
    LOCALES,
    YT,
    callback_update,
    message_update,
    translated,
)
from tests.test_telegram_localization import app as app

UNAVAILABLE = "This choice is no longer available. Send the link again."
EXPIRED = "This choice has expired. Send the link again."
ERRORS = [
    ("https://", "Couldn't recognize the link. Send a video link from {platforms}."),
    (YT + " extra", "Couldn't recognize the link. Send a video link from {platforms}."),
    (
        "https://example.invalid/video",
        "This platform isn't supported here. Send a video link from {platforms}.",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [*LOCALES, "pt-BR", None])
@pytest.mark.parametrize("enabled", [(False, False), (True, False), (False, True), (True, True)])
@pytest.mark.parametrize("text,source", ERRORS)
async def test_error_guidance_lists_only_available_platforms(app, code, enabled, text, source):
    dp, bot, session, _, _, downloads = app(instagram=enabled[0], tiktok=enabled[1])
    service = handlers.download_service
    await dp.feed_update(bot, message_update(text, code))
    assert len(session.calls) == 1 and isinstance(session.calls[0], SendMessage)
    reply = session.calls[0].text
    locale = resolve_locale(code)
    label = {
        (False, False): "YouTube",
        (True, False): "YouTube and Instagram",
        (False, True): "YouTube and TikTok",
        (True, True): "YouTube, Instagram and TikTok",
    }[enabled]
    platforms = translated(label, locale)
    assert reply == translated(source, locale, platforms=platforms)
    assert ("Instagram" in reply) is enabled[0]
    assert ("TikTok" in reply) is enabled[1]
    assert "YouTube" in reply
    assert not service.plan_calls and not service.calls and not downloads
    assert get_i18n().current_locale == "en"


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("text,source", ERRORS)
async def test_error_guidance_respects_existing_tiktok_user_policy(
    app, monkeypatch, locale, text, source
):
    dp, bot, session, _, tiktok, downloads = app(instagram=True, tiktok=True)
    monkeypatch.setattr(tiktok, "allows", lambda message: False)
    await dp.feed_update(bot, message_update(text, locale))
    assert len(session.calls) == 1
    assert session.calls[0].text == translated(
        source, locale, platforms=translated("YouTube and Instagram", locale)
    )
    assert "TikTok" not in session.calls[0].text and not downloads


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["youtube", "instagram"])
@pytest.mark.parametrize("current", [*LOCALES, "pt-BR", None])
async def test_restart_refusal_then_fresh_and_repeated_request(
    app, monkeypatch, tmp_path, platform, current
):
    instagram = platform == "instagram"
    delivered = []
    if instagram:
        _, plan = collection(tmp_path, 2, photos=(2,))
        monkeypatch.setattr(InstagramCarouselService, "inspect_item_reference", lambda *a: plan)

        async def send(self, message, selected, *args):
            delivered.append((get_i18n().current_locale, selected))

        monkeypatch.setattr(InstagramPostHandler, "_send_carousel", send)
    url = IG + "?img_index=3" if instagram else YT
    before_dp, before_bot, before_session, *_ = app(instagram=instagram)
    await before_dp.feed_update(before_bot, message_update(url, "ru"))
    old_card = before_session.messages[-1]
    old_data = old_card.reply_markup.inline_keyboard[1][0].callback_data
    old_view = old_card.model_dump(mode="json")

    # Restart boundary: new dispatcher, handler instances and empty YouTube store.
    monkeypatch.setattr(handlers, "pending_interaction_store", InMemoryPendingInteractionStore())
    clock = [0.0]
    dp, bot, session, _, _, downloads = app(
        instagram=instagram, download_admission=DownloadAdmission(clock=lambda: clock[0])
    )
    locale = resolve_locale(current)
    await asyncio.gather(
        dp.feed_update(bot, callback_update(old_card, old_data, current)),
        dp.feed_update(bot, callback_update(old_card, old_data, current)),
    )
    assert len(session.calls) == 2
    assert all(isinstance(call, AnswerCallbackQuery) for call in session.calls)
    assert all(
        call.text == translated(EXPIRED if instagram else UNAVAILABLE, locale)
        for call in session.calls
    )
    assert not delivered and not downloads
    assert old_card.model_dump(mode="json") == old_view  # No unsafe visual cleanup.

    for expected_count in (1, 2):
        clock[0] += 3  # A new request after the Phase 9C link cooldown, without sleep.
        await dp.feed_update(bot, message_update(url, current))
        card = session.messages[-1]
        data = card.reply_markup.inline_keyboard[1][0].callback_data
        switched = "en" if locale == "es" else "es"
        await asyncio.gather(
            dp.feed_update(bot, callback_update(card, data, switched)),
            dp.feed_update(bot, callback_update(card, data, switched)),
        )
        if instagram:
            assert len(delivered) == expected_count and not downloads
            assert all(lang == locale for lang, _ in delivered)
            assert all(item.requested_position == 3 for _, item in delivered)
            assert all([v.position for v in item.selected_videos] == [3] for _, item in delivered)
        else:
            assert len(downloads) == expected_count and not delivered
            assert all(lang == locale for lang, _ in downloads)
            assert all(args[2].mode is DownloadMode.AUDIO_ONLY for _, args in downloads)
        calls_before = len(session.calls)
        await dp.feed_update(bot, callback_update(old_card, old_data, current))
        assert len(session.calls) == calls_before + 1
        assert isinstance(session.calls[-1], AnswerCallbackQuery)
        assert session.calls[-1].text == translated(UNAVAILABLE, locale)
    assert get_i18n().current_locale == "en"
