import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.methods import (
    AnswerCallbackQuery,
    EditMessageReplyMarkup,
    EditMessageText,
    SendMessage,
)

import social_video_downloader.handlers as handlers
from social_video_downloader.domain.errors import (
    DownloadFailedError,
    MediaProcessingError,
    MetadataExtractionError,
)
from social_video_downloader.domain.models import (
    DownloadedMedia,
    DownloadMode,
    DownloadOptions,
    MediaMetadata,
    QualityOption,
)
from social_video_downloader.handlers import handle_choice_callback, handle_start, handle_text
from social_video_downloader.infrastructure.telegram_audio import PreparedAudio
from social_video_downloader.services.choice_model import (
    ChoicePlan,
    ChoicePlanState,
    ModeChoice,
    QualityChoice,
    UserChoiceKind,
)
from social_video_downloader.services.quality_tiers import QualityTier
from social_video_downloader.telegram_interactions import (
    InMemoryPendingInteractionStore,
    PendingInteractionStatus,
    PendingInteractionStep,
    build_mode_callback_data,
    build_quality_callback_data,
)
from tests.localization_fixtures import russian_presentation as russian_presentation


@pytest.fixture
def message():
    result = MagicMock()
    result.answer = AsyncMock()
    result.answer_document = AsyncMock()
    result.answer_audio = AsyncMock()
    result.answer_video = AsyncMock()
    result.answer.return_value = SimpleNamespace(message_id=789, edit_text=AsyncMock())
    result.from_user = SimpleNamespace(id=123)
    result.chat = SimpleNamespace(id=456)
    result.message_id = 111
    result.text = ""
    return result


@pytest.fixture(autouse=True)
def audio_preparation(monkeypatch):
    # Handler fakes write placeholder bytes; real FFmpeg is exercised separately.
    prepare = MagicMock(side_effect=lambda path, duration: PreparedAudio(path, None))
    monkeypatch.setattr(handlers, "prepare_telegram_audio", prepare)
    return prepare


class FakeDownloadService:
    def __init__(self, plan: ChoicePlan | None = None, error=None, plan_error=None, duration=None):
        self.plan = plan or direct_plan()
        self.error = error
        self.plan_error = plan_error
        self.calls = []
        self.plan_calls = []
        self.duration = duration

    def create_choice_plan(self, url: str) -> ChoicePlan:
        self.plan_calls.append(url)
        if self.plan_error is not None:
            raise self.plan_error
        return self.plan

    async def create_choice_plan_async(self, url: str) -> ChoicePlan:
        return self.create_choice_plan(url)

    def download(
        self,
        url: str,
        output_dir: Path,
        options: DownloadOptions | None = None,
    ) -> DownloadedMedia:
        self.calls.append((url, output_dir, options))
        if self.error is not None:
            raise self.error

        suffix = (
            ".m4a" if options is not None and options.mode is DownloadMode.AUDIO_ONLY else ".mp4"
        )
        file_path = output_dir / f"example{suffix}"
        file_path.write_bytes(b"test media")
        return DownloadedMedia(
            file_path=file_path,
            metadata=MediaMetadata(
                title="Example video",
                source_url=url,
                platform=handlers.Platform.YOUTUBE,
                duration_seconds=self.duration,
            ),
        )


def quality_choice(quality_id: str, tier: QualityTier) -> QualityChoice:
    return QualityChoice(
        tier=tier,
        quality=QualityOption(
            id=quality_id,
            label=quality_id,
            mode=DownloadMode.VIDEO_WITH_AUDIO,
            width=1280,
            height=720,
        ),
        final_options=DownloadOptions(
            mode=DownloadMode.VIDEO_WITH_AUDIO,
            quality_id=quality_id,
        ),
    )


def direct_plan(options: DownloadOptions | None = None) -> ChoicePlan:
    final_options = options or DownloadOptions(
        mode=DownloadMode.VIDEO_WITH_AUDIO,
        quality_id="direct-quality",
    )
    return ChoicePlan(
        state=ChoicePlanState.DIRECT_DOWNLOAD,
        technical_modes=(DownloadMode.VIDEO_WITH_AUDIO,),
        hidden_modes=(),
        unavailable_choices=(),
        automatic_options=final_options,
        mode_choices=(
            ModeChoice(
                kind=UserChoiceKind.VIDEO,
                mode=DownloadMode.VIDEO_WITH_AUDIO,
                final_options=final_options,
            ),
        ),
    )


def choose_mode_plan() -> ChoicePlan:
    return ChoicePlan(
        state=ChoicePlanState.CHOOSE_MODE,
        technical_modes=(DownloadMode.VIDEO_WITH_AUDIO, DownloadMode.AUDIO_ONLY),
        hidden_modes=(),
        unavailable_choices=(),
        mode_choices=(
            ModeChoice(
                kind=UserChoiceKind.VIDEO,
                mode=DownloadMode.VIDEO_WITH_AUDIO,
                final_options=None,
                quality_choices=(
                    quality_choice("mode-video-low", QualityTier.LOW),
                    quality_choice("mode-video-high", QualityTier.HIGH),
                ),
            ),
            ModeChoice(
                kind=UserChoiceKind.AUDIO,
                mode=DownloadMode.AUDIO_ONLY,
                final_options=DownloadOptions(mode=DownloadMode.AUDIO_ONLY),
            ),
        ),
    )


