"""Domain models used by the downloader core."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class Platform(StrEnum):
    """Supported media platforms."""

    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"


@dataclass(frozen=True, slots=True)
class MediaMetadata:
    """Platform-independent metadata describing media."""

    title: str
    source_url: str
    platform: Platform
    duration_seconds: float | None = None
    uploader: str | None = None

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("Media title must not be empty.")

        if not self.source_url.strip():
            raise ValueError("Media source URL must not be empty.")

        if self.duration_seconds is not None and self.duration_seconds < 0:
            raise ValueError("Media duration must not be negative.")


@dataclass(frozen=True, slots=True)
class DownloadedMedia:
    """A downloaded media file and its metadata."""

    file_path: Path
    metadata: MediaMetadata
