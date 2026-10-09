"""Common interface for media platform providers."""

from pathlib import Path
from typing import Protocol

from social_video_downloader.domain.models import (
    DownloadedMedia,
    MediaMetadata,
    Platform,
)


class MediaProvider(Protocol):
    """Interface implemented by each supported media provider."""

    @property
    def platform(self) -> Platform:
        """Return the platform handled by this provider."""
        ...

    def can_handle(self, url: str) -> bool:
        """Return whether this provider supports the given URL."""
        ...

    def extract_metadata(self, url: str) -> MediaMetadata:
        """Extract platform-independent metadata for a media URL."""
        ...

    def download(self, url: str, output_dir: Path) -> DownloadedMedia:
        """Download media into the supplied directory and return its result."""
        ...
