"""Small synthetic FFmpeg fixtures; no YouTube or Telegram network access."""

import hashlib
import json
import shutil
import subprocess

import pytest

from social_video_downloader.domain.errors import MediaProcessingError
from social_video_downloader.infrastructure.telegram_audio import prepare_telegram_audio

pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="Local synthetic audio tests require ffmpeg and ffprobe.",
)


def packet_hashes(path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_packets",
            "-show_data_hash",
            "sha256",
            "-show_entries",
            "packet=data_hash",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return [packet["data_hash"] for packet in json.loads(result.stdout)["packets"]]


@pytest.mark.parametrize(
    ("extension", "codec", "route"),
    [
        ("m4a", "aac", "passthrough"),
        ("mkv", "aac", "remux"),
        ("webm", "libopus", "transcode"),
    ],
)
def test_synthetic_audio_routes_preserve_or_convert_as_required(tmp_path, extension, codec, route):
    source = tmp_path / f"synthetic.{extension}"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000",
            "-t",
            "0.35",
            "-ac",
            "2",
            "-c:a",
            codec,
            "-b:a",
            "96000",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    original_hash = hashlib.sha256(source.read_bytes()).digest()
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.run(command, **kwargs)

    prepared = prepare_telegram_audio(source, runner=runner)
    assert hashlib.sha256(source.read_bytes()).digest() == original_hash
    assert prepared.duration == 1
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=format_name:stream=codec_type,codec_name",
            "-of",
            "json",
            str(prepared.file_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    info = json.loads(result.stdout)
    assert "m4a" in info["format"]["format_name"].split(",")
    assert info["streams"] == [{"codec_name": "aac", "codec_type": "audio"}]
    ffmpeg_calls = [call for call in calls if call[0] == "ffmpeg"]
    if route == "passthrough":
        assert prepared.file_path == source
        assert not ffmpeg_calls
        assert len(calls) == 1
    else:
        assert len(ffmpeg_calls) == 1
        assert (
            len(calls) == 3
        )  # One input probe and one output verification, no duration-only probe.
        assert ffmpeg_calls[0][ffmpeg_calls[0].index("-c:a") + 1] == (
            "copy" if route == "remux" else "aac"
        )
        if route == "remux":
            assert packet_hashes(source) == packet_hashes(prepared.file_path)


def test_real_corrupt_audio_is_rejected_without_output(tmp_path):
    source = tmp_path / "corrupt.m4a"
    source.write_bytes(b"not a media file")
    with pytest.raises(MediaProcessingError):
        prepare_telegram_audio(source)
    assert list(tmp_path.iterdir()) == [source]
