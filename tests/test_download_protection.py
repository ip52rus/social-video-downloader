"""Phase 9C: synthetic Telegram updates, clocks and owned workers; no external API."""

import asyncio
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from threading import Event
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from aiogram import Bot
from aiogram.methods import EditMessageText, SendMessage

from social_video_downloader import download_protection as protection
from social_video_downloader import handlers
from social_video_downloader.bot import create_dispatcher
from social_video_downloader.config import Settings
from social_video_downloader.domain.errors import DownloadCleanupError, MetadataExtractionError
from social_video_downloader.telegram_i18n import get_i18n
from social_video_downloader.telegram_instagram import InstagramReelHandler
from social_video_downloader.telegram_instagram_posts import InstagramPostHandler
from social_video_downloader.telegram_interactions import InMemoryPendingInteractionStore
from tests.test_handlers import FakeDownloadService, choose_mode_plan, direct_plan
from tests.test_telegram_carousel import collection
from tests.test_telegram_localization import IG, TT, YT, Session, callback_update, message_update


def gate(**kwargs):
    return protection.DownloadAdmission(free_bytes=lambda: 100 * 1024**3, **kwargs)


@pytest_asyncio.fixture
async def app(monkeypatch):
    now = [0.0]
    utc = [datetime(2026, 1, 1, tzinfo=UTC)]
    admission = gate(clock=lambda: now[0], utc_clock=lambda: utc[0])
    service = FakeDownloadService(plan=choose_mode_plan())
    store = InMemoryPendingInteractionStore(clock=lambda: utc[0])
    monkeypatch.setattr(handlers, "download_service", service)
    monkeypatch.setattr(handlers, "pending_interaction_store", store)
    download = AsyncMock(
        return_value=handlers.YouTubeDeliveryResult(
            handlers.YouTubeDeliveryState.DELIVERED, "confirmed synthetic delivery"
        )
    )
    monkeypatch.setattr(handlers, "_download_and_deliver_media", download)
    ig = InstagramReelHandler()
    tt = SimpleNamespace(handle=AsyncMock(), allows=lambda _: True)
    session = Session()
    bot = Bot("123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi", session=session)
    dp = create_dispatcher(
        Settings("synthetic", instagram_telegram_enabled=True, tiktok_telegram_enabled=True),
        instagram_reels=ig,
        tiktok_videos=tt,
        download_admission=admission,
    )
    yield SimpleNamespace(
        dp=dp,
        bot=bot,
        session=session,
        gate=admission,
        service=service,
        download=download,
        ig=ig,
        tt=tt,
        now=now,
        utc=utc,
        store=store,
    )
    await session.close()


async def send(app, text=YT, code="en", user=7):
    await app.dp.feed_update(app.bot, message_update(text, code, user=user))


def prompt(app):
    return next(m for m in reversed(app.session.messages) if m.reply_markup is not None)


def text(app):
    return app.session.calls[-1].text


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", ["en", "ru", "es"])
@pytest.mark.parametrize("second", [YT, IG, TT])
async def test_one_pending_request_across_platforms_and_localized_refusal(app, locale, second):
    await send(app, code=locale)
    await send(app, second, code=locale)
    assert text(app) == get_i18n().gettext(protection.ACTIVE_MESSAGE, locale=locale)
    assert len(app.service.plan_calls) == 1
    app.tt.handle.assert_not_awaited()
    assert app.ig._post_handler is None
    assert len(app.gate._leases) == 1


@pytest.mark.asyncio
async def test_gate_is_reserved_before_metadata_and_accepts_other_users(app):
    entered, release = asyncio.Event(), asyncio.Event()

    async def planning(url):
        entered.set()
        await release.wait()
        return choose_mode_plan()

    app.service.create_choice_plan_async = planning
    first = asyncio.create_task(send(app))
    await entered.wait()
    await send(app, TT)
    assert text(app) == protection.ACTIVE_MESSAGE
    await send(app, TT, user=8)
    app.tt.handle.assert_awaited_once()
    assert not first.done()
    release.set()
    await first