def terminal_video_mode_plan() -> ChoicePlan:
    video_options = DownloadOptions(
        mode=DownloadMode.VIDEO_WITH_AUDIO,
        quality_id="terminal-video",
    )
    return ChoicePlan(
        state=ChoicePlanState.CHOOSE_MODE,
        technical_modes=(DownloadMode.VIDEO_WITH_AUDIO, DownloadMode.AUDIO_ONLY),
        hidden_modes=(),
        unavailable_choices=(),
        mode_choices=(
            ModeChoice(
                kind=UserChoiceKind.VIDEO,
                mode=DownloadMode.VIDEO_WITH_AUDIO,
                final_options=video_options,
            ),
            ModeChoice(
                kind=UserChoiceKind.AUDIO,
                mode=DownloadMode.AUDIO_ONLY,
                final_options=DownloadOptions(mode=DownloadMode.AUDIO_ONLY),
            ),
        ),
    )


def choose_quality_plan() -> ChoicePlan:
    return ChoicePlan(
        state=ChoicePlanState.CHOOSE_QUALITY,
        technical_modes=(DownloadMode.VIDEO_WITH_AUDIO,),
        hidden_modes=(),
        unavailable_choices=(),
        quality_choices=(
            quality_choice("quality-low", QualityTier.LOW),
            quality_choice("quality-medium", QualityTier.MEDIUM),
        ),
    )


def blocked_plan() -> ChoicePlan:
    return ChoicePlan(
        state=ChoicePlanState.BLOCKED,
        technical_modes=(),
        hidden_modes=(),
        unavailable_choices=(),
        blocked_reason="internal_reason",
    )


def pending_store(id_value: str = "interaction-id") -> InMemoryPendingInteractionStore:
    return InMemoryPendingInteractionStore(id_factory=lambda: id_value)


def callback_query(
    data: str,
    *,
    user_id: int = 123,
    chat_id: int = 456,
    message_id: int = 789,
):
    callback = MagicMock()
    callback.data = data
    callback.from_user = SimpleNamespace(id=user_id)
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.chat = SimpleNamespace(id=chat_id)
    callback.message.message_id = message_id
    callback.message.edit_reply_markup = AsyncMock()
    callback.message.edit_text = AsyncMock()
    callback.message.answer = AsyncMock()
    callback.message.answer_audio = AsyncMock()
    callback.message.answer_video = AsyncMock()
    return callback


async def create_pending_interaction(monkeypatch, plan: ChoicePlan):
    store = pending_store()
    monkeypatch.setattr(handlers, "pending_interaction_store", store)
    return store.create(
        owner_user_id=123,
        chat_id=456,
        message_id=789,
        url="https://www.youtube.com/watch?v=abc",
        plan=plan,
        active_step=PendingInteractionStep.MODE,
        locale="ru",
    )


@pytest.mark.asyncio
async def test_start_explains_current_download_capabilities(message):
    await handle_start(message)

    reply = message.answer.await_args.args[0]
    assert "YouTube" in reply
    assert "Instagram" in reply
    assert "TikTok" in reply
    assert "скачать" in reply.lower()


@pytest.mark.asyncio
async def test_youtube_url_is_downloaded_and_delivered_then_workspace_is_cleaned(
    message, monkeypatch
):
    options = DownloadOptions(
        mode=DownloadMode.VIDEO_WITH_AUDIO,
        quality_id="direct-quality",
    )
    service = FakeDownloadService(plan=direct_plan(options))
    monkeypatch.setattr(handlers, "download_service", service)
    monkeypatch.setattr(
        handlers,
        "pending_interaction_store",
        InMemoryPendingInteractionStore(id_factory=MagicMock(side_effect=AssertionError)),
    )
    monkeypatch.setattr(handlers, "prepare_telegram_video", lambda path: path)
    monkeypatch.setattr(
        handlers,
        "inspect_telegram_video",
        lambda path: {
            "format": {"duration": "72.534"},
            "streams": [
                {
                    "codec_type": "video",
                    "width": 1080,
                    "height": 1920,
                    "side_data_list": [],
                }
            ],
        },
    )
    message.text = "https://www.youtube.com/watch?v=abc"

    await handle_text(message)

    assert len(service.calls) == 1
    assert service.calls[0][0] == "https://www.youtube.com/watch?v=abc"
    assert service.calls[0][2] == options
    message.answer_video.assert_awaited_once()
    uploaded_file = message.answer_video.await_args.args[0]
    assert uploaded_file.path.name == "example.mp4"
    assert message.answer_video.await_args.kwargs["supports_streaming"] is True
    assert message.answer_video.await_args.kwargs["width"] == 1080
    assert message.answer_video.await_args.kwargs["height"] == 1920
    assert message.answer_video.await_args.kwargs["duration"] == 73
    assert not uploaded_file.path.exists()
    assert message.answer.await_args_list[0].args[0] == handlers.tr(
        "Download request accepted. Results appear in separate messages."
    )


