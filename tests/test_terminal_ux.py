"""E4 acceptance: actual Telegram handlers, synthetic media and offline Bot API."""

import asyncio
from datetime import UTC, datetime, timedelta
from tempfile import TemporaryDirectory
from threading import Event

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError, TelegramServerError
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendAudio, SendMessage, SendVideo
from aiogram.types import Update

from social_video_downloader import handlers
from social_video_downloader.domain.errors import DownloadFailedError
from social_video_downloader.domain.models import DownloadMode, DownloadOptions
from social_video_downloader.infrastructure.telegram_audio import PreparedAudio
from social_video_downloader.services.instagram_carousel import InstagramCarouselService
from social_video_downloader.telegram_i18n import get_i18n
from social_video_downloader.telegram_instagram_posts import InstagramPostHandler
from social_video_downloader.telegram_interactions import (
    InMemoryPendingInteractionStore,
    build_mode_callback_data,
)
from tests.test_handlers import (
    FakeDownloadService,
    choose_mode_plan,
    direct_plan,
    terminal_video_mode_plan,
)
from tests.test_telegram_carousel import collection
from tests.test_telegram_localization import (
    IG,
    LOCALES,
    REAL_DELIVERY,
    YT,
    callback_update,
    message_update,
    translated,
)
from tests.test_telegram_localization import app as app

SENT = "✅ File sent."
UNCERTAIN = (
    "Telegram delivery wasn't confirmed. The file may have arrived. "
    "There will be no automatic retry."
)
INTERRUPTED = "Request interrupted. Delivery isn't confirmed. There will be no automatic retry."
ACCEPTED = "Download request accepted. Results appear in separate messages."


def real_pipeline(monkeypatch, plan=None):
    service = FakeDownloadService(plan=plan or direct_plan())
    monkeypatch.setattr(handlers, "download_service", service)
    monkeypatch.setattr(handlers, "_download_and_deliver_media", REAL_DELIVERY)
    monkeypatch.setattr(handlers, "prepare_telegram_video", lambda path: path)
    monkeypatch.setattr(
        handlers, "prepare_telegram_audio", lambda path, _: PreparedAudio(path, None)
    )
    monkeypatch.setattr(
        handlers,
        "inspect_telegram_video",
        lambda path: {"streams": [{"codec_type": "video", "width": 64, "height": 96}]},
    )
    return service


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "locale,expected",
    [
        (
            "en",
            (
                "👋 Hi! I can help you download videos from YouTube, Instagram and "
                "TikTok.\n\n🔗 Just send a video link.\n\nIf buttons appear, choose "
                "the format or quality you want — and I'll send the file right "
                "here."
            ),
        ),
        (
            "ru",
            (
                "👋 Привет! Я помогу скачать видео из YouTube, Instagram и "
                "TikTok.\n\n🔗 Просто отправь ссылку на видео.\n\nЕсли появятся "
                "кнопки, выбери нужный формат или качество — и я пришлю файл "
                "прямо сюда."
            ),
        ),
        (
            "es",
            (
                "👋 ¡Hola! Te ayudo a descargar vídeos de YouTube, Instagram y "
                "TikTok.\n\n🔗 Solo envía un enlace a un vídeo.\n\nSi aparecen "
                "botones, elige el formato o la calidad que quieras y te enviaré "
                "el archivo aquí mismo."
            ),
        ),
    ],
)
async def test_exact_approved_start_copy(app, locale, expected):
    dp, bot, session, *_ = app(instagram=True, tiktok=True)
    await dp.feed_update(bot, message_update("/start", locale))
    assert len(session.calls) == 1 and isinstance(session.calls[0], SendMessage)
    assert session.calls[0].text == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LOCALES)
