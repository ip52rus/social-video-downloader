"""E1b integration: real dispatcher/updates, fake Bot API and synthetic media only."""

import ast
import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import (
    AnswerCallbackQuery,
    EditMessageReplyMarkup,
    SendAudio,
    SendMessage,
    SendVideo,
)
from aiogram.types import Message, Update
from babel.messages.pofile import read_po

from social_video_downloader import handlers
from social_video_downloader.bot import create_dispatcher
from social_video_downloader.config import Settings
from social_video_downloader.domain.errors import (
    DownloadCleanupError,
    DownloaderError,
    DownloadFailedError,
    MediaProcessingError,
    MetadataBusyError,
    MetadataExtractionError,
    UnsupportedPlatformError,
)
from social_video_downloader.services.instagram_carousel import InstagramCarouselService
from social_video_downloader.telegram_i18n import get_i18n, resolve_locale, trn
from social_video_downloader.telegram_instagram import InstagramReelHandler
from social_video_downloader.telegram_instagram_posts import InstagramPostHandler
from social_video_downloader.telegram_interactions import InMemoryPendingInteractionStore
from social_video_downloader.telegram_tiktok import TelegramTikTokHandler
from tests.test_handlers import FakeDownloadService, blocked_plan, choose_mode_plan, direct_plan
from tests.test_i18n_packaging import compiler
from tests.test_telegram_carousel import collection
from tests.test_tiktok_integration import FixtureProvider

ROOT = Path(__file__).resolve().parents[1]
IG = "https://www.instagram.com/p/Synthetic_01/"
YT = "https://www.youtube.com/watch?v=abcdefghijk"
TT = "https://www.tiktok.com/@fixture/video/7123456789012345678"
LOCALES = ("en", "ru", "es")
REAL_DELIVERY = handlers._download_and_deliver_media