@pytest.mark.asyncio
async def test_youtube_choose_mode_creates_pending_interaction_and_mode_keyboard(
    message, monkeypatch
):
    store = pending_store()
    service = FakeDownloadService(plan=choose_mode_plan())
    monkeypatch.setattr(handlers, "download_service", service)
    monkeypatch.setattr(handlers, "pending_interaction_store", store)
    message.text = "https://www.youtube.com/watch?v=abc"

    await handle_text(message)

    assert service.calls == []
    reply_markup = message.answer.return_value.edit_text.await_args.kwargs["reply_markup"]
    buttons = reply_markup.inline_keyboard
    assert [row[0].text for row in buttons] == ["🎬 Видео", "🎵 Аудио"]
    assert "youtube" not in buttons[0][0].callback_data
    assert buttons[0][0].callback_data == build_mode_callback_data("interaction-id", 0)
    pending = store.lookup("interaction-id", owner_user_id=123, chat_id=456, message_id=789)
    assert pending.interaction is not None
    assert pending.interaction.plan is service.plan
    original_message_lookup = store.lookup(
        "interaction-id",
        owner_user_id=123,
        chat_id=456,
        message_id=message.message_id,
    )
    assert original_message_lookup.status is PendingInteractionStatus.WRONG_MESSAGE


@pytest.mark.asyncio
async def test_choice_callback_is_bound_to_keyboard_message_id(message, monkeypatch):
    store = pending_store()
    service = FakeDownloadService(plan=choose_mode_plan())
    download = AsyncMock()
    monkeypatch.setattr(handlers, "download_service", service)
    monkeypatch.setattr(handlers, "pending_interaction_store", store)
    monkeypatch.setattr(handlers, "_download_and_deliver_media", download)
    message.text = "https://www.youtube.com/watch?v=abc"

    await handle_text(message)

    wrong_message_callback = callback_query(
        build_mode_callback_data("interaction-id", 1),
        message_id=message.message_id,
    )
    await handle_choice_callback(wrong_message_callback)
    download.assert_not_awaited()

    keyboard_message_callback = callback_query(
        build_mode_callback_data("interaction-id", 1),
        message_id=789,
    )
    await handle_choice_callback(keyboard_message_callback)

    download.assert_awaited_once()


@pytest.mark.asyncio
async def test_youtube_choose_quality_creates_pending_interaction_and_quality_keyboard(
    message, monkeypatch
):
    store = pending_store()
    service = FakeDownloadService(plan=choose_quality_plan())
    monkeypatch.setattr(handlers, "download_service", service)
    monkeypatch.setattr(handlers, "pending_interaction_store", store)
    message.text = "https://www.youtube.com/watch?v=abc"

    await handle_text(message)

    assert service.calls == []
    reply_markup = message.answer.return_value.edit_text.await_args.kwargs["reply_markup"]
    buttons = reply_markup.inline_keyboard
    assert [row[0].text for row in buttons] == ["Низкое", "Среднее"]
    assert buttons[1][0].callback_data == build_quality_callback_data("interaction-id", 1)
    pending = store.lookup("interaction-id", owner_user_id=123, chat_id=456, message_id=789)
    assert pending.interaction is not None
    assert pending.interaction.plan is service.plan
    original_message_lookup = store.lookup(
        "interaction-id",
        owner_user_id=123,
        chat_id=456,
        message_id=message.message_id,
    )
    assert original_message_lookup.status is PendingInteractionStatus.WRONG_MESSAGE


@pytest.mark.asyncio
async def test_youtube_blocked_plan_does_not_download(message, monkeypatch):
    service = FakeDownloadService(plan=blocked_plan())
    monkeypatch.setattr(handlers, "download_service", service)
    message.text = "https://www.youtube.com/watch?v=abc"

    await handle_text(message)

    assert service.calls == []
    reply = message.answer.await_args.args[0]
    assert "нет безопасного варианта" in reply
    assert "internal_reason" not in reply


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("url", "platform_label"),
    [
        ("https://www.instagram.com/reel/example", "Instagram"),
        ("https://www.tiktok.com/@creator/video/123", "TikTok"),
    ],
)
async def test_non_youtube_platforms_are_recognized_but_not_downloaded(
    message, monkeypatch, url, platform_label
):
    service = FakeDownloadService()
    monkeypatch.setattr(handlers, "download_service", service)
    message.text = url

    await handle_text(message)

    assert service.calls == []
    reply = message.answer.await_args.args[0]
    assert platform_label in reply
    assert "пока не подключено" in reply


@pytest.mark.asyncio
async def test_download_failure_returns_safe_message_and_cleans_workspace(message, monkeypatch):
    service = FakeDownloadService(error=DownloadFailedError("private provider detail"))
    monkeypatch.setattr(handlers, "download_service", service)
    message.text = "https://www.youtube.com/watch?v=abc"

    await handle_text(message)

    assert message.answer_video.await_count == 0
    replies = [call.args[0] for call in message.answer.await_args_list]
    assert any("Не удалось скачать видео" in reply for reply in replies)
    assert all("private provider detail" not in reply for reply in replies)
    assert not service.calls[0][1].exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["", "not a URL", "ftp://youtube.com/watch?v=abc"])
