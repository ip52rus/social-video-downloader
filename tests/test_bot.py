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
        assert bot.session.api.base == "https://api.telegram.org/bot{token}/{method}"
    finally:
        await bot.session.close()


@pytest.mark.asyncio
async def test_create_bot_uses_configured_local_api_endpoint_and_timeout():
    settings = Settings.from_env(
        {
            "TELEGRAM_BOT_TOKEN": "123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
            "TELEGRAM_API_BASE_URL": "http://127.0.0.1:8081",
            "TELEGRAM_API_TIMEOUT_SECONDS": "2400",
        }
    )

    bot = create_bot(settings)
    try:
        assert isinstance(bot, Bot)
        assert bot.session.api.base == "http://127.0.0.1:8081/bot{token}/{method}"
        assert bot.session.api.is_local is True
        assert bot.session.timeout == 2400
    finally:
        await bot.session.close()


def test_create_dispatcher_returns_aiogram_dispatcher():
    assert isinstance(create_dispatcher(), Dispatcher)
