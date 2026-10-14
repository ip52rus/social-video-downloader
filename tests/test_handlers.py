from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import social_video_downloader.handlers as handlers
from social_video_downloader.domain.errors import DownloadFailedError
from social_video_downloader.domain.models import (
    DownloadedMedia,
    DownloadMode,
    DownloadOptions,
    MediaMetadata,
    QualityOption,
)
from social_video_downloader.handlers import handle_choice_callback, handle_start, handle_text
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


@pytest.fixture
def message():
    result = MagicMock()
    result.answer = AsyncMock()
    result.answer_document = AsyncMock()
    result.answer_audio = AsyncMock()
    result.answer_video = AsyncMock()
    result.answer.return_value = SimpleNamespace(message_id=789)
    result.from_user = SimpleNamespace(id=123)
    result.chat = SimpleNamespace(id=456)
    result.message_id = 111
    result.text = ""
    return result


class FakeDownloadService:
    def __init__(self, plan: ChoicePlan | None = None, error=None, plan_error=None):
        self.plan = plan or direct_plan()
        self.error = error
        self.plan_error = plan_error
        self.calls = []
        self.plan_calls = []

    def create_choice_plan(self, url: str) -> ChoicePlan:
        self.plan_calls.append(url)
        if self.plan_error is not None:
            raise self.plan_error
        return self.plan

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
    )


@pytest.mark.asyncio
async def test_start_explains_current_download_capabilities(message):
    await handle_start(message)

    reply = message.answer.await_args.args[0]
    assert "YouTube" in reply
    assert "Instagram" in reply
    assert "TikTok" in reply
    assert "скачивать" in reply.lower()


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
    assert message.answer.await_args_list[0].args[0].startswith("Ссылка YouTube распознана")


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
    reply_markup = message.answer.await_args.kwargs["reply_markup"]
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
    reply_markup = message.answer.await_args.kwargs["reply_markup"]
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
    callback.message.edit_reply_markup.assert_awaited_once_with(reply_markup=None)


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
    callback.message.edit_reply_markup.assert_awaited_once()
    reply_markup = callback.message.edit_reply_markup.await_args.kwargs["reply_markup"]
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

    callback.message.edit_reply_markup = AsyncMock(side_effect=edit_after_ack)

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
