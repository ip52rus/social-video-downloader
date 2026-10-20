"""aiogram bot construction and polling lifecycle."""

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from social_video_downloader.config import Settings
from social_video_downloader.handlers import create_router
from social_video_downloader.logging_config import configure_logging


def create_bot(settings: Settings) -> Bot:
    """Create the Telegram bot without starting network activity."""
    if settings.telegram_api_base_url is None:
        return Bot(token=settings.telegram_bot_token)

    api = TelegramAPIServer.from_base(settings.telegram_api_base_url, is_local=True)
    session = AiohttpSession(
        api=api,
        timeout=settings.telegram_api_timeout_seconds,
    )
    return Bot(token=settings.telegram_bot_token, session=session)


def create_dispatcher(
    settings: Settings | None = None, *, instagram_reels=None, tiktok_videos=None
) -> Dispatcher:
    """Create the root dispatcher and register Telegram handlers."""
    dispatcher = Dispatcher()
    if settings is not None and settings.tiktok_telegram_enabled:
        from social_video_downloader.telegram_tiktok import TelegramTikTokHandler

        dispatcher["tiktok_videos"] = (
            tiktok_videos
            if tiktok_videos is not None
            else TelegramTikTokHandler(max_concurrent=settings.tiktok_max_concurrent_operations)
        )
    if settings is not None and settings.instagram_telegram_enabled:
        from social_video_downloader.telegram_instagram import InstagramReelHandler

        dispatcher["instagram_reels"] = (
            instagram_reels if instagram_reels is not None else InstagramReelHandler()
        )
    dispatcher.include_router(create_router())
    return dispatcher


async def run_bot(settings: Settings) -> None:
    """Start polling and close the bot session when polling stops."""
    bot = create_bot(settings)
    dispatcher = create_dispatcher(settings)
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


def main() -> None:
    """Load configuration, configure logs, and run the Telegram polling loop."""
    settings = Settings.from_env()
    configure_logging(settings)
    asyncio.run(run_bot(settings))
