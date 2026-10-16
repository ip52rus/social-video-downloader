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


def inspect_telegram_video(path: Path, runner: Runner | None = None) -> dict[str, Any]:
    """Return container and stream metadata for diagnosing Telegram upload issues."""
    execute = runner or subprocess.run
    source = Path(path)
    try:
        result = execute(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                (
                    "format=format_name,duration,size,bit_rate:"
                    "stream=index,codec_type,codec_name,width,height,sample_aspect_ratio,"
                    "display_aspect_ratio,avg_frame_rate,r_frame_rate,bit_rate,pix_fmt,"
                    "duration,nb_frames:stream_tags=rotate:"
                    "stream_side_data=side_data_type,rotation"
                ),
                "-of",
                "json",
                str(source),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout)
        if not isinstance(data, dict):
            raise TypeError("ffprobe returned an unexpected JSON shape")
        return data
    except (OSError, subprocess.SubprocessError, TypeError, json.JSONDecodeError) as exc:
        raise MediaProcessingError("Unable to inspect video metadata for Telegram upload.") from exc


def telegram_video_upload_parameters(probe_data: dict[str, Any]) -> dict[str, int]:
    """Extract real display dimensions and duration for Telegram's sendVideo method."""
    streams = probe_data.get("streams")
    if not isinstance(streams, list):
        raise MediaProcessingError("Video metadata does not contain stream information.")
    video_stream = next(
        (
            stream
            for stream in streams
            if isinstance(stream, dict) and stream.get("codec_type") == "video"
        ),
        None,
    )
    if video_stream is None:
        raise MediaProcessingError("Video metadata does not contain a video stream.")

    try:
        width = int(video_stream["width"])
        height = int(video_stream["height"])
    except (KeyError, TypeError, ValueError) as exc:
        raise MediaProcessingError("Video metadata does not contain valid dimensions.") from exc
    if width <= 0 or height <= 0:
        raise MediaProcessingError("Video metadata contains invalid dimensions.")

    rotation: float | None = None
    side_data = video_stream.get("side_data_list", [])
    if isinstance(side_data, list):
        for item in side_data:
            if isinstance(item, dict) and item.get("rotation") is not None:
                try:
                    rotation = float(item["rotation"])
                    break
                except (TypeError, ValueError):
                    continue
    if rotation is None:
        tags = video_stream.get("tags")
        if isinstance(tags, dict) and tags.get("rotate") is not None:
            try:
                rotation = float(tags["rotate"])
            except (TypeError, ValueError):
                rotation = None

    # Telegram dimensions should describe the displayed orientation, not the
    # encoded storage orientation when a rotation matrix/tag is present.
    if rotation is not None and int(round(rotation)) % 180 != 0:
        width, height = height, width

    parameters = {"width": width, "height": height}
    format_data = probe_data.get("format")
    duration_value = format_data.get("duration") if isinstance(format_data, dict) else None
    if duration_value is None:
        duration_value = video_stream.get("duration")
    try:
        duration = int(round(float(duration_value)))
    except (TypeError, ValueError, OverflowError):
        duration = 0
    if duration > 0:
        parameters["duration"] = duration
    return parameters