@pytest.mark.asyncio
async def test_global_capacity_includes_waiting_choices_and_has_no_queue(app):
    for user in range(1, 5):
        await send(app, user=user)
    assert len(app.service.plan_calls) == 4
    await send(app, user=5)
    assert text(app) == protection.BUSY_MESSAGE
    assert len(app.service.plan_calls) == 4
    assert len(app.gate._leases) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", ["en", "ru", "es"])
async def test_cancel_waiting_choice_invalidates_payload_and_frees_slot(app, locale):
    await send(app, code="ru")
    card = prompt(app)
    payload = card.reply_markup.inline_keyboard[1][0].callback_data
    await send(app, "/cancel", code=locale)
    assert text(app) == get_i18n().gettext(
        "Choice cancelled. You can send another link.", locale=locale
    )
    assert not app.gate._leases
    await app.dp.feed_update(app.bot, callback_update(card, payload, code=locale))
    assert text(app) == get_i18n().gettext(protection.STALE_MESSAGE, locale=locale)
    app.download.assert_not_awaited()
    app.now[0] = 3
    await send(app, TT)
    app.tt.handle.assert_awaited_once()


@pytest.mark.asyncio
async def test_pinned_language_mode_quality_and_repeated_callbacks(app):
    await send(app, code="ru")
    card = prompt(app)
    mode = card.reply_markup.inline_keyboard[0][0].callback_data
    await app.dp.feed_update(app.bot, callback_update(card, mode, code="es"))
    quality_card = prompt(app)
    assert quality_card.text == get_i18n().gettext("Choose the quality:", locale="ru")
    quality = quality_card.reply_markup.inline_keyboard[0][0].callback_data
    await app.dp.feed_update(app.bot, callback_update(quality_card, quality, code="es"))
    app.download.assert_awaited_once()
    assert not app.gate._leases
    await app.dp.feed_update(app.bot, callback_update(quality_card, quality, code="es"))
    app.download.assert_awaited_once()
    assert text(app) == get_i18n().gettext(protection.STALE_MESSAGE, locale="es")


@pytest.mark.asyncio
async def test_foreign_and_wrong_message_do_not_consume_or_release(app):
    await send(app)
    card = prompt(app)
    data = card.reply_markup.inline_keyboard[1][0].callback_data
    for changes in ({"user": 8}, {"message_id": 987654}, {"chat": {"id": 999, "type": "private"}}):
        await app.dp.feed_update(app.bot, callback_update(card, data, **changes))
        assert len(app.gate._leases) == 1
    app.download.assert_not_awaited()
    await app.dp.feed_update(app.bot, callback_update(card, data))
    app.download.assert_awaited_once()


@pytest.mark.asyncio
async def test_active_callback_cannot_be_cancelled_or_started_twice(app):
    await send(app)
    card = prompt(app)
    payload = card.reply_markup.inline_keyboard[1][0].callback_data
    entered, release = asyncio.Event(), asyncio.Event()

    async def delivery(*args):
        entered.set()
        await release.wait()
        return handlers.YouTubeDeliveryResult(handlers.YouTubeDeliveryState.DELIVERED, "confirmed")

    app.download.side_effect = delivery
    running = asyncio.create_task(app.dp.feed_update(app.bot, callback_update(card, payload)))
    await entered.wait()
    await send(app, "/cancel")
    assert "already running" in text(app)
    await app.dp.feed_update(app.bot, callback_update(card, payload))
    app.download.assert_awaited_once()
    await send(app, IG)
    assert text(app) == protection.ACTIVE_MESSAGE
    release.set()
    await running
    assert not app.gate._leases


@pytest.mark.asyncio
async def test_publication_response_lost_releases_without_exposing_download(app):
    app.session.fail = SendMessage
    await send(app)
    assert not app.gate._leases
    assert not app.store._interactions
    app.download.assert_not_awaited()
    app.now[0] = 3
    await send(app, TT)
    app.tt.handle.assert_awaited_once()