async def test_text_handler_rejects_invalid_links(message, text):
    message.text = text

    await handle_text(message)

    assert "Не удалось распознать ссылку" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_text_handler_rejects_unsupported_platform(message):
    message.text = "https://example.com/video"

    await handle_text(message)

    assert "пока не поддерживается" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_audio_mode_callback_downloads_exact_stored_options(monkeypatch):
    interaction = await create_pending_interaction(monkeypatch, choose_mode_plan())
    download = AsyncMock()
    service = MagicMock()
    service.create_choice_plan = MagicMock(side_effect=AssertionError)
    monkeypatch.setattr(handlers, "download_service", service)
    monkeypatch.setattr(handlers, "_download_and_deliver_media", download)
    callback = callback_query(build_mode_callback_data(interaction.interaction_id, 1))

    await handle_choice_callback(callback)

    download.assert_awaited_once()
    assert download.await_args.args[2] == DownloadOptions(mode=DownloadMode.AUDIO_ONLY)
    service.create_choice_plan.assert_not_called()
    callback.message.edit_text.assert_awaited_once_with(
        handlers.tr("Download request accepted. Results appear in separate messages."),
        reply_markup=None,
    )


@pytest.mark.asyncio
async def test_audio_mode_callback_delivers_audio_without_video_processing(monkeypatch):
    interaction = await create_pending_interaction(monkeypatch, choose_mode_plan())
    service = FakeDownloadService()
    monkeypatch.setattr(handlers, "download_service", service)
    monkeypatch.setattr(
        handlers,
        "prepare_telegram_video",
        MagicMock(side_effect=AssertionError("video preparation should not run")),
    )
    monkeypatch.setattr(
        handlers,
        "inspect_telegram_video",
        MagicMock(side_effect=AssertionError("video probing should not run")),
    )
    callback = callback_query(build_mode_callback_data(interaction.interaction_id, 1))

    await handle_choice_callback(callback)

    assert service.calls[0][2] == DownloadOptions(mode=DownloadMode.AUDIO_ONLY)
    callback.message.answer_audio.assert_awaited_once()
    callback.message.answer_video.assert_not_awaited()


@pytest.mark.asyncio
async def test_video_delivery_still_uses_video_processing(message, monkeypatch):
    service = FakeDownloadService()
    monkeypatch.setattr(handlers, "download_service", service)
    prepare = MagicMock(side_effect=lambda path: path)
    inspect = MagicMock(
        return_value={
            "format": {"duration": "72.534"},
            "streams": [
                {
                    "codec_type": "video",
                    "width": 1080,
                    "height": 1920,
                    "side_data_list": [],
                }
            ],
        }
    )
    monkeypatch.setattr(handlers, "prepare_telegram_video", prepare)
    monkeypatch.setattr(handlers, "inspect_telegram_video", inspect)

    await handlers._download_and_deliver_media(
        message,
        "https://www.youtube.com/watch?v=abc",
        DownloadOptions(mode=DownloadMode.VIDEO_WITH_AUDIO),
    )

    prepare.assert_called_once()
    inspect.assert_called_once()
    message.answer_video.assert_awaited_once()
    message.answer_audio.assert_not_awaited()


@pytest.mark.asyncio
async def test_terminal_callback_acknowledges_before_download(monkeypatch):
    interaction = await create_pending_interaction(monkeypatch, terminal_video_mode_plan())
    callback = callback_query(build_mode_callback_data(interaction.interaction_id, 0))

    async def download_after_ack(*args):
        assert callback.answer.await_count == 1

    monkeypatch.setattr(
        handlers,
        "_download_and_deliver_media",
        AsyncMock(side_effect=download_after_ack),
    )

    await handle_choice_callback(callback)

    callback.answer.assert_awaited_once_with("Начинаю скачивание…")


@pytest.mark.asyncio
async def test_terminal_video_mode_callback_downloads_exact_stored_options(monkeypatch):
    interaction = await create_pending_interaction(monkeypatch, terminal_video_mode_plan())
    download = AsyncMock()
    monkeypatch.setattr(handlers, "_download_and_deliver_media", download)
    callback = callback_query(build_mode_callback_data(interaction.interaction_id, 0))

    await handle_choice_callback(callback)

    download.assert_awaited_once()
    assert download.await_args.args[2] == DownloadOptions(
        mode=DownloadMode.VIDEO_WITH_AUDIO,
        quality_id="terminal-video",
    )


