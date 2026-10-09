"""Domain models used by the downloader core."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class Platform(StrEnum):
    """Supported media platforms."""

    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"


class DownloadMode(StrEnum):
    """Requested media output mode."""

    VIDEO_WITH_AUDIO = "video_with_audio"
    VIDEO_ONLY = "video_only"
    AUDIO_ONLY = "audio_only"


@dataclass(frozen=True, slots=True)
class DownloadOptions:
    """Platform-independent options for a media download."""

    mode: DownloadMode = DownloadMode.VIDEO_WITH_AUDIO
    quality_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.mode, DownloadMode):
            raise TypeError("Download mode must be a DownloadMode value.")

        if self.quality_id is not None:
            if not isinstance(self.quality_id, str):
                raise TypeError("Quality ID must be a string or None.")

            if not self.quality_id.strip():
                raise ValueError("quality ID must not be empty or whitespace.")


@dataclass(frozen=True, slots=True)
class QualityOption:
    """A provider-specific quality choice with a user-facing label."""

    id: str
    label: str
    mode: DownloadMode
    height: int | None = None
    bitrate_kbps: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Quality option ID must not be empty.")

        if not isinstance(self.label, str) or not self.label.strip():
            raise ValueError("Quality option label must not be empty.")

        if not isinstance(self.mode, DownloadMode):
            raise TypeError("Quality option mode must be a DownloadMode value.")

        if self.height is not None and (
            isinstance(self.height, bool) or not isinstance(self.height, int) or self.height <= 0
        ):
            raise ValueError("Quality height must be a positive integer.")

        if self.bitrate_kbps is not None and (
            isinstance(self.bitrate_kbps, bool)
            or not isinstance(self.bitrate_kbps, int)
            or self.bitrate_kbps <= 0
        ):
            raise ValueError("Quality bitrate must be a positive integer.")


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
