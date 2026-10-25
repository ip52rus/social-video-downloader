"""Offline locale foundation and activation compatibility."""

import asyncio
from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from string import Formatter
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.types import CallbackQuery, Chat, Message, User
from babel import UnknownLocaleError

from social_video_downloader import handlers
from social_video_downloader.bot import create_dispatcher
from social_video_downloader.domain.carousel import (
    CarouselItem,
    CarouselItemKind,
    CarouselParentIdentity,
    CarouselPlanState,
    CarouselScope,
    CarouselSelectionPlan,
)
from social_video_downloader.domain.models import DownloadMode, DownloadOptions, QualityOption
from social_video_downloader.services.choice_model import (
    ChoicePlan,
    ChoicePlanState,
    ModeChoice,
    QualityChoice,
    UserChoiceKind,
)
from social_video_downloader.services.quality_tiers import QualityTier
from social_video_downloader.telegram_i18n import (
    DEFAULT_LOCALE,
    RequestLocaleMiddleware,
    create_i18n,
    get_i18n,
    locale_for_event,
    resolve_locale,
)
from social_video_downloader.telegram_instagram_interactions import InstagramChoiceStore
from social_video_downloader.telegram_interactions import (
    InMemoryPendingInteractionStore,
    PendingInteraction,
    PendingInteractionStatus,
    build_mode_callback_data,
    parse_callback_data,
)


@pytest.mark.parametrize(
    "code,expected",
    [
        ("en", "en"),
        ("en-US", "en"),
        ("EN-us", "en"),
        ("ru", "ru"),
        ("ru-RU", "ru"),
        ("ru-Cyrl-RU", "ru"),
        ("es", "es"),
        ("es-MX", "es"),
        ("es-419", "es"),
        ("pt-BR", "en"),
        ("fr", "en"),
        ("zh-Hans-CN", "en"),
        ("zz-ZZ", "en"),
        (None, "en"),
        ("", "en"),
        (" ", "en"),
        (" ru ", "en"),
        ("ru_RU", "en"),
        ("ru--RU", "en"),
        ("ru-", "en"),
        ("-ru", "en"),
        ("ru.UTF-8", "en"),
        ("ru@custom", "en"),
        ("rü", "en"),
        ("ru/../../es", "en"),
        ("ru\x00", "en"),
        ("ru\n", "en"),
        ("ru-" + "a" * 65, "en"),
        ("ru-RU-x-private", "en"),
        (42, "en"),
        (True, "en"),
        (b"ru", "en"),
        ({"language": "ru"}, "en"),
    ],
)
def test_locale_resolution(code, expected):
    assert resolve_locale(code) == expected


