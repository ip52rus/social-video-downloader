"""Deterministic tests for Telegram playback compatibility preparation."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from social_video_downloader.domain.errors import MediaProcessingError
from social_video_downloader.infrastructure.telegram_media import prepare_telegram_video


def _probe(video: str, audio: str) -> SimpleNamespace:
    return SimpleNamespace(stdout=json.dumps({
        "streams": [
            {"codec_type": "video", "codec_name": video},
            {"codec_type": "audio", "codec_name": audio},
        ]
    }))


def test_compatible_mp4_is_preserved_without_transcoding(tmp_path: Path) -> None:
    source = tmp_path / "already-compatible.mp4"
    source.write_bytes(b"original")
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return _probe("h264", "aac")

    result = prepare_telegram_video(source, runner=runner)
    assert result == source
    assert source.read_bytes() == b"original"
    assert len(calls) == 1
    assert calls[0][0] == "ffprobe"


def test_incompatible_codecs_are_transcoded_and_verified(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"av1 and opus")
    probe_results = iter([_probe("av1", "opus"), _probe("h264", "aac")])
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        if command[0] == "ffprobe":
            return next(probe_results)
        assert command[0] == "ffmpeg"
        assert "libx264" in command
        assert "aac" in command
        Path(command[-1]).write_bytes(b"transcoded")
        return SimpleNamespace(stdout="")

    result = prepare_telegram_video(source, runner=runner)
    assert result.name == "source.telegram-compatible.mp4"
    assert result.read_bytes() == b"transcoded"
    assert source.read_bytes() == b"av1 and opus"
    assert [call[0] for call in calls] == ["ffprobe", "ffmpeg", "ffprobe"]


def test_non_mp4_with_compatible_codecs_is_remuxed_to_mp4(tmp_path: Path) -> None:
    source = tmp_path / "source.mkv"
    source.write_bytes(b"source")
    probes = iter([_probe("h264", "aac"), _probe("h264", "aac")])

    def runner(command, **kwargs):
        if command[0] == "ffprobe":
            return next(probes)
        Path(command[-1]).write_bytes(b"remuxed")
        return SimpleNamespace(stdout="")

    result = prepare_telegram_video(source, runner=runner)
    assert result.suffix == ".mp4"
    assert result.read_bytes() == b"remuxed"


def test_ffmpeg_failure_is_mapped_to_media_processing_error(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"av1 and opus")

    def runner(command, **kwargs):
        if command[0] == "ffprobe":
            return _probe("av1", "opus")
        raise subprocess.CalledProcessError(1, command, stderr="private ffmpeg details")

    with pytest.raises(MediaProcessingError, match="Unable to prepare video"):
        prepare_telegram_video(source, runner=runner)


def test_missing_audio_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "video.mp4"
    source.write_bytes(b"video only")

    def runner(command, **kwargs):
        return SimpleNamespace(stdout=json.dumps({
            "streams": [{"codec_type": "video", "codec_name": "h264"}]
        }))

    with pytest.raises(MediaProcessingError, match="both video and audio"):
        prepare_telegram_video(source, runner=runner)
