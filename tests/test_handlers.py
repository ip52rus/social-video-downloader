from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

import social_video_downloader.handlers as handlers
from social_video_downloader.domain.errors import DownloadFailedError
from social_video_downloader.domain.models import DownloadedMedia, MediaMetadata
from social_video_downloader.handlers import handle_start, handle_text


@pytest.fixture
def message():
    result = MagicMock()
    result.answer = AsyncMock()
    result.answer_document = AsyncMock()
    result.answer_video = AsyncMock()
    result.text = ""
    return result


class FakeDownloadService:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def download(self, url: str, output_dir: Path) -> DownloadedMedia:
        self.calls.append((url, output_dir))
        if self.error is not None:
            raise self.error

        file_path = output_dir / "example.mp4"
        file_path.write_bytes(b"test media")
        return DownloadedMedia(
            file_path=file_path,
            metadata=MediaMetadata(
                title="Example video",
                source_url=url,
                platform=handlers.Platform.YOUTUBE,
            ),
        )


@pytest.mark.asyncio
async def test_start_explains_current_download_capabilities(message):
    await handle_start(message)

    reply = message.answer.await_args.args[0]
    assert "YouTube" in reply
    assert "Instagram" in reply
    assert "TikTok" in reply
    assert "скачивать" in reply.lower()


@pytest.mark.asyncio
async def test_youtube_url_is_downloaded_and_delivered_then_workspace_is_cleaned(
    message, monkeypatch
):
    service = FakeDownloadService()
    monkeypatch.setattr(handlers, "download_service", service)
    monkeypatch.setattr(handlers, "prepare_telegram_video", lambda path: path)
    monkeypatch.setattr(
        handlers,
        "inspect_telegram_video",
        lambda path: {
            "format": {"duration": "72.534"},
            "streams": [
                {
                    "codec_type": "video",
                    "width": 1080,
                    "height": 1920,
                    "side_data_list": [],
                }
            ],
        },
    )
    message.text = "https://www.youtube.com/watch?v=abc"

    await handle_text(message)

    assert len(service.calls) == 1
    assert service.calls[0][0] == "https://www.youtube.com/watch?v=abc"
    message.answer_video.assert_awaited_once()
    uploaded_file = message.answer_video.await_args.args[0]
    assert uploaded_file.path.name == "example.mp4"
    assert message.answer_video.await_args.kwargs["supports_streaming"] is True
    assert message.answer_video.await_args.kwargs["width"] == 1080
    assert message.answer_video.await_args.kwargs["height"] == 1920
    assert message.answer_video.await_args.kwargs["duration"] == 73
    assert not uploaded_file.path.exists()
    assert message.answer.await_args_list[0].args[0].startswith("Ссылка YouTube распознана")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("url", "platform_label"),
    [
        ("https://www.instagram.com/reel/example", "Instagram"),
        ("https://www.tiktok.com/@creator/video/123", "TikTok"),
    ],
)
async def test_non_youtube_platforms_are_recognized_but_not_downloaded(
    message, monkeypatch, url, platform_label
):
    service = FakeDownloadService()
    monkeypatch.setattr(handlers, "download_service", service)
    message.text = url

    await handle_text(message)

    assert service.calls == []
    reply = message.answer.await_args.args[0]
    assert platform_label in reply
    assert "пока не подключено" in reply


@pytest.mark.asyncio
async def test_download_failure_returns_safe_message_and_cleans_workspace(message, monkeypatch):
    service = FakeDownloadService(error=DownloadFailedError("private provider detail"))
    monkeypatch.setattr(handlers, "download_service", service)
    message.text = "https://www.youtube.com/watch?v=abc"

    await handle_text(message)

    assert message.answer_video.await_count == 0
    replies = [call.args[0] for call in message.answer.await_args_list]
    assert any("Не удалось скачать видео" in reply for reply in replies)
    assert all("private provider detail" not in reply for reply in replies)
    assert not service.calls[0][1].exists()


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



def test_video_preparation_can_be_disabled_for_controlled_test(monkeypatch, tmp_path):
    source = tmp_path / "original.mp4"
    source.write_bytes(b"original")
    monkeypatch.setenv("TELEGRAM_VIDEO_TRANSCODING", "false")
    monkeypatch.setattr(
        handlers,
        "prepare_telegram_video",
        lambda path: pytest.fail("transcoding must be bypassed"),
    )

    assert handlers._prepare_video_for_telegram(source) == source
