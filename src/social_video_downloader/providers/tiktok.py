"""Experimental native single-video provider; no default registry activation."""

from pathlib import Path

from social_video_downloader.domain.errors import (
    DownloadCleanupError,
    DownloadFailedError,
    DownloadTimeoutError,
    InvalidMediaURLError,
    MediaProcessingError,
    MetadataExtractionError,
    UnsupportedDownloadModeError,
    UnsupportedQualityError,
)
from social_video_downloader.domain.models import (
    DownloadedMedia,
    DownloadMode,
    DownloadOptions,
    MediaMetadata,
    Platform,
)
from social_video_downloader.infrastructure import tiktok_native as native


class TikTokProvider:
    platform = Platform.TIKTOK

    @staticmethod
    def canonical_url(url: str) -> str:
        try:
            return native.publication(url.strip())[1]
        except Exception:
            raise InvalidMediaURLError("Public TikTok video URL required.") from None

    def can_handle(self, url: str) -> bool:
        try:
            self.canonical_url(url)
        except InvalidMediaURLError:
            return False
        return True

    def extract_metadata(self, url: str) -> MediaMetadata:
        # Local catalog descriptor, not a claim that remote access was verified.
        return MediaMetadata("TikTok video", self.canonical_url(url), self.platform)

    def get_supported_modes(self, url: str) -> tuple[DownloadMode, ...]:
        self.canonical_url(url)
        return (DownloadMode.VIDEO_WITH_AUDIO,)

    def get_available_qualities(self, url: str, mode: DownloadMode) -> tuple:
        self.canonical_url(url)
        if mode is not DownloadMode.VIDEO_WITH_AUDIO:
            raise UnsupportedDownloadModeError("TikTok supports standard video only.")
        return ()

    def download_prepared(self, url: str, output_dir: Path, options=None, *, cancelled=None):
        canonical = self.canonical_url(url)
        options = options or DownloadOptions()
        if options.mode is not DownloadMode.VIDEO_WITH_AUDIO:
            raise UnsupportedDownloadModeError("TikTok supports standard video only.")
        if options.quality_id is not None:
            raise UnsupportedQualityError("TikTok quality selection is unavailable.")
        try:
            video = native.download_video(
                canonical, output_dir, cancelled=cancelled, public_page=True
            )
        except native.Refusal as exc:
            category = str(exc)
            if category in {"cleanup_failed", "workspace_cleanup_failed", "case_cleanup_failed"}:
                error = DownloadCleanupError
            elif category in {"deadline", "subprocess_deadline", "cancelled", "interrupted"}:
                error = DownloadTimeoutError
            elif category in {
                "metadata_schema",
                "missing_embed_state",
                "missing_public_state",
                "source_identity_mismatch",
                "ambiguous_metadata",
                "non_public_or_drm",
                "non_public_or_unavailable",
                "unsupported_page_video",
                "metadata_body_limit",
                "metadata_content_type",
                "unsupported_photo",
            }:
                error = MetadataExtractionError
            elif category in {
                "incomplete_response",
                "not_mp4",
                "unsupported_streams",
                "separate_streams_unsupported",
                "preparation_requires_conversion",
                "preparation_not_passthrough",
            }:
                error = MediaProcessingError
            else:
                error = DownloadFailedError
            raise error("TikTok operation could not complete safely.") from None
        except Exception:
            raise DownloadFailedError("TikTok operation failed.") from None
        metadata = MediaMetadata(
            "TikTok video",
            canonical,
            self.platform,
            duration_seconds=video.parameters.get("duration"),
        )
        return DownloadedMedia(video.file_path, metadata), video.parameters

    def download(
        self, url: str, output_dir: Path, options: DownloadOptions | None = None, *, cancelled=None
    ) -> DownloadedMedia:
        return self.download_prepared(url, output_dir, options, cancelled=cancelled)[0]
