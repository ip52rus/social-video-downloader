"""Private short-lived carousel execution boundary. Never process a parent playlist."""

import contextlib
import json
import math
import os
import resource
import shutil
import subprocess
import sys
from pathlib import Path
from time import monotonic

from yt_dlp.utils import DownloadError

from social_video_downloader.domain.errors import DownloadFailedError, MediaProcessingError
from social_video_downloader.infrastructure.instagram_metadata import parent_identity_matches
from social_video_downloader.infrastructure.telegram_media import inspect_telegram_video
from social_video_downloader.providers.instagram import InstagramProvider
from social_video_downloader.services.instagram_acquisition import (
    CarouselAcquisitionLimits,
    plan_from_payload,
    validate_plan,
)


class _BudgetExceeded(DownloadFailedError):
    pass


class _MediaBudget:
    """Count actual response bytes before writes, independent of size headers/hooks."""

    def __init__(self, limits: CarouselAcquisitionLimits):
        self.limits = limits
        self.total = 0
        self.current = 0

    def wrap(self, response):
        original_read = response.read

        def bounded_read(size=-1):
            remaining = min(
                self.limits.max_file_bytes - self.current,
                self.limits.max_total_bytes - self.total,
                self.limits.max_temp_bytes - self.total,
            )
            if remaining <= 0:
                response.close()
                raise _BudgetExceeded("Carousel media byte budget exhausted.")
            # Limit the network read itself, not only bytes written after a hook.
            chunk = original_read(min(64 * 1024, remaining, size if size >= 0 else remaining))
            self.current += len(chunk)
            self.total += len(chunk)
            if len(chunk) > remaining:
                raise _BudgetExceeded("Media response violated its bounded read contract.")
            return chunk

        response.read = bounded_read
        return response


def _same_selection(plan, facts):
    # Formats/URLs may refresh, but no source position, identity or kind may change.
    return (
        facts.issue is None
        and parent_identity_matches(plan.parent_identity, plan.publication_url)
        and parent_identity_matches(facts.parent_identity, facts.publication_url)
        and facts.parent_identity == plan.parent_identity
        and facts.publication_url == plan.publication_url
        and facts.total_entries == plan.total_entries
        and tuple((x.position, x.item_id, x.kind) for x in facts.items)
        == tuple((x.position, x.item_id, x.kind) for x in plan.items)
        and all(
            facts.items[x.position - 1].admissible_format_count > 0 for x in plan.selected_videos
        )
    )


def _validate_file(path: Path, remaining: float) -> float | None:
    def runner(command, **kwargs):
        # Reuse the existing ffprobe reader, not the Telegram transformation policy.
        # Scan packets as well as headers; nonempty ffprobe error output fails closed.
        command = [command[0], "-protocol_whitelist", "file,pipe", "-count_packets", *command[1:]]
        result = subprocess.run(command, timeout=max(0.001, remaining), **kwargs)
        if result.stderr.strip():
            raise MediaProcessingError("Downloaded carousel video has probe errors.")
        return result

    data = inspect_telegram_video(path, runner=runner)
    streams = data.get("streams", [])
    if not isinstance(streams, list) or any(not isinstance(s, dict) for s in streams):
        raise MediaProcessingError("Carousel stream information is invalid.")
    videos = [s for s in streams if s.get("codec_type") == "video"]
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    container = data.get("format", {}).get("format_name", "").split(",")
    if not videos or "mp4" not in container:
        raise MediaProcessingError("Carousel requires an actual MP4 video stream.")
    # Audio may be absent, but an existing undecodable/unidentified stream is not
    # silently discarded. No audio is created and the acquired file is not changed.
    if any(
        not isinstance(s.get("codec_name"), str)
        or s["codec_name"].strip().lower() in {"", "none", "unknown"}
        for s in (*videos, *audio)
    ):
        raise MediaProcessingError("Carousel stream codec is invalid.")
    if any(
        type(video.get(k)) is not int or video[k] <= 0
        for video in videos
        for k in ("width", "height")
    ):
        raise MediaProcessingError("Carousel video dimensions are invalid.")
    try:
        duration = float(data.get("format", {}).get("duration"))
    except (TypeError, ValueError):
        return None
    return duration if math.isfinite(duration) and duration > 0 else None


