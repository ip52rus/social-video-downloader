from pathlib import Path
from unittest.mock import MagicMock

import pytest

from social_video_downloader.domain.errors import UnsupportedPlatformError
from social_video_downloader.domain.models import (
    DownloadedMedia,
    DownloadMode,
    DownloadOptions,
    MediaMetadata,
    Platform,
)
from social_video_downloader.services.download import DownloadService


def test_service_normalizes_url_and_delegates_to_matching_provider(tmp_path: Path):
    provider = MagicMock()
    provider.platform = Platform.YOUTUBE
    expected = DownloadedMedia(
        file_path=tmp_path / "video.mp4",
        metadata=MediaMetadata(
            title="Example",
            source_url="https://youtu.be/example",
            platform=Platform.YOUTUBE,
        ),
    )
    provider.download.return_value = expected
    service = DownloadService([provider])
    options = DownloadOptions(mode=DownloadMode.VIDEO_ONLY)

    result = service.download("youtu.be/example", tmp_path, options)

    assert result is expected
    provider.download.assert_called_once_with("https://youtu.be/example", tmp_path, options)


def test_service_rejects_recognized_platform_without_a_provider(tmp_path: Path):
    service = DownloadService()

    with pytest.raises(UnsupportedPlatformError):
        service.download("https://www.instagram.com/reel/example", tmp_path)


def test_service_rejects_unknown_domains(tmp_path: Path):
    service = DownloadService()

    with pytest.raises(UnsupportedPlatformError):
        service.download("https://example.com/video", tmp_path)
