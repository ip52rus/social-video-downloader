from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from social_video_downloader.domain.models import (
    DownloadedMedia,
    MediaMetadata,
    Platform,
)


def test_platform_values():
    assert Platform.YOUTUBE.value == "youtube"
    assert Platform.INSTAGRAM.value == "instagram"
    assert Platform.TIKTOK.value == "tiktok"


def test_media_metadata_accepts_valid_data():
    metadata = MediaMetadata(
        title="Test video",
        source_url="https://www.youtube.com/watch?v=example",
        platform=Platform.YOUTUBE,
        duration_seconds=120.5,
        uploader="Test channel",
    )

    assert metadata.title == "Test video"
    assert metadata.platform is Platform.YOUTUBE
    assert metadata.duration_seconds == 120.5
    assert metadata.uploader == "Test channel"


def test_media_metadata_allows_optional_fields_to_be_missing():
    metadata = MediaMetadata(
        title="Test video",
        source_url="https://www.youtube.com/watch?v=example",
        platform=Platform.YOUTUBE,
    )

    assert metadata.duration_seconds is None
    assert metadata.uploader is None


@pytest.mark.parametrize("title", ["", "   ", "\n"])
def test_media_metadata_rejects_empty_title(title):
    with pytest.raises(ValueError, match="title"):
        MediaMetadata(
            title=title,
            source_url="https://example.com/video",
            platform=Platform.YOUTUBE,
        )


@pytest.mark.parametrize("source_url", ["", "   ", "\n"])
def test_media_metadata_rejects_empty_source_url(source_url):
    with pytest.raises(ValueError, match="URL"):
        MediaMetadata(
            title="Test video",
            source_url=source_url,
            platform=Platform.YOUTUBE,
        )


def test_media_metadata_rejects_negative_duration():
    with pytest.raises(ValueError, match="negative"):
        MediaMetadata(
            title="Test video",
            source_url="https://example.com/video",
            platform=Platform.YOUTUBE,
            duration_seconds=-1,
        )


def test_media_metadata_is_immutable():
    metadata = MediaMetadata(
        title="Test video",
        source_url="https://example.com/video",
        platform=Platform.YOUTUBE,
    )

    with pytest.raises(FrozenInstanceError):
        metadata.title = "Changed title"


def test_downloaded_media_contains_path_and_metadata():
    metadata = MediaMetadata(
        title="Test video",
        source_url="https://example.com/video",
        platform=Platform.YOUTUBE,
    )
    file_path = Path("/tmp/test-video.mp4")

    downloaded = DownloadedMedia(
        file_path=file_path,
        metadata=metadata,
    )

    assert downloaded.file_path == file_path
    assert downloaded.metadata is metadata
