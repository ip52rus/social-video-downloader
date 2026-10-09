"""Telegram command and URL-intake handlers."""

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from social_video_downloader.domain.errors import InvalidMediaURLError, UnsupportedPlatformError
from social_video_downloader.domain.models import Platform
from social_video_downloader.domain.urls import detect_platform, normalize_media_url

router = Router(name="telegram-handlers")

_PLATFORM_LABELS = {
    Platform.YOUTUBE: "YouTube",
    Platform.INSTAGRAM: "Instagram",
    Platform.TIKTOK: "TikTok",
}

_START_MESSAGE = (
    "Привет! Я бот для скачивания видео и другого медиа. "
    "Отправь ссылку на YouTube, Instagram или TikTok. "
    "Сейчас бот умеет проверять ссылки, а скачивание будет подключено следующим этапом."
)


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    """Explain the current bot capabilities and how to submit a link."""
    await message.answer(_START_MESSAGE)


@router.message(F.text)
async def handle_text(message: Message) -> None:
    """Validate a submitted URL and acknowledge its recognized platform."""
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
            "Эта платформа пока не поддерживается. Отправь ссылку на YouTube, "
            "Instagram или TikTok."
        )
        return

    platform_label = _PLATFORM_LABELS[platform]
    await message.answer(
        f"Ссылка {platform_label} распознана. Скачивание пока не подключено — "
        "это появится в следующем этапе разработки."
    )