@pytest.mark.asyncio
async def test_video_mode_callback_transitions_to_quality_without_download(monkeypatch):
    interaction = await create_pending_interaction(monkeypatch, choose_mode_plan())
    download = AsyncMock()
    monkeypatch.setattr(handlers, "_download_and_deliver_media", download)
    callback = callback_query(build_mode_callback_data(interaction.interaction_id, 0))

    await handle_choice_callback(callback)

    download.assert_not_awaited()
    callback.message.edit_text.assert_awaited_once()
    assert callback.message.edit_text.await_args.args == ("Выбери качество:",)
    callback.message.edit_reply_markup.assert_not_awaited()
    reply_markup = callback.message.edit_text.await_args.kwargs["reply_markup"]
    assert [row[0].text for row in reply_markup.inline_keyboard] == ["Низкое", "Высокое"]
    result = handlers.pending_interaction_store.lookup(
        interaction.interaction_id,
        owner_user_id=123,
        chat_id=456,
        message_id=789,
    )
    assert result.interaction is not None
    assert result.interaction.selected_mode_index == 0


@pytest.mark.asyncio
async def test_mode_to_quality_callback_acknowledges_before_keyboard_edit(monkeypatch):
    interaction = await create_pending_interaction(monkeypatch, choose_mode_plan())
    callback = callback_query(build_mode_callback_data(interaction.interaction_id, 0))

    async def edit_after_ack(*args, **kwargs):
        assert callback.answer.await_count == 1

    callback.message.edit_text = AsyncMock(side_effect=edit_after_ack)

    await handle_choice_callback(callback)

    callback.answer.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_invalid_mode_index_is_safe_failure(monkeypatch):
    interaction = await create_pending_interaction(monkeypatch, choose_mode_plan())
    download = AsyncMock()
    monkeypatch.setattr(handlers, "_download_and_deliver_media", download)
    callback = callback_query(build_mode_callback_data(interaction.interaction_id, 99))

    await handle_choice_callback(callback)

    download.assert_not_awaited()
    assert "Не удалось обработать выбор" in callback.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_quality_callback_downloads_exact_stored_quality_options(monkeypatch):
    store = pending_store()
    monkeypatch.setattr(handlers, "pending_interaction_store", store)
    interaction = store.create(
        owner_user_id=123,
        chat_id=456,
        message_id=789,
        url="https://www.youtube.com/watch?v=abc",
        plan=choose_quality_plan(),
        active_step=PendingInteractionStep.QUALITY,
        locale="ru",
    )
    download = AsyncMock()
    monkeypatch.setattr(handlers, "_download_and_deliver_media", download)
    callback = callback_query(build_quality_callback_data(interaction.interaction_id, 1))

    await handle_choice_callback(callback)

    download.assert_awaited_once()
    assert download.await_args.args[2] == DownloadOptions(
        mode=DownloadMode.VIDEO_WITH_AUDIO,
        quality_id="quality-medium",
    )


@pytest.mark.asyncio
async def test_quality_callback_respects_selected_mode_context(monkeypatch):
    store = pending_store()
    monkeypatch.setattr(handlers, "pending_interaction_store", store)
    plan = ChoicePlan(
        state=ChoicePlanState.CHOOSE_MODE,
        technical_modes=(DownloadMode.VIDEO_WITH_AUDIO,),
        hidden_modes=(),
        unavailable_choices=(),
        mode_choices=choose_mode_plan().mode_choices,
        quality_choices=(quality_choice("top-level-quality", QualityTier.MEDIUM),),
    )
    interaction = store.create(
        owner_user_id=123,
        chat_id=456,
        message_id=789,
        url="https://www.youtube.com/watch?v=abc",
        plan=plan,
        active_step=PendingInteractionStep.MODE,
        locale="ru",
    )
    store.transition_to_quality(
        interaction.interaction_id,
        owner_user_id=123,
        chat_id=456,
        mode_index=0,
        message_id=789,
    )
    download = AsyncMock()
    monkeypatch.setattr(handlers, "_download_and_deliver_media", download)
    callback = callback_query(build_quality_callback_data(interaction.interaction_id, 1))

    await handle_choice_callback(callback)

    download.assert_awaited_once()
    assert download.await_args.args[2] == DownloadOptions(
        mode=DownloadMode.VIDEO_WITH_AUDIO,
        quality_id="mode-video-high",
    )


@pytest.mark.asyncio
async def test_invalid_quality_index_is_safe_failure(monkeypatch):
    interaction = await create_pending_interaction(monkeypatch, choose_quality_plan())
    download = AsyncMock()
    monkeypatch.setattr(handlers, "_download_and_deliver_media", download)
    callback = callback_query(build_quality_callback_data(interaction.interaction_id, 99))

    await handle_choice_callback(callback)

    download.assert_not_awaited()
    assert "Не удалось обработать выбор" in callback.answer.await_args.args[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        "not-callback",
        "dl:v2:interaction-id:m:0",
        "dl:v1:interaction-id:x:0",
    ],
)
async def test_malformed_or_unsupported_callback_is_safe_failure(monkeypatch, payload):
    download = AsyncMock()
    monkeypatch.setattr(handlers, "_download_and_deliver_media", download)

    await handle_choice_callback(callback_query(payload))

    download.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_callback_is_safe_failure(monkeypatch):
    monkeypatch.setattr(handlers, "pending_interaction_store", pending_store())
    download = AsyncMock()
    monkeypatch.setattr(handlers, "_download_and_deliver_media", download)

    await handle_choice_callback(callback_query(build_mode_callback_data("missing", 0)))

    download.assert_not_awaited()


