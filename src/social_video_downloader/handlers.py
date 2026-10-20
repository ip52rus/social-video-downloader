"""Telegram command and URL-intake handlers."""

import asyncio
import json
import logging
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError, TelegramEntityTooLarge
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from social_video_downloader.domain.errors import (
    DownloaderError,
    DownloadFailedError,
    InvalidMediaURLError,
    MediaProcessingError,
    MetadataExtractionError,
    UnsupportedPlatformError,
)
from social_video_downloader.domain.models import DownloadMode, DownloadOptions, Platform
from social_video_downloader.domain.urls import detect_platform, normalize_media_url
from social_video_downloader.infrastructure.telegram_audio import prepare_telegram_audio
from social_video_downloader.infrastructure.telegram_media import (
    inspect_telegram_video,
    prepare_telegram_video,
    telegram_video_upload_parameters,
)
from social_video_downloader.services.choice_model import (
    ChoicePlan,
    ChoicePlanState,
    ModeChoice,
    QualityChoice,
    UserChoiceKind,
)
from social_video_downloader.services.download import DownloadService
from social_video_downloader.services.quality_tiers import QualityTier
from social_video_downloader.telegram_interactions import (
    CallbackAction,
    CallbackParseStatus,
    InMemoryPendingInteractionStore,
    PendingInteraction,
    PendingInteractionStatus,
    PendingInteractionStep,
    build_mode_callback_data,
    build_quality_callback_data,
    parse_callback_data,
)

logger = logging.getLogger(__name__)
download_service = DownloadService()
pending_interaction_store = InMemoryPendingInteractionStore()

_PLATFORM_LABELS = {
    Platform.YOUTUBE: "YouTube",
    Platform.INSTAGRAM: "Instagram",
    Platform.TIKTOK: "TikTok",
}

_START_MESSAGE = (
    "Привет! Я бот для скачивания видео и другого медиа. "
    "Отправь ссылку на YouTube, Instagram или TikTok. "
    "Сейчас бот умеет скачивать отдельные видео с YouTube. "
    "Загрузка из Instagram и TikTok пока не подключена."
)

_MODE_LABELS = {
    UserChoiceKind.VIDEO: "🎬 Видео",
    UserChoiceKind.AUDIO: "🎵 Аудио",
}

_QUALITY_LABELS = {
    QualityTier.LOW: "Низкое",
    QualityTier.MEDIUM: "Среднее",
    QualityTier.HIGH: "Высокое",
}

_STALE_CALLBACK_MESSAGE = "Выбор больше недоступен. Отправь ссылку ещё раз."
_INVALID_CALLBACK_MESSAGE = "Не удалось обработать выбор. Отправь ссылку ещё раз."
_BLOCKED_CHOICE_MESSAGE = "Для этой ссылки нет безопасного варианта скачивания."


def _download_error_message(error: DownloaderError) -> str:
    """Translate expected domain failures into safe, actionable user messages."""
    if isinstance(error, MetadataExtractionError):
        return "Не удалось получить данные видео. Возможно, оно удалено, закрыто или недоступно."
    if isinstance(error, MediaProcessingError):
        return "Видео скачано не полностью или не удалось обработать. Попробуй другую ссылку."
    if isinstance(error, DownloadFailedError):
        return "Не удалось скачать видео. Попробуй ещё раз позже."
    if isinstance(error, UnsupportedPlatformError):
        return "Скачивание с этой платформы пока не подключено."
    return "Не удалось обработать эту ссылку. Проверь её и попробуй ещё раз."


async def _notify_download_error(message: Message, error: DownloaderError) -> None:
    """Attempt an error response without replacing the original domain failure."""
    try:
        await message.answer(_download_error_message(error))
    except TelegramAPIError as notification_error:
        logger.warning(
            "Download error notification failed: original_error=%s telegram_error=%s",
            type(error).__name__,
            type(notification_error).__name__,
        )


async def handle_start(message: Message, instagram_reels=None, tiktok_videos=None) -> None:
    """Explain current capabilities and how to submit a link."""
    if tiktok_videos is not None and tiktok_videos.allows(message):
        instagram = ", публичный Instagram Reel или /p/" if instagram_reels is not None else ""
        await message.answer(f"Отправь ссылку на YouTube{instagram} или публичное TikTok-видео.")
    elif instagram_reels is None:
        await message.answer(_START_MESSAGE)
    else:
        await message.answer(
            "Отправь ссылку на YouTube, публичный Instagram Reel или /p/. "
            "Из каруселей скачиваются только видео, в исходном порядке; "
            "ссылки на отдельные элементы пока не поддерживаются."
        )