class Session(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls = []
        self.messages = []
        self.fail = None
        self.error_type = TelegramNetworkError

    async def close(self):
        pass

    async def stream_content(self, *args, **kwargs):
        yield b""

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if self.fail is type(method):
            self.fail = None
            raise self.error_type(method=method, message="Synthetic lost response")
        if isinstance(method, AnswerCallbackQuery):
            return True
        if isinstance(method, (SendMessage, EditMessageReplyMarkup, SendVideo, SendAudio)):
            payload = {
                "message_id": getattr(method, "message_id", None) or 1000 + len(self.messages),
                "date": 0,
                "chat": {"id": method.chat_id, "type": "private"},
                "from": {
                    "id": bot.id,
                    "is_bot": True,
                    "first_name": "Synthetic",
                    "language_code": "en",
                },
            }
            if isinstance(method, SendMessage):
                payload.update(text=method.text, reply_markup=method.reply_markup)
                assert len(method.text) <= 4096
            if isinstance(method, SendVideo):
                payload["video"] = dict(
                    file_id="fixture", file_unique_id="fixture", width=64, height=96, duration=1
                )
            if isinstance(method, SendAudio):
                payload["audio"] = dict(file_id="fixture", file_unique_id="fixture", duration=1)
            result = Message.model_validate(payload).as_(bot)
            self.messages.append(result)
            return result
        raise AssertionError("Unexpected Bot API request")


def message_update(text, code, user=7):
    sender = {"id": user, "is_bot": False, "first_name": "Synthetic"}
    if code is not None:
        sender["language_code"] = code
    return Update.model_validate(
        {
            "update_id": user,
            "message": {
                "message_id": 10,
                "date": 0,
                "chat": {"id": user, "type": "private"},
                "from": sender,
                "text": text,
            },
        }
    )


def callback_update(prompt, data, code="es", user=7, **changes):
    payload = prompt.model_dump(mode="json", exclude_none=True)
    payload.update(changes)
    return Update.model_validate(
        {
            "update_id": 90,
            "callback_query": {
                "id": "synthetic",
                "from": {
                    "id": user,
                    "is_bot": False,
                    "first_name": "Synthetic",
                    "language_code": code,
                },
                "chat_instance": "synthetic",
                "data": data,
                "message": payload,
            },
        }
    )


def translated(source, locale, **values):
    return get_i18n().gettext(source, locale=locale).format(**values)


@pytest_asyncio.fixture
async def app(monkeypatch):
    sessions = []
    monkeypatch.setattr(handlers, "pending_interaction_store", InMemoryPendingInteractionStore())
    monkeypatch.setattr(handlers, "download_service", FakeDownloadService(plan=choose_mode_plan()))
    downloads = []

    async def selected(*args):
        downloads.append((get_i18n().current_locale, args))

    monkeypatch.setattr(handlers, "_download_and_deliver_media", selected)

    def create(*, instagram=False, tiktok=False):
        session = Session()
        bot = Bot("123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi", session=session)
        owner = InstagramReelHandler()
        tt = TelegramTikTokHandler(provider=FixtureProvider())
        dispatcher = create_dispatcher(
            Settings(
                "synthetic", instagram_telegram_enabled=instagram, tiktok_telegram_enabled=tiktok
            ),
            instagram_reels=owner,
            tiktok_videos=tt,
        )
        sessions.append(session)
        return dispatcher, bot, session, owner, tt, downloads

    yield create
    for session in sessions:
        await session.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code", ["en", "ru", "es", "en-US", "ru-RU", "es-MX", "es-419", "pt-BR", None, "", "ru--RU"]
)
@pytest.mark.parametrize("enabled", [(False, False), (True, False), (False, True), (True, True)])
async def test_start_real_dispatcher_flags_and_sender_language(app, code, enabled):
    dp, bot, session, *_ = app(instagram=enabled[0], tiktok=enabled[1])
    await dp.feed_update(bot, message_update("/start", code))
    locale = resolve_locale(code)
    if enabled == (True, True):
        source = (
            "Send a YouTube link, a public Instagram Reel or /p/ link, or a "
            "public TikTok video link."
        )
    elif enabled == (False, True):
        source = "Send a YouTube link or a public TikTok video link."
    elif enabled == (True, False):
        source = (
            "Send a YouTube link or a public Instagram Reel or /p/ link. Only "
            "videos are downloaded from carousels, in their original order; "
            "with img_index, choose all videos or the specified video."
        )
    else:
        source = handlers._START_MESSAGE
    calls = [c for c in session.calls if isinstance(c, SendMessage)]
    assert calls[0].text == translated(source, locale)
    assert len(calls) == (2 if enabled == (True, True) else 1)
    assert get_i18n().current_locale == "en"


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize(
    "case",
    [
        "space",
        "invalid",
        "unsupported",
        "disabled",
        "busy",
        "metadata",
        "download",
        "processing",
        "platform",
        "domain",
        "unexpected",
        "blocked",
        "direct",
    ],
)
async def test_youtube_messages_are_rendered_by_dispatcher(app, monkeypatch, locale, case):
    dp, bot, session, _, _, downloads = app()
    text = YT
    errors = {
        "busy": MetadataBusyError(),
        "metadata": MetadataExtractionError(),
        "download": DownloadFailedError(),
        "processing": MediaProcessingError(),
        "platform": UnsupportedPlatformError(),
        "domain": DownloaderError(),
        "unexpected": RuntimeError(),
    }
    sources = {
        "space": (
            "Couldn't recognize the link. Send a full HTTP or HTTPS link to "
            "YouTube, Instagram or TikTok."
        ),
        "invalid": (
            "Couldn't recognize the link. Send a full HTTP or HTTPS link to "
            "YouTube, Instagram or TikTok."
        ),
        "unsupported": (
            "This platform isn't supported yet. Send a YouTube, Instagram or TikTok link."
        ),
        "disabled": (
            "Recognized a {platform_label} link, but downloads from this "
            "platform aren't enabled yet."
        ),
        "busy": "YouTube processing is busy or temporarily unavailable. Try again later.",
        "metadata": (
            "Couldn't get video information. The video may be deleted, private or unavailable."
        ),
        "download": "Couldn't download the video. Try again later.",
        "processing": (
            "The video download is incomplete or couldn't be processed. Try another link."
        ),
        "platform": "Downloads from this platform aren't enabled yet.",
        "domain": "Couldn't process this link. Check it and try again.",
        "unexpected": "Something went wrong. Try again later.",
        "blocked": handlers._BLOCKED_CHOICE_MESSAGE,
        "direct": "YouTube link recognized. Starting download…",
    }
    if case == "space":
        text = YT + " more"
    if case == "invalid":
        text = "https://"
    if case == "unsupported":
        text = "https://example.invalid/video"
    if case == "disabled":
        text = IG
    service = FakeDownloadService(
        plan=blocked_plan() if case == "blocked" else direct_plan(), plan_error=errors.get(case)
    )
    monkeypatch.setattr(handlers, "download_service", service)
    await dp.feed_update(bot, message_update(text, locale))
    assert session.calls[0].text == translated(sources[case], locale, platform_label="Instagram")
    assert len(session.calls) == 1
    assert len(downloads) == (1 if case == "direct" else 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("original,current", [("ru", "es"), ("en", "ru"), ("es", "en")])
async def test_youtube_mode_quality_delivery_pins_locale_and_one_shot(app, original, current):
    dp, bot, session, _, _, downloads = app()
    await dp.feed_update(bot, message_update(YT, original))
    prompt = session.messages[-1]
    assert prompt.text == translated("Choose a format:", original)
    assert [r[0].text for r in prompt.reply_markup.inline_keyboard] == [
        translated("🎬 Video", original),
        translated("🎵 Audio", original),
    ]
    mode = prompt.reply_markup.inline_keyboard[0][0].callback_data
    await dp.feed_update(bot, callback_update(prompt, mode, current))
    edit = next(c for c in session.calls if isinstance(c, EditMessageReplyMarkup))
    assert [r[0].text for r in edit.reply_markup.inline_keyboard] == [
        translated("Low", original),
        translated("High", original),
    ]
    quality = edit.reply_markup.inline_keyboard[1][0].callback_data
    await dp.feed_update(bot, callback_update(prompt, quality, current))
    assert downloads[0][0] == original
    assert downloads[0][1][2].quality_id == "mode-video-high"
    assert [c.text for c in session.calls if isinstance(c, AnswerCallbackQuery)][-1] == translated(
        "Starting download…", original
    )
    await dp.feed_update(bot, callback_update(prompt, quality, current))
    assert len(downloads) == 1
    assert session.calls[-1].text == translated(handlers._STALE_CALLBACK_MESSAGE, current)
    assert get_i18n().current_locale == "en"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case", ["foreign", "chat", "message", "unknown", "malformed", "expired", "restart", "index"]
)
async def test_invalid_youtube_callback_uses_current_sender(app, monkeypatch, case):
    dp, bot, session, _, _, downloads = app()
    await dp.feed_update(bot, message_update(YT, "ru"))
    prompt = session.messages[-1]
    data = prompt.reply_markup.inline_keyboard[0][0].callback_data
    changes = {}
    user = 7
    if case == "foreign":
        user = 8
    if case == "chat":
        changes["chat"] = {"id": 8, "type": "private"}
    if case == "message":
        changes["message_id"] = 888
    if case == "unknown":
        data = "dl:v1:unknown:m:0"
    if case == "malformed":
        data = "malformed"
    if case == "index":
        data = data.rsplit(":", 1)[0] + ":99"
    if case == "restart":
        monkeypatch.setattr(
            handlers, "pending_interaction_store", InMemoryPendingInteractionStore()
        )
    if case == "expired":
        store = handlers.pending_interaction_store
        store._clock = lambda: datetime.now(UTC) + timedelta(hours=1)
    await dp.feed_update(bot, callback_update(prompt, data, "es", user, **changes))
    source = (
        handlers._INVALID_CALLBACK_MESSAGE
        if case in {"malformed", "index"}
        else handlers._STALE_CALLBACK_MESSAGE
    )
    assert session.calls[-1].text == translated(source, "es")
    assert not downloads


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("position", [1, 2, 3, 4])
async def test_instagram_item_labels_and_source_positions(
    app, monkeypatch, tmp_path, locale, position
):
    _, plan = collection(tmp_path, 2, photos=(2,))
    monkeypatch.setattr(InstagramCarouselService, "inspect_item_reference", lambda *a: plan)
    dp, bot, session, owner, _, _ = app(instagram=True)
    await dp.feed_update(bot, message_update(IG + "?img_index=" + str(position), locale))
    call = session.calls[-1]
    if position == 4:
        assert call.text == translated(
            "There is no such item in this post. Check the number in the link.", locale
        )
        assert call.reply_markup is None
        return
    if position == 2:
        source = (
            "Item #{position} is a photo. Photo downloads aren't supported yet."
            " You can download all videos from this post."
        )
    else:
        source = (
            "You selected video #{position} in the Instagram carousel. What "
            "would you like to download?"
        )
    assert call.text == translated(source, locale, position=position)
    buttons = call.reply_markup.inline_keyboard
    assert len(buttons) == (1 if position == 2 else 2)
    assert buttons[0][0].text == translated("All videos in the carousel", locale)
    if position != 2:
        assert buttons[1][0].text == translated("Only video #{position}", locale, position=position)
    assert not owner._active