@pytest.mark.asyncio
async def test_expired_callback_is_safe_failure(monkeypatch):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    current_time = {"value": now}
    store = InMemoryPendingInteractionStore(clock=lambda: current_time["value"])
    monkeypatch.setattr(handlers, "pending_interaction_store", store)
    interaction = store.create(
        owner_user_id=123,
        chat_id=456,
        message_id=789,
        url="https://www.youtube.com/watch?v=abc",
        plan=terminal_video_mode_plan(),
    )
    current_time["value"] = now + timedelta(minutes=15)
    download = AsyncMock()
    monkeypatch.setattr(handlers, "_download_and_deliver_media", download)

    await handle_choice_callback(
        callback_query(build_mode_callback_data(interaction.interaction_id, 0))
    )

    download.assert_not_awaited()


@pytest.mark.asyncio
async def test_wrong_owner_callback_is_safe_failure(monkeypatch):
    interaction = await create_pending_interaction(monkeypatch, terminal_video_mode_plan())
    download = AsyncMock()
    monkeypatch.setattr(handlers, "_download_and_deliver_media", download)

    await handle_choice_callback(
        callback_query(build_mode_callback_data(interaction.interaction_id, 0), user_id=999)
    )

    download.assert_not_awaited()


@pytest.mark.asyncio
async def test_wrong_chat_callback_is_safe_failure(monkeypatch):
    interaction = await create_pending_interaction(monkeypatch, terminal_video_mode_plan())
    download = AsyncMock()
    monkeypatch.setattr(handlers, "_download_and_deliver_media", download)

    await handle_choice_callback(
        callback_query(build_mode_callback_data(interaction.interaction_id, 0), chat_id=999)
    )

    download.assert_not_awaited()


@pytest.mark.asyncio
async def test_wrong_message_callback_is_safe_failure(monkeypatch):
    interaction = await create_pending_interaction(monkeypatch, terminal_video_mode_plan())
    download = AsyncMock()
    monkeypatch.setattr(handlers, "_download_and_deliver_media", download)

    await handle_choice_callback(
        callback_query(build_mode_callback_data(interaction.interaction_id, 0), message_id=999)
    )

    download.assert_not_awaited()


@pytest.mark.asyncio
async def test_consumed_callback_is_safe_failure(monkeypatch):
    interaction = await create_pending_interaction(monkeypatch, terminal_video_mode_plan())
    handlers.pending_interaction_store.consume_terminal(
        interaction.interaction_id,
        owner_user_id=123,
        chat_id=456,
        message_id=789,
    )
    download = AsyncMock()
    monkeypatch.setattr(handlers, "_download_and_deliver_media", download)

    await handle_choice_callback(
        callback_query(build_mode_callback_data(interaction.interaction_id, 0))
    )

    download.assert_not_awaited()


@pytest.mark.asyncio
async def test_double_click_starts_only_one_download(monkeypatch):
    interaction = await create_pending_interaction(monkeypatch, terminal_video_mode_plan())
    download = AsyncMock()
    monkeypatch.setattr(handlers, "_download_and_deliver_media", download)
    first = callback_query(build_mode_callback_data(interaction.interaction_id, 0))
    second = callback_query(build_mode_callback_data(interaction.interaction_id, 0))

    await handle_choice_callback(first)
    await handle_choice_callback(second)

    download.assert_awaited_once()


def telegram_failure(error_type, operation):
    methods = {
        "ack": AnswerCallbackQuery(callback_query_id="test-callback"),
        "edit": EditMessageReplyMarkup(chat_id=456, message_id=789),
        "edit_text": EditMessageText(chat_id=456, message_id=789, text="Choose the quality:"),
        "notify": SendMessage(chat_id=456, text="test response"),
    }
    return error_type(method=methods[operation], message="sensitive diagnostic details")


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [TelegramNetworkError, TelegramBadRequest])
@pytest.mark.parametrize("failure_stage", ["ack", "edit", "both"])
@pytest.mark.parametrize("flow", ["audio", "video", "quality"])
async def test_terminal_api_failures_preserve_exact_download_once(
    monkeypatch, caplog, error_type, failure_stage, flow
):
    plan = choose_quality_plan() if flow == "quality" else terminal_video_mode_plan()
    interaction = await create_pending_interaction(monkeypatch, plan)
    if flow == "quality":
        payload = build_quality_callback_data(interaction.interaction_id, 1)
        options = plan.quality_choices[1].final_options
    else:
        index = 1 if flow == "audio" else 0
        payload = build_mode_callback_data(interaction.interaction_id, index)
        options = plan.mode_choices[index].final_options
    callback = callback_query(payload)
    if failure_stage in {"ack", "both"}:
        callback.answer.side_effect = telegram_failure(error_type, "ack")
    if failure_stage in {"edit", "both"}:
        callback.message.edit_text.side_effect = telegram_failure(error_type, "edit_text")
    download = AsyncMock()
    monkeypatch.setattr(handlers, "_download_and_deliver_media", download)
    service = MagicMock()
    monkeypatch.setattr(handlers, "download_service", service)

    await handle_choice_callback(callback)
    second = callback_query(payload)
    await handle_choice_callback(second)

    download.assert_awaited_once_with(callback.message, interaction.url, options)
    assert download.await_args.args[2] is options
    callback.answer.assert_awaited_once_with("Начинаю скачивание…")
    callback.message.edit_text.assert_awaited_once_with(
        handlers.tr("Download request accepted. Results appear in separate messages."),
        reply_markup=None,
    )
    second.answer.assert_awaited_once_with(handlers.tr(handlers._STALE_CALLBACK_MESSAGE))
    service.create_choice_plan.assert_not_called()
    assert (
        '"category": "telegram_network"'
        if error_type is TelegramNetworkError
        else '"category": "telegram_api"'
    ) in caplog.text
    assert "sensitive diagnostic details" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.asyncio