async def test_start_does_not_advertise_disallowed_tiktok(app, monkeypatch, locale):
    dp, bot, session, _, tt, _ = app(instagram=True, tiktok=True)
    monkeypatch.setattr(tt, "allows", lambda message: False)
    await dp.feed_update(bot, message_update("/start", locale))
    assert len(session.calls) == 1
    assert "Instagram" in session.calls[0].text and "TikTok" not in session.calls[0].text
    assert "img_index" not in session.calls[0].text


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("callback", [False, True])
@pytest.mark.parametrize(
    "case",
    [
        "video",
        "audio",
        "missing_video",
        "missing_audio",
        "network_before",
        "network_after",
        "server",
        "timeout",
        "rejected",
        "download",
        "cleanup",
    ],
)
async def test_terminal_result_uses_media_evidence_once(app, monkeypatch, locale, callback, case):
    dp, bot, session, *_ = app()
    audio = case in {"audio", "missing_audio"}
    options = DownloadOptions(
        mode=DownloadMode.AUDIO_ONLY if audio else DownloadMode.VIDEO_WITH_AUDIO,
        quality_id=None if audio else "direct-quality",
    )
    service = real_pipeline(
        monkeypatch, terminal_video_mode_plan() if callback else direct_plan(options)
    )
    if case == "download":
        service.error = DownloadFailedError("Synthetic private detail")
    if case == "cleanup":

        class FailedCleanup(TemporaryDirectory):
            def __exit__(self, *args):
                super().__exit__(*args)
                raise OSError("Synthetic cleanup failure")

        monkeypatch.setattr(handlers, "TemporaryDirectory", FailedCleanup)
    original = session.make_request
    attempted = []

    async def transport(bot, method, timeout=None):
        if isinstance(method, (SendVideo, SendAudio)):
            attempted.append(method)
            if case in {"network_before", "server", "timeout", "rejected"}:
                session.calls.append(method)
                error = {
                    "network_before": TelegramNetworkError,
                    "server": TelegramServerError,
                    "rejected": TelegramBadRequest,
                }.get(case)
                if error:
                    raise error(method=method, message="Synthetic private failure")
                raise TimeoutError()
            result = await original(bot, method, timeout)
            if case == "network_after":
                raise TelegramNetworkError(
                    method=method, message="Synthetic lost response after send"
                )
            if case in {"missing_video", "missing_audio"}:
                return result.model_copy(update={"audio" if audio else "video": None})
            return result
        return await original(bot, method, timeout)

    monkeypatch.setattr(session, "make_request", transport)
    await dp.feed_update(bot, message_update(YT, locale))
    prompt = None
    if callback:
        prompt = session.messages[-1]
        data = prompt.reply_markup.inline_keyboard[1 if audio else 0][0].callback_data
        await dp.feed_update(bot, callback_update(prompt, data, "es" if locale != "es" else "en"))
    terminal = session.calls[-1]
    assert isinstance(terminal, EditMessageText) and terminal.reply_markup is None
    if case in {"video", "audio"}:
        source = SENT
    elif case == "cleanup":
        source = (
            "File sent. An error occurred while finishing the request; "
            "there will be no automatic retry."
        )
    elif case == "download":
        source = "Couldn't download the video. Try again later."
    elif case == "rejected":
        source = "Couldn't send the file to Telegram. Try again later."
    else:
        source = UNCERTAIN
    assert terminal.text == translated(source, locale)
    assert "Synthetic private" not in terminal.text
    assert len(service.calls) == 1 and not service.calls[0][1].exists()
    expected_options = (
        service.plan.mode_choices[1 if audio else 0].final_options if callback else options
    )
    assert service.calls[0][2] is expected_options
    assert len(attempted) == (0 if case == "download" else 1)
    assert len([c for c in session.calls if isinstance(c, SendMessage)]) == 1
    assert terminal.message_id == session.messages[0].message_id
    if callback:
        await asyncio.gather(
            *[dp.feed_update(bot, callback_update(prompt, data, "es")) for _ in range(2)]
        )
        assert len(service.calls) == 1 and len(attempted) == (0 if case == "download" else 1)
        assert session.calls[-1].text == translated(handlers._STALE_CALLBACK_MESSAGE, "es")


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("applied", [False, True])
@pytest.mark.parametrize("error_type", [TelegramNetworkError, TelegramBadRequest])
async def test_terminal_edit_failure_cannot_resend_media(
    app, monkeypatch, locale, applied, error_type
):
    dp, bot, session, *_ = app()
    service = real_pipeline(monkeypatch, terminal_video_mode_plan())
    original = session.make_request
    attempts = 0

    async def transport(bot, method, timeout=None):
        nonlocal attempts
        if isinstance(method, EditMessageText) and method.text == translated(SENT, locale):
            attempts += 1
            if applied:
                await original(bot, method, timeout)
            else:
                session.calls.append(method)
            raise error_type(method=method, message="Synthetic terminal edit failure")
        return await original(bot, method, timeout)

    monkeypatch.setattr(session, "make_request", transport)
    await dp.feed_update(bot, message_update(YT, locale))
    prompt = session.messages[-1]
    data = prompt.reply_markup.inline_keyboard[0][0].callback_data
    await dp.feed_update(bot, callback_update(prompt, data, "es"))
    await dp.feed_update(bot, callback_update(prompt, data, "en"))
    assert attempts == 1 and len(service.calls) == 1
    assert len([c for c in session.calls if isinstance(c, SendVideo)]) == 1
    final_card = [m for m in session.messages if m.message_id == prompt.message_id][-1]
    assert final_card.text == translated(SENT if applied else ACCEPTED, locale)
    assert final_card.reply_markup is None
    assert len([c for c in session.calls if isinstance(c, SendMessage)]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LOCALES)