@pytest.mark.asyncio
@pytest.mark.parametrize("original,current", [("ru", "es"), ("en", "ru"), ("es", "en")])
@pytest.mark.parametrize(
    "case",
    [
        "valid",
        "foreign",
        "chat",
        "message",
        "expired",
        "restart",
        "malformed",
        "busy",
        "ack",
        "edit",
    ],
)
async def test_instagram_atomic_locale_ownership_and_admission(
    app, monkeypatch, tmp_path, original, current, case
):
    _, plan = collection(tmp_path, 2, photos=(2,))
    monkeypatch.setattr(InstagramCarouselService, "inspect_item_reference", lambda *a: plan)
    dp, bot, session, owner, _, _ = app(instagram=True)
    sent = []

    async def deliver(self, message, selected, *args):
        sent.append((get_i18n().current_locale, selected))

    monkeypatch.setattr(InstagramPostHandler, "_send_carousel", deliver)
    await dp.feed_update(bot, message_update(IG + "?img_index=3", original))
    prompt = session.messages[-1]
    data = prompt.reply_markup.inline_keyboard[1][0].callback_data
    changes = {}
    user = 7
    if case == "foreign":
        user = 8
    if case == "chat":
        changes["chat"] = {"id": 8, "type": "private"}
    if case == "message":
        changes["message_id"] = 888
    if case == "expired":
        owner._post_handler._choices._clock = lambda: datetime.now(UTC) + timedelta(hours=1)
    if case == "restart":
        owner._post_handler = InstagramPostHandler(owner)
    if case == "malformed":
        data = "ig:invalid"
    if case == "busy":
        owner._active = True
    if case == "ack":
        session.fail = AnswerCallbackQuery
    if case == "edit":
        session.fail = EditMessageReplyMarkup
    await dp.feed_update(bot, callback_update(prompt, data, current, user, **changes))
    if case in {"valid", "edit"}:
        assert len(sent) == 1 and sent[0][0] == original
        assert sent[0][1].requested_position == 3
        assert [v.position for v in sent[0][1].selected_videos] == [3]
        await dp.feed_update(bot, callback_update(prompt, data, current))
        assert len(sent) == 1
        assert session.calls[-1].text == translated(
            "This choice has expired or belongs to another user.", current
        )
    elif case == "busy":
        assert session.calls[-1].text == translated("The bot is busy. Try again later.", original)
        assert not sent
    elif case == "ack":
        assert not sent and not owner._active
        # Failed acknowledgement leaves the same choice usable, with its original locale.
        await dp.feed_update(bot, callback_update(prompt, data, current))
        assert len(sent) == 1 and sent[0][0] == original
    else:
        source = (
            "This choice has expired. Send the link again."
            if case == "malformed"
            else "This choice has expired or belongs to another user."
        )
        assert session.calls[-1].text == translated(source, current)
        assert not sent


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("case", ["busy", "invalid", "prepare", "uncertain", "cleanup", "success"])
async def test_tiktok_localized_status_caption_and_no_retry(app, monkeypatch, locale, case):
    dp, bot, session, _, tt, _ = app(tiktok=True)
    source = None
    text = TT
    if case == "busy":
        tt._active_users.add(7)
        source = "The bot is busy. Try again later."
    elif case == "invalid":
        text = "https://www.tiktok.com/unsupported"
        source = "Send a full or short link to a public TikTok video."
    elif case in {"prepare", "cleanup"}:
        error = DownloadFailedError() if case == "prepare" else DownloadCleanupError()

        def fail(*a):
            raise error

        monkeypatch.setattr(tt, "_prepare", fail)
        source = (
            "Couldn't download or prepare the TikTok video. Try another link."
            if case == "prepare"
            else "Couldn't safely finish the operation. TikTok downloads are paused."
        )
    elif case == "uncertain":
        session.fail = SendVideo
        source = "Couldn't confirm video delivery. There will be no automatic retry."
    await dp.feed_update(bot, message_update(text, locale))
    calls = [c for c in session.calls if isinstance(c, SendVideo)]
    assert len(calls) == (1 if case in {"success", "uncertain"} else 0)
    if calls:
        assert calls[0].caption == translated("TikTok video", locale)
    if source:
        assert session.calls[-1].text == translated(source, locale)
    else:
        assert session.calls[0].text == translated(
            "TikTok link recognized. Starting download…", locale
        )