async def handle_text(message: Message, instagram_reels=None, tiktok_videos=None) -> None:
    """Validate a submitted URL, download YouTube media, and deliver the file."""
    submitted_text = (message.text or "").strip()

    if any(character.isspace() for character in submitted_text):
        await message.answer(
            "Не удалось распознать ссылку. Отправь полную HTTP- или HTTPS-ссылку "
            "на YouTube, Instagram или TikTok."
        )
        return

    try:
        normalized_url = normalize_media_url(submitted_text)
        platform = detect_platform(normalized_url)
    except InvalidMediaURLError:
        await message.answer(
            "Не удалось распознать ссылку. Отправь полную HTTP- или HTTPS-ссылку "
            "на YouTube, Instagram или TikTok."
        )
        return
    except UnsupportedPlatformError:
        await message.answer(
            "Эта платформа пока не поддерживается. Отправь ссылку на YouTube, Instagram или TikTok."
        )
        return

    platform_label = _PLATFORM_LABELS[platform]
    if platform is Platform.TIKTOK and tiktok_videos is not None:
        await tiktok_videos.handle(message, submitted_text)
        return
    if platform is Platform.INSTAGRAM and instagram_reels is not None:
        await instagram_reels.handle(message, submitted_text)
        return
    if platform is not Platform.YOUTUBE:
        await message.answer(
            f"Ссылка {platform_label} распознана, но скачивание "
            "с этой платформы пока не подключено."
        )
        return

    try:
        plan = download_service.create_choice_plan(normalized_url)
    except DownloaderError as error:
        logger.warning("Media planning failed: %s", type(error).__name__)
        await _notify_download_error(message, error)
        return
    except Exception:
        logger.exception("Unexpected failure while planning media download")
        await message.answer("Произошла внутренняя ошибка. Попробуй ещё раз позже.")
        return

    if plan.state is ChoicePlanState.DIRECT_DOWNLOAD:
        if plan.automatic_options is None:
            await message.answer(_BLOCKED_CHOICE_MESSAGE)
            return
        await message.answer("Ссылка YouTube распознана. Начинаю скачивание…")
        await _download_and_deliver_media(message, normalized_url, plan.automatic_options)
        return

    if plan.state is ChoicePlanState.CHOOSE_MODE:
        await _send_mode_choices(message, normalized_url, plan)
        return

    if plan.state is ChoicePlanState.CHOOSE_QUALITY:
        await _send_quality_choices(message, normalized_url, plan)
        return

    await message.answer(_BLOCKED_CHOICE_MESSAGE)


async def handle_choice_callback(callback: CallbackQuery) -> None:
    """Resolve mode and quality callbacks against stored pending interaction state."""
    parse_result = parse_callback_data(callback.data or "")
    if parse_result.status is not CallbackParseStatus.VALID or parse_result.callback is None:
        await callback.answer(_INVALID_CALLBACK_MESSAGE)
        return

    message = callback.message
    owner_user_id = callback.from_user.id
    chat_id = _callback_chat_id(callback)
    if message is None or chat_id is None:
        await callback.answer(_STALE_CALLBACK_MESSAGE)
        return

    message_id = getattr(message, "message_id", None)
    parsed_callback = parse_result.callback
    lookup = pending_interaction_store.lookup(
        parsed_callback.interaction_id,
        owner_user_id=owner_user_id,
        chat_id=chat_id,
        message_id=message_id,
    )
    if lookup.status is not PendingInteractionStatus.FOUND or lookup.interaction is None:
        await callback.answer(_callback_status_message(lookup.status))
        return

    if parsed_callback.action is CallbackAction.MODE:
        await _handle_mode_callback(callback, lookup.interaction, parsed_callback.choice_index)
        return

    await _handle_quality_callback(callback, lookup.interaction, parsed_callback.choice_index)