@pytest.mark.asyncio
async def test_edit_response_lost_retains_bound_choice_until_cancel(app):
    app.session.fail = EditMessageText
    await send(app)
    assert len(app.gate._leases) == 1
    await send(app, "/cancel")
    assert not app.gate._leases
    app.download.assert_not_awaited()


@pytest.mark.asyncio
async def test_callback_arriving_before_publication_returns_cannot_free_live_worker(app):
    original = app.session.make_request
    entered, release_edit, downloading, release_download = (asyncio.Event() for _ in range(4))

    async def request(bot, method, timeout=None):
        result = await original(bot, method, timeout)
        if isinstance(method, EditMessageText) and method.reply_markup:
            entered.set()
            await release_edit.wait()
        return result

    async def deliver(*args):
        downloading.set()
        await release_download.wait()
        return handlers.YouTubeDeliveryResult(handlers.YouTubeDeliveryState.DELIVERED, "confirmed")

    app.session.make_request = request
    app.download.side_effect = deliver
    initial = asyncio.create_task(send(app))
    await entered.wait()
    card = prompt(app)
    payload = card.reply_markup.inline_keyboard[1][0].callback_data
    click = asyncio.create_task(app.dp.feed_update(app.bot, callback_update(card, payload)))
    # consume occurs before waiting for the publication presentation lock.
    for _ in range(100):
        if app.gate._leases[7].pending is None:
            break
        await asyncio.sleep(0)
    assert app.gate._leases[7].contexts == 2
    release_edit.set()
    await initial
    await downloading.wait()
    await send(app, TT)
    assert text(app) == protection.ACTIVE_MESSAGE
    release_download.set()
    await click
    assert not app.gate._leases
    app.download.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["success", "refusal", "timeout", "cancel"])
async def test_direct_request_releases_only_after_handler_completes(app, outcome):
    app.service.plan = direct_plan()
    if outcome == "refusal":
        app.service.plan_error = MetadataExtractionError("synthetic")
    elif outcome == "timeout":
        app.download.side_effect = TimeoutError
    elif outcome == "cancel":
        app.download.side_effect = asyncio.CancelledError
    if outcome in {"timeout", "cancel"}:
        with pytest.raises(TimeoutError if outcome == "timeout" else asyncio.CancelledError):
            await send(app)
    else:
        await send(app)
    assert not app.gate._leases
    assert protection._current.get() is None
    await send(app, TT)
    assert text(app) == protection.RATE_MESSAGE
    app.now[0] = 3
    await send(app, TT)
    app.tt.handle.assert_awaited_once()


@pytest.mark.asyncio
async def test_expiry_releases_waiting_slot_without_restarting_media(app):
    await send(app)
    card = prompt(app)
    payload = card.reply_markup.inline_keyboard[1][0].callback_data
    app.utc[0] += timedelta(minutes=15)
    app.now[0] = 900
    await send(app, TT)
    app.tt.handle.assert_awaited_once()
    await app.dp.feed_update(app.bot, callback_update(card, payload))
    app.download.assert_not_awaited()
    assert not app.gate._leases


@pytest.mark.asyncio
async def test_restart_old_callback_is_stale_without_new_admission(app, monkeypatch):
    await send(app)
    card = prompt(app)
    payload = card.reply_markup.inline_keyboard[1][0].callback_data
    monkeypatch.setattr(handlers, "pending_interaction_store", InMemoryPendingInteractionStore())
    await app.dp.feed_update(app.bot, callback_update(card, payload))
    app.download.assert_not_awaited()
    assert text(app) == get_i18n().gettext(protection.STALE_MESSAGE, locale="es")


