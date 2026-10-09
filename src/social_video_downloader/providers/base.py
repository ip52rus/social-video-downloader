"""Common interface for media platform providers."""

from pathlib import Path
from typing import Protocol

from social_video_downloader.domain.models import (
    DownloadedMedia,
    DownloadMode,
    DownloadOptions,
    MediaMetadata,
    Platform,
    QualityOption,
)


class MediaProvider(Protocol):
    """Interface implemented by each media platform provider."""

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

    def get_supported_modes(self, url: str) -> tuple[DownloadMode, ...]:
        """Return the output modes available for this URL."""
        ...

    def get_available_qualities(
        self,
        url: str,
        mode: DownloadMode,
    ) -> tuple[QualityOption, ...]:
        """List selectable qualities for a mode.

        An empty tuple means that explicit quality choices cannot be offered.
        In that case, a download with no quality ID must use the best available
        quality supported by the platform.
        """
        ...

    def download(
        self,
        url: str,
        output_dir: Path,
        options: DownloadOptions | None = None,
    ) -> DownloadedMedia:
        """Download media using the requested mode and optional quality.

        Providers must reject unsupported modes and unknown quality IDs with
        the corresponding domain errors. If ``options`` is None, providers
        must use the default video-with-audio mode. If ``options.quality_id``
        is None, the provider should choose the best available quality.
        """
        ...
