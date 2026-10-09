"""Prepare MP4 files for reliable playback in Telegram clients."""

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from social_video_downloader.domain.errors import MediaProcessingError

Runner = Callable[..., Any]
_COMPATIBLE_VIDEO_CODEC = "h264"
_COMPATIBLE_AUDIO_CODEC = "aac"


def _probe_streams(path: Path, runner: Runner) -> tuple[str | None, str | None]:
    """Return the first video and audio codec names, failing closed on invalid media."""
    result = runner(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,codec_name",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        streams = json.loads(result.stdout)["streams"]
        video = next(
            (item.get("codec_name") for item in streams if item.get("codec_type") == "video"),
            None,
        )
        audio = next(
            (item.get("codec_name") for item in streams if item.get("codec_type") == "audio"),
            None,
        )
    except (AttributeError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise MediaProcessingError("Unable to inspect downloaded media streams.") from exc
    if not video or not audio:
        raise MediaProcessingError("Downloaded video must contain both video and audio streams.")
    return str(video).lower(), str(audio).lower()


def prepare_telegram_video(path: Path, runner: Runner | None = None) -> Path:
    """Return a Telegram-friendly MP4, transcoding only when needed.

    H.264 video and AAC audio are used for broad client compatibility. FFmpeg's
    default autorotation preserves visual orientation; no scale filter is applied.
    """
    execute = runner or subprocess.run
    source = Path(path)
    if not source.is_file():
        raise MediaProcessingError("Downloaded media file is missing.")
    try:
        video_codec, audio_codec = _probe_streams(source, execute)
        if (
            source.suffix.lower() == ".mp4"
            and video_codec == _COMPATIBLE_VIDEO_CODEC
            and audio_codec == _COMPATIBLE_AUDIO_CODEC
        ):
            return source

        output = source.with_name(f"{source.stem}.telegram-compatible.mp4")
        execute(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(source),
                "-map",
                "0:v:0",
                "-map",
                "0:a:0",
                "-map_metadata",
                "0",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(output),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        if not output.is_file() or output.stat().st_size == 0:
            raise MediaProcessingError("FFmpeg did not produce a usable compatible video.")
        converted_video, converted_audio = _probe_streams(output, execute)
        if (
            output.suffix.lower() != ".mp4"
            or converted_video != _COMPATIBLE_VIDEO_CODEC
            or converted_audio != _COMPATIBLE_AUDIO_CODEC
        ):
            raise MediaProcessingError("Converted video does not use compatible codecs.")
        return output
    except MediaProcessingError:
        raise
    except (OSError, subprocess.SubprocessError) as exc:
        raise MediaProcessingError("Unable to prepare video for Telegram playback.") from exc
