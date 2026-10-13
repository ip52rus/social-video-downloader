"""Tests for application-level video quality tier mapping."""

import pytest

from social_video_downloader.domain.models import DownloadMode, QualityOption
from social_video_downloader.services.quality_tiers import (
    QualityTier,
    ResolutionConfidence,
    build_quality_tier_plan,
    classify_quality,
)


def video_quality(
    quality_id: str,
    *,
    width: int | None = None,
    height: int | None = None,
) -> QualityOption:
    return QualityOption(
        id=quality_id,
        label=quality_id,
        mode=DownloadMode.VIDEO_WITH_AUDIO,
        width=width,
        height=height,
    )


@pytest.mark.parametrize(
    ("quality", "expected_resolution"),
    [
        (video_quality("landscape-1080", width=1920, height=1080), 1080),
        (video_quality("portrait-1080", width=1080, height=1920), 1080),
        (video_quality("square-1080", width=1080, height=1080), 1080),
    ],
)
def test_classifies_orientation_independent_resolution(
    quality: QualityOption,
    expected_resolution: int,
) -> None:
    classified = classify_quality(quality)

    assert classified is not None
    assert classified.resolution == expected_resolution
    assert classified.confidence is ResolutionConfidence.DIMENSIONS


def test_maps_exact_480_720_1080_targets() -> None:
    plan = build_quality_tier_plan(
        (
            video_quality("480", width=854, height=480),
            video_quality("720", width=1280, height=720),
            video_quality("1080", width=1920, height=1080),
        )
    )

    assert [(choice.tier, choice.quality_id) for choice in plan.choices] == [
        (QualityTier.LOW, "480"),
        (QualityTier.MEDIUM, "720"),
        (QualityTier.HIGH, "1080"),
    ]
    assert plan.should_show_quality_screen
    assert plan.single_choice is None


def test_missing_exact_target_uses_highest_available_below_target() -> None:
    plan = build_quality_tier_plan(
        (
            video_quality("360", width=640, height=360),
            video_quality("540", width=960, height=540),
            video_quality("1080", width=1920, height=1080),
        )
    )

    assert [(choice.tier, choice.quality_id) for choice in plan.choices] == [
        (QualityTier.LOW, "360"),
        (QualityTier.MEDIUM, "540"),
        (QualityTier.HIGH, "1080"),
    ]


def test_all_available_below_target_uses_highest_available_below_target() -> None:
    plan = build_quality_tier_plan(
        (
            video_quality("480", width=854, height=480),
            video_quality("900", width=1600, height=900),
        )
    )

    assert [(choice.tier, choice.quality_id) for choice in plan.choices] == [
        (QualityTier.LOW, "480"),
        (QualityTier.HIGH, "900"),
    ]


def test_all_available_above_target_uses_lowest_available_above_target() -> None:
    plan = build_quality_tier_plan(
        (
            video_quality("1440", width=2560, height=1440),
            video_quality("2160", width=3840, height=2160),
        )
    )

    assert [(choice.tier, choice.quality_id) for choice in plan.choices] == [
        (QualityTier.HIGH, "1440"),
    ]
    assert plan.single_choice is plan.choices[0]
    assert not plan.should_show_quality_screen


@pytest.mark.parametrize(
    "quality",
    [
        video_quality("height-only", height=720),
        video_quality("width-only", width=720),
    ],
)
def test_one_dimension_fallback_is_classified_with_lower_confidence(
    quality: QualityOption,
) -> None:
    classified = classify_quality(quality)

    assert classified is not None
    assert classified.resolution == 720
    assert classified.confidence is ResolutionConfidence.SINGLE_DIMENSION


def test_unclassifiable_option_is_excluded_from_tier_mapping() -> None:
    plan = build_quality_tier_plan(
        (
            video_quality("unknown"),
            video_quality("720", width=1280, height=720),
        )
    )

    assert [(choice.tier, choice.quality_id) for choice in plan.choices] == [
        (QualityTier.MEDIUM, "720"),
    ]


def test_returns_no_choices_when_all_options_are_unclassifiable() -> None:
    plan = build_quality_tier_plan((video_quality("unknown"),))

    assert plan.choices == ()
    assert not plan.should_show_quality_screen
    assert plan.single_choice is None


def test_duplicate_tier_mappings_collapse_to_closest_semantic_tier() -> None:
    plan = build_quality_tier_plan((video_quality("720", width=1280, height=720),))

    assert [(choice.tier, choice.quality_id) for choice in plan.choices] == [
        (QualityTier.MEDIUM, "720"),
    ]
    assert plan.single_choice is plan.choices[0]
    assert not plan.should_show_quality_screen


def test_duplicate_tier_tie_break_prefers_tier_above_actual_resolution() -> None:
    plan = build_quality_tier_plan((video_quality("600", width=800, height=600),))

    assert [(choice.tier, choice.quality_id) for choice in plan.choices] == [
        (QualityTier.MEDIUM, "600"),
    ]


def test_mapping_is_deterministic_independent_of_input_order() -> None:
    qualities = (
        video_quality("720-b", width=1280, height=720),
        video_quality("720-a", width=1280, height=720),
        video_quality("1080", width=1920, height=1080),
        video_quality("360", width=640, height=360),
    )

    forward = build_quality_tier_plan(qualities)
    reverse = build_quality_tier_plan(tuple(reversed(qualities)))

    assert [(choice.tier, choice.quality_id) for choice in forward.choices] == [
        (QualityTier.LOW, "360"),
        (QualityTier.MEDIUM, "720-a"),
        (QualityTier.HIGH, "1080"),
    ]
    assert forward == reverse


def test_ignores_audio_options_for_video_tier_mapping() -> None:
    audio = QualityOption(
        id="audio",
        label="audio",
        mode=DownloadMode.AUDIO_ONLY,
        bitrate_kbps=128,
    )

    plan = build_quality_tier_plan(
        (
            audio,
            video_quality("720", width=1280, height=720),
        )
    )

    assert [(choice.tier, choice.quality_id) for choice in plan.choices] == [
        (QualityTier.MEDIUM, "720"),
    ]
