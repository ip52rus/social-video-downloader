"""Telegram command and URL-intake handlers."""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError, TelegramEntityTooLarge
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, Message

from social_video_downloader.domain.errors import (
    DownloaderError,
    DownloadFailedError,
    InvalidMediaURLError,
    MediaProcessingError,
    MetadataExtractionError,
    UnsupportedPlatformError,
)
from social_video_downloader.domain.models import Platform
from social_video_downloader.domain.urls import detect_platform, normalize_media_url
from social_video_downloader.infrastructure.telegram_media import (
    inspect_telegram_video,
    prepare_telegram_video,
    telegram_video_upload_parameters,
)
from social_video_downloader.services.download import DownloadService

logger = logging.getLogger(__name__)
router = Router(name="telegram-handlers")
download_service = DownloadService()


def _prepare_video_for_telegram(path: Path) -> Path:
    """Optionally bypass transcoding for a controlled compatibility test."""
    setting = os.getenv("TELEGRAM_VIDEO_TRANSCODING", "true").strip().lower()
    if setting in {"0", "false", "no", "off"}:
        logger.warning(
            "Telegram video transcoding disabled; uploading original downloaded file: %s",
            path,
        )
        return path
    return prepare_telegram_video(path)


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


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    """Explain current capabilities and how to submit a link."""
    await message.answer(_START_MESSAGE)


@router.message(F.text)
async def handle_text(message: Message) -> None:
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
    if platform is not Platform.YOUTUBE:
        await message.answer(
            f"Ссылка {platform_label} распознана, но скачивание "
            "с этой платформы пока не подключено."
        )
        return

    await message.answer("Ссылка YouTube распознана. Начинаю скачивание…")

    try:
        with TemporaryDirectory(prefix="social-video-downloader-") as temporary_directory:
            downloaded = await asyncio.to_thread(
                download_service.download,
                normalized_url,
                Path(temporary_directory),
            )
            if not downloaded.file_path.is_file():
                raise MediaProcessingError("The downloader returned a missing output file.")

            telegram_video = await asyncio.to_thread(
                _prepare_video_for_telegram,
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
        await message.answer(_download_error_message(error))
    except Exception:
        logger.exception("Unexpected failure while downloading or delivering media")
        await message.answer("Произошла внутренняя ошибка. Попробуй ещё раз позже.")