@pytest.mark.asyncio
async def test_owned_thread_repeated_cancellation_retains_cross_platform_slot(app):
    entered, release = Event(), Event()
    app.service.plan = direct_plan()

    def worker():
        entered.set()
        release.wait(10)

    async def delivery(*args):
        await handlers._run_workspace_thread(worker)

    app.download.side_effect = delivery
    running = asyncio.create_task(send(app))
    while not entered.is_set():
        await asyncio.sleep(0)
    try:
        running.cancel()
        await asyncio.sleep(0)
        running.cancel()
        await asyncio.sleep(0)
        await send(app, TT)
        assert text(app) == protection.ACTIVE_MESSAGE
        assert not running.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await running
    assert not app.gate._leases


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["youtube", "instagram", "tiktok"])
async def test_quarantine_cannot_expire_cancel_or_release_global_capacity(app, platform):
    async def unsafe(*args):
        protection.retain_current_request()
        raise DownloadCleanupError("synthetic")

    if platform == "youtube":
        app.service.create_choice_plan_async = unsafe
        url = YT
    else:
        target = app.ig if platform == "instagram" else app.tt
        target.handle = unsafe
        url = IG if platform == "instagram" else TT
    if platform == "youtube":
        await send(app, url)
    else:
        with pytest.raises(DownloadCleanupError):
            await send(app, url)
    lease = app.gate._leases[7]
    assert lease.quarantined and lease.contexts == 0
    app.utc[0] += timedelta(days=1)
    await send(app, "/cancel")
    assert "already running" in text(app)
    await send(app, TT)
    assert text(app) == protection.ACTIVE_MESSAGE
    assert app.gate._leases[7] is lease


@pytest.mark.asyncio
async def test_metadata_cancellation_with_uncertain_owner_holds_slot(app):
    app.service._youtube_metadata = SimpleNamespace(blocked=True)
    app.service.create_choice_plan_async = AsyncMock(side_effect=asyncio.CancelledError)
    with pytest.raises(asyncio.CancelledError):
        await send(app)
    assert app.gate._leases[7].quarantined
    assert protection._current.get() is None


@pytest.mark.asyncio
async def test_instagram_waiting_choice_shared_gate_consume_and_cancel(app, monkeypatch, tmp_path):
    _, plan = collection(tmp_path, 2)
    app.ig._post_handler = post = InstagramPostHandler(app.ig)
    post._choices._clock = lambda: app.utc[0]

    async def offer(message, raw):
        await post._offer_choice(message, plan, 1)

    monkeypatch.setattr(app.ig, "handle", offer)
    delivered = AsyncMock()
    monkeypatch.setattr(post, "_send_carousel", delivered)
    await send(app, IG, code="ru")
    card = prompt(app)
    payload = card.reply_markup.inline_keyboard[1][0].callback_data
    await send(app, YT)
    assert text(app) == protection.ACTIVE_MESSAGE
    await app.dp.feed_update(app.bot, callback_update(card, payload, user=8))
    delivered.assert_not_awaited()
    await app.dp.feed_update(app.bot, callback_update(card, payload, code="es"))
    delivered.assert_awaited_once()
    assert not app.gate._leases
    await app.dp.feed_update(app.bot, callback_update(card, payload, code="es"))
    delivered.assert_awaited_once()
    app.now[0] = 3
    await send(app, IG)
    await send(app, "/cancel")
    assert not post._choices._choices
    assert not app.gate._leases


def test_disk_admission_is_fail_closed_without_queued_work():
    admission = protection.DownloadAdmission(free_bytes=lambda: 0)
    assert admission.admit(7) == (None, protection.BUSY_MESSAGE)
    assert not admission._leases
    admission = protection.DownloadAdmission(free_bytes=Mock(side_effect=OSError))
    assert admission.admit(7) == (None, protection.BUSY_MESSAGE)


def test_rate_bookkeeping_is_bounded_and_expired_entries_reclaimed():
    now = [0]
    admission = gate(max_active=1, clock=lambda: now[0])
    for user in range(5000):
        lease, _ = admission.admit(user)
        if lease:
            admission.leave(lease)
    assert len(admission._attempts) == 4096
    now[0] = 3
    assert admission.admit(9999)[0] is not None
    assert len(admission._attempts) == 1