def _probe_streams(
    path: Path, runner: Runner, *, allow_silent: bool = False
) -> tuple[str, str | None, bool]:
    """Read actual codecs/container, distinguishing absent audio from invalid audio."""
    result = runner(
        [
            "ffprobe",
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-show_entries",
            "format=format_name:stream=codec_type,codec_name,width,height",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        data = json.loads(result.stdout)
        streams = data["streams"]
        container = data["format"]["format_name"]
        if (
            not isinstance(streams, list)
            or any(
                not isinstance(item, dict)
                or not isinstance(item.get("codec_type"), str)
                or not item["codec_type"]
                for item in streams
            )
            or not isinstance(container, str)
            or container.strip().lower() in {"", "unknown"}
            or getattr(result, "stderr", "")
        ):
            raise TypeError("Invalid stream or container metadata")
        videos = [item for item in streams if item["codec_type"] == "video"]
        audios = [item for item in streams if item["codec_type"] == "audio"]
        if any(
            not isinstance(item.get("codec_name"), str)
            or item["codec_name"].strip().lower() in {"", "none", "unknown"}
            for item in (*videos, *audios)
        ) or any(
            type(item.get(key)) is not int or item[key] <= 0
            for item in videos
            for key in ("width", "height")
        ):
            raise TypeError("Invalid codec or video dimensions")
    except (AttributeError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise MediaProcessingError("Unable to inspect downloaded media streams.") from exc
    if not videos or (not audios and not allow_silent):
        raise MediaProcessingError("Downloaded video must contain both video and audio streams.")
    return (
        videos[0]["codec_name"].strip().lower(),
        audios[0]["codec_name"].strip().lower() if audios else None,
        "mp4" in container.split(","),
    )


def prepare_telegram_video(
    path: Path, runner: Runner | None = None, *, allow_silent: bool = False
) -> Path:
    """Return a Telegram-friendly MP4, transcoding only when needed.

    Audio is required by default; explicit opt-in allows video-only output without
    inventing audio. H.264 video and optional AAC audio are used. FFmpeg's
    default autorotation preserves visual orientation; no scale filter is applied.
    """
    execute = runner or subprocess.run
    source = Path(path)
    if not source.is_file():
        raise MediaProcessingError("Downloaded media file is missing.")
    output = None
    completed = False
    try:
        video_codec, audio_codec, is_mp4 = _probe_streams(
            source, execute, allow_silent=allow_silent
        )
        compatible_audio = audio_codec in {_COMPATIBLE_AUDIO_CODEC, None}
        if (
            source.suffix.lower() == ".mp4"
            and is_mp4
            and video_codec == _COMPATIBLE_VIDEO_CODEC
            and compatible_audio
        ):
            return source

        destination = source.with_name(f"{source.stem}.telegram-compatible.mp4")
        if destination.exists() or destination.is_symlink():
            raise MediaProcessingError("Compatible video output already exists.")
        output = destination
        audio_map = ["-map", "0:a:0"] if audio_codec is not None else ["-an"]

        # If the streams are already compatible, try a stream-copy remux first.
        # This avoids expensive lossy re-encoding for files such as MKV containers
        # that already contain H.264 video and AAC audio.
        if video_codec == _COMPATIBLE_VIDEO_CODEC and compatible_audio:
            try:
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
                        *audio_map,
                        "-map_metadata",
                        "0",
                        "-c",
                        "copy",
                        "-movflags",
                        "+faststart",
                        str(output),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                if output.is_file() and output.stat().st_size > 0:
                    remuxed_video, remuxed_audio, remuxed_mp4 = _probe_streams(
                        output, execute, allow_silent=allow_silent
                    )
                    if (
                        output.suffix.lower() == ".mp4"
                        and remuxed_mp4
                        and remuxed_video == _COMPATIBLE_VIDEO_CODEC
                        and remuxed_audio == audio_codec
                    ):
                        completed = True
                        return output
            except (OSError, subprocess.SubprocessError, MediaProcessingError):
                # Some otherwise compatible streams cannot be copied into MP4.
                # Fall back to transcoding rather than failing the download.
                pass
            output.unlink(missing_ok=True)

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
                *audio_map,
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
                *(["-c:a", "aac", "-b:a", "192k"] if audio_codec is not None else []),
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
        converted_video, converted_audio, converted_mp4 = _probe_streams(
            output, execute, allow_silent=allow_silent
        )
        if (
            output.suffix.lower() != ".mp4"
            or not converted_mp4
            or converted_video != _COMPATIBLE_VIDEO_CODEC
            or converted_audio != (_COMPATIBLE_AUDIO_CODEC if audio_codec is not None else None)
        ):
            raise MediaProcessingError("Converted video does not use compatible codecs.")
        completed = True
        return output
    except MediaProcessingError:
        raise
    except (OSError, subprocess.SubprocessError) as exc:
        raise MediaProcessingError("Unable to prepare video for Telegram playback.") from exc
    finally:
        if output is not None and not completed:
            output.unlink(missing_ok=True)
