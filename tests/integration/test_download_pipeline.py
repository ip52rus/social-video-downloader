"""Integration tests for the downloader components working together."""

from pathlib import Path

import pytest

from social_video_downloader.domain.errors import (
    InvalidMediaURLError,
    UnsupportedPlatformError,
)
from social_video_downloader.domain.models import (
    DownloadedMedia,
    MediaMetadata,
    Platform,
)
from social_video_downloader.domain.urls import detect_platform, normalize_media_url
from social_video_downloader.infrastructure.filenames import safe_filename
from social_video_downloader.infrastructure.workspace import temporary_workspace
from social_video_downloader.providers.base import MediaProvider


class FakeYouTubeProvider:
    """Deterministic provider used to exercise the downloader components."""

    @property
    def platform(self) -> Platform:
        return Platform.YOUTUBE

    def can_handle(self, url: str) -> bool:
        try:
            return detect_platform(url) is self.platform
        except (InvalidMediaURLError, UnsupportedPlatformError):
            return False

    def extract_metadata(self, url: str) -> MediaMetadata:
        normalized_url = normalize_media_url(url)
        if not self.can_handle(normalized_url):
            raise UnsupportedPlatformError("The test provider only supports YouTube.")

        return MediaMetadata(
            title="Тестовое видео",
            source_url=normalized_url,
            platform=self.platform,
            duration_seconds=12.5,
            uploader="Integration Test",
        )

    def download(self, url: str, output_dir: Path) -> DownloadedMedia:
        metadata = self.extract_metadata(url)
        file_path = output_dir / safe_filename(metadata.title, extension="mp4")
        file_path.write_bytes(b"fake media payload")

        return DownloadedMedia(file_path=file_path, metadata=metadata)


def test_url_flows_through_provider_and_temporary_workspace() -> None:
    raw_url = "  youtu.be/abc123?si=demo#chapter  "
    normalized_url = normalize_media_url(raw_url)

    assert normalized_url == "https://youtu.be/abc123?si=demo"
    assert detect_platform(normalized_url) is Platform.YOUTUBE

    provider: MediaProvider = FakeYouTubeProvider()
    assert provider.can_handle(normalized_url)

    workspace_path: Path
    with temporary_workspace() as workspace:
        workspace_path = workspace

        metadata = provider.extract_metadata(normalized_url)
        assert metadata.source_url == normalized_url
        assert metadata.platform is Platform.YOUTUBE
        assert metadata.duration_seconds == 12.5

        downloaded = provider.download(normalized_url, workspace)
        assert downloaded.metadata == metadata
        assert downloaded.file_path == workspace / "Тестовое видео.mp4"
        assert downloaded.file_path.is_file()
        assert downloaded.file_path.read_bytes() == b"fake media payload"

    assert not workspace_path.exists()


@pytest.mark.parametrize(
    "url",
    [
        "https://example.org/video",
        "https://[invalid",
    ],
)
def test_provider_rejects_unsupported_or_invalid_urls(url: str) -> None:
    provider: MediaProvider = FakeYouTubeProvider()

    assert not provider.can_handle(url)
