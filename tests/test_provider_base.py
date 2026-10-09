"""Tests for the common media provider contract."""

from pathlib import Path

from social_video_downloader.domain.errors import (
    UnsupportedDownloadModeError,
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
from social_video_downloader.providers.base import MediaProvider


class FakeProvider:
    """Test provider used to verify the common provider contract."""

    @property
    def platform(self) -> Platform:
        return Platform.YOUTUBE

    def can_handle(self, url: str) -> bool:
        return "youtube.com" in url

    def extract_metadata(self, url: str) -> MediaMetadata:
        return MediaMetadata(
            title="Test video",
            source_url=url,
            platform=self.platform,
            duration_seconds=60,
            uploader="Test channel",
        )

    def get_supported_modes(self, url: str) -> tuple[DownloadMode, ...]:
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
        if options.mode not in self.get_supported_modes(url):
            raise UnsupportedDownloadModeError("The requested mode is unsupported.")

        available_qualities = self.get_available_qualities(url, options.mode)
        if options.quality_id is not None and not any(
            quality.id == options.quality_id for quality in available_qualities
        ):
            raise UnsupportedQualityError("The requested quality is unavailable.")

        metadata = self.extract_metadata(url)
        extension = "mp3" if options.mode is DownloadMode.AUDIO_ONLY else "mp4"
        file_path = output_dir / f"test-video.{extension}"
        file_path.write_bytes(options.mode.value.encode("utf-8"))

        return DownloadedMedia(
            file_path=file_path,
            metadata=metadata,
        )


def test_provider_implements_common_contract(tmp_path: Path) -> None:
    provider: MediaProvider = FakeProvider()
    url = "https://www.youtube.com/watch?v=example"

    assert provider.platform is Platform.YOUTUBE
    assert provider.can_handle(url)

    metadata = provider.extract_metadata(url)

    assert metadata.title == "Test video"
    assert metadata.source_url == url
    assert metadata.platform is Platform.YOUTUBE

    downloaded = provider.download(url, tmp_path)

    assert downloaded.file_path == tmp_path / "test-video.mp4"
    assert downloaded.file_path.read_bytes() == b"video_with_audio"
    assert downloaded.metadata == metadata


def test_provider_lists_supported_modes() -> None:
    provider: MediaProvider = FakeProvider()
    url = "https://www.youtube.com/watch?v=example"

    assert provider.get_supported_modes(url) == (
        DownloadMode.VIDEO_WITH_AUDIO,
        DownloadMode.VIDEO_ONLY,
        DownloadMode.AUDIO_ONLY,
    )


def test_provider_lists_quality_options_for_requested_mode() -> None:
    provider: MediaProvider = FakeProvider()
    url = "https://www.youtube.com/watch?v=example"

    video_options = provider.get_available_qualities(url, DownloadMode.VIDEO_ONLY)
    audio_options = provider.get_available_qualities(url, DownloadMode.AUDIO_ONLY)

    assert video_options[0].id == "video-720"
    assert video_options[0].height == 720
    assert audio_options[0].id == "audio-192"
    assert audio_options[0].bitrate_kbps == 192


def test_provider_downloads_video_only_with_selected_quality(tmp_path: Path) -> None:
    provider: MediaProvider = FakeProvider()
    options = DownloadOptions(
        mode=DownloadMode.VIDEO_ONLY,
        quality_id="video-720",
    )

    downloaded = provider.download(
        "https://www.youtube.com/watch?v=example",
        tmp_path,
        options,
    )

    assert downloaded.file_path.suffix == ".mp4"
    assert downloaded.file_path.read_bytes() == b"video_only"


def test_provider_downloads_audio_only_with_selected_quality(tmp_path: Path) -> None:
    provider: MediaProvider = FakeProvider()
    options = DownloadOptions(
        mode=DownloadMode.AUDIO_ONLY,
        quality_id="audio-192",
    )

    downloaded = provider.download(
        "https://www.youtube.com/watch?v=example",
        tmp_path,
        options,
    )

    assert downloaded.file_path.suffix == ".mp3"
    assert downloaded.file_path.read_bytes() == b"audio_only"


def test_provider_defaults_to_automatic_best_available_quality(tmp_path: Path) -> None:
    provider: MediaProvider = FakeProvider()

    downloaded = provider.download(
        "https://www.youtube.com/watch?v=example",
        tmp_path,
        DownloadOptions(quality_id=None),
    )

    assert downloaded.file_path.is_file()


def test_provider_rejects_unsupported_mode(tmp_path: Path) -> None:
    class VideoOnlyProvider(FakeProvider):
        def get_supported_modes(self, url: str) -> tuple[DownloadMode, ...]:
            return (DownloadMode.VIDEO_ONLY,)

    provider: MediaProvider = VideoOnlyProvider()

    try:
        provider.download(
            "https://www.youtube.com/watch?v=example",
            tmp_path,
            DownloadOptions(mode=DownloadMode.AUDIO_ONLY),
        )
    except UnsupportedDownloadModeError:
        pass
    else:
        raise AssertionError("Unsupported mode was not rejected.")


def test_provider_rejects_unknown_quality_id(tmp_path: Path) -> None:
    provider: MediaProvider = FakeProvider()

    try:
        provider.download(
            "https://www.youtube.com/watch?v=example",
            tmp_path,
            DownloadOptions(quality_id="not-available"),
        )
    except UnsupportedQualityError:
        pass
    else:
        raise AssertionError("Unknown quality ID was not rejected.")
