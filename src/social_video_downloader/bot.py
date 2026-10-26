"""aiogram bot construction and polling lifecycle."""

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from social_video_downloader import handlers
from social_video_downloader.config import Settings
from social_video_downloader.download_protection import (
    DownloadAdmission,
    DownloadProtectionMiddleware,
)
from social_video_downloader.handlers import create_router
from social_video_downloader.logging_config import configure_logging
from social_video_downloader.operation_logging import Operation, report_failure
from social_video_downloader.telegram_i18n import RequestLocaleMiddleware, get_i18n


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
    settings: Settings | None = None,
    *,
    instagram_reels=None,
    tiktok_videos=None,
    download_admission=None,
) -> Dispatcher:
    """Create the root dispatcher and register Telegram handlers."""
    dispatcher = Dispatcher()
    admission = download_admission or DownloadAdmission(
        **(
            {
                "limits": settings.download_limits,
                "max_active": settings.download_max_active_requests,
                "link_interval": settings.download_link_interval_seconds,
                "max_pending": settings.download_max_pending_requests,
                "notice_interval": settings.download_notice_interval_seconds,
                "youtube_limits": settings.youtube_limits,
            }
            if settings
            else {}
        )
    )
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
            instagram_reels
            if instagram_reels is not None
            else InstagramReelHandler(limits=admission.limits)
        )
    router = create_router()
    localization = RequestLocaleMiddleware(get_i18n())
    localization.setup(router, exclude={"update"})
    protection = DownloadProtectionMiddleware(
        admission,
        handlers.validated_download_callback,
    )
    router.message.middleware(protection)
    router.callback_query.middleware(protection)
    dispatcher.include_router(router)
    return dispatcher


async def run_bot(settings: Settings) -> None:
    """Start polling and close the bot session when polling stops."""
    bot = create_bot(settings)
    dispatcher = create_dispatcher(settings)
    with Operation("service", "polling") as operation:
        try:
            with operation.at("polling"):
                await dispatcher.start_polling(bot)
        finally:
            with operation.at("session_close"):
                await bot.session.close()


def main() -> None:
    """Load configuration, configure logs, and run the Telegram polling loop."""
    try:
        settings = Settings.from_env()
        configure_logging(settings)
        asyncio.run(run_bot(settings))
    except Exception as error:
        report_failure("service", "unknown", error)
        raise SystemExit(1) from None