async def _download_and_deliver_media(
    message: Message,
    url: str,
    options: DownloadOptions,
) -> None:
    """Download media with selected options and deliver it through the existing pipeline."""
    try:
        with TemporaryDirectory(prefix="social-video-downloader-") as temporary_directory:
            downloaded = await asyncio.to_thread(
                download_service.download,
                url,
                Path(temporary_directory),
                options,
            )
            if not downloaded.file_path.is_file():
                raise MediaProcessingError("The downloader returned a missing output file.")

            if options.mode is DownloadMode.AUDIO_ONLY:
                audio = await asyncio.to_thread(
                    prepare_telegram_audio,
                    downloaded.file_path,
                    downloaded.metadata.duration_seconds,
                )
                audio_parameters = (
                    {"duration": audio.duration} if audio.duration is not None else {}
                )
                await message.answer_audio(
                    FSInputFile(audio.file_path),
                    caption=downloaded.metadata.title[:1024],
                    **audio_parameters,
                )
                return

            telegram_video = await asyncio.to_thread(
                prepare_telegram_video,
                downloaded.file_path,
            )
            upload_parameters: dict[str, int] = {}

            try:
                probe_data = await asyncio.to_thread(inspect_telegram_video, telegram_video)
                upload_parameters = telegram_video_upload_parameters(probe_data)
                logger.info(
                    "Telegram upload input: python=%s handler_module=%s path=%s "
                    "resolved_path=%s filename=%s file_size=%s upload_parameters=%s probe=%s",
                    sys.executable,
                    __file__,
                    telegram_video,
                    telegram_video.resolve(),
                    telegram_video.name,
                    telegram_video.stat().st_size,
                    upload_parameters,
                    json.dumps(probe_data, ensure_ascii=False, sort_keys=True),
                )
            except Exception:
                # Diagnostics must not prevent a valid media file from being delivered.
                logger.exception(
                    "Could not inspect Telegram upload input; continuing with upload: path=%s",
                    telegram_video,
                )

            sent_message = await message.answer_video(
                FSInputFile(telegram_video),
                caption=downloaded.metadata.title[:1024],
                supports_streaming=True,
                **upload_parameters,
            )

            video = sent_message.video
            if video is not None:
                logger.info(
                    "Telegram video metadata: width=%s height=%s duration=%s "
                    "file_name=%s mime_type=%s file_size=%s",
                    video.width,
                    video.height,
                    video.duration,
                    video.file_name,
                    video.mime_type,
                    video.file_size,
                )
            else:
                logger.warning(
                    "Telegram returned a sent message without video metadata for file %s",
                    telegram_video.name,
                )
    except TelegramEntityTooLarge:
        await message.answer(
            "Файл слишком большой для отправки через Telegram. Попробуй видео меньшего размера."
        )
    except TelegramAPIError:
        logger.exception("Telegram could not deliver the downloaded media file")
        await message.answer("Не удалось отправить файл в Telegram. Попробуй ещё раз позже.")
    except DownloaderError as error:
        logger.warning("Media download failed: %s", type(error).__name__)
        await _notify_download_error(message, error)
    except Exception:
        logger.exception("Unexpected failure while downloading or delivering media")
        await message.answer("Произошла внутренняя ошибка. Попробуй ещё раз позже.")


async def _send_mode_choices(message: Message, url: str, plan: ChoicePlan) -> None:
    owner_user_id = message.from_user.id
    chat_id = message.chat.id
    interaction = pending_interaction_store.create(
        owner_user_id=owner_user_id,
        chat_id=chat_id,
        url=url,
        plan=plan,
        active_step=PendingInteractionStep.MODE,
    )
    sent_message = await message.answer(
        "Выбери формат:",
        reply_markup=_mode_keyboard(interaction.interaction_id, plan.mode_choices),
    )
    pending_interaction_store.set_message_id(
        interaction.interaction_id,
        owner_user_id=owner_user_id,
        chat_id=chat_id,
        message_id=sent_message.message_id,
    )


async def _send_quality_choices(message: Message, url: str, plan: ChoicePlan) -> None:
    owner_user_id = message.from_user.id
    chat_id = message.chat.id
    interaction = pending_interaction_store.create(
        owner_user_id=owner_user_id,
        chat_id=chat_id,
        url=url,
        plan=plan,
        active_step=PendingInteractionStep.QUALITY,
    )
    sent_message = await message.answer(
        "Выбери качество:",
        reply_markup=_quality_keyboard(interaction.interaction_id, plan.quality_choices),
    )
    pending_interaction_store.set_message_id(
        interaction.interaction_id,
        owner_user_id=owner_user_id,
        chat_id=chat_id,
        message_id=sent_message.message_id,
    )