@pytest.mark.asyncio
async def test_parallel_dispatcher_messages_callbacks_and_nested_restore(app, monkeypatch):
    dp, bot, session, *_ = app()
    entered = 0
    ready = asyncio.Event()
    release = asyncio.Event()

    async def plan(url):
        nonlocal entered
        entered += 1
        if entered == 3:
            ready.set()
        await release.wait()
        return choose_mode_plan()

    monkeypatch.setattr(handlers.download_service, "create_choice_plan_async", plan)
    tasks = [
        asyncio.create_task(dp.feed_update(bot, message_update(YT, code, user=i + 1)))
        for i, code in enumerate(LOCALES)
    ]
    try:
        await asyncio.wait_for(ready.wait(), 3)
        release.set()
        await asyncio.gather(*tasks)
    finally:
        release.set()
        await asyncio.gather(*tasks, return_exceptions=True)
    prompts = sorted(session.messages, key=lambda m: m.chat.id)
    for code, prompt in zip(LOCALES, prompts, strict=True):
        assert prompt.text == translated("Choose a format:", code)
    with get_i18n().use_locale("ru"):
        await asyncio.gather(
            *[
                dp.feed_update(
                    bot,
                    callback_update(
                        p, p.reply_markup.inline_keyboard[0][0].callback_data, "es", i + 1
                    ),
                )
                for i, p in enumerate(prompts)
            ]
        )
        assert get_i18n().current_locale == "ru"
    edits = sorted(
        (c for c in session.calls if isinstance(c, EditMessageReplyMarkup)), key=lambda c: c.chat_id
    )
    assert [c.reply_markup.inline_keyboard[0][0].text for c in edits] == [
        translated("Low", c) for c in LOCALES
    ]
    assert get_i18n().current_locale == "en"


