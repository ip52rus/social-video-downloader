"""Telegram command and URL-intake handlers."""

import asyncio
import logging
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
from social_video_downloader.infrastructure.telegram_media import prepare_telegram_video
from social_video_downloader.services.download import DownloadService

logger = logging.getLogger(__name__)
router = Router(name="telegram-handlers")
download_service = DownloadService()

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
                prepare_telegram_video,
                downloaded.file_path,
            )
            sent_message = await message.answer_video(
                FSInputFile(telegram_video),
                caption=downloaded.metadata.title[:1024],
                supports_streaming=True,
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