async def test_concurrent_terminal_callbacks_with_ack_failure_download_once(monkeypatch):
    interaction = await create_pending_interaction(monkeypatch, terminal_video_mode_plan())
    payload = build_mode_callback_data(interaction.interaction_id, 0)
    first, second = callback_query(payload), callback_query(payload)

    async def fail_after_yield(*args):
        await asyncio.sleep(0)
        raise telegram_failure(TelegramNetworkError, "ack")

    first.answer.side_effect = fail_after_yield
    download = AsyncMock()
    monkeypatch.setattr(handlers, "_download_and_deliver_media", download)

    await asyncio.gather(handle_choice_callback(first), handle_choice_callback(second))

    download.assert_awaited_once()
    second.answer.assert_awaited_once_with(handlers.tr(handlers._STALE_CALLBACK_MESSAGE))


@pytest.mark.asyncio
@pytest.mark.parametrize("flow", ["audio", "video"])
async def test_callback_api_failures_do_not_repeat_media_upload(monkeypatch, flow):
    interaction = await create_pending_interaction(monkeypatch, terminal_video_mode_plan())
    service = FakeDownloadService()
    monkeypatch.setattr(handlers, "download_service", service)
    monkeypatch.setattr(handlers, "prepare_telegram_video", lambda path: path)
    monkeypatch.setattr(
        handlers,
        "inspect_telegram_video",
        lambda path: {"streams": [{"codec_type": "video", "width": 640, "height": 360}]},
    )
    payload = build_mode_callback_data(interaction.interaction_id, 1 if flow == "audio" else 0)
    callback = callback_query(payload)
    callback.answer.side_effect = telegram_failure(TelegramNetworkError, "ack")
    callback.message.edit_text.side_effect = telegram_failure(TelegramBadRequest, "edit_text")

    await handle_choice_callback(callback)
    await handle_choice_callback(callback_query(payload))

    assert len(service.calls) == 1
    expected = callback.message.answer_audio if flow == "audio" else callback.message.answer_video
    other = callback.message.answer_video if flow == "audio" else callback.message.answer_audio
    expected.assert_awaited_once()
    other.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_terminal_consume_never_downloads(monkeypatch):
    interaction = await create_pending_interaction(monkeypatch, terminal_video_mode_plan())
    store = handlers.pending_interaction_store
    original_consume = store.consume_terminal

    def competing_consume(*args, **kwargs):
        original_consume(*args, **kwargs)
        return original_consume(*args, **kwargs)

    monkeypatch.setattr(store, "consume_terminal", competing_consume)
    download = AsyncMock()
    monkeypatch.setattr(handlers, "_download_and_deliver_media", download)
    callback = callback_query(build_mode_callback_data(interaction.interaction_id, 0))

    await handle_choice_callback(callback)

    download.assert_not_awaited()
    callback.answer.assert_awaited_once_with("Запрос уже обрабатывается.")
    callback.message.edit_reply_markup.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [TelegramNetworkError, TelegramBadRequest])
@pytest.mark.parametrize("failure_stage", ["ack", "edit", "both"])
async def test_quality_transition_api_failure_keeps_recoverable_state(
    monkeypatch, caplog, error_type, failure_stage
):
    interaction = await create_pending_interaction(monkeypatch, choose_mode_plan())
    payload = build_mode_callback_data(interaction.interaction_id, 0)
    callback = callback_query(payload)
    if failure_stage in {"ack", "both"}:
        callback.answer.side_effect = telegram_failure(error_type, "ack")
    if failure_stage in {"edit", "both"}:
        callback.message.edit_text.side_effect = telegram_failure(error_type, "edit_text")
    download = AsyncMock()
    monkeypatch.setattr(handlers, "_download_and_deliver_media", download)

    await handle_choice_callback(callback)

    result = handlers.pending_interaction_store.lookup(
        interaction.interaction_id, owner_user_id=123, chat_id=456, message_id=789
    )
    assert result.status is PendingInteractionStatus.FOUND
    assert result.interaction.consumed is False
    assert result.interaction.active_step is PendingInteractionStep.QUALITY
    assert result.interaction.selected_mode_index == 0
    download.assert_not_awaited()
    callback.message.edit_text.assert_awaited_once()
    assert "sensitive diagnostic details" not in caplog.text

    # The old mode button can retry, while an already-applied edit is valid too.
    if failure_stage in {"edit", "both"}:
        retry = callback_query(payload)
        await handle_choice_callback(retry)
        retry.message.edit_text.assert_awaited_once()
        download.assert_not_awaited()
    quality = callback_query(build_quality_callback_data(interaction.interaction_id, 1))
    await handle_choice_callback(quality)
    download.assert_awaited_once_with(
        quality.message,
        interaction.url,
        interaction.plan.mode_choices[0].quality_choices[1].final_options,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [TelegramNetworkError, TelegramBadRequest])
