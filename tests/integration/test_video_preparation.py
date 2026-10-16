"""Actual local FFmpeg/ffprobe routes; generated media only, no platform requests."""

import hashlib
import json
import shutil
import subprocess

import pytest

from social_video_downloader.domain.errors import MediaProcessingError
from social_video_downloader.infrastructure.telegram_media import (
    inspect_telegram_video,
    prepare_telegram_video,
    telegram_video_upload_parameters,
)

pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="Local video preparation requires FFmpeg and ffprobe.",
)


def generate(path, video="libx264", audio=False):
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=blue:s=64x96:r=10",
    ]
    if audio:
        command += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000"]
    command += ["-t", "0.6", "-c:v", video, "-pix_fmt", "yuv420p"]
    if audio:
        command += ["-c:a", "aac" if video == "libx264" else "pcm_s16le"]
    subprocess.run([*command, str(path)], check=True, capture_output=True, timeout=15)


def packet_hashes(path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_packets",
            "-show_data_hash",
            "sha256",
            "-show_entries",
            "packet=stream_index,data_hash",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    # Containers may interleave streams differently without changing packet payloads.
    streams = {}
    for packet in json.loads(result.stdout)["packets"]:
        streams.setdefault(packet["stream_index"], []).append(packet["data_hash"])
    return streams


@pytest.mark.parametrize(
    ("extension", "video", "audio", "allow_silent", "route"),
    [
        ("mp4", "libx264", False, True, "passthrough"),
        ("mp4", "libx264", True, False, "passthrough"),
        ("mkv", "libx264", False, True, "remux"),
        ("mkv", "libx264", True, False, "remux"),
        ("mkv", "mpeg4", False, True, "transcode"),
        ("mkv", "mpeg4", True, False, "transcode"),
    ],
)
def test_actual_preparation_routes(tmp_path, extension, video, audio, allow_silent, route):
    source = tmp_path / f"source.{extension}"
    generate(source, video, audio)
    original = source.read_bytes()
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.run(command, timeout=15, **kwargs)

    prepared = prepare_telegram_video(source, runner, allow_silent=allow_silent)
    assert source.read_bytes() == original
    data = inspect_telegram_video(prepared)
    assert "mp4" in data["format"]["format_name"].split(",")
    videos = [s for s in data["streams"] if s["codec_type"] == "video"]
    audios = [s for s in data["streams"] if s["codec_type"] == "audio"]
    assert [s["codec_name"] for s in videos] == ["h264"]
    assert [s["codec_name"] for s in audios] == (["aac"] if audio else [])
    parameters = telegram_video_upload_parameters(data)
    assert parameters == {"width": 64, "height": 96, "duration": 1}
    ffmpeg = [c for c in calls if c[0] == "ffmpeg"]
    if route == "passthrough":
        assert prepared == source and not ffmpeg
        assert hashlib.sha256(prepared.read_bytes()).digest() == hashlib.sha256(original).digest()
        assert list(tmp_path.iterdir()) == [source]
    else:
        assert len(ffmpeg) == 1
        assert ("copy" in ffmpeg[0]) == (route == "remux")
        assert ("libx264" in ffmpeg[0]) == (route == "transcode")
        assert ("0:a:0" in ffmpeg[0]) == audio
        if route == "remux":
            assert packet_hashes(source) == packet_hashes(prepared)
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-i",
            str(prepared),
            "-f",
            "null",
            "-",
        ],
        check=True,
        capture_output=True,
        timeout=15,
    )


@pytest.mark.parametrize("audio", [False, True])
def test_actual_remux_failure_falls_back_without_changing_audio_policy(tmp_path, audio):
    source = tmp_path / "source.mkv"
    generate(source, audio=audio)
    commands = []

    def runner(command, **kwargs):
        if command[0] == "ffmpeg":
            commands.append(command)
            if "copy" in command:
                type(source)(command[-1]).write_bytes(b"partial")
                raise subprocess.CalledProcessError(1, command, stderr="synthetic remux failure")
        return subprocess.run(command, timeout=15, **kwargs)

    result = prepare_telegram_video(source, runner, allow_silent=True)
    assert len(commands) == 2 and "libx264" in commands[-1]
    streams = inspect_telegram_video(result)["streams"]
    assert [s["codec_type"] for s in streams] == (["video", "audio"] if audio else ["video"])


@pytest.mark.parametrize("route", ["passthrough", "remux", "transcode"])
def test_actual_silent_preparation_preserves_rotation(tmp_path, route):
    base = tmp_path / "base.mp4"
    rotated = tmp_path / ("rotated.mp4" if route == "passthrough" else "rotated.mov")
    generate(base, video="mpeg4" if route == "transcode" else "libx264")
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-display_rotation",
            "90",
            "-i",
            str(base),
            "-c",
            "copy",
            str(rotated),
        ],
        check=True,
        capture_output=True,
        timeout=15,
    )
    original = rotated.read_bytes()
    with pytest.raises(MediaProcessingError, match="both video and audio"):
        prepare_telegram_video(rotated)
    result = prepare_telegram_video(rotated, allow_silent=True)
    assert (result == rotated) == (route == "passthrough")
    assert rotated.read_bytes() == original
    assert telegram_video_upload_parameters(inspect_telegram_video(result)) == {
        "width": 96,
        "height": 64,
        "duration": 1,
    }


def test_actual_matroska_disguised_as_mp4_does_not_pass_through(tmp_path):
    source = tmp_path / "source.mkv"
    generate(source, audio=True)
    disguised = source.with_suffix(".mp4")
    source.rename(disguised)
    prepared = prepare_telegram_video(disguised)
    assert prepared != disguised
    assert "mp4" in inspect_telegram_video(prepared)["format"]["format_name"].split(",")
    assert packet_hashes(prepared) == packet_hashes(disguised)


@pytest.mark.parametrize("allow_silent", [False, True])
@pytest.mark.parametrize("kind", ["corrupt", "audio-only"])
def test_actual_invalid_or_audio_only_media_rejected(tmp_path, allow_silent, kind):
    source = tmp_path / "invalid.mp4"
    if kind == "corrupt":
        source.write_bytes(b"not a container")
    else:
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440",
                "-t",
                "0.3",
                "-c:a",
                "aac",
                str(source),
            ],
            check=True,
            capture_output=True,
            timeout=15,
        )
    with pytest.raises(MediaProcessingError):
        prepare_telegram_video(source, allow_silent=allow_silent)
    assert list(tmp_path.iterdir()) == [source]
