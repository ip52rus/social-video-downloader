"""E3: real dispatcher and store, synthetic Bot API only; no external requests."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage

from social_video_downloader import handlers
from social_video_downloader.telegram_i18n import get_i18n
from social_video_downloader.telegram_interactions import (
    InMemoryPendingInteractionStore,
    build_mode_callback_data,
    build_quality_callback_data,
)
from social_video_downloader.telegram_interactions import (
    PendingInteractionStatus as Status,
)
from tests.test_handlers import FakeDownloadService, choose_mode_plan, choose_quality_plan
from tests.test_telegram_localization import (
    LOCALES,
    YT,
    callback_update,
    message_update,
    translated,
)
from tests.test_telegram_localization import (
    app as app,
)

RECEIPT = "YouTube link recognized. If no buttons appear, send the link again."
ACCEPTED = "Download request accepted. Results appear in separate messages."
TOKEN = "e3-offline-choice"


def store_for_test(monkeypatch, **kwargs):
    store = InMemoryPendingInteractionStore(id_factory=lambda: TOKEN, **kwargs)
    monkeypatch.setattr(handlers, "pending_interaction_store", store)
    return store


def lookup(store, message_id):
    return store.lookup(TOKEN, owner_user_id=7, chat_id=7, message_id=message_id)


@pytest.mark.parametrize("bound", [None, 1000])
@pytest.mark.parametrize("received", [None, 999, 1000])
@pytest.mark.parametrize("operation", ["lookup", "transition_to_quality", "consume_terminal"])
def test_store_requires_confirmed_exact_message(bound, received, operation):
    store = InMemoryPendingInteractionStore()
    record = store.create(
        owner_user_id=7, chat_id=7, message_id=bound, url=YT, plan=choose_mode_plan()
    )
    extra = {"mode_index": 0} if operation == "transition_to_quality" else {}
    result = getattr(store, operation)(
        record.interaction_id, owner_user_id=7, chat_id=7, message_id=received, **extra
    )
    expected = Status.FOUND if bound == received == 1000 else Status.WRONG_MESSAGE
    assert result.status is expected
    if expected is Status.WRONG_MESSAGE:
        assert result.interaction is None  # No pinned locale or plan on rejected messages.
        binding = store.set_message_id(
            record.interaction_id, owner_user_id=7, chat_id=7, message_id=1000
        )
        assert binding.status is Status.FOUND
        # All rejected reads/mutations leave the one-shot choice usable exactly once.
        assert (
            store.consume_terminal(
                record.interaction_id, owner_user_id=7, chat_id=7, message_id=1000
            ).status
            is Status.FOUND
        )


@pytest.mark.parametrize("replacement", [0, -1, None, True, "1000", 1001])
def test_binding_cannot_retarget_or_accept_invalid_message_id(replacement):
    store = InMemoryPendingInteractionStore()
    record = store.create(owner_user_id=7, chat_id=7, url=YT, plan=choose_mode_plan())
    assert (
        store.set_message_id(
            record.interaction_id, owner_user_id=7, chat_id=7, message_id=1000
        ).status
        is Status.FOUND
    )
    assert (
        store.set_message_id(
            record.interaction_id, owner_user_id=7, chat_id=7, message_id=replacement
        ).status
        is Status.WRONG_MESSAGE
    )
    assert (
        store.lookup(record.interaction_id, owner_user_id=7, chat_id=7, message_id=1000).status
        is Status.FOUND
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("quality_only", [False, True])
async def test_early_callback_before_binding_and_during_applied_edit(
    app, monkeypatch, locale, quality_only
):
    dp, bot, session, _, _, downloads = app()
    store = store_for_test(monkeypatch)
    plan = choose_quality_plan() if quality_only else choose_mode_plan()
    monkeypatch.setattr(handlers, "download_service", FakeDownloadService(plan=plan))
    payload = (
        build_quality_callback_data(TOKEN, 1)
        if quality_only
        else build_mode_callback_data(TOKEN, 1)
    )
    original = session.make_request
    card_id = None

    async def publication(bot, method, timeout=None):
        nonlocal card_id
        result = await original(bot, method, timeout)
        if isinstance(method, SendMessage):
            assert method.reply_markup is None
            assert method.text == translated(RECEIPT, locale)
            card_id = result.message_id
            assert lookup(store, card_id).status is Status.WRONG_MESSAGE
            await dp.feed_update(bot, callback_update(result, payload, "es"))
            assert not downloads
            assert session.calls[-1].text == translated(handlers._STALE_CALLBACK_MESSAGE, "es")
        elif isinstance(method, EditMessageText) and method.reply_markup is not None:
            assert method.message_id == card_id
            assert lookup(store, card_id).status is Status.FOUND
            # Telegram exposes the buttons while the publisher still awaits its response.
            await dp.feed_update(bot, callback_update(result, payload, "es"))
            assert len(downloads) == 1 and downloads[0][0] == locale
        return result

    monkeypatch.setattr(session, "make_request", publication)
    await dp.feed_update(bot, message_update(YT, locale))
    assert lookup(store, card_id).status is Status.UNKNOWN
    await dp.feed_update(bot, callback_update(session.messages[-1], payload, "es"))
    assert len(downloads) == 1
    assert len([c for c in session.calls if isinstance(c, SendMessage)]) == 1
    receipts = [
        c for c in session.calls if isinstance(c, EditMessageText) and c.reply_markup is None
    ]
    assert len(receipts) == 1 and receipts[0].text == translated(ACCEPTED, locale)


@pytest.mark.asyncio
@pytest.mark.parametrize("applied", [False, True])
@pytest.mark.parametrize("error_type", [TelegramNetworkError, TelegramBadRequest])
async def test_failed_initial_send_removes_pending_without_retry(
    app, monkeypatch, caplog, applied, error_type
):
    dp, bot, session, _, _, downloads = app()
    store = store_for_test(monkeypatch)
    original = session.make_request

    async def failed_send(bot, method, timeout=None):
        assert isinstance(method, SendMessage) and method.reply_markup is None
        if applied:
            await original(bot, method, timeout)
        else:
            session.calls.append(method)
        raise error_type(method=method, message="Private synthetic details")

    monkeypatch.setattr(session, "make_request", failed_send)
    await dp.feed_update(bot, message_update(YT, "ru"))
    assert lookup(store, 1000).status is Status.UNKNOWN
    assert len(session.calls) == 1 and not downloads
    assert "Private synthetic details" not in caplog.text
    assert all(m.reply_markup is None for m in session.messages)


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("applied", [False, True])
async def test_publication_edit_failure_preserves_binding_without_retry(
    app, monkeypatch, locale, applied
):
    dp, bot, session, _, _, downloads = app()
    store = store_for_test(monkeypatch)
    original = session.make_request
    attempts = 0

    async def lost_edit(bot, method, timeout=None):
        nonlocal attempts
        if isinstance(method, EditMessageText):
            attempts += 1
            if applied:
                await original(bot, method, timeout)
            else:
                session.calls.append(method)
            raise TelegramNetworkError(method=method, message="Synthetic lost response")
        return await original(bot, method, timeout)

    monkeypatch.setattr(session, "make_request", lost_edit)
    await dp.feed_update(bot, message_update(YT, locale))
    card = session.messages[-1]
    assert attempts == 1 and len(session.calls) == 2 and not downloads
    assert lookup(store, card.message_id).interaction.locale == locale
    assert card.text == translated("Choose a format:" if applied else RECEIPT, locale)
    if applied:
        monkeypatch.setattr(session, "make_request", original)
        payload = card.reply_markup.inline_keyboard[1][0].callback_data
        await asyncio.gather(
            dp.feed_update(bot, callback_update(card, payload, "en")),
            dp.feed_update(bot, callback_update(card, payload, "es")),
        )
        assert len(downloads) == 1 and downloads[0][0] == locale
        assert session.messages[-1].text == translated(ACCEPTED, locale)
        assert session.messages[-1].reply_markup is None
    else:
        assert card.reply_markup is None  # Honest receipt retains recovery guidance.


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", [SendMessage, EditMessageText])
@pytest.mark.parametrize("applied", [False, True])
async def test_repeated_cancellation_at_publication_boundaries(app, monkeypatch, stage, applied):
    dp, bot, session, _, _, downloads = app()
    store = store_for_test(monkeypatch)
    original = session.make_request
    entered, cancelling, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def paused(bot, method, timeout=None):
        if not isinstance(method, stage):
            return await original(bot, method, timeout)
        if applied:
            await original(bot, method, timeout)
        else:
            session.calls.append(method)
        entered.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            cancelling.set()
            await release.wait()  # Allow the second cancel to reach this exact boundary.
            raise

    monkeypatch.setattr(session, "make_request", paused)
    task = asyncio.create_task(dp.feed_update(bot, message_update(YT, "ru")))
    try:
        await asyncio.wait_for(entered.wait(), 3)
        task.cancel()
        await asyncio.wait_for(cancelling.wait(), 3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert not downloads and get_i18n().current_locale == "en"
    expected = Status.UNKNOWN if stage is SendMessage else Status.FOUND
    assert lookup(store, 1000).status is expected
    if stage is EditMessageText and applied:
        monkeypatch.setattr(session, "make_request", original)
        card = session.messages[-1]
        await dp.feed_update(
            bot, callback_update(card, card.reply_markup.inline_keyboard[1][0].callback_data, "es")
        )
        assert len(downloads) == 1 and downloads[0][0] == "ru"


@pytest.mark.asyncio
async def test_expiry_during_send_does_not_publish_or_extend_ttl(app, monkeypatch):
    dp, bot, session, _, _, downloads = app()
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    store = store_for_test(monkeypatch, clock=lambda: now[0])
    original = session.make_request

    async def delayed_send(bot, method, timeout=None):
        result = await original(bot, method, timeout)
        assert isinstance(method, SendMessage)
        now[0] += timedelta(minutes=15)
        return result

    monkeypatch.setattr(session, "make_request", delayed_send)
    await dp.feed_update(bot, message_update(YT, "en"))
    assert len(session.calls) == 1 and not downloads
    assert lookup(store, 1000).status is Status.UNKNOWN
    assert session.messages[0].reply_markup is None


@pytest.mark.asyncio
@pytest.mark.parametrize("same_user", [False, True])
async def test_two_concurrent_requests_bind_to_their_own_cards(app, monkeypatch, same_user):
    dp, bot, session, _, _, downloads = app()
    original = session.make_request
    entered = 0
    ready, release = asyncio.Event(), asyncio.Event()

    async def overlap(bot, method, timeout=None):
        nonlocal entered
        result = await original(bot, method, timeout)
        if isinstance(method, SendMessage):
            entered += 1
            if entered == 2:
                ready.set()
            await release.wait()
        return result

    monkeypatch.setattr(session, "make_request", overlap)
    tasks = [
        asyncio.create_task(dp.feed_update(bot, message_update(YT, "ru", user=7))),
        asyncio.create_task(
            dp.feed_update(bot, message_update(YT + "&t=1", "es", user=7 if same_user else 8))
        ),
    ]
    try:
        await asyncio.wait_for(ready.wait(), 3)
        release.set()
        await asyncio.gather(*tasks)
    finally:
        release.set()
        await asyncio.gather(*tasks, return_exceptions=True)
    cards = [m for m in session.messages if m.reply_markup is not None]
    assert len(cards) == 2 and cards[0].message_id != cards[1].message_id
    first, second = cards
    # A valid token replayed from the other message must not consume anything.
    await dp.feed_update(
        bot,
        callback_update(
            second,
            first.reply_markup.inline_keyboard[1][0].callback_data,
            "en",
            user=second.chat.id,
        ),
    )
    assert not downloads
    await asyncio.gather(
        *[
            dp.feed_update(
                bot,
                callback_update(
                    card,
                    card.reply_markup.inline_keyboard[1][0].callback_data,
                    "en",
                    user=card.chat.id,
                ),
            )
            for card in cards
        ]
    )
    assert sorted(locale for locale, _ in downloads) == ["es", "ru"]
    assert len(downloads) == 2
    assert len([c for c in session.calls if isinstance(c, SendMessage)]) == 2
    assert len([c for c in session.calls if isinstance(c, EditMessageText)]) == 4
    assert len([c for c in session.calls if isinstance(c, AnswerCallbackQuery)]) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("applied", [False, True])
async def test_terminal_receipt_lost_response_never_repeats_download(
    app, monkeypatch, locale, applied
):
    dp, bot, session, _, _, downloads = app()
    await dp.feed_update(bot, message_update(YT, locale))
    card = session.messages[-1]
    payload = card.reply_markup.inline_keyboard[1][0].callback_data
    original = session.make_request
    attempts = 0

    async def failed_receipt(bot, method, timeout=None):
        nonlocal attempts
        if isinstance(method, EditMessageText):
            attempts += 1
            assert method.text == translated(ACCEPTED, locale)
            assert method.reply_markup is None
            if applied:
                await original(bot, method, timeout)
            else:
                session.calls.append(method)
            raise TelegramNetworkError(method=method, message="Synthetic lost receipt response")
        return await original(bot, method, timeout)

    monkeypatch.setattr(session, "make_request", failed_receipt)
    await asyncio.gather(
        dp.feed_update(bot, callback_update(card, payload, "en")),
        dp.feed_update(bot, callback_update(card, payload, "es")),
    )
    assert attempts == 1 and len(downloads) == 1
    assert downloads[0][0] == locale
    assert len([c for c in session.calls if isinstance(c, SendMessage)]) == 1
    # Even if the old keyboard remains visible, every later callback is stale.
    await dp.feed_update(bot, callback_update(card, payload, "es"))
    assert attempts == 1 and len(downloads) == 1
    assert session.calls[-1].text == translated(handlers._STALE_CALLBACK_MESSAGE, "es")


@pytest.mark.parametrize("replacement", [0, -1, None, True, "1000"])
def test_initial_binding_rejects_invalid_id_without_consuming(replacement):
    store = InMemoryPendingInteractionStore()
    record = store.create(owner_user_id=7, chat_id=7, url=YT, plan=choose_mode_plan())
    assert (
        store.set_message_id(
            record.interaction_id, owner_user_id=7, chat_id=7, message_id=replacement
        ).status
        is Status.WRONG_MESSAGE
    )
    assert (
        store.lookup(record.interaction_id, owner_user_id=7, chat_id=7, message_id=1000).status
        is Status.WRONG_MESSAGE
    )
    assert (
        store.set_message_id(
            record.interaction_id, owner_user_id=7, chat_id=7, message_id=1000
        ).status
        is Status.FOUND
    )
    bound = store.lookup(record.interaction_id, owner_user_id=7, chat_id=7, message_id=1000)
    assert bound.interaction.created_at == record.created_at
    assert bound.interaction.expires_at == record.expires_at
