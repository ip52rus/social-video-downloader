import pytest
from aiogram import Bot, Dispatcher

from social_video_downloader.bot import create_bot, create_dispatcher
from social_video_downloader.config import Settings


@pytest.mark.asyncio
async def test_create_bot_uses_configured_token_and_closes_session():
    settings = Settings.from_env(
        {"TELEGRAM_BOT_TOKEN": "123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi"}
    )

    bot = create_bot(settings)
    try:
        assert isinstance(bot, Bot)
        assert bot.token == settings.telegram_bot_token
    finally:
        await bot.session.close()


def test_create_dispatcher_returns_aiogram_dispatcher():
    assert isinstance(create_dispatcher(), Dispatcher)