@pytest.mark.parametrize("error", [UnknownLocaleError("fixture"), ValueError(), TypeError()])
def test_babel_parse_errors_fall_back_without_logging(monkeypatch, caplog, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr("social_video_downloader.telegram_i18n.Locale.parse", fail)
    assert resolve_locale("ru-RU") == DEFAULT_LOCALE
    assert not caplog.records


def test_oversized_input_never_reaches_babel(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Oversized tag reached parser")

    monkeypatch.setattr("social_video_downloader.telegram_i18n.Locale.parse", forbidden)
    assert resolve_locale("ru-" + "a" * 10000) == "en"


def user(code="en", user_id=1, *, bot=False):
    return User(id=user_id, is_bot=bot, first_name="Synthetic", language_code=code)


def message(code="en", *, user_id=1, chat_id=2, message_id=3):
    return Message(
        message_id=message_id,
        date=datetime.now(UTC),
        chat=Chat(id=chat_id, type="private"),
        from_user=user(code, user_id),
    )


def callback(code="en", *, user_id=1):
    return CallbackQuery(
        id="synthetic",
        from_user=user(code, user_id),
        chat_instance="synthetic",
        message=message("en", user_id=99).model_copy(
            update={"from_user": user("en", 99, bot=True)}
        ),
        data="synthetic",
    )


@pytest.mark.parametrize("code", ["en-US", "ru-RU", "es-MX", None])
def test_event_sender_including_callback_not_bot_message(code):
    assert locale_for_event(message(code)) == resolve_locale(code)
    assert locale_for_event(callback(code)) == resolve_locale(code)
    assert locale_for_event(message().model_copy(update={"from_user": None})) == "en"


@pytest.fixture
def engine():
    return create_i18n()


EXPECTED = {
    "en": "I18n foundation",
    "ru": "Основа локализации",
    "es": "Base de internacionalización",
}


@pytest.mark.asyncio
async def test_parallel_real_middleware_contexts(engine):
    middleware = RequestLocaleMiddleware(engine)
    ready, release = asyncio.Event(), asyncio.Event()
    entered = 0

    async def invoke(code, event):
        async def handler(_, data):
            nonlocal entered
            assert data["i18n"] is engine
            entered += 1
            if entered == 18:
                ready.set()
            await release.wait()
            assert engine.gettext("I18n foundation") == EXPECTED[resolve_locale(code)]
            await asyncio.sleep(0)
            assert engine.current_locale == resolve_locale(code)

        await middleware(handler, event, {})

    tasks = [
        asyncio.create_task(invoke(code, constructor(code)))
        for code in ("ru-RU", "en-US", "es-MX")
        for constructor in (message, callback)
        for _ in range(3)
    ]
    try:
        await asyncio.wait_for(ready.wait(), 2)
    finally:
        release.set()
        await asyncio.gather(*tasks)
    assert engine.current_locale == "en"


@pytest.mark.asyncio
async def test_other_event_uses_standard_user_context(engine):
    async def handler(_, data):
        assert engine.current_locale == "es"

    await RequestLocaleMiddleware(engine)(
        handler, SimpleNamespace(), {"event_from_user": user("es-MX")}
    )
    assert engine.current_locale == "en"


@pytest.mark.asyncio
async def test_context_restored_after_exception(engine):
    async def handler(_, data):
        assert engine.current_locale == "ru"
        raise ValueError("Synthetic handler failure")

    with engine.use_locale("es"), pytest.raises(ValueError):
        try:
            await RequestLocaleMiddleware(engine)(handler, message("ru"), {})
        finally:
            assert engine.current_locale == "es"
    assert engine.current_locale == "en"


@pytest.mark.asyncio
@pytest.mark.parametrize("repeat", [False, True])
async def test_context_restored_after_cancellation(engine, repeat):
    entered, unwinding, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def handler(_, data):
        assert engine.current_locale == "ru"
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            unwinding.set()
            await release.wait()

    task = asyncio.create_task(RequestLocaleMiddleware(engine)(handler, message("ru"), {}))
    try:
        await entered.wait()
        task.cancel()
        await unwinding.wait()
        if repeat:
            task.cancel()
    finally:
        release.set()
        results = await asyncio.gather(task, return_exceptions=True)
    assert isinstance(results[0], asyncio.CancelledError)
    assert engine.current_locale == "en"


def youtube_plan():
    return ChoicePlan(
        ChoicePlanState.CHOOSE_MODE,
        (DownloadMode.VIDEO_WITH_AUDIO,),
        (),
        (),
        mode_choices=(
            ModeChoice(
                UserChoiceKind.VIDEO,
                DownloadMode.VIDEO_WITH_AUDIO,
                DownloadOptions(quality_id="fixture-exact"),
            ),
        ),
    )


def instagram_plan():
    items = (CarouselItem(1, "synthetic-child", CarouselItemKind.VIDEO, ("fixture",), 1),)
    return CarouselSelectionPlan(
        "https://www.instagram.com/p/B/",
        1,
        items,
        items,
        CarouselScope.PUBLICATION,
        CarouselPlanState.READY,
        parent_identity=CarouselParentIdentity("1", "B"),
    )


@pytest.mark.parametrize("locale", ["en", "ru", "es"])
@pytest.mark.parametrize("kind", ["youtube", "instagram"])
@pytest.mark.parametrize(
    "status", ["valid", "foreign", "wrong-chat", "wrong-message", "expired", "restart"]
)
def test_foundation_pinned_locale_model(engine, locale, kind, status):
    """Prototype use after real store validation, NOT activated callback acceptance."""
    now = [datetime.now(UTC)]
    caller, chat_id, message_id = 1, 2, 3
    if kind == "youtube":
        store = InMemoryPendingInteractionStore(clock=lambda: now[0])
        record = store.create(
            owner_user_id=1,
            chat_id=2,
            url="https://example.invalid/video",
            plan=youtube_plan(),
            message_id=3,
            locale=locale,
        )
        token = record.interaction_id
    else:
        store = InstagramChoiceStore(clock=lambda: now[0])
        record = store.create(1, 2, (instagram_plan(),), locale=locale)
        token = record.token
        assert store.bind(token, 3)
    if status == "foreign":
        caller = 9
    elif status == "wrong-chat":
        chat_id = 9
    elif status == "wrong-message":
        message_id = 9
    elif status == "expired":
        now[0] += timedelta(hours=1)
    elif status == "restart":
        store = InMemoryPendingInteractionStore() if kind == "youtube" else InstagramChoiceStore()
    current = "es" if locale != "es" else "en"
    with engine.use_locale(locale_for_event(callback(current, user_id=caller))):
        if kind == "youtube":
            result = store.lookup(
                token, owner_user_id=caller, chat_id=chat_id, message_id=message_id
            )
            validated = (
                result.interaction if result.status is PendingInteractionStatus.FOUND else None
            )
        else:
            validated_plan = store.resolve(token, 0, caller, chat_id, message_id)
            validated = record if validated_plan is not None else None
        if validated is not None:
            with engine.use_locale(validated.locale):
                assert engine.gettext("I18n foundation") == EXPECTED[locale]
        else:
            assert engine.gettext("I18n foundation") == EXPECTED[current]
        assert engine.current_locale == current
    assert engine.current_locale == "en"


@pytest.mark.parametrize("kind", ["youtube", "instagram"])
def test_locale_survives_binding_and_consume_without_payload_change(kind):
    if kind == "youtube":
        store = InMemoryPendingInteractionStore()
        record = store.create(
            owner_user_id=1,
            chat_id=2,
            url="https://example.invalid/video",
            plan=youtube_plan(),
            locale="ru",
        )
        store.set_message_id(record.interaction_id, owner_user_id=1, chat_id=2, message_id=3)
        found = store.consume_terminal(
            record.interaction_id, owner_user_id=1, chat_id=2, message_id=3
        )
        assert found.interaction.locale == "ru" and found.interaction.plan is record.plan
        payload = build_mode_callback_data(record.interaction_id, 0)
        assert parse_callback_data(payload).callback.interaction_id == record.interaction_id
        assert record.expires_at - record.created_at == timedelta(minutes=15)
    else:
        store = InstagramChoiceStore()
        record = store.create(1, 2, (instagram_plan(),), locale="es")
        assert store.bind(record.token, 3)
        assert store._choices[record.token].locale == "es"
        assert store.resolve(record.token, 0, 1, 2, 3, consume=True) is record.plans[0]
        assert store.resolve(record.token, 0, 1, 2, 3) is None


@pytest.mark.parametrize("locale", [None, "", "fr", "ru-RU", 1])
def test_store_rejects_unresolved_locale(locale):
    with pytest.raises(ValueError):
        InMemoryPendingInteractionStore().create(
            owner_user_id=1,
            chat_id=2,
            url="https://example.invalid/video",
            plan=youtube_plan(),
            locale=locale,
        )
    with pytest.raises(ValueError):
        InstagramChoiceStore().create(1, 2, (instagram_plan(),), locale=locale)


def test_default_and_keyword_only_preserve_old_constructors():
    now = datetime.now(UTC)
    record = PendingInteraction(
        "fixture",
        1,
        2,
        3,
        "https://example.invalid/video",
        youtube_plan(),
        now,
        now + timedelta(minutes=15),
        True,
    )
    assert record.consumed and record.locale == "en"
    assert next(f for f in fields(PendingInteraction) if f.name == "locale").kw_only
    assert replace(record, consumed=False).locale == "en"
    assert InstagramChoiceStore().create(1, 2, (instagram_plan(),)).locale == "en"


@pytest.mark.parametrize("locale", ["en", "ru", "es"])
def test_catalogs_and_english_fallback(engine, locale):
    assert set(engine.available_locales) == {"en", "ru", "es"}
    assert engine.gettext("I18n foundation", locale=locale) == EXPECTED[locale]
    assert (
        engine.gettext("Untranslated English source", locale=locale)
        == "Untranslated English source"
    )


@pytest.mark.parametrize("locale", ["en", "ru", "es"])
@pytest.mark.parametrize("count", [0, 1, 2, 5, 11, 21, 22, 25, 101])
def test_real_gettext_plural_and_placeholders(engine, locale, count):
    forms = {
        "en": ("file", "files"),
        "es": ("archivo", "archivos"),
        "ru": ("файл", "файла", "файлов"),
    }
    index = (
        (
            0
            if count % 10 == 1 and count % 100 != 11
            else 1
            if count % 10 in (2, 3, 4) and not 10 <= count % 100 <= 19
            else 2
        )
        if locale == "ru"
        else int(count != 1)
    )
    template = engine.gettext("{count} file", "{count} files", n=count, locale=locale)
    assert {name for _, name, _, _ in Formatter().parse(template) if name} == {"count"}
    assert template.format(count=count) == f"{count} {forms[locale][index]}"


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", ["en", "ru", "es"])
async def test_start_copy_uses_active_context(locale):
    msg = SimpleNamespace(from_user=user(locale), answer=AsyncMock())
    with get_i18n().use_locale(locale):
        await handlers.handle_start(msg)
        msg.answer.assert_awaited_once_with(
            get_i18n().gettext(handlers._START_MESSAGE).format(platforms="YouTube")
        )


def test_dispatcher_installs_localization():
    dispatcher = create_dispatcher()
    routers = [dispatcher, *dispatcher.sub_routers]
    assert any(
        isinstance(middleware, RequestLocaleMiddleware)
        for router in routers
        for observer in router.observers.values()
        for middleware in observer.outer_middleware
    )


def test_pinned_locale_survives_quality_transition():
    options = DownloadOptions(quality_id="fixture-exact")
    quality = QualityChoice(
        QualityTier.LOW,
        QualityOption(
            "fixture-exact", "Synthetic", DownloadMode.VIDEO_WITH_AUDIO, height=480, width=854
        ),
        options,
    )
    plan = replace(
        youtube_plan(),
        mode_choices=(
            ModeChoice(UserChoiceKind.VIDEO, DownloadMode.VIDEO_WITH_AUDIO, None, (quality,)),
        ),
    )
    store = InMemoryPendingInteractionStore()
    original = store.create(
        owner_user_id=1,
        chat_id=2,
        message_id=3,
        url="https://example.invalid/video",
        plan=plan,
        locale="es",
    )
    result = store.transition_to_quality(
        original.interaction_id, owner_user_id=1, chat_id=2, message_id=3, mode_index=0
    )
    assert result.status is PendingInteractionStatus.FOUND
    assert result.interaction.locale == "es"
    assert result.interaction.expires_at == original.expires_at
    assert result.interaction.plan.mode_choices[0].quality_choices[0].final_options is options