@pytest.mark.asyncio
@pytest.mark.parametrize("repeat", [False, True])
async def test_dispatcher_cancellation_restores_locale(app, monkeypatch, repeat):
    dp, bot, session, *_ = app()
    entered = asyncio.Event()
    unwinding = asyncio.Event()
    release = asyncio.Event()

    async def plan(url):
        assert get_i18n().current_locale == "ru"
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            unwinding.set()
            await release.wait()

    monkeypatch.setattr(handlers.download_service, "create_choice_plan_async", plan)
    task = asyncio.create_task(dp.feed_update(bot, message_update(YT, "ru")))
    try:
        await entered.wait()
        task.cancel()
        await unwinding.wait()
        if repeat:
            task.cancel()
    finally:
        release.set()
        result = await asyncio.gather(task, return_exceptions=True)
    assert isinstance(result[0], asyncio.CancelledError)
    assert get_i18n().current_locale == "en" and not session.calls


@pytest.mark.parametrize("locale", LOCALES)
def test_complete_catalog_and_public_literal_inventory(locale):
    path = ROOT / "src/social_video_downloader/locales" / locale / "LC_MESSAGES/messages.po"
    with path.open("rb") as stream:
        catalog = read_po(stream, locale=locale)
    assert not catalog.fuzzy and not list(catalog.check())
    messages = [m for m in catalog if m.id]
    assert len(messages) == 70
    for message in messages:
        assert not message.fuzzy
        variants = message.string if isinstance(message.string, tuple) else (message.string,)
        assert all(variants)
        if "{" in str(message.id):
            assert "python-brace-format" in message.flags
        for text in variants:
            assert len(text) < 4096
    for name in ("handlers", "telegram_instagram", "telegram_instagram_posts", "telegram_tiktok"):
        tree = ast.parse((ROOT / "src/social_video_downloader" / (name + ".py")).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not any("\u0400" <= c <= "\u04ff" for c in node.value)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"tr", "trn"}
                and isinstance(node.args[0], ast.Constant)
            ):
                assert catalog.get(node.args[0].value) is not None


@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("count", [0, 1, 2, 5, 11, 21])
def test_real_user_plural_messages(locale, count):
    with get_i18n().use_locale(locale):
        text = trn(
            (
                "Delivery confirmed: {count} video out of {total}. The rest were "
                "not sent; there will be no automatic retry."
            ),
            (
                "Delivery confirmed: {count} videos out of {total}. The rest were "
                "not sent; there will be no automatic retry."
            ),
            count,
            total=25,
        )
        assert str(count) in text and "25" in text and "{" not in text
        if locale == "en":
            assert (" videos " in text) == (count != 1)
        if locale == "es":
            assert (" vídeos " in text) == (count != 1)