def acquire_in_workspace(plan, workspace: Path, limits, provider=None):
    """Synchronous child body; caller supplies an isolated owned workspace.

    Public entry point always runs this in a killable process. Injection is only for
    deterministic tests; no alternate acquisition implementation exists in production.
    """
    validate_plan(plan, limits)
    provider = provider or InstagramProvider()
    started = monotonic()
    if list(workspace.iterdir()):
        raise DownloadFailedError("Carousel workspace must be empty.")
    if shutil.disk_usage(workspace).free < min(limits.max_total_bytes, limits.max_temp_bytes):
        raise DownloadFailedError("Insufficient temporary disk space for carousel limits.")
    facts, entries = provider.fresh_carousel_entries(plan.publication_url)
    if not _same_selection(plan, facts) or len(entries) != plan.total_entries:
        raise DownloadFailedError("Carousel changed; create a new selection plan.")
    # Validate every selected child BEFORE the first acquisition, never parent processing.
    children = [(x, provider._single_video(entries[x.position - 1])) for x in plan.selected_videos]
    budget = _MediaBudget(limits)
    durations = []
    for item, child in children:
        if monotonic() - started >= limits.max_seconds:
            raise _BudgetExceeded("Carousel deadline exhausted.")
        budget.current = 0
        source = workspace / f"video-{item.position:04d}.mp4"
        options = {
            **provider._base_options(),
            "outtmpl": str(source),
            "max_filesize": min(
                limits.max_file_bytes,
                limits.max_total_bytes - budget.total,
                limits.max_temp_bytes - budget.total,
            ),
            "continuedl": False,
            "overwrites": False,
            "fixup": "never",
            "postprocessors": [],
            "external_downloader": None,
            "buffersize": 64 * 1024,
            "noresizebuffer": True,
            "http_chunk_size": 0,
            "writeinfojson": False,
            "writethumbnail": False,
        }
        with provider._new_ydl(options) as ydl:
            original_open = ydl.urlopen
            opened = False

            def media_open(request, original_open=original_open):
                nonlocal opened
                if opened:
                    raise DownloadFailedError("Repeated media acquisition is not permitted.")
                opened = True
                return budget.wrap(original_open(request))

            ydl.urlopen = media_open
            # Strip extractor filenames, collections, postprocessors and private metadata.
            # Only the already validated format list reaches real yt-dlp selection.
            info = {
                "id": f"video-{item.position}",
                "title": "Instagram Video",
                "formats": [
                    {
                        key: value
                        for key, value in fmt.items()
                        if key
                        in {
                            "format_id",
                            "url",
                            "ext",
                            "protocol",
                            "vcodec",
                            "acodec",
                            "width",
                            "height",
                            "tbr",
                            "abr",
                            "vbr",
                            "fps",
                            "asr",
                            "audio_channels",
                            "filesize",
                            "filesize_approx",
                            "quality",
                            "preference",
                            "source_preference",
                            "language",
                            "language_preference",
                            "http_headers",
                        }
                    }
                    for fmt in child["formats"]
                ],
            }
            try:
                result = ydl.process_ie_result(info, download=True)
            except DownloadError:
                raise DownloadFailedError("Carousel video acquisition failed.") from None
            provider._single_video(result)
        expected = [
            workspace / f"video-{x.position:04d}.mp4"
            for x in plan.selected_videos[: len(durations) + 1]
        ]
        files = sorted(workspace.iterdir())
        if (
            files != expected
            or any(p.is_symlink() or not p.is_file() or not p.stat().st_size for p in files)
            or source.stat().st_size > limits.max_file_bytes
            or sum(p.stat().st_size for p in files)
            > min(limits.max_total_bytes, limits.max_temp_bytes)
        ):
            raise MediaProcessingError(
                "Carousel did not produce exactly the expected regular files."
            )
        durations.append(_validate_file(source, limits.max_seconds - (monotonic() - started)))
    return {"durations": durations}


def main():
    try:
        payload = json.load(sys.stdin)
        plan = plan_from_payload(payload["plan"])
        limits = CarouselAcquisitionLimits(**payload["limits"])
        # OS per-file backstop includes partial and unexpected files. Stream budgets
        # enforce aggregate media bytes; parent hard deadline also covers extraction.
        resource.setrlimit(resource.RLIMIT_FSIZE, (limits.max_file_bytes, limits.max_file_bytes))
        with (
            open(os.devnull, "w") as sink,
            contextlib.redirect_stdout(sink),
            contextlib.redirect_stderr(sink),
        ):
            result = acquire_in_workspace(plan, Path(payload["workspace"]), limits)
        print(json.dumps(result))
    except Exception as exc:
        # Safe type category only: never upstream messages or tracebacks.
        print(json.dumps({"error": type(exc).__name__}))
        sys.exit(1)


if __name__ == "__main__":
    main()
