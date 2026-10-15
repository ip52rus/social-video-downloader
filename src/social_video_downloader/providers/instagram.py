"""Experimental anonymous provider for individual public Instagram Reels."""

from collections.abc import Mapping
from math import isfinite
from pathlib import Path
from re import fullmatch
from time import monotonic
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import yt_dlp

from social_video_downloader.domain.errors import (
    DownloaderError,
    DownloadFailedError,
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
    QualityOption,
)
from social_video_downloader.domain.urls import normalize_media_url
from social_video_downloader.infrastructure.filenames import safe_filename
from social_video_downloader.infrastructure.workspace import temporary_workspace


class _QuietLogger:
    """Keep upstream messages containing URLs or account data out of application logs."""

    def debug(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        pass

    def error(self, message: str) -> None:
        pass


class InstagramProvider:
    """Acquire one Reel; registration and Telegram activation are a separate stage.

    Only direct MP4 video formats are admitted. Unknown audio codecs in progressive
    extractor data are allowed; actual streams still require transport validation.
    """

    _INSPECTION_CACHE_TTL_SECONDS = 180.0
    _INSPECTION_CACHE_MAX_ENTRIES = 32

    def __init__(self, ydl_factory: Any = None) -> None:
        self._ydl_factory = ydl_factory
        self._inspection_cache: dict[str, tuple[float, dict[str, Any]]] = {}

    @property
    def platform(self) -> Platform:
        return Platform.INSTAGRAM

    @staticmethod
    def _reel_url(url: str) -> str:
        normalized = normalize_media_url(url)
        parts = urlsplit(normalized)
        match = fullmatch(r"/reel/([A-Za-z0-9_-]+)/?", parts.path)
        if (
            parts.hostname not in {"instagram.com", "www.instagram.com", "m.instagram.com"}
            or parts.port is not None
            or match is None
        ):
            raise InvalidMediaURLError("Only individual Instagram Reel URLs are supported.")
        # Tracking parameters must not change extractor/cache identity or enter logs.
        return f"https://www.instagram.com/reel/{match[1]}/"

    def can_handle(self, url: str) -> bool:
        try:
            self._reel_url(url)
        except DownloaderError:
            return False
        return True

    @staticmethod
    def _base_options() -> dict[str, Any]:
        return {
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "logger": _QuietLogger(),
            "retries": 0,
            "fragment_retries": 0,
            "extractor_retries": 0,
            "socket_timeout": 20,
            "format": "best",
            "cachedir": False,
        }

    def _new_ydl(self, options: dict[str, Any]) -> Any:
        return (self._ydl_factory or yt_dlp.YoutubeDL)(options)

    @staticmethod
    def _positive_number(value: Any) -> bool:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        try:
            return isfinite(value) and value > 0
        except OverflowError:
            return False

    @classmethod
    def _usable_format(cls, item: Any) -> bool:
        if not isinstance(item, Mapping):
            return False
        locator = item.get("url")
        if not isinstance(locator, str):
            return False
        try:
            parts = urlsplit(locator)
        except ValueError:
            return False
        extension = item.get("ext") or parts.path.rsplit(".", 1)[-1].lower()
        codec = item.get("vcodec")
        has_video = (isinstance(codec, str) and codec.strip().lower() not in {"", "none"}) or (
            codec is None
            and cls._positive_number(item.get("width"))
            and cls._positive_number(item.get("height"))
        )
        return (
            parts.scheme in {"https", "http"}
            and bool(parts.hostname)
            and extension == "mp4"
            and item.get("protocol") in {None, "https", "http"}
            and has_video
            and (item.get("acodec") is None or str(item.get("acodec")).strip().lower() != "none")
            and not item.get("has_drm")
        )

    @classmethod
    def _single_video(cls, raw: Any) -> dict[str, Any]:
        if (
            not isinstance(raw, Mapping)
            or raw.get("_type", "video") != "video"
            or "entries" in raw
            or raw.get("is_private")
            or raw.get("availability") not in {None, "public"}
            or raw.get("has_drm")
        ):
            raise MetadataExtractionError("Instagram did not return a public single video.")
        formats = raw.get("formats")
        if not isinstance(formats, list):
            raise MetadataExtractionError("Instagram did not return usable video formats.")
        usable = [dict(item) for item in formats if cls._usable_format(item)]
        if not usable:
            raise MetadataExtractionError("Instagram did not return a supported video format.")
        # Never hand a collection, redirect or unclassified format to yt-dlp processing.
        return {**raw, "formats": usable}

    def _inspect(self, url: str, *, consume: bool = False) -> tuple[str, dict[str, Any]]:
        normalized = self._reel_url(url)
        now = monotonic()
        self._inspection_cache = {
            key: value
            for key, value in self._inspection_cache.items()
            if now - value[0] < self._INSPECTION_CACHE_TTL_SECONDS
        }
        cached = (
            self._inspection_cache.pop(normalized, None)
            if consume
            else self._inspection_cache.get(normalized)
        )
        if cached is not None:
            return normalized, cached[1]
        try:
            with self._new_ydl(self._base_options()) as ydl:
                raw = ydl.extract_info(
                    normalized, download=False, process=False, ie_key="Instagram"
                )
                info = self._single_video(raw)
        except DownloaderError:
            raise
        except Exception as exc:
            raise MetadataExtractionError("Unable to inspect the Instagram Reel.") from exc
        if not consume:
            if len(self._inspection_cache) >= self._INSPECTION_CACHE_MAX_ENTRIES:
                self._inspection_cache.pop(next(iter(self._inspection_cache)))
            self._inspection_cache[normalized] = (monotonic(), info)
        return normalized, info

    @classmethod
    def _metadata(cls, info: Mapping[str, Any], url: str) -> MediaMetadata:
        title = info.get("title")
        uploader = info.get("uploader")
        duration = info.get("duration")
        return MediaMetadata(
            title=title.strip() if isinstance(title, str) and title.strip() else "Instagram Reel",
            source_url=url,
            platform=Platform.INSTAGRAM,
            duration_seconds=float(duration) if cls._positive_number(duration) else None,
            uploader=uploader.strip() if isinstance(uploader, str) and uploader.strip() else None,
        )

    def extract_metadata(self, url: str) -> MediaMetadata:
        normalized, info = self._inspect(url)
        return self._metadata(info, normalized)

    def get_supported_modes(self, url: str) -> tuple[DownloadMode, ...]:
        if not self.can_handle(url):
            return ()
        self._inspect(url)
        return (DownloadMode.VIDEO_WITH_AUDIO,)

    def get_available_qualities(self, url: str, mode: DownloadMode) -> tuple[QualityOption, ...]:
        if mode is not DownloadMode.VIDEO_WITH_AUDIO:
            raise UnsupportedDownloadModeError("Instagram supports only the normal video mode.")
        self._inspect(url)
        return ()

    def download(
        self,
        url: str,
        output_dir: Path,
        options: DownloadOptions | None = None,
    ) -> DownloadedMedia:
        selected = options if options is not None else DownloadOptions()
        if not isinstance(selected, DownloadOptions):
            raise TypeError("options must be a DownloadOptions instance or None.")
        if selected.mode is not DownloadMode.VIDEO_WITH_AUDIO:
            raise UnsupportedDownloadModeError("Instagram supports only the normal video mode.")
        if selected.quality_id is not None:
            raise UnsupportedQualityError("Instagram does not expose selectable quality IDs.")
        normalized, info = self._inspect(url, consume=True)
        metadata = self._metadata(info, normalized)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            with temporary_workspace(base_dir=output_dir) as workspace:
                # Fixed acquisition path avoids trusting extractor filenames or media IDs.
                source = workspace / "reel.mp4"
                with self._new_ydl({**self._base_options(), "outtmpl": str(source)}) as ydl:
                    result = ydl.process_ie_result(info, download=True)
                self._single_video(result)
                files = list(workspace.iterdir())
                if (
                    files != [source]
                    or source.is_symlink()
                    or not source.is_file()
                    or source.stat().st_size == 0
                ):
                    raise MediaProcessingError("Instagram did not produce exactly one media file.")
                destination = output_dir / safe_filename(
                    f"Instagram Reel {uuid4().hex}", extension="mp4"
                )
                source.replace(destination)
        except DownloaderError:
            raise
        except Exception as exc:
            raise DownloadFailedError("The Instagram Reel download failed.") from exc
        return DownloadedMedia(file_path=destination, metadata=metadata)
