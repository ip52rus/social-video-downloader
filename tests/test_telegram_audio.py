"""Network-free audio compatibility, duration and performance-gate tests."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from social_video_downloader.domain.errors import MediaProcessingError
from social_video_downloader.infrastructure.telegram_audio import prepare_telegram_audio


def probe(codec="aac", container="mov,mp4,m4a,3gp,3g2,mj2", duration="72.534", **stream):
    return {
        "format": {"format_name": container, "duration": duration},
        "streams": [{"codec_type": "audio", "codec_name": codec, **stream}],
    }


class AudioRunner:
    def __init__(self, *probes, ffmpeg_error=False):
        self.probes = iter(probes)
        self.calls = []
        self.ffmpeg_error = ffmpeg_error

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        if command[0] == "ffprobe":
            return SimpleNamespace(stdout=json.dumps(next(self.probes)))
        Path(command[-1]).write_bytes(b"prepared audio")
        if self.ffmpeg_error:
            raise subprocess.CalledProcessError(1, command, stderr="private ffmpeg details")
        return SimpleNamespace(stdout="")


def source_file(tmp_path, name="source.m4a"):
    path = tmp_path / name
    path.write_bytes(b"original audio")
    return path


def test_native_aac_m4a_is_reused_without_ffmpeg_or_duplicate_probe(tmp_path):
    source = source_file(tmp_path)
    runner = AudioRunner(probe())

    prepared = prepare_telegram_audio(source, runner=runner)

    assert prepared.file_path == source
    assert prepared.duration == 73
    assert source.read_bytes() == b"original audio"
    assert [call[0] for call in runner.calls] == ["ffprobe"]
    assert list(tmp_path.iterdir()) == [source]


@pytest.mark.parametrize(("metadata", "expected"), [(12.6, 13), (12, 12), (0.1, 1)])
def test_reliable_metadata_duration_avoids_duration_probe_fields(tmp_path, metadata, expected):
    runner = AudioRunner(probe(duration="999"))

    prepared = prepare_telegram_audio(source_file(tmp_path), metadata, runner)

    assert prepared.duration == expected
    assert len(runner.calls) == 1
    assert "duration" not in runner.calls[0][runner.calls[0].index("-show_entries") + 1]


@pytest.mark.parametrize(
    "metadata", [None, 0, -1, float("nan"), float("inf"), -float("inf"), True, 1e300]
)
def test_unusable_metadata_duration_uses_same_probe(tmp_path, metadata):
    runner = AudioRunner(probe(duration="21.5"))

    prepared = prepare_telegram_audio(source_file(tmp_path), metadata, runner)

    assert prepared.duration == 22
    assert [call[0] for call in runner.calls] == ["ffprobe"]


@pytest.mark.parametrize("duration", [None, "N/A", "0", "-1", "NaN", "Infinity", True])
def test_unusable_probe_duration_is_omitted_safely(tmp_path, duration):
    prepared = prepare_telegram_audio(
        source_file(tmp_path), runner=AudioRunner(probe(duration=duration))
    )
    assert prepared.duration is None


def test_missing_container_duration_uses_audio_stream_duration(tmp_path):
    data = probe(duration=None)
    data["streams"][0]["duration"] = "42.2"
    prepared = prepare_telegram_audio(source_file(tmp_path), runner=AudioRunner(data))
    assert prepared.duration == 42


def test_aac_in_other_container_uses_stream_copy_and_verifies_once(tmp_path):
    source = source_file(tmp_path, "source.mkv")
    runner = AudioRunner(probe(container="matroska,webm"), probe(duration="72.4"))

    prepared = prepare_telegram_audio(source, runner=runner)

    command = runner.calls[1]
    assert [call[0] for call in runner.calls] == ["ffprobe", "ffmpeg", "ffprobe"]
    assert command[command.index("-c:a") + 1] == "copy"
    assert "-b:a" not in command
    assert prepared.file_path.suffix == ".m4a"
    assert prepared.duration == 72
    assert source.read_bytes() == b"original audio"


def test_source_probe_duration_is_available_when_output_duration_is_missing(tmp_path):
    runner = AudioRunner(probe(container="matroska"), probe(duration=None))
    prepared = prepare_telegram_audio(source_file(tmp_path, "source.mkv"), runner=runner)
    assert prepared.duration == 73


@pytest.mark.parametrize(
    ("bitrate", "channels", "expected"),
    [(96000, 2, "96000"), (192000, 2, "128000"), (None, 2, "128000"), (128000, 1, "64000")],
)
def test_opus_transcode_uses_capped_bitrate_and_verified_duration(
    tmp_path, bitrate, channels, expected
):
    source = source_file(tmp_path, "source.webm")
    runner = AudioRunner(
        probe("opus", "matroska,webm", "300", bit_rate=bitrate, channels=channels),
        probe(duration="72.534"),
    )

    prepared = prepare_telegram_audio(source, runner=runner)

    assert [call[0] for call in runner.calls] == ["ffprobe", "ffmpeg", "ffprobe"]
    command = runner.calls[1]
    assert command[command.index("-c:a") + 1] == "aac"
    assert command[command.index("-b:a") + 1] == expected
    assert command[command.index("-map") + 1] == "0:a:0"
    assert prepared.file_path.suffix == ".m4a"
    assert prepared.duration == 73  # Final output, not the source probe's 300 seconds.


def test_extension_alone_does_not_bypass_conversion(tmp_path):
    source = source_file(tmp_path, "fake.m4a")
    runner = AudioRunner(probe("opus", "matroska,webm"), probe())
    prepared = prepare_telegram_audio(source, runner=runner)
    assert prepared.file_path != source
    assert runner.calls[1][runner.calls[1].index("-c:a") + 1] == "aac"


def test_m4a_extension_with_wrong_container_is_remuxed(tmp_path):
    source = source_file(tmp_path)
    runner = AudioRunner(probe(container="aac"), probe())
    assert prepare_telegram_audio(source, runner=runner).file_path != source
    assert runner.calls[1][runner.calls[1].index("-c:a") + 1] == "copy"


@pytest.mark.parametrize("missing", [True, False])
def test_missing_or_empty_input_is_rejected_before_probe(tmp_path, missing):
    source = tmp_path / "missing.m4a"
    if not missing:
        source.touch()
    runner = AudioRunner()
    with pytest.raises(MediaProcessingError):
        prepare_telegram_audio(source, runner=runner)
    assert not runner.calls


@pytest.mark.parametrize("data", [None, [], {}, {"streams": [None]}, probe(codec="")])
def test_invalid_probe_is_rejected(tmp_path, data):
    source = source_file(tmp_path)
    with pytest.raises(MediaProcessingError):
        prepare_telegram_audio(source, runner=AudioRunner(data))
    assert list(tmp_path.iterdir()) == [source]


def test_corrupt_input_probe_failure_is_safe(tmp_path):
    source = source_file(tmp_path)

    def fail_probe(command, **kwargs):
        raise subprocess.CalledProcessError(1, command, stderr="private corrupt media details")

    with pytest.raises(MediaProcessingError, match="Unable to prepare audio"):
        prepare_telegram_audio(source, runner=fail_probe)


def test_ffmpeg_failure_removes_partial_output_and_preserves_input(tmp_path):
    source = source_file(tmp_path, "source.webm")
    runner = AudioRunner(probe("opus", "matroska,webm"), ffmpeg_error=True)
    with pytest.raises(MediaProcessingError):
        prepare_telegram_audio(source, runner=runner)
    assert list(tmp_path.iterdir()) == [source]
    assert source.read_bytes() == b"original audio"


@pytest.mark.parametrize("bad_output", [probe("opus"), probe(container="matroska,webm")])
def test_output_codec_and_container_are_verified_and_failed_output_removed(tmp_path, bad_output):
    source = source_file(tmp_path, "source.webm")
    with pytest.raises(MediaProcessingError):
        prepare_telegram_audio(source, runner=AudioRunner(probe("opus", "matroska"), bad_output))
    assert list(tmp_path.iterdir()) == [source]


def test_remux_failure_falls_back_to_one_transcode(tmp_path):
    source = source_file(tmp_path, "source.mkv")
    runner = AudioRunner(probe(container="matroska"), probe())

    def fail_copy(command, **kwargs):
        if "copy" in command:
            runner.calls.append(command)
            Path(command[-1]).write_bytes(b"partial remux")
            raise subprocess.CalledProcessError(1, command)
        return runner(command, **kwargs)

    prepared = prepare_telegram_audio(source, runner=fail_copy)
    assert prepared.file_path.read_bytes() == b"prepared audio"
    assert [call[0] for call in runner.calls] == ["ffprobe", "ffmpeg", "ffmpeg", "ffprobe"]


def test_audio_with_video_stream_is_not_passed_through(tmp_path):
    source = source_file(tmp_path)
    data = probe()
    data["streams"].append({"codec_type": "video", "codec_name": "h264"})
    runner = AudioRunner(data, probe())
    assert prepare_telegram_audio(source, runner=runner).file_path != source
    assert runner.calls[1][runner.calls[1].index("-c:a") + 1] == "copy"
