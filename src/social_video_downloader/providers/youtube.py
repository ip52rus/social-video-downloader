"""YouTube media provider implemented with yt-dlp."""

from collections.abc import Mapping
from math import isfinite
from pathlib import Path
from time import monotonic
from typing import Any

import yt_dlp

from social_video_downloader.domain.errors import (
    DownloaderError,
    DownloadFailedError,
    MediaProcessingError,
    MetadataExtractionError,
    UnsupportedDownloadModeError,
    UnsupportedPlatformError,
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
from social_video_downloader.domain.urls import detect_platform, normalize_media_url
from social_video_downloader.infrastructure.filenames import safe_filename
from social_video_downloader.infrastructure.workspace import temporary_workspace


class YouTubeProvider:
    """Download individual YouTube videos in supported output modes."""

    _INSPECTION_CACHE_TTL_SECONDS = 180.0
    _INSPECTION_CACHE_MAX_ENTRIES = 32

    def __init__(self, ydl_factory: Any = None) -> None:
        """Accept a factory override to make the provider testable without network access."""
        self._ydl_factory = ydl_factory
        self._inspection_cache: dict[str, tuple[float, dict[str, Any]]] = {}

    @property
    def platform(self) -> Platform:
        return Platform.YOUTUBE

    @staticmethod
    def _base_options() -> dict[str, Any]:
        """Return fresh yt-dlp options for each operation."""
        return {
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "retries": 10,
            "fragment_retries": 10,
            "js_runtimes": {"deno": {}},
        }

    def _new_ydl(self, options: dict[str, Any]) -> Any:
        factory = self._ydl_factory or yt_dlp.YoutubeDL
        return factory(options)

    @staticmethod
    def _normalize_youtube_url(url: str) -> str:
        normalized = normalize_media_url(url)
        if detect_platform(normalized) is not Platform.YOUTUBE:
            raise UnsupportedPlatformError("The URL does not point to YouTube.")
        return normalized

    def can_handle(self, url: str) -> bool:
        try:
            return detect_platform(url) is Platform.YOUTUBE
        except DownloaderError:
            return False

    @staticmethod
    def _read_raw_info(ydl: Any, url: str) -> dict[str, Any]:
        """Read extractor data without choosing a format or starting a download."""
        try:
            info = ydl.extract_info(url, download=False, process=False)
        except Exception as exc:
            raise MetadataExtractionError("Unable to inspect the YouTube media.") from exc

        if not isinstance(info, Mapping):
            raise MetadataExtractionError("YouTube returned no usable media information.")

        if info.get("_type") == "playlist" or "entries" in info:
            raise MetadataExtractionError("Playlist downloads are not supported.")

        return dict(info)

    def _cached_info(self, url: str) -> dict[str, Any] | None:
        cached = self._inspection_cache.get(url)
        if cached is None:
            return None

        cached_at, info = cached
        if monotonic() - cached_at >= self._INSPECTION_CACHE_TTL_SECONDS:
            self._inspection_cache.pop(url, None)
            return None

        return info

    def _take_cached_info(self, url: str) -> dict[str, Any] | None:
        cached = self._inspection_cache.pop(url, None)
        if cached is None:
            return None

        cached_at, info = cached
        if monotonic() - cached_at >= self._INSPECTION_CACHE_TTL_SECONDS:
            return None

        return info

    def _remember_info(self, url: str, info: dict[str, Any]) -> None:
        now = monotonic()
        expired = [
            key
            for key, (created_at, _) in self._inspection_cache.items()
            if now - created_at >= self._INSPECTION_CACHE_TTL_SECONDS
        ]
        for key in expired:
            self._inspection_cache.pop(key, None)

        if url not in self._inspection_cache and (
            len(self._inspection_cache) >= self._INSPECTION_CACHE_MAX_ENTRIES
        ):
            oldest_url = min(
                self._inspection_cache,
                key=lambda key: self._inspection_cache[key][0],
            )
            self._inspection_cache.pop(oldest_url, None)

        self._inspection_cache[url] = (now, info)

    def _inspect(self, url: str) -> tuple[str, dict[str, Any]]:
        normalized = self._normalize_youtube_url(url)
        cached_info = self._cached_info(normalized)
        if cached_info is not None:
            return normalized, cached_info

        try:
            with self._new_ydl(self._base_options()) as ydl:
                info = self._read_raw_info(ydl, normalized)
        except DownloaderError:
            raise
        except Exception as exc:
            raise MetadataExtractionError("Unable to inspect the YouTube media.") from exc

        self._remember_info(normalized, info)
        return normalized, info

    @staticmethod
    def _positive_int(value: Any) -> int | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if not isfinite(value) or value <= 0:
            return None
        return int(value)

    @staticmethod
    def _has_video(media_format: Mapping[str, Any]) -> bool:
        codec = media_format.get("vcodec")
        if codec is not None:
            return str(codec).strip().lower() not in {"", "none"}
        return YouTubeProvider._positive_int(media_format.get("height")) is not None

    @staticmethod
    def _has_audio(media_format: Mapping[str, Any]) -> bool:
        codec = media_format.get("acodec")
        return codec is not None and str(codec).strip().lower() not in {"", "none"}

    @staticmethod
    def _formats(info: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
        formats = info.get("formats")
        if isinstance(formats, list):
            return tuple(item for item in formats if isinstance(item, Mapping))

        if "format_id" in info:
            return (info,)

        return ()

    @classmethod
    def _supported_modes_from_info(
        cls,
        info: Mapping[str, Any],
    ) -> tuple[DownloadMode, ...]:
        formats = cls._formats(info)

        has_video_only = any(cls._has_video(item) and not cls._has_audio(item) for item in formats)
        has_audio_only = any(cls._has_audio(item) and not cls._has_video(item) for item in formats)
        has_combined = any(cls._has_video(item) and cls._has_audio(item) for item in formats)

        modes: list[DownloadMode] = []

        if has_combined or (has_video_only and has_audio_only):
            modes.append(DownloadMode.VIDEO_WITH_AUDIO)
        if has_video_only:
            modes.append(DownloadMode.VIDEO_ONLY)
        if has_audio_only:
            modes.append(DownloadMode.AUDIO_ONLY)

        return tuple(modes)

    def get_supported_modes(self, url: str) -> tuple[DownloadMode, ...]:
        if not self.can_handle(url):
            return ()

        _, info = self._inspect(url)
        return self._supported_modes_from_info(info)

    @classmethod
    def _qualities_from_info(
        cls,
        info: Mapping[str, Any],
        mode: DownloadMode,
    ) -> tuple[QualityOption, ...]:
        formats = cls._formats(info)

        if mode in {DownloadMode.VIDEO_WITH_AUDIO, DownloadMode.VIDEO_ONLY}:
            dimensions_by_height: dict[int, int | None] = {}

            for media_format in formats:
                has_video = cls._has_video(media_format)
                has_audio = cls._has_audio(media_format)

                if not has_video:
                    continue
                if mode is DownloadMode.VIDEO_ONLY and has_audio:
                    continue

                height = cls._positive_int(media_format.get("height"))
                width = cls._positive_int(media_format.get("width"))
                if height is not None:
                    current_width = dimensions_by_height.get(height)
                    if height not in dimensions_by_height or (
                        width is not None and (current_width is None or width > current_width)
                    ):
                        dimensions_by_height[height] = width

            options = []
            for height, width in sorted(dimensions_by_height.items(), reverse=True):
                label = (
                    f"{width}×{height} (max)"
                    if width is not None and width <= height
                    else f"{height}p (max)"
                )
                options.append(
                    QualityOption(
                        id=f"height-{height}",
                        label=label,
                        mode=mode,
                        height=height,
                    )
                )
            return tuple(options)

        if mode is not DownloadMode.AUDIO_ONLY:
            return ()

        audio_formats = [
            media_format
            for media_format in formats
            if cls._has_audio(media_format) and not cls._has_video(media_format)
        ]

        def bitrate(media_format: Mapping[str, Any]) -> int | None:
            return cls._positive_int(media_format.get("abr") or media_format.get("tbr"))

        audio_formats.sort(
            key=lambda item: (
                bitrate(item) or 0,
                str(item.get("format_id", "")),
            ),
            reverse=True,
        )

        options: list[QualityOption] = []
        seen_labels: set[str] = set()
        seen_ids: set[str] = set()

        for media_format in audio_formats:
            format_id = media_format.get("format_id")
            if not isinstance(format_id, str) or not format_id.strip():
                continue

            quality_id = f"audio:{format_id}"
            if quality_id in seen_ids:
                continue

            extension = str(media_format.get("ext") or "audio").upper()
            codec = str(media_format.get("acodec") or "audio").split(".", maxsplit=1)[0]
            codec = codec.upper()
            current_bitrate = bitrate(media_format)

            if current_bitrate is None:
                label = f"{extension} · {codec}"
            else:
                label = f"{extension} · {current_bitrate} kbps · {codec}"

            if label in seen_labels:
                continue

            seen_ids.add(quality_id)
            seen_labels.add(label)
            options.append(
                QualityOption(
                    id=quality_id,
                    label=label,
                    mode=mode,
                    bitrate_kbps=current_bitrate,
                )
            )

        return tuple(options)

    def get_available_qualities(
        self,
        url: str,
        mode: DownloadMode,
    ) -> tuple[QualityOption, ...]:
        if not isinstance(mode, DownloadMode) or not self.can_handle(url):
            return ()

        _, info = self._inspect(url)

        if mode not in self._supported_modes_from_info(info):
            return ()

        return self._qualities_from_info(info, mode)

    @staticmethod
    def _format_selector(
        mode: DownloadMode,
        quality: QualityOption | None,
    ) -> str:
        """Translate a validated quality choice into a yt-dlp format selector."""
        if mode is DownloadMode.AUDIO_ONLY:
            if quality is None:
                return "ba"
            return quality.id.removeprefix("audio:")

        if quality is None:
            if mode is DownloadMode.VIDEO_ONLY:
                return "bv"
            return "bv*+ba/b"

        if quality.height is None:
            raise UnsupportedQualityError("The selected video quality has no height.")

        height = quality.height
        if mode is DownloadMode.VIDEO_ONLY:
            return f"bv[height<={height}]"

        return f"bv[height<={height}]+ba/b[height<={height}]"

    @staticmethod
    def _metadata_from_info(info: Mapping[str, Any], source_url: str) -> MediaMetadata:
        title = info.get("title")
        if not isinstance(title, str) or not title.strip():
            raise MetadataExtractionError("YouTube did not provide a usable title.")

        duration_value = info.get("duration")
        duration: float | None = None
        if (
            isinstance(duration_value, (int, float))
            and not isinstance(duration_value, bool)
            and isfinite(duration_value)
            and duration_value >= 0
        ):
            duration = float(duration_value)

        uploader = next(
            (
                value.strip()
                for key in ("uploader", "channel", "creator")
                if isinstance((value := info.get(key)), str) and value.strip()
            ),
            None,
        )

        return MediaMetadata(
            title=title.strip(),
            source_url=source_url,
            platform=Platform.YOUTUBE,
            duration_seconds=duration,
            uploader=uploader,
        )

    def extract_metadata(self, url: str) -> MediaMetadata:
        normalized, info = self._inspect(url)
        return self._metadata_from_info(info, normalized)

    @staticmethod
    def _find_downloaded_file(
        workspace: Path,
        result: Any,
    ) -> Path:
        if isinstance(result, Mapping):
            value = result.get("filepath")
            if isinstance(value, (str, Path)):
                candidate = Path(value)
                try:
                    if candidate.is_file() and candidate.resolve().is_relative_to(
                        workspace.resolve()
                    ):
                        return candidate
                except OSError:
                    pass

        ignored_suffixes = {
            ".json",
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".vtt",
            ".srt",
            ".ass",
            ".lrc",
            ".part",
            ".ytdl",
            ".tmp",
        }
        candidates = [
            path
            for path in workspace.iterdir()
            if path.is_file()
            and path.suffix.lower() not in ignored_suffixes
            and not path.name.endswith(".part")
        ]

        if len(candidates) != 1:
            raise MediaProcessingError("yt-dlp did not produce exactly one final media file.")

        return candidates[0]

    @staticmethod
    def _unique_destination(
        output_dir: Path,
        title: str,
        media_id: str,
        extension: str,
    ) -> Path:
        base_name = f"{title} [{media_id}]" if media_id else title

        attempt = 1
        while True:
            name = base_name if attempt == 1 else f"{base_name} ({attempt})"
            filename = safe_filename(name, extension=extension or None)
            destination = output_dir / filename

            if not destination.exists():
                return destination

            attempt += 1

    def download(
        self,
        url: str,
        output_dir: Path,
        options: DownloadOptions | None = None,
    ) -> DownloadedMedia:
        selected_options = options or DownloadOptions()
        if not isinstance(selected_options, DownloadOptions):
            raise TypeError("options must be a DownloadOptions instance or None.")

        normalized = self._normalize_youtube_url(url)

        try:
            output_dir.mkdir(parents=True, exist_ok=True)

            with temporary_workspace(base_dir=output_dir) as workspace:
                ydl_options = self._base_options()
                ydl_options["outtmpl"] = str(workspace / "%(id)s.%(format_id)s.%(ext)s")

                with self._new_ydl(ydl_options) as ydl:
                    info = self._take_cached_info(normalized)
                    if info is None:
                        info = self._read_raw_info(ydl, normalized)
                    metadata = self._metadata_from_info(info, normalized)
                    supported_modes = self._supported_modes_from_info(info)

                    if selected_options.mode not in supported_modes:
                        raise UnsupportedDownloadModeError(
                            f"YouTube cannot provide mode: {selected_options.mode.value}."
                        )

                    qualities = self._qualities_from_info(info, selected_options.mode)
                    quality: QualityOption | None = None

                    if selected_options.quality_id is not None:
                        quality = next(
                            (item for item in qualities if item.id == selected_options.quality_id),
                            None,
                        )
                        if quality is None:
                            raise UnsupportedQualityError(
                                "The selected quality is not available for this video."
                            )

                    format_selector = self._format_selector(
                        selected_options.mode,
                        quality,
                    )
                    ydl.params["format"] = format_selector
                    ydl.format_selector = ydl.build_format_selector(format_selector)

                    if selected_options.mode is DownloadMode.VIDEO_WITH_AUDIO:
                        ydl.params["merge_output_format"] = "mp4"
                    else:
                        ydl.params.pop("merge_output_format", None)

                    result = ydl.process_ie_result(info, download=True)

                source_path = self._find_downloaded_file(workspace, result)
                extension = source_path.suffix.removeprefix(".")
                media_id = str(info.get("id") or info.get("display_id") or "")
                destination = self._unique_destination(
                    output_dir,
                    metadata.title,
                    media_id,
                    extension,
                )
                source_path.replace(destination)

        except DownloaderError:
            raise
        except Exception as exc:
            if type(exc).__name__ in {"PostProcessingError", "FFmpegPostProcessorError"}:
                raise MediaProcessingError("YouTube media processing failed.") from exc
            raise DownloadFailedError("The YouTube download failed.") from exc

        return DownloadedMedia(file_path=destination, metadata=metadata)