async def test_cancelled_worker_drains_before_terminal_edit(app, monkeypatch, locale):
    dp, bot, session, *_ = app()
    service = real_pipeline(monkeypatch)
    original_download = service.download
    loop = asyncio.get_running_loop()
    entered = asyncio.Event()
    release = Event()
    finished = Event()
    workspace = []

    def blocked(*args):
        workspace.append(args[1])
        loop.call_soon_threadsafe(entered.set)
        assert release.wait(5)
        try:
            return original_download(*args)
        finally:
            finished.set()

    monkeypatch.setattr(service, "download", blocked)
    original_request = session.make_request

    async def transport(bot, method, timeout=None):
        if isinstance(method, EditMessageText):
            assert finished.is_set() and not workspace[0].exists()
        return await original_request(bot, method, timeout)

    monkeypatch.setattr(session, "make_request", transport)
    task = asyncio.create_task(dp.feed_update(bot, message_update(YT, locale)))
    try:
        await asyncio.wait_for(entered.wait(), 3)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not any(isinstance(c, EditMessageText) for c in session.calls)
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 3)
    assert session.calls[-1].text == translated(INTERRUPTED, locale)
    assert not any(isinstance(c, (SendVideo, SendAudio)) for c in session.calls)
    assert get_i18n().current_locale == "en"