@pytest.mark.parametrize("cleanup_fails", [True, False])
def test_cleanup_failure_retains_lease_but_inner_error_with_clean_exit_does_not(cleanup_fails):
    admission = gate()
    lease, _ = admission.admit(7)
    context = protection._current.set(lease)

    @contextmanager
    def workspace():
        try:
            yield "synthetic owned workspace"
        finally:
            if cleanup_fails:
                raise OSError("synthetic cleanup failure")

    try:
        with pytest.raises(OSError), protection.protected_cleanup(workspace()):
            raise OSError("synthetic download failure")
    finally:
        protection._current.reset(context)
        admission.leave(lease)
    assert lease.quarantined is cleanup_fails
    assert bool(admission._leases) is cleanup_fails


@pytest.mark.asyncio
@pytest.mark.parametrize("first", [IG, TT])
@pytest.mark.parametrize("second", [YT, IG, TT])
async def test_cross_platform_guard_also_starts_with_instagram_and_tiktok(app, first, second):
    entered, release = asyncio.Event(), asyncio.Event()

    async def operation(*args):
        entered.set()
        await release.wait()

    target = app.ig if first == IG else app.tt
    target.handle = AsyncMock(side_effect=operation)
    running = asyncio.create_task(send(app, first))
    await entered.wait()
    try:
        await send(app, second)
        assert text(app) == protection.ACTIVE_MESSAGE
        assert not app.service.plan_calls
        target.handle.assert_awaited_once()
        await send(app, "/cancel")
        assert "already running" in text(app)
    finally:
        release.set()
        await running
    assert not app.gate._leases


@pytest.mark.asyncio
async def test_concurrent_users_ru_en_es_keep_independent_leases_and_locales(app):
    await asyncio.gather(
        *(send(app, code=locale, user=i) for i, locale in enumerate(("ru", "en", "es"), 1))
    )
    assert len(app.gate._leases) == 3
    prompts = [m for m in app.session.messages if m.reply_markup]
    assert {m.chat.id: m.text for m in prompts} == {
        i: get_i18n().gettext("Choose a format:", locale=locale)
        for i, locale in enumerate(("ru", "en", "es"), 1)
    }
    await send(app, "/cancel", user=2)
    assert set(app.gate._leases) == {1, 3}
    assert protection._current.get() is None
    assert get_i18n().current_locale == "en"


@pytest.mark.asyncio
async def test_actual_tiktok_cleanup_error_quarantines_shared_lease(app):
    from social_video_downloader.telegram_tiktok import TelegramTikTokHandler
    from tests.test_tiktok_integration import FixtureProvider

    provider = FixtureProvider()
    provider.download_prepared = Mock(side_effect=DownloadCleanupError("synthetic"))
    app.dp["tiktok_videos"] = handler = TelegramTikTokHandler(provider=provider)
    await send(app, TT)
    assert handler._blocked and handler._active_users == {7}
    assert app.gate._leases[7].quarantined
    await send(app, IG)
    assert text(app) == protection.ACTIVE_MESSAGE


@pytest.mark.asyncio
async def test_actual_instagram_carousel_cleanup_error_quarantines_shared_lease(
    app, monkeypatch, tmp_path
):
    _, plan = collection(tmp_path, 1)
    post = app.ig._post_handler = InstagramPostHandler(app.ig)
    monkeypatch.setattr(
        post, "_send_carousel", AsyncMock(side_effect=DownloadCleanupError("synthetic"))
    )

    async def offer(message, raw):
        await post._offer_choice(message, plan, 1)

    monkeypatch.setattr(app.ig, "handle", offer)
    await send(app, IG)
    card = prompt(app)
    payload = card.reply_markup.inline_keyboard[0][0].callback_data
    await app.dp.feed_update(app.bot, callback_update(card, payload))
    assert app.ig._blocked and app.ig._active
    assert app.gate._leases[7].quarantined
    await send(app, TT)
    assert text(app) == protection.ACTIVE_MESSAGE


