"""aiogram bot construction and polling lifecycle."""

import asyncio

from aiogram import Bot, Dispatcher

from social_video_downloader.config import Settings
from social_video_downloader.logging_config import configure_logging


def create_bot(settings: Settings) -> Bot:
    """Create the Telegram bot without starting network activity."""
    return Bot(token=settings.telegram_bot_token)


def create_dispatcher() -> Dispatcher:
    """Create the root dispatcher; feature routers are registered in later steps."""
    return Dispatcher()


async def run_bot(settings: Settings) -> None:
    """Start polling and close the bot session when polling stops."""
    bot = create_bot(settings)
    dispatcher = create_dispatcher()
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


def main() -> None:
    """Load configuration, configure logs, and run the Telegram polling loop."""
    settings = Settings.from_env()
    configure_logging(settings)
    asyncio.run(run_bot(settings))