@pytest.mark.asyncio
@pytest.mark.parametrize("repeat", [False, True])
async def test_cancelled_upload_is_uncertain_and_repeat_cancel_does_not_leak(
    app, monkeypatch, repeat
):
    dp, bot, session, *_ = app()
    service = real_pipeline(monkeypatch)
    original = session.make_request
    uploading, editing, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def transport(bot, method, timeout=None):
        if isinstance(method, SendVideo):
            result = await original(bot, method, timeout)  # May already have arrived.
            uploading.set()
            await release.wait()
            return result
        if isinstance(method, EditMessageText):
            editing.set()
            if repeat:
                await release.wait()
        return await original(bot, method, timeout)

    monkeypatch.setattr(session, "make_request", transport)
    task = asyncio.create_task(dp.feed_update(bot, message_update(YT, "ru")))
    try:
        await asyncio.wait_for(uploading.wait(), 3)
        task.cancel()
        await asyncio.wait_for(editing.wait(), 3)
        if repeat:
            task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert len(service.calls) == 1 and not service.calls[0][1].exists()
    assert len([c for c in session.calls if isinstance(c, SendVideo)]) == 1
    if not repeat:
        assert session.messages[-1].text == translated(INTERRUPTED, "ru")
    assert all(
        c.text != translated(SENT, "ru") for c in session.calls if isinstance(c, EditMessageText)
    )
    assert get_i18n().current_locale == "en"


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["foreign", "chat", "message", "expired", "unknown", "malformed"])
async def test_invalid_callback_cannot_erase_an_owners_card(app, monkeypatch, case):
    dp, bot, session, _, _, downloads = app()
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    monkeypatch.setattr(
        handlers, "pending_interaction_store", InMemoryPendingInteractionStore(clock=lambda: now[0])
    )
    await dp.feed_update(bot, message_update(YT, "ru"))
    card = session.messages[-1]
    data = card.reply_markup.inline_keyboard[1][0].callback_data
    changes = {}
    user = 7
    if case == "foreign":
        user = 8
    if case == "chat":
        changes["chat"] = {"id": 8, "type": "private"}
    if case == "message":
        changes["message_id"] = card.message_id + 1
    if case == "expired":
        now[0] += timedelta(minutes=15)
    if case == "unknown":
        data = build_mode_callback_data("missing", 1)
    if case == "malformed":
        data = "yt:invalid"
    edits_before = sum(isinstance(c, EditMessageText) for c in session.calls)
    await dp.feed_update(bot, callback_update(card, data, "es", user, **changes))
    assert sum(isinstance(c, EditMessageText) for c in session.calls) == edits_before
    assert not downloads and card.reply_markup is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LOCALES)
