"""Integration tests for the downloader components working together."""

from pathlib import Path

import pytest

from social_video_downloader.domain.errors import (
    InvalidMediaURLError,
    UnsupportedDownloadModeError,
    UnsupportedPlatformError,
    UnsupportedQualityError,
)
from social_video_downloader.domain.models import (
    DownloadedMedia,
    DownloadMode,
    DownloadOptions,
    MediaMetadata,
    Platform,
    QualityOption,
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

    def get_supported_modes(self, url: str) -> tuple[DownloadMode, ...]:
        if not self.can_handle(url):
            return ()
        return (
            DownloadMode.VIDEO_WITH_AUDIO,
            DownloadMode.VIDEO_ONLY,
            DownloadMode.AUDIO_ONLY,
        )

    def get_available_qualities(
        self,
        url: str,
        mode: DownloadMode,
    ) -> tuple[QualityOption, ...]:
        if not self.can_handle(url) or mode not in self.get_supported_modes(url):
            return ()

        if mode is DownloadMode.AUDIO_ONLY:
            return (
                QualityOption(
                    id="audio-192",
                    label="192 kbps",
                    mode=mode,
                    bitrate_kbps=192,
                ),
            )

        return (
            QualityOption(
                id="video-720",
                label="720p",
                mode=mode,
                height=720,
            ),
        )

    def download(
        self,
        url: str,
        output_dir: Path,
        options: DownloadOptions | None = None,
    ) -> DownloadedMedia:
        if options is None:
            options = DownloadOptions()
        supported_modes = self.get_supported_modes(url)
        if options.mode not in supported_modes:
            raise UnsupportedDownloadModeError("The requested mode is unsupported.")

        available_qualities = self.get_available_qualities(url, options.mode)
        if options.quality_id is not None and not any(
            quality.id == options.quality_id for quality in available_qualities
        ):
            raise UnsupportedQualityError("The requested quality is unavailable.")

        metadata = self.extract_metadata(url)
        extension = "mp3" if options.mode is DownloadMode.AUDIO_ONLY else "mp4"
        filename = safe_filename(metadata.title, extension=extension)
        file_path = output_dir / filename
        file_path.write_bytes(options.mode.value.encode("utf-8"))

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
        assert downloaded.file_path.read_bytes() == b"video_with_audio"

    assert not workspace_path.exists()


def test_integration_provider_supports_audio_only(tmp_path: Path) -> None:
    provider: MediaProvider = FakeYouTubeProvider()
    url = "https://youtu.be/abc123"
    options = DownloadOptions(
        mode=DownloadMode.AUDIO_ONLY,
        quality_id="audio-192",
    )

    downloaded = provider.download(url, tmp_path, options)

    assert downloaded.file_path.suffix == ".mp3"
    assert downloaded.file_path.read_bytes() == b"audio_only"


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


def test_provider_rejects_unknown_quality(tmp_path: Path) -> None:
    provider: MediaProvider = FakeYouTubeProvider()

    with pytest.raises(UnsupportedQualityError):
        provider.download(
            "https://youtu.be/abc123",
            tmp_path,
            DownloadOptions(quality_id="not-available"),
        )
