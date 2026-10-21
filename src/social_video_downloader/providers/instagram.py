"""Experimental anonymous provider for individual public Instagram videos."""

from collections.abc import Iterator, Mapping
from math import isfinite
from pathlib import Path
from re import fullmatch
from time import monotonic
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import yt_dlp
from yt_dlp.utils import determine_ext, determine_protocol

from social_video_downloader.domain.carousel import (
    CarouselInspection,
    CarouselIssue,
    CarouselItem,
    CarouselItemKind,
)
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
from social_video_downloader.infrastructure.instagram_metadata import (
    CarouselInstagramIE,
    ItemEvidence,
    parent_identity_matches,
)
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
    """Acquire one video; registration and Telegram activation are a separate stage.

    Only direct MP4 candidates are admitted. Missing codec/dimension metadata is
    unknown; actual video and audio streams still require transport validation.
    """

    _INSPECTION_CACHE_TTL_SECONDS = 180.0
    _INSPECTION_CACHE_MAX_ENTRIES = 32

    def __init__(self, ydl_factory: Any = None) -> None:
        self._ydl_factory = ydl_factory
        self._inspection_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._carousel_cache: dict[str, tuple[float, CarouselInspection]] = {}

    @property
    def platform(self) -> Platform:
        return Platform.INSTAGRAM

    @staticmethod
    def _media_url(url: str) -> str:
        normalized = normalize_media_url(url)
        parts = urlsplit(normalized)
        match = fullmatch(r"/(reel|p)/([A-Za-z0-9_-]+)/?", parts.path)
        if (
            parts.hostname not in {"instagram.com", "www.instagram.com", "m.instagram.com"}
            or parts.port is not None
            or match is None
        ):
            raise InvalidMediaURLError("Only individual Instagram Reel or post URLs are supported.")
        # Tracking parameters must not change extractor/cache identity or enter logs.
        return f"https://www.instagram.com/{match[1]}/{match[2]}/"

    def can_handle(self, url: str) -> bool:
        try:
            self._media_url(url)
        except DownloaderError:
            return False
        return True

    @classmethod
    def _base_options(cls) -> dict[str, Any]:
        return {
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "logger": _QuietLogger(),
            "retries": 0,
            "fragment_retries": 0,
            "extractor_retries": 0,
            "socket_timeout": 20,
            "format": cls._select_format,
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
        locator_extension = determine_ext(locator, default_ext="").lower()
        extension = item.get("ext") or locator_extension
        codec = item.get("vcodec")
        # Instagram video_versions may omit both codecs and dimensions. A direct
        # MP4 locator is a candidate, not proof of streams; explicit audio-only
        # metadata still fails here and real streams are checked during preparation.
        video_candidate = codec is None or (
            isinstance(codec, str) and codec.strip().lower() not in {"", "none"}
        )
        return (
            parts.scheme in {"https", "http"}
            and bool(parts.hostname)
            and extension == "mp4"
            and item.get("protocol") in {None, "https", "http"}
            and determine_protocol(dict(item)) in {"https", "http"}
            # A declared HTTP protocol must not disguise a manifest URL either.
            and determine_protocol({"url": locator}) in {"https", "http"}
            and locator_extension not in {"m3u8", "mpd", "f4m"}
            and all(
                item.get(key) is None
                for key in ("fragments", "fragment_base_url", "manifest_stream_number")
            )
            and not item.get("manifest_url")
            and video_candidate
            and not item.get("has_drm")
        )

    @staticmethod
    def _explicitly_silent(item: Mapping[str, Any]) -> bool:
        # Unknown audio stays unknown; only the explicit extractor marker is silence.
        return str(item.get("acodec") or "").strip().lower() == "none"

    @staticmethod
    def _compatibility_rank(item: Mapping[str, Any]) -> int:
        video = str(item.get("vcodec") or "").lower()
        audio = str(item.get("acodec") or "").lower()
        h264 = video in {"h264", "avc1", "avc3"} or video.startswith(("avc1.", "avc3."))
        aac = audio == "aac" or audio.startswith("mp4a.40.")
        if h264 and aac:
            return 0
        if (item.get("vcodec") is None or h264) and (
            item.get("acodec") is None or aac or InstagramProvider._explicitly_silent(item)
        ):
            return 1
        return 2

    @classmethod
    def _select_format(cls, context: Mapping[str, Any]) -> Iterator[dict[str, Any]]:
        # yt-dlp sorts formats from worst to best before invoking this selector.
        # Compatibility wins across classes. Within one, prefer non-silent/unknown
        # audio over explicit silence, then retain yt-dlp's native quality order.
        formats = [item for item in context["formats"] if cls._usable_format(item)]
        for rank in (0, 1, 2):
            for silent in (False, True):
                for item in reversed(formats):
                    if (
                        cls._compatibility_rank(item) == rank
                        and cls._explicitly_silent(item) == silent
                    ):
                        yield dict(item)
                        return

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
        normalized = self._media_url(url)
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
            raise MetadataExtractionError("Unable to inspect the Instagram video.") from exc
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
        default_title = (
            "Instagram Reel" if urlsplit(url).path.startswith("/reel/") else "Instagram Video"
        )
        return MediaMetadata(
            title=title.strip() if isinstance(title, str) and title.strip() else default_title,
            source_url=url,
            platform=Platform.INSTAGRAM,
            duration_seconds=float(duration) if cls._positive_number(duration) else None,
            uploader=uploader.strip() if isinstance(uploader, str) and uploader.strip() else None,
        )

    def extract_metadata(self, url: str) -> MediaMetadata:
        normalized, info = self._inspect(url)
        return self._metadata(info, normalized)

    def inspect_carousel(self, url: str) -> CarouselInspection:
        """Return immutable facts only; single-file download still rejects collections.

        Reference-intent validation belongs to InstagramCarouselService. This factual
        entry point accepts only already-canonical publication identities.
        """
        canonical = self._media_url(url)
        if url != canonical or not urlsplit(canonical).path.startswith("/p/"):
            raise InvalidMediaURLError("Carousel inspection requires a canonical publication URL.")
        now = monotonic()
        self._carousel_cache = {
            key: value
            for key, value in self._carousel_cache.items()
            if now - value[0] < self._INSPECTION_CACHE_TTL_SECONDS
        }
        if cached := self._carousel_cache.get(canonical):
            return cached[1]
        inspection, _ = self.fresh_carousel_entries(canonical)
        if len(self._carousel_cache) >= self._INSPECTION_CACHE_MAX_ENTRIES:
            self._carousel_cache.pop(next(iter(self._carousel_cache)))
        self._carousel_cache[canonical] = (monotonic(), inspection)
        return inspection

    def fresh_carousel_entries(self, url: str) -> tuple[CarouselInspection, tuple[dict, ...]]:
        """Internal acquisition boundary: one fresh extraction, no cached locators.

        Child metadata stays in the acquisition process and never enters public results.
        The same adapter and factual guards as metadata-only inspection are used.
        """
        try:
            raw = self._extract_post(url)
            facts = self._carousel_facts(url, raw)
            return facts, tuple(raw["entries"]) if facts.issue is None else ()
        except DownloaderError:
            raise
        except Exception as exc:
            raise MetadataExtractionError("Unable to inspect the Instagram carousel.") from exc

    def _extract_post(self, url: str) -> Any:
        canonical = self._media_url(url)
        if url != canonical or not urlsplit(canonical).path.startswith("/p/"):
            raise InvalidMediaURLError("Post inspection requires a canonical publication URL.")
        with self._new_ydl(
            {**self._base_options(), "skip_download": True, "getcomments": False}
        ) as ydl:
            ydl.add_info_extractor(CarouselInstagramIE(ydl))
            return ydl.extract_info(canonical, download=False, process=False, ie_key="Instagram")

    def inspect_post(self, url: str) -> MediaMetadata | CarouselInspection:
        """Positively identify a single video or return guarded carousel facts.

        A blocked result is never permission to re-extract through another path.
        Single-video acquisition consumes this validated snapshot from the usual cache.
        """
        try:
            self._inspection_cache.pop(url, None)
            raw = self._extract_post(url)
            if isinstance(raw, Mapping) and raw.get("_type") == "playlist":
                return self._carousel_facts(url, raw)
            if (
                not isinstance(raw, Mapping)
                or not isinstance(evidence := raw.get("_carousel_item_evidence"), ItemEvidence)
                or evidence.kind is not CarouselItemKind.VIDEO
                or evidence.unavailable
                or evidence.item_id is None
                or evidence.mapped_id is None
                or raw.get("id") != evidence.mapped_id
                or raw.get("_carousel_unavailable")
                or raw.get("needs_auth")
                or "_carousel_source_count" in raw
            ):
                return CarouselInspection(url, None, issue=CarouselIssue.UNSUPPORTED_CONTENT)
            try:
                info = self._single_video(raw)
            except MetadataExtractionError:
                return CarouselInspection(url, None, issue=CarouselIssue.UNSUPPORTED_VIDEO)
            # Source evidence has already been checked; do not pass adapter internals
            # into yt-dlp processing or a public result.
            info.pop("_carousel_item_evidence", None)
            info.pop("_carousel_unavailable", None)
            if len(self._inspection_cache) >= self._INSPECTION_CACHE_MAX_ENTRIES:
                self._inspection_cache.pop(next(iter(self._inspection_cache)))
            self._inspection_cache[url] = (monotonic(), info)
            return self._metadata(info, url)
        except DownloaderError:
            raise
        except Exception as exc:
            raise MetadataExtractionError("Unable to inspect the Instagram publication.") from exc

    @classmethod
    def _carousel_facts(cls, canonical: str, raw: Any) -> CarouselInspection:
        if (
            not isinstance(raw, Mapping)
            or raw.get("_type") != "playlist"
            or raw.get("is_private")
            or raw.get("availability") not in {None, "public"}
            or raw.get("has_drm")
            or raw.get("_carousel_unavailable")
        ):
            return CarouselInspection(canonical, None, issue=CarouselIssue.UNSUPPORTED_CONTENT)
        entries, count = raw.get("entries"), raw.get("_carousel_source_count")
        parent = raw.get("_carousel_parent_identity")
        if not parent_identity_matches(parent, canonical):
            return CarouselInspection(canonical, count, issue=CarouselIssue.UNSTABLE_IDENTITIES)
        if not isinstance(entries, list) or type(count) is not int or len(entries) != count:
            return CarouselInspection(
                canonical,
                count if type(count) is int else None,
                issue=CarouselIssue.INVALID_METADATA,
            )
        items = []
        issue = None
        for position, entry in enumerate(entries, 1):
            if not isinstance(entry, Mapping) or not isinstance(
                evidence := entry.get("_carousel_item_evidence"), ItemEvidence
            ):
                return CarouselInspection(canonical, count, issue=CarouselIssue.INVALID_METADATA)
            if evidence.item_id is None or entry.get("id") != evidence.mapped_id:
                issue = CarouselIssue.UNSTABLE_IDENTITIES
            formats = entry.get("formats")
            admissible = (
                sum(cls._usable_format(f) for f in formats) if isinstance(formats, list) else 0
            )
            if (
                entry.get("_type", "video") != "video"
                or "entries" in entry
                or entry.get("is_private")
                or entry.get("availability") not in {None, "public"}
                or entry.get("has_drm")
                or evidence.unavailable
            ):
                admissible = 0
                issue = CarouselIssue.UNSUPPORTED_CONTENT
            items.append(
                CarouselItem(
                    position, evidence.item_id, evidence.kind, evidence.signals, admissible
                )
            )
        ids = [item.item_id for item in items]
        if len(set(ids)) != len(ids):
            issue = CarouselIssue.UNSTABLE_IDENTITIES
        return CarouselInspection(canonical, count, tuple(items), issue, parent_identity=parent)

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
                label = (
                    "Instagram Reel"
                    if urlsplit(normalized).path.startswith("/reel/")
                    else "Instagram Video"
                )
                destination = output_dir / safe_filename(f"{label} {uuid4().hex}", extension="mp4")
                source.replace(destination)
        except DownloaderError:
            raise
        except Exception as exc:
            raise DownloadFailedError("The Instagram video download failed.") from exc
        return DownloadedMedia(file_path=destination, metadata=metadata)
