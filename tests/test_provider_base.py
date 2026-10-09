from pathlib import Path

from social_video_downloader.domain.models import (
    DownloadedMedia,
    MediaMetadata,
    Platform,
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

    def download(self, url: str, output_dir: Path) -> DownloadedMedia:
        metadata = self.extract_metadata(url)
        file_path = output_dir / "test-video.mp4"
        file_path.write_bytes(b"test media")

        return DownloadedMedia(
            file_path=file_path,
            metadata=metadata,
        )


def test_provider_implements_common_contract(tmp_path):
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
    assert downloaded.file_path.read_bytes() == b"test media"
    assert downloaded.metadata == metadata