@pytest.mark.asyncio
@pytest.mark.parametrize("pipeline", ["youtube", "reel", "single_post"])
async def test_actual_workspace_cleanup_failure_keeps_shared_lease(app, monkeypatch, pipeline):
    from tempfile import TemporaryDirectory

    from social_video_downloader import telegram_instagram as reels
    from social_video_downloader import telegram_instagram_posts as posts
    from tests.test_telegram_localization import REAL_DELIVERY

    class FailedCleanup(TemporaryDirectory):
        def __exit__(self, *args):
            super().__exit__(*args)
            raise OSError("Synthetic cleanup failure")

    if pipeline == "youtube":
        app.service.plan = direct_plan()
        monkeypatch.setattr(handlers, "_download_and_deliver_media", REAL_DELIVERY)
        monkeypatch.setattr(handlers, "TemporaryDirectory", FailedCleanup)
        monkeypatch.setattr(handlers, "prepare_telegram_video", lambda p: p)
        monkeypatch.setattr(handlers, "inspect_telegram_video", lambda p: {})
        await send(app)
    else:
        monkeypatch.setattr(
            reels if pipeline == "reel" else posts, "TemporaryDirectory", FailedCleanup
        )

        def prepare(url, workspace, guard, **kwargs):
            path = workspace / "synthetic.mp4"
            path.write_bytes(b"local synthetic media")
            return path, {"width": 64, "height": 96}

        monkeypatch.setattr(app.ig, "_prepare", prepare)
        if pipeline == "single_post":
            from social_video_downloader.domain.models import MediaMetadata, Platform

            monkeypatch.setattr(
                posts.InstagramCarouselService,
                "inspect_publication",
                lambda *a: MediaMetadata("synthetic", IG, Platform.INSTAGRAM),
            )
        await send(
            app, "https://www.instagram.com/reel/Synthetic_01/" if pipeline == "reel" else IG
        )
    assert app.gate._leases[7].quarantined
    assert app.gate._leases[7].contexts == 0
    await send(app, TT)
    assert text(app) == protection.ACTIVE_MESSAGE


@pytest.mark.asyncio
async def test_preexisting_metadata_quarantine_does_not_capture_unrelated_users(app):
    from social_video_downloader.domain.errors import MetadataBusyError

    app.service._youtube_metadata = SimpleNamespace(blocked=True)
    app.service.plan_error = MetadataBusyError("synthetic pre-existing quarantine")
    await send(app)
    assert not app.gate._leases
    app.now[0] = 3
    await send(app, TT)
    app.tt.handle.assert_awaited_once()
    assert not app.gate._leases


@pytest.mark.asyncio
async def test_instagram_waiting_expiry_uses_original_store_deadline(app, monkeypatch, tmp_path):
    _, plan = collection(tmp_path, 1)
    post = app.ig._post_handler = InstagramPostHandler(app.ig)
    post._choices._clock = lambda: app.utc[0]

    async def offer(message, raw):
        await post._offer_choice(message, plan, 1)

    monkeypatch.setattr(app.ig, "handle", offer)
    monkeypatch.setattr(post, "_send_carousel", AsyncMock())
    await send(app, IG)
    card = prompt(app)
    data = card.reply_markup.inline_keyboard[0][0].callback_data
    expiry = app.gate._leases[7].pending.expires_at
    assert expiry == app.utc[0] + timedelta(minutes=15)
    app.utc[0] = expiry
    app.now[0] = 900
    await send(app, TT)
    app.tt.handle.assert_awaited_once()
    await app.dp.feed_update(app.bot, callback_update(card, data))
    post._send_carousel.assert_not_awaited()
    assert not app.gate._leases
    assert not post._choices._choices
