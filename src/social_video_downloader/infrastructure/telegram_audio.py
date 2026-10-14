"""Prepare verified AAC/M4A audio for Telegram without unnecessary encoding."""

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Any

from social_video_downloader.domain.errors import MediaProcessingError

Runner = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class PreparedAudio:
    file_path: Path
    duration: int | None


@dataclass(frozen=True, slots=True)
class _AudioProbe:
    codec: str
    containers: frozenset[str]
    audio_count: int
    has_video: bool
    bitrate: float | None
    channels: float | None
    duration: int | None


def _positive_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) and number > 0 else None


def _duration(value: Any) -> int | None:
    seconds = _positive_number(value)
    # Telegram Integer fields must fit a signed 32-bit value.
    return max(1, round(seconds)) if seconds is not None and seconds <= 2**31 - 1 else None


def _inspect_audio(path: Path, execute: Runner, *, need_duration: bool) -> _AudioProbe:
    fields = "format=format_name,bit_rate:stream=codec_type,codec_name,bit_rate,channels"
    if need_duration:
        fields = (
            "format=format_name,bit_rate,duration:"
            "stream=codec_type,codec_name,bit_rate,channels,duration"
        )
    result = execute(
        ["ffprobe", "-v", "error", "-show_entries", fields, "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    if not isinstance(data, dict) or not isinstance(data.get("streams"), list):
        raise MediaProcessingError("Audio probe returned invalid stream information.")
    streams = data["streams"]
    if not all(isinstance(stream, dict) for stream in streams):
        raise MediaProcessingError("Audio probe returned invalid stream information.")
    audio = [stream for stream in streams if stream.get("codec_type") == "audio"]
    container = data.get("format")
    if not audio or not isinstance(container, dict):
        raise MediaProcessingError("Downloaded media does not contain usable audio.")
    codec = audio[0].get("codec_name")
    names = container.get("format_name")
    if not isinstance(codec, str) or not codec or not isinstance(names, str) or not names:
        raise MediaProcessingError("Audio codec or container could not be identified.")
    has_video = any(stream.get("codec_type") == "video" for stream in streams)
    bitrate = _positive_number(audio[0].get("bit_rate"))
    if bitrate is None and len(audio) == 1 and not has_video:
        bitrate = _positive_number(container.get("bit_rate"))
    duration = None
    if need_duration:
        duration = _duration(container.get("duration")) or _duration(audio[0].get("duration"))
    return _AudioProbe(
        codec=codec.lower(),
        containers=frozenset(names.split(",")),
        audio_count=len(audio),
        has_video=has_video,
        bitrate=bitrate,
        channels=_positive_number(audio[0].get("channels")),
        duration=duration,
    )


def _compatible_m4a(path: Path, probe: _AudioProbe) -> bool:
    return (
        path.suffix.lower() == ".m4a"
        and "m4a" in probe.containers
        and probe.codec == "aac"
        and probe.audio_count == 1
        and not probe.has_video
    )


def prepare_telegram_audio(
    path: Path,
    metadata_duration: float | None = None,
    runner: Runner | None = None,
) -> PreparedAudio:
    """Reuse AAC/M4A, stream-copy AAC, or encode incompatible audio once and verify it."""
    execute = runner or subprocess.run
    source = Path(path)
    output: Path | None = None
    duration = _duration(metadata_duration)
    try:
        if not source.is_file() or source.stat().st_size == 0:
            raise MediaProcessingError("Downloaded audio file is missing or empty.")
        probe = _inspect_audio(source, execute, need_duration=duration is None)
        if _compatible_m4a(source, probe):
            return PreparedAudio(source, duration or probe.duration)

        output = source.with_name(f"{source.stem}.telegram-compatible.m4a")

        def convert(codec_arguments: list[str]) -> PreparedAudio:
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
                    "0:a:0",
                    "-vn",
                    "-map_metadata",
                    "0",
                    *codec_arguments,
                    "-movflags",
                    "+faststart",
                    "-f",
                    "ipod",
                    str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            if not output.is_file() or output.stat().st_size == 0:
                raise MediaProcessingError("FFmpeg did not produce usable audio.")
            prepared = _inspect_audio(output, execute, need_duration=duration is None)
            if not _compatible_m4a(output, prepared):
                raise MediaProcessingError("Prepared audio is not AAC in an M4A container.")
            return PreparedAudio(output, duration or prepared.duration or probe.duration)

        if probe.codec == "aac":
            try:
                return convert(["-c:a", "copy"])
            except (
                OSError,
                subprocess.SubprocessError,
                MediaProcessingError,
                json.JSONDecodeError,
            ):
                output.unlink(missing_ok=True)

        # Cap encoding at 128 kbps (64 kbps mono), and do not raise a known source bitrate.
        ceiling = 64000 if probe.channels == 1 else 128000
        bitrate = min(ceiling, max(1, int(probe.bitrate))) if probe.bitrate else ceiling
        return convert(["-c:a", "aac", "-b:a", str(bitrate)])
    except (
        OSError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
        MediaProcessingError,
    ) as error:
        if output is not None:
            output.unlink(missing_ok=True)
        raise MediaProcessingError("Unable to prepare audio for Telegram playback.") from error
