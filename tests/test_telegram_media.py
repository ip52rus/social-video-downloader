"""Deterministic tests for Telegram playback compatibility preparation."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from social_video_downloader.domain.errors import MediaProcessingError
from social_video_downloader.infrastructure.telegram_media import (
    inspect_telegram_video,
    prepare_telegram_video,
    telegram_video_upload_parameters,
)


def _probe(
    video: str = "h264", audio: str | None = "aac", container: str = "mov,mp4,m4a,3gp,3g2,mj2"
) -> SimpleNamespace:
    return SimpleNamespace(
        stdout=json.dumps(
            {
                "format": {"format_name": container},
                "streams": [
                    {"codec_type": "video", "codec_name": video, "width": 64, "height": 96},
                    *([{"codec_type": "audio", "codec_name": audio}] if audio is not None else []),
                ],
            }
        )
    )


def test_inspect_telegram_video_returns_container_and_stream_metadata(tmp_path: Path) -> None:
    source = tmp_path / "video.mp4"
    source.write_bytes(b"video")
    metadata = {
        "format": {"format_name": "mov,mp4,m4a", "duration": "72.534", "size": "5"},
        "streams": [
            {
                "index": 0,
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1080,
                "height": 1920,
                "sample_aspect_ratio": "1:1",
                "display_aspect_ratio": "9:16",
            },
            {"index": 1, "codec_type": "audio", "codec_name": "aac"},
        ],
    }
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout=json.dumps(metadata))

    result = inspect_telegram_video(source, runner=runner)

    assert result == metadata
    assert calls[0][0] == "ffprobe"
    assert "-show_entries" in calls[0]
    assert str(source) == calls[0][-1]


def test_inspect_telegram_video_maps_ffprobe_failure(tmp_path: Path) -> None:
    source = tmp_path / "video.mp4"

    def runner(command, **kwargs):
        raise subprocess.CalledProcessError(1, command, stderr="probe failed")

    with pytest.raises(MediaProcessingError, match="Unable to inspect video metadata"):
        inspect_telegram_video(source, runner=runner)


def test_upload_parameters_use_real_video_dimensions_and_duration() -> None:
    parameters = telegram_video_upload_parameters(
        {
            "format": {"duration": "72.534"},
            "streams": [
                {
                    "codec_type": "video",
                    "width": 1080,
                    "height": 1920,
                    "side_data_list": [],
                }
            ],
        }
    )

    assert parameters == {"width": 1080, "height": 1920, "duration": 73}


def test_upload_parameters_swap_dimensions_for_quarter_turn_rotation() -> None:
    parameters = telegram_video_upload_parameters(
        {
            "format": {"duration": "12"},
            "streams": [
                {
                    "codec_type": "video",
                    "width": 1920,
                    "height": 1080,
                    "side_data_list": [{"side_data_type": "Display Matrix", "rotation": -90}],
                }
            ],
        }
    )

    assert parameters == {"width": 1080, "height": 1920, "duration": 12}


def test_upload_parameters_omit_unknown_duration() -> None:
    parameters = telegram_video_upload_parameters(
        {
            "streams": [
                {
                    "codec_type": "video",
                    "width": 1080,
                    "height": 1920,
                }
            ]
        }
    )

    assert parameters == {"width": 1080, "height": 1920}


def test_upload_parameters_reject_missing_video_dimensions() -> None:
    with pytest.raises(MediaProcessingError, match="valid dimensions"):
        telegram_video_upload_parameters({"streams": [{"codec_type": "video"}]})


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


def test_non_mp4_with_compatible_codecs_is_remuxed_without_transcoding(tmp_path: Path) -> None:
    source = tmp_path / "source.mkv"
    source.write_bytes(b"source")
    probes = iter([_probe("h264", "aac"), _probe("h264", "aac")])
    ffmpeg_commands = []

    def runner(command, **kwargs):
        if command[0] == "ffprobe":
            return next(probes)
        ffmpeg_commands.append(command)
        Path(command[-1]).write_bytes(b"remuxed")
        return SimpleNamespace(stdout="")

    result = prepare_telegram_video(source, runner=runner)
    assert result.suffix == ".mp4"
    assert result.read_bytes() == b"remuxed"
    assert len(ffmpeg_commands) == 1
    assert "-c" in ffmpeg_commands[0]
    assert ffmpeg_commands[0][ffmpeg_commands[0].index("-c") + 1] == "copy"
    assert "libx264" not in ffmpeg_commands[0]


def test_remux_failure_falls_back_to_transcoding(tmp_path: Path) -> None:
    source = tmp_path / "source.mkv"
    source.write_bytes(b"source")
    probes = iter([_probe("h264", "aac"), _probe("h264", "aac")])
    ffmpeg_commands = []

    def runner(command, **kwargs):
        if command[0] == "ffprobe":
            return next(probes)
        ffmpeg_commands.append(command)
        if "-c" in command and command[command.index("-c") + 1] == "copy":
            raise subprocess.CalledProcessError(1, command, stderr="remux unsupported")
        Path(command[-1]).write_bytes(b"transcoded")
        return SimpleNamespace(stdout="")

    result = prepare_telegram_video(source, runner=runner)
    assert result.suffix == ".mp4"
    assert result.read_bytes() == b"transcoded"
    assert len(ffmpeg_commands) == 2
    assert ffmpeg_commands[0][ffmpeg_commands[0].index("-c") + 1] == "copy"
    assert "libx264" in ffmpeg_commands[1]


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
        return _probe(audio=None)

    with pytest.raises(MediaProcessingError, match="both video and audio"):
        prepare_telegram_video(source, runner=runner)


def test_silent_mp4_opt_in_is_byte_preserving_without_ffmpeg(tmp_path):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"original video bytes")
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return _probe(audio=None)

    assert prepare_telegram_video(source, runner, allow_silent=True) == source
    assert source.read_bytes() == b"original video bytes"
    assert [c[0] for c in calls] == ["ffprobe"]
    assert list(tmp_path.iterdir()) == [source]


@pytest.mark.parametrize("audio", [None, "aac"])
@pytest.mark.parametrize("fallback", [False, True])
def test_optional_audio_remux_and_failure_fallback(tmp_path, audio, fallback):
    source = tmp_path / "video.mkv"
    source.write_bytes(b"original")
    probes = iter([_probe(audio=audio, container="matroska,webm"), _probe(audio=audio)])
    commands = []

    def runner(command, **kwargs):
        if command[0] == "ffprobe":
            return next(probes)
        commands.append(command)
        Path(command[-1]).write_bytes(b"partial" if len(commands) == 1 else b"converted")
        if fallback and len(commands) == 1:
            raise subprocess.CalledProcessError(1, command, stderr="private failure details")
        return SimpleNamespace(stdout="")

    prepared = prepare_telegram_video(source, runner, allow_silent=True)
    assert prepared.read_bytes() == (b"converted" if fallback else b"partial")
    assert source.read_bytes() == b"original"
    assert len(commands) == (2 if fallback else 1)
    assert commands[0][commands[0].index("-c") + 1] == "copy"
    for command in commands:
        assert ("0:a:0" in command) == (audio is not None)
        assert ("-an" in command) == (audio is None)
        assert "anullsrc" not in command


@pytest.mark.parametrize("allow_silent", [False, True])
@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"streams": []},
        {"streams": {}},
        {"streams": [None]},
        {"streams": [{"codec_type": "audio", "codec_name": "aac"}]},
        {"streams": [{"codec_type": "video", "codec_name": "unknown"}]},
        {"streams": [{"codec_type": "video", "codec_name": None}]},
        {"streams": [{"codec_type": "video", "codec_name": 123}]},
    ],
)
def test_malformed_or_audio_only_probe_fails_closed(tmp_path, allow_silent, bad):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"original")
    metadata = {"format": {"format_name": "mp4"}, **bad}

    def runner(command, **kwargs):
        assert command[0] == "ffprobe"
        return SimpleNamespace(stdout=json.dumps(metadata))

    with pytest.raises(MediaProcessingError):
        prepare_telegram_video(source, runner, allow_silent=allow_silent)
    assert list(tmp_path.iterdir()) == [source]


@pytest.mark.parametrize("codec", [None, "", "none", "unknown", 123, {}, []])
@pytest.mark.parametrize("kind", ["video", "audio"])
def test_invalid_present_codec_is_not_absent_audio(tmp_path, codec, kind):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"original")
    metadata = json.loads(_probe().stdout)
    next(x for x in metadata["streams"] if x["codec_type"] == kind)["codec_name"] = codec

    with pytest.raises(MediaProcessingError):
        prepare_telegram_video(
            source, lambda *a, **k: SimpleNamespace(stdout=json.dumps(metadata)), allow_silent=True
        )


@pytest.mark.parametrize("kind", [None, 123])
def test_malformed_extra_stream_is_not_silently_ignored(tmp_path, kind):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"original")
    metadata = json.loads(_probe(audio=None).stdout)
    metadata["streams"].append({"codec_type": kind})
    with pytest.raises(MediaProcessingError):
        prepare_telegram_video(
            source, lambda *a, **k: SimpleNamespace(stdout=json.dumps(metadata)), allow_silent=True
        )


@pytest.mark.parametrize("container", [None, "", "unknown", [], {}])
def test_missing_or_malformed_container_is_not_mp4(tmp_path, container):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"original")
    with pytest.raises(MediaProcessingError):
        prepare_telegram_video(source, lambda *a, **k: _probe(container=container))


@pytest.mark.parametrize("dimension", [None, 0, -1, True, "720"])
def test_invalid_video_dimensions_fail_closed(tmp_path, dimension):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"original")
    data = json.loads(_probe().stdout)
    data["streams"][0]["width"] = dimension
    with pytest.raises(MediaProcessingError):
        prepare_telegram_video(source, lambda *a, **k: SimpleNamespace(stdout=json.dumps(data)))


def test_mislabeled_mp4_container_is_remuxed(tmp_path):
    source = tmp_path / "actually-matroska.mp4"
    source.write_bytes(b"source")
    probes = iter([_probe(container="matroska,webm"), _probe()])
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        if command[0] == "ffprobe":
            return next(probes)
        assert "copy" in command
        Path(command[-1]).write_bytes(b"remuxed")

    assert prepare_telegram_video(source, runner) != source
    assert [c[0] for c in calls] == ["ffprobe", "ffmpeg", "ffprobe"]


@pytest.mark.parametrize("audio", [None, "aac"])
@pytest.mark.parametrize(
    "failure", ["ffmpeg", "probe", "empty", "wrong_container", "changed_audio", "invalid_video"]
)
def test_failed_conversion_removes_owned_outputs(tmp_path, audio, failure):
    source = tmp_path / "video.mkv"
    source.write_bytes(b"original")
    probes = 0

    def runner(command, **kwargs):
        nonlocal probes
        if command[0] == "ffprobe":
            probes += 1
            if probes == 1:
                return _probe(video="vp9", audio=audio, container="matroska,webm")
            if failure == "probe":
                raise subprocess.CalledProcessError(1, command, stderr="private upstream data")
            return _probe(
                video="unknown" if failure == "invalid_video" else "h264",
                audio=("aac" if audio is None else None) if failure == "changed_audio" else audio,
                container="matroska" if failure == "wrong_container" else "mp4",
            )
        Path(command[-1]).write_bytes(b"" if failure == "empty" else b"partial")
        if failure == "ffmpeg":
            raise subprocess.CalledProcessError(1, command, stderr="private upstream data")

    with pytest.raises(MediaProcessingError) as error:
        prepare_telegram_video(source, runner, allow_silent=True)
    assert "private upstream data" not in str(error.value)
    assert source.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [source]


@pytest.mark.parametrize("audio", [None, "aac"])
def test_remux_cannot_change_audio_presence(tmp_path, audio):
    source = tmp_path / "video.mkv"
    source.write_bytes(b"original")
    probes = iter(
        [
            _probe(audio=audio, container="matroska"),
            _probe(audio="aac" if audio is None else None),
            _probe(audio=audio),
        ]
    )
    commands = []

    def runner(command, **kwargs):
        if command[0] == "ffprobe":
            return next(probes)
        commands.append(command)
        Path(command[-1]).write_bytes(b"output")

    prepare_telegram_video(source, runner, allow_silent=True)
    assert len(commands) == 2 and "copy" in commands[0] and "libx264" in commands[1]


def test_interrupted_conversion_cleans_up_partial_file(tmp_path):
    source = tmp_path / "video.mkv"
    source.write_bytes(b"original")

    def runner(command, **kwargs):
        if command[0] == "ffprobe":
            return _probe(video="vp9", audio=None, container="matroska")
        Path(command[-1]).write_bytes(b"partial")
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        prepare_telegram_video(source, runner, allow_silent=True)
    assert list(tmp_path.iterdir()) == [source]


def test_existing_derivative_is_not_overwritten_or_removed(tmp_path):
    source = tmp_path / "video.mkv"
    source.write_bytes(b"source")
    existing = tmp_path / "video.telegram-compatible.mp4"
    existing.write_bytes(b"unrelated")
    with pytest.raises(MediaProcessingError, match="already exists"):
        prepare_telegram_video(source, lambda *a, **k: _probe(container="matroska"))
    assert existing.read_bytes() == b"unrelated"
