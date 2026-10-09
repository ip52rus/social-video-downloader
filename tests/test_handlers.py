from unittest.mock import AsyncMock, MagicMock

import pytest

from social_video_downloader.handlers import handle_start, handle_text


@pytest.fixture
def message():
    result = MagicMock()
    result.answer = AsyncMock()
    result.text = ""
    return result


@pytest.mark.asyncio
async def test_start_explains_how_to_submit_a_link(message):
    await handle_start(message)

    reply = message.answer.await_args.args[0]
    assert "YouTube" in reply
    assert "Instagram" in reply
    assert "TikTok" in reply
    assert "скачивание" in reply.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("url", "platform_label"),
    [
        ("https://www.youtube.com/watch?v=abc", "YouTube"),
        ("https://www.instagram.com/reel/example", "Instagram"),
        ("https://www.tiktok.com/@creator/video/123", "TikTok"),
        ("youtu.be/abc?si=share", "YouTube"),
    ],
)
async def test_text_handler_recognizes_supported_platforms(message, url, platform_label):
    message.text = url

    await handle_text(message)

    reply = message.answer.await_args.args[0]
    assert platform_label in reply
    assert "Скачивание пока не подключено" in reply


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