@pytest.mark.parametrize("case", ["unmarked", "empty"])
def test_compiler_rejects_unmarked_placeholders_and_empty_translation(tmp_path, case):
    module = compiler()
    source = module.CATALOG_ROOT / "en/LC_MESSAGES/messages.po"
    text = source.read_text()
    if case == "unmarked":
        text = text.replace("#, python-brace-format\n", "", 1)
    else:
        text = text.replace('msgstr "Low"', 'msgstr ""')
    path = tmp_path / "messages.po"
    path.write_text(text)
    with pytest.raises(ValueError):
        module.compile_catalog(path, "en")


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("case", ["invalid", "busy", "prepare", "timeout", "uncertain", "success"])
async def test_reel_actual_status_and_upload_count(app, monkeypatch, locale, case):
    dp, bot, session, owner, _, _ = app(instagram=True)
    text = "https://www.instagram.com/reel/Synthetic_01/"
    source = None

    def prepare(url, workspace, guard):
        if case in {"prepare", "timeout"}:
            raise (DownloadFailedError() if case == "prepare" else TimeoutError())
        path = workspace / "fixture.mp4"
        path.write_bytes(b"synthetic media")
        return path, {"width": 64, "height": 96, "duration": 1}

    monkeypatch.setattr(owner, "_prepare", prepare)
    if case == "invalid":
        text = "https://www.instagram.com/stories/fixture/1/"
        source = (
            "Public Reels and /p/ posts are supported. For /p/, use "
            "img_index to select an item; other selectors aren't "
            "supported."
        )
    elif case == "busy":
        owner._active = True
        source = (
            "A Reel is already being processed. Wait for it to finish before sending another link."
        )
    elif case in {"prepare", "timeout"}:
        source = "Couldn't download or prepare the Reel within the limits."
    elif case == "uncertain":
        session.fail = SendVideo
        source = "Couldn't confirm video delivery. There will be no automatic retry."
    await dp.feed_update(bot, message_update(text, locale))
    assert len([c for c in session.calls if isinstance(c, SendVideo)]) == (
        1 if case in {"uncertain", "success"} else 0
    )
    if source:
        assert session.calls[-1].text == translated(source, locale)
    else:
        assert session.calls[0].text == translated(
            "Reel link recognized. Starting download…", locale
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize(
    "case",
    [
        "no-videos",
        "ambiguous",
        "unknown",
        "busy",
        "limit",
        "partial",
        "uncertain",
        "delivery",
        "cleanup",
        "prepare",
        "success",
        "single",
    ],
)
async def test_post_actual_errors_partial_counts_and_automatic_flow(
    app, monkeypatch, tmp_path, locale, case
):
    from social_video_downloader.domain.carousel import CarouselIssue, CarouselPlanState
    from social_video_downloader.domain.models import MediaMetadata, Platform
    from social_video_downloader.infrastructure.telegram_carousel import (
        CarouselDeliveryError,
        CarouselDeliveryProgress,
    )

    _, plan = collection(tmp_path, 11 if case == "limit" else 2)
    issue = {
        "no-videos": CarouselIssue.NO_VIDEOS,
        "ambiguous": CarouselIssue.AMBIGUOUS_REFERENCE,
        "unknown": CarouselIssue.UNKNOWN_ITEM,
    }.get(case)
    if issue:
        plan = replace(plan, state=CarouselPlanState.BLOCKED, issue=issue)
    if case == "single":
        plan = MediaMetadata("Synthetic", IG, Platform.INSTAGRAM)
    monkeypatch.setattr(InstagramCarouselService, "inspect_publication", lambda *a: plan)
    dp, bot, session, owner, _, _ = app(instagram=True)
    sends = []

    async def send(self, message, selected, guard, operation):
        sends.append(selected)
        if case == "partial":
            raise CarouselDeliveryError("upload", CarouselDeliveryProgress(2, (1,)))
        if case == "uncertain":
            raise CarouselDeliveryError("upload", CarouselDeliveryProgress(2, (1,), (2,)))
        if case == "delivery":
            raise CarouselDeliveryError("prepare", CarouselDeliveryProgress(2))
        if case == "cleanup":
            raise DownloadCleanupError()
        if case == "prepare":
            raise DownloadFailedError()

    monkeypatch.setattr(InstagramPostHandler, "_send_carousel", send)

    def prepare(url, workspace, guard, **kwargs):
        path = workspace / "fixture.mp4"
        path.write_bytes(b"synthetic media")
        return path, {"width": 64, "height": 96, "duration": 1}

    monkeypatch.setattr(owner, "_prepare", prepare)
    if case == "busy":
        owner._active = True
    await dp.feed_update(bot, message_update(IG, locale))
    sources = {
        "no-videos": "No videos are available in this post. Photos aren't downloaded.",
        "ambiguous": (
            "Use a link to the whole post without individual item selectors or unknown parameters."
        ),
        "unknown": (
            "Can't safely download the entire carousel: one or more "
            "items are unavailable or unrecognized."
        ),
        "busy": "An Instagram link is already being processed. Send the next one later.",
        "uncertain": (
            "Couldn't confirm delivery of the entire carousel. Some "
            "videos may have been delivered; there will be no "
            "automatic retry."
        ),
        "delivery": "Couldn't prepare or send the carousel. There will be no automatic retry.",
        "cleanup": "Instagram is temporarily unavailable. Try again later.",
        "prepare": (
            "Couldn't download or prepare the post within the "
            "limits. Incomplete carousels are not sent."
        ),
        "success": "Carousel recognized. Preparing videos to send…",
    }
    if case in sources:
        assert session.calls[-1].text == translated(sources[case], locale)
    elif case == "partial":
        with get_i18n().use_locale(locale):
            expected = trn(
                (
                    "Delivery confirmed: {count} video out of {total}. The "
                    "rest were not sent; there will be no automatic retry."
                ),
                (
                    "Delivery confirmed: {count} videos out of {total}. The "
                    "rest were not sent; there will be no automatic retry."
                ),
                1,
                total=2,
            )
        assert session.calls[-1].text == expected
    elif case == "limit":
        with get_i18n().use_locale(locale):
            expected = trn(
                "This post has {count} video. The limit is {limit}; no videos will be skipped.",
                "This post has {count} videos. The limit is {limit}; no videos will be skipped.",
                11,
                limit=10,
            )
        assert session.calls[-1].text == expected
    else:
        assert session.calls[0].text == translated(
            "Single Instagram video recognized. Starting download…", locale
        )
        assert len([c for c in session.calls if isinstance(c, SendVideo)]) == 1
    assert len(sends) == (
        1 if case in {"partial", "uncertain", "delivery", "cleanup", "prepare", "success"} else 0
    )
    assert owner._blocked == (case == "cleanup")


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("case", ["cleanup", "delivery", "prepare", "timeout"])
async def test_instagram_callback_error_is_pinned(app, monkeypatch, tmp_path, locale, case):
    from social_video_downloader.infrastructure.telegram_carousel import (
        CarouselDeliveryError,
        CarouselDeliveryProgress,
    )

    _, plan = collection(tmp_path, 2)
    monkeypatch.setattr(InstagramCarouselService, "inspect_item_reference", lambda *a: plan)
    dp, bot, session, owner, _, _ = app(instagram=True)
    errors = {
        "cleanup": DownloadCleanupError(),
        "delivery": CarouselDeliveryError("upload", CarouselDeliveryProgress(2, (), (1,))),
        "prepare": DownloadFailedError(),
        "timeout": TimeoutError(),
    }
    sends = []

    async def fail(self, *args):
        sends.append(get_i18n().current_locale)
        raise errors[case]

    monkeypatch.setattr(InstagramPostHandler, "_send_carousel", fail)
    await dp.feed_update(bot, message_update(IG + "?img_index=2", locale))
    prompt = session.messages[-1]
    other = "es" if locale != "es" else "ru"
    data = prompt.reply_markup.inline_keyboard[1][0].callback_data
    await dp.feed_update(bot, callback_update(prompt, data, other))
    source = (
        "Instagram is temporarily unavailable. Try again later."
        if case == "cleanup"
        else "Couldn't confirm video delivery. There will be no automatic retry."
        if case == "delivery"
        else "Couldn't download or prepare the video. There will be no automatic retry."
    )
    assert session.calls[-1].text == translated(source, locale)
    assert sends == [locale]
    assert owner._blocked == (case == "cleanup")


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("failure", [AnswerCallbackQuery, EditMessageReplyMarkup])
async def test_youtube_lost_notification_keeps_pinned_quality_and_one_delivery(
    app, locale, failure
):
    dp, bot, session, _, _, downloads = app()
    await dp.feed_update(bot, message_update(YT, locale))
    prompt = session.messages[-1]
    mode = prompt.reply_markup.inline_keyboard[0][0].callback_data
    session.fail = failure
    await dp.feed_update(bot, callback_update(prompt, mode, "es"))
    edit = next(c for c in session.calls if isinstance(c, EditMessageReplyMarkup))
    assert edit.reply_markup.inline_keyboard[0][0].text == translated("Low", locale)
    quality = edit.reply_markup.inline_keyboard[0][0].callback_data
    await dp.feed_update(bot, callback_update(prompt, quality, "es"))
    assert len(downloads) == 1 and downloads[0][0] == locale


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("case", ["blocked", "account", "unexpected"])
async def test_tiktok_remaining_public_failures(app, monkeypatch, locale, case):
    dp, bot, session, _, tt, _ = app(tiktok=True)
    if case == "blocked":
        tt._blocked = True
    if case == "unexpected":

        def fail(*a):
            raise RuntimeError("private diagnostic")

        monkeypatch.setattr(tt, "_prepare", fail)
    await dp.feed_update(bot, message_update(TT, locale, user=0 if case == "account" else 7))
    source = {
        "blocked": "TikTok downloads are paused after an operation cleanup error.",
        "account": "TikTok downloads aren't available for this account right now.",
        "unexpected": "Couldn't process the TikTok video.",
    }[case]
    assert session.calls[-1].text == translated(source, locale)
    assert not any(isinstance(c, SendVideo) for c in session.calls)
    assert "private diagnostic" not in session.calls[-1].text


@pytest.mark.asyncio
async def test_dispatcher_exception_restores_context_without_translating_private_error(
    app, monkeypatch
):
    dp, bot, session, *_ = app()

    async def fail(*a):
        assert get_i18n().current_locale == "es"
        raise RuntimeError("private diagnostic")

    monkeypatch.setattr(handlers.download_service, "create_choice_plan_async", fail)
    with get_i18n().use_locale("ru"):
        await dp.feed_update(bot, message_update(YT, "es"))
        assert get_i18n().current_locale == "ru"
    assert session.calls[-1].text == translated("Something went wrong. Try again later.", "es")
    assert get_i18n().current_locale == "en"


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize(
    "case", ["download", "prepare", "unexpected", "uncertain", "oversize", "success", "audio"]
)
async def test_actual_youtube_delivery_messages_counts_and_source_caption(
    app, monkeypatch, locale, case
):
    from aiogram.exceptions import TelegramEntityTooLarge

    from social_video_downloader.domain.models import DownloadMode, DownloadOptions
    from social_video_downloader.infrastructure.telegram_audio import PreparedAudio

    dp, bot, session, *_ = app()
    options = DownloadOptions(
        mode=DownloadMode.AUDIO_ONLY if case == "audio" else DownloadMode.VIDEO_WITH_AUDIO,
        quality_id="direct-quality",
    )
    service = FakeDownloadService(
        plan=direct_plan(options),
        error=DownloadFailedError()
        if case == "download"
        else RuntimeError()
        if case == "unexpected"
        else None,
    )
    original = service.download

    def download(*args):
        media = original(*args)
        return replace(media, metadata=replace(media.metadata, title="Synthetic {title}"))

    monkeypatch.setattr(service, "download", download)
    monkeypatch.setattr(handlers, "download_service", service)
    monkeypatch.setattr(handlers, "_download_and_deliver_media", REAL_DELIVERY)

    def prepare(path):
        if case == "prepare":
            raise MediaProcessingError()
        return path

    monkeypatch.setattr(handlers, "prepare_telegram_video", prepare)
    monkeypatch.setattr(
        handlers, "prepare_telegram_audio", lambda path, duration: PreparedAudio(path, None)
    )
    monkeypatch.setattr(
        handlers,
        "inspect_telegram_video",
        lambda path: {"streams": [{"codec_type": "video", "width": 64, "height": 96}]},
    )
    if case in {"uncertain", "oversize"}:
        session.fail = SendVideo
        if case == "oversize":
            session.error_type = TelegramEntityTooLarge
    await dp.feed_update(bot, message_update(YT, locale))
    sources = {
        "download": "Couldn't download the video. Try again later.",
        "prepare": "The video download is incomplete or couldn't be processed. Try another link.",
        "unexpected": "Something went wrong. Try again later.",
        "uncertain": "Couldn't send the file to Telegram. Try again later.",
        "oversize": "The file is too large to send through Telegram. Try a smaller video.",
    }
    if case in sources:
        assert session.calls[-1].text == translated(sources[case], locale)
    uploads = [c for c in session.calls if isinstance(c, (SendVideo, SendAudio))]
    assert len(uploads) == (1 if case in {"uncertain", "oversize", "success", "audio"} else 0)
    if uploads:
        assert uploads[0].caption == "Synthetic {title}"
    assert len(service.calls) == 1
    assert len(session.calls) == (3 if case in {"uncertain", "oversize"} else 2)


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LOCALES)
async def test_tiktok_cleanup_notification_and_quarantine_preserve_send_count(
    app, monkeypatch, locale
):
    from tempfile import TemporaryDirectory

    from social_video_downloader import telegram_tiktok

    class FailedCleanup(TemporaryDirectory):
        def cleanup(self):
            super().cleanup()
            raise OSError("Synthetic cleanup failure")

    dp, bot, session, _, tt, _ = app(tiktok=True)
    monkeypatch.setattr(telegram_tiktok, "TemporaryDirectory", FailedCleanup)
    await dp.feed_update(bot, message_update(TT, locale))
    assert session.calls[-1].text == translated(
        "Operation cleanup failed. TikTok downloads are paused.", locale
    )
    assert tt._blocked and 7 in tt._active_users
    assert len([c for c in session.calls if isinstance(c, SendVideo)]) == 1