async def test_late_quality_edits_cannot_repaint_a_consumed_card(app, monkeypatch, locale):
    dp, bot, session, _, _, downloads = app()
    await dp.feed_update(bot, message_update(YT, locale))
    card = session.messages[-1]
    mode = card.reply_markup.inline_keyboard[0][0].callback_data
    audio = card.reply_markup.inline_keyboard[1][0].callback_data
    original = session.make_request
    entered, release, two_modes, terminal = (
        asyncio.Event(),
        asyncio.Event(),
        asyncio.Event(),
        asyncio.Event(),
    )
    acknowledgements = 0

    async def transport(bot, method, timeout=None):
        nonlocal acknowledgements
        if isinstance(method, AnswerCallbackQuery):
            if method.text is None:
                acknowledgements += 1
                if acknowledgements == 2:
                    two_modes.set()
            if method.text == translated("Starting download…", locale):
                terminal.set()
        if isinstance(method, EditMessageText) and method.text == translated(
            "Choose the quality:", locale
        ):
            entered.set()
            await release.wait()
        return await original(bot, method, timeout)

    monkeypatch.setattr(session, "make_request", transport)

    async def direct_callback(data, code):
        # Exercise the underlying E4 presentation lock under forced overlap.
        # Phase 9C's separately tested dispatcher gate now refuses that overlap.
        update = Update.model_validate(
            callback_update(card, data, code).model_dump(), context={"bot": bot}
        )
        await handlers.handle_choice_callback(update.callback_query)

    tasks = [asyncio.create_task(direct_callback(mode, "es"))]
    try:
        await asyncio.wait_for(entered.wait(), 3)
        tasks.append(asyncio.create_task(direct_callback(mode, "en")))
        await asyncio.wait_for(two_modes.wait(), 3)
        tasks.append(asyncio.create_task(direct_callback(audio, "es")))
        await asyncio.wait_for(terminal.wait(), 3)
        assert not downloads
        release.set()
        await asyncio.gather(*tasks)
    finally:
        release.set()
        await asyncio.gather(*tasks, return_exceptions=True)
    assert len(downloads) == 1 and downloads[0][0] == locale
    assert session.messages[-1].text == translated(SENT, locale)
    assert session.messages[-1].reply_markup is None
    assert (
        len(
            [
                c
                for c in session.calls
                if isinstance(c, EditMessageText)
                and c.text == translated("Choose the quality:", locale)
            ]
        )
        == 1
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("bind_failure", [False, True])
async def test_instagram_prompt_retires_only_after_known_validation(
    app, monkeypatch, tmp_path, locale, bind_failure
):
    _, plan = collection(tmp_path, 2, photos=(2,))
    monkeypatch.setattr(InstagramCarouselService, "inspect_item_reference", lambda *args: plan)
    dp, bot, session, owner, _, _ = app(instagram=True)
    delivered = []

    async def deliver(self, message, selected, *args):
        delivered.append(selected.requested_position)

    monkeypatch.setattr(InstagramPostHandler, "_send_carousel", deliver)
    if bind_failure:
        owner._post_handler = InstagramPostHandler(owner)
        monkeypatch.setattr(owner._post_handler._choices, "bind", lambda *args: False)
    await dp.feed_update(bot, message_update(IG + "?img_index=3", locale))
    if bind_failure:
        assert not delivered and session.messages[-1].reply_markup is None
        assert session.messages[-1].text == translated(
            "This choice has expired. Send the link again.", locale
        )
    else:
        card = session.messages[-1]
        data = card.reply_markup.inline_keyboard[1][0].callback_data
        await dp.feed_update(bot, callback_update(card, data, "es"))
        assert delivered == [3]
        assert session.messages[-1].reply_markup is None
        assert session.messages[-1].text == translated(
            "Instagram selection accepted. Results appear in separate messages.", locale
        )
        await dp.feed_update(bot, callback_update(card, data, "es"))
        assert delivered == [3]


def test_presentation_lock_is_request_local_and_survives_state_replacement():
    store = InMemoryPendingInteractionStore()
    first = store.create(owner_user_id=7, chat_id=7, url=YT, plan=choose_mode_plan())
    bound = store.set_message_id(
        first.interaction_id, owner_user_id=7, chat_id=7, message_id=9
    ).interaction
    transitioned = store.transition_to_quality(
        first.interaction_id, owner_user_id=7, chat_id=7, message_id=9, mode_index=0
    ).interaction
    consumed = store.consume_terminal(
        first.interaction_id, owner_user_id=7, chat_id=7, message_id=9
    ).interaction
    second = store.create(owner_user_id=8, chat_id=8, url=YT, plan=choose_mode_plan())
    assert (
        first.presentation_lock
        is bound.presentation_lock
        is transitioned.presentation_lock
        is consumed.presentation_lock
    )
    assert first.presentation_lock is not second.presentation_lock
    assert first.expires_at == bound.expires_at == transitioned.expires_at == consumed.expires_at


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [RuntimeError, TelegramNetworkError])
async def test_terminal_notification_failure_does_not_replace_cancellation(
    app, monkeypatch, caplog, error_type
):
    dp, bot, session, *_ = app()
    service = real_pipeline(monkeypatch)
    original = session.make_request
    uploading, release = asyncio.Event(), asyncio.Event()

    async def transport(bot, method, timeout=None):
        if isinstance(method, SendVideo):
            await original(bot, method, timeout)
            uploading.set()
            await release.wait()
        if isinstance(method, EditMessageText):
            if error_type is RuntimeError:
                raise RuntimeError("Synthetic private notification failure")
            raise error_type(method=method, message="Synthetic private notification failure")
        return await original(bot, method, timeout)

    monkeypatch.setattr(session, "make_request", transport)
    task = asyncio.create_task(dp.feed_update(bot, message_update(YT, "ru")))
    try:
        await asyncio.wait_for(uploading.wait(), 3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert len(service.calls) == 1 and not service.calls[0][1].exists()
    assert "Synthetic private notification failure" not in caplog.text
    assert get_i18n().current_locale == "en"