@pytest.mark.parametrize("phase", ["planning", "download"])
async def test_metadata_error_notification_failure_is_safe(
    message, monkeypatch, caplog, error_type, phase
):
    original = MetadataExtractionError("private source details")
    service = FakeDownloadService(
        plan_error=original if phase == "planning" else None,
        error=original if phase == "download" else None,
    )
    monkeypatch.setattr(handlers, "download_service", service)
    message.answer.side_effect = telegram_failure(error_type, "notify")
    message.text = "https://www.youtube.com/watch?v=abc"

    if phase == "planning":
        await handle_text(message)
        assert len(service.plan_calls) == 1
        assert not service.calls
    else:
        await handlers._download_and_deliver_media(message, message.text, DownloadOptions())
        assert len(service.calls) == 1

    message.answer.assert_awaited_once_with(handlers._download_error_message(original))
    assert '"category": "metadata_unavailable"' in caplog.text
    assert (
        '"category": "telegram_network"'
        if error_type is TelegramNetworkError
        else '"category": "telegram_api"'
    ) in caplog.text
    assert "private source details" not in caplog.text
    assert "sensitive diagnostic details" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
    message.answer_video.assert_not_awaited()
    message.answer_audio.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [asyncio.CancelledError, RuntimeError])
@pytest.mark.parametrize("stage", ["terminal_ack", "terminal_edit", "mode_ack", "mode_edit"])
async def test_callback_cancellation_and_programming_errors_propagate(monkeypatch, failure, stage):
    plan = choose_mode_plan() if stage.startswith("mode") else terminal_video_mode_plan()
    interaction = await create_pending_interaction(monkeypatch, plan)
    callback = callback_query(build_mode_callback_data(interaction.interaction_id, 0))
    target = callback.answer if stage.endswith("ack") else callback.message.edit_text
    target.side_effect = failure()
    download = AsyncMock()
    monkeypatch.setattr(handlers, "_download_and_deliver_media", download)

    with pytest.raises(failure):
        await handle_choice_callback(callback)

    download.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [asyncio.CancelledError, RuntimeError])
async def test_error_notification_does_not_hide_cancellation_or_programming_errors(
    message, failure
):
    message.answer.side_effect = failure()

    with pytest.raises(failure):
        await handlers._notify_download_error(message, MetadataExtractionError("test failure"))


@pytest.mark.asyncio
@pytest.mark.parametrize("prepared_duration", [73, None])
async def test_audio_delivery_uses_prepared_file_and_duration(
    message, monkeypatch, audio_preparation, prepared_duration
):
    service = FakeDownloadService(duration=72.534)
    monkeypatch.setattr(handlers, "download_service", service)
    prepared_paths = []

    def prepare(path, duration):
        assert duration == 72.534
        output = path.with_name("prepared.m4a")
        output.write_bytes(b"prepared audio")
        prepared_paths.append(output)
        return PreparedAudio(output, prepared_duration)

    audio_preparation.side_effect = prepare

    async def receive_audio(file, **parameters):
        assert Path(file.path) == prepared_paths[0]
        assert Path(file.path).read_bytes() == b"prepared audio"
        assert parameters == {
            "caption": "Example video",
            **({"duration": prepared_duration} if prepared_duration else {}),
        }

    message.answer_audio.side_effect = receive_audio
    await handlers._download_and_deliver_media(
        message,
        "https://www.youtube.com/watch?v=abc",
        DownloadOptions(mode=DownloadMode.AUDIO_ONLY),
    )

    audio_preparation.assert_called_once()
    message.answer_audio.assert_awaited_once()
    message.answer_video.assert_not_awaited()
    assert not prepared_paths[0].parent.exists()


@pytest.mark.asyncio
async def test_audio_preparation_failure_is_safe_and_cleans_workspace(
    message, monkeypatch, audio_preparation
):
    service = FakeDownloadService()
    monkeypatch.setattr(handlers, "download_service", service)
    audio_preparation.side_effect = MediaProcessingError("private preparation details")

    await handlers._download_and_deliver_media(
        message,
        "https://www.youtube.com/watch?v=abc",
        DownloadOptions(mode=DownloadMode.AUDIO_ONLY),
    )

    message.answer_audio.assert_not_awaited()
    message.answer_video.assert_not_awaited()
    assert "private" not in message.answer.await_args.args[0]
    assert not service.calls[0][1].exists()
