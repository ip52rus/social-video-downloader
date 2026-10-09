"""Tests for platform-independent download mode and quality options."""

from dataclasses import FrozenInstanceError

import pytest

from social_video_downloader.domain.models import (
    DownloadMode,
    DownloadOptions,
    QualityOption,
)


def test_download_modes_cover_all_required_outputs() -> None:
    assert DownloadMode.VIDEO_WITH_AUDIO.value == "video_with_audio"
    assert DownloadMode.VIDEO_ONLY.value == "video_only"
    assert DownloadMode.AUDIO_ONLY.value == "audio_only"


def test_download_options_default_to_best_available_quality() -> None:
    options = DownloadOptions()

    assert options.mode is DownloadMode.VIDEO_WITH_AUDIO
    assert options.quality_id is None


def test_download_options_can_select_audio_only_and_a_quality() -> None:
    options = DownloadOptions(
        mode=DownloadMode.AUDIO_ONLY,
        quality_id="audio-192",
    )

    assert options.mode is DownloadMode.AUDIO_ONLY
    assert options.quality_id == "audio-192"


def test_download_options_are_immutable() -> None:
    options = DownloadOptions()

    with pytest.raises(FrozenInstanceError):
        options.mode = DownloadMode.AUDIO_ONLY


@pytest.mark.parametrize("quality_id", ["", "   "])
def test_download_options_reject_blank_quality_id(quality_id: str) -> None:
    with pytest.raises(ValueError, match="quality"):
        DownloadOptions(quality_id=quality_id)


@pytest.mark.parametrize(
    ("mode", "height", "bitrate_kbps"),
    [
        (DownloadMode.VIDEO_WITH_AUDIO, 1080, None),
        (DownloadMode.VIDEO_ONLY, 720, None),
        (DownloadMode.AUDIO_ONLY, None, 192),
    ],
)
def test_quality_option_describes_available_quality(
    mode: DownloadMode,
    height: int | None,
    bitrate_kbps: int | None,
) -> None:
    option = QualityOption(
        id="provider-specific-id",
        label="1080p" if height else "192 kbps",
        mode=mode,
        height=height,
        bitrate_kbps=bitrate_kbps,
    )

    assert option.id == "provider-specific-id"
    assert option.mode is mode
    assert option.height == height
    assert option.bitrate_kbps == bitrate_kbps


@pytest.mark.parametrize(
    ("option_id", "label"),
    [("", "720p"), ("720", "  ")],
)
def test_quality_option_rejects_blank_id_or_label(
    option_id: str,
    label: str,
) -> None:
    with pytest.raises(ValueError):
        QualityOption(id=option_id, label=label, mode=DownloadMode.VIDEO_ONLY)


@pytest.mark.parametrize("height", [0, -1])
def test_quality_option_rejects_nonpositive_height(height: int) -> None:
    with pytest.raises(ValueError, match="height"):
        QualityOption(
            id="video-720",
            label="720p",
            mode=DownloadMode.VIDEO_ONLY,
            height=height,
        )


@pytest.mark.parametrize("bitrate", [0, -1])
def test_quality_option_rejects_nonpositive_bitrate(bitrate: int) -> None:
    with pytest.raises(ValueError, match="bitrate"):
        QualityOption(
            id="audio-192",
            label="192 kbps",
            mode=DownloadMode.AUDIO_ONLY,
            bitrate_kbps=bitrate,
        )