async def _handle_mode_callback(
    callback: CallbackQuery,
    interaction: PendingInteraction,
    mode_index: int,
) -> None:
    if mode_index < 0 or mode_index >= len(interaction.plan.mode_choices):
        await callback.answer(_INVALID_CALLBACK_MESSAGE)
        return

    mode_choice = interaction.plan.mode_choices[mode_index]
    if mode_choice.final_options is not None:
        await _consume_and_download(callback, interaction, mode_choice.final_options)
        return

    if not mode_choice.quality_choices:
        await callback.answer(_INVALID_CALLBACK_MESSAGE)
        return

    transition = pending_interaction_store.transition_to_quality(
        interaction.interaction_id,
        owner_user_id=callback.from_user.id,
        chat_id=interaction.chat_id,
        mode_index=mode_index,
        message_id=getattr(callback.message, "message_id", None),
    )
    if transition.status is not PendingInteractionStatus.FOUND or transition.interaction is None:
        await callback.answer(_callback_status_message(transition.status))
        return

    try:
        await callback.answer()
    except TelegramAPIError as error:
        logger.warning("Quality transition acknowledgement failed: %s", type(error).__name__)
    if callback.message is not None:
        try:
            await callback.message.edit_reply_markup(
                reply_markup=_quality_keyboard(
                    interaction.interaction_id,
                    transition.interaction.plan.mode_choices[mode_index].quality_choices,
                )
            )
        except TelegramAPIError as error:
            # Keep the state: the edit may have reached Telegram despite a lost response.
            # An old mode button can safely retry this same nonterminal transition.
            logger.warning("Quality keyboard edit failed: %s", type(error).__name__)


async def _handle_quality_callback(
    callback: CallbackQuery,
    interaction: PendingInteraction,
    quality_index: int,
) -> None:
    quality_choices = _active_quality_choices(interaction)
    if quality_index < 0 or quality_index >= len(quality_choices):
        await callback.answer(_INVALID_CALLBACK_MESSAGE)
        return

    await _consume_and_download(
        callback,
        interaction,
        quality_choices[quality_index].final_options,
    )


async def _consume_and_download(
    callback: CallbackQuery,
    interaction: PendingInteraction,
    options: DownloadOptions,
) -> None:
    consume = pending_interaction_store.consume_terminal(
        interaction.interaction_id,
        owner_user_id=callback.from_user.id,
        chat_id=interaction.chat_id,
        message_id=getattr(callback.message, "message_id", None),
    )
    if consume.status is not PendingInteractionStatus.FOUND:
        await callback.answer(_callback_status_message(consume.status))
        return

    pending_interaction_store.remove(interaction.interaction_id)
    try:
        await callback.answer("Начинаю скачивание…")
    except TelegramAPIError as error:
        logger.warning("Terminal callback acknowledgement failed: %s", type(error).__name__)
    if callback.message is not None:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except TelegramAPIError as error:
            logger.warning("Terminal keyboard cleanup failed: %s", type(error).__name__)
        await _download_and_deliver_media(callback.message, interaction.url, options)


def _mode_keyboard(
    interaction_id: str,
    mode_choices: tuple[ModeChoice, ...],
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_MODE_LABELS[choice.kind],
                    callback_data=build_mode_callback_data(interaction_id, index),
                )
            ]
            for index, choice in enumerate(mode_choices)
        ]
    )


def _quality_keyboard(
    interaction_id: str,
    quality_choices: tuple[QualityChoice, ...],
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_QUALITY_LABELS[choice.tier],
                    callback_data=build_quality_callback_data(interaction_id, index),
                )
            ]
            for index, choice in enumerate(quality_choices)
        ]
    )


def _active_quality_choices(interaction: PendingInteraction) -> tuple[QualityChoice, ...]:
    if interaction.selected_mode_index is None:
        return interaction.plan.quality_choices
    if interaction.selected_mode_index >= len(interaction.plan.mode_choices):
        return ()
    return interaction.plan.mode_choices[interaction.selected_mode_index].quality_choices


def _callback_chat_id(callback: CallbackQuery) -> int | None:
    message = callback.message
    chat = getattr(message, "chat", None)
    chat_id = getattr(chat, "id", None)
    return chat_id if isinstance(chat_id, int) else None


def _callback_status_message(status: PendingInteractionStatus) -> str:
    if status is PendingInteractionStatus.CONSUMED:
        return "Запрос уже обрабатывается."
    return _STALE_CALLBACK_MESSAGE


def create_router() -> Router:
    """Fresh registration state for each dispatcher; callback behavior is unchanged."""
    router = Router(name="telegram-handlers")
    router.message.register(handle_start, CommandStart())
    router.message.register(handle_text, F.text)
    router.callback_query.register(handle_choice_callback, F.data)
    return router
