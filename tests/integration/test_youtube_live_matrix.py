"""Opt-in real YouTube download matrix; never runs without an explicit URL."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from social_video_downloader.domain.models import DownloadMode, DownloadOptions
from social_video_downloader.providers.youtube import YouTubeProvider

LIVE_URL = os.getenv("YOUTUBE_LIVE_TEST_URL")
pytestmark = pytest.mark.skipif(
    not LIVE_URL,
    reason="Set YOUTUBE_LIVE_TEST_URL to opt in to real YouTube downloads.",
)


def _probe_streams(file_path: Path) -> list[dict[str, Any]]:
    """Read the actual output streams with ffprobe rather than trusting the filename."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,codec_name,width,height,sample_rate,channels",
            "-of",
            "json",
            str(file_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(result.stdout).get("streams", [])


def test_real_youtube_format_and_output_mode_matrix(tmp_path: Path) -> None:
    """Exercise automatic merge, selected video quality, and two audio containers."""
    if shutil.which("ffprobe") is None:
        pytest.fail("ffprobe is required for live YouTube matrix verification.")

    assert LIVE_URL is not None
    provider = YouTubeProvider()

    supported_modes = provider.get_supported_modes(LIVE_URL)
    required_modes = {
        DownloadMode.VIDEO_WITH_AUDIO,
        DownloadMode.VIDEO_ONLY,
        DownloadMode.AUDIO_ONLY,
    }
    assert required_modes.issubset(supported_modes), (
        f"The chosen public video does not expose all required modes: {supported_modes!r}"
    )

    video_qualities = provider.get_available_qualities(LIVE_URL, DownloadMode.VIDEO_ONLY)
    assert video_qualities, "YouTube exposed no selectable video qualities."
    selected_video_quality = video_qualities[-1]

    audio_qualities = provider.get_available_qualities(LIVE_URL, DownloadMode.AUDIO_ONLY)
    audio_qualities_by_extension = {}
    for quality in audio_qualities:
        extension = quality.label.split(" · ", maxsplit=1)[0]
        audio_qualities_by_extension.setdefault(extension, quality)

    assert len(audio_qualities_by_extension) >= 2, (
        "The chosen public video must expose at least two audio containers; "
        f"found {tuple(audio_qualities_by_extension)}."
    )

    cases: list[tuple[DownloadMode, str | None, str | None]] = [
        (DownloadMode.VIDEO_WITH_AUDIO, None, "mp4"),
        (DownloadMode.VIDEO_ONLY, selected_video_quality.id, None),
    ]
    cases.extend(
        (DownloadMode.AUDIO_ONLY, quality.id, extension.lower())
        for extension, quality in list(audio_qualities_by_extension.items())[:2]
    )

    for mode, quality_id, expected_extension in cases:
        downloaded = provider.download(
            LIVE_URL,
            tmp_path,
            DownloadOptions(mode=mode, quality_id=quality_id),
        )

        assert downloaded.file_path.is_file(), f"{mode.value} did not produce a file."
        assert downloaded.file_path.stat().st_size > 0, f"{mode.value} produced an empty file."
        if expected_extension is not None:
            assert downloaded.file_path.suffix.lower() == f".{expected_extension}", (
                f"{mode.value} produced unexpected container {downloaded.file_path.suffix!r}."
            )

        streams = _probe_streams(downloaded.file_path)
        video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
        audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]

        if mode is DownloadMode.VIDEO_WITH_AUDIO:
            assert video_streams, "Combined output contains no video stream."
            assert audio_streams, "Combined output contains no audio stream."
        elif mode is DownloadMode.VIDEO_ONLY:
            assert video_streams, "Video-only output contains no video stream."
            assert not audio_streams, "Video-only output unexpectedly contains audio."
        else:
            assert audio_streams, "Audio-only output contains no audio stream."
            assert not video_streams, "Audio-only output unexpectedly contains video."

        for stream in video_streams:
            assert stream.get("codec_name"), "ffprobe did not identify the video codec."
            assert stream.get("width") and stream.get("height"), "Video dimensions are missing."
        for stream in audio_streams:
            assert stream.get("codec_name"), "ffprobe did not identify the audio codec."
            assert stream.get("sample_rate"), "Audio sample rate is missing."
