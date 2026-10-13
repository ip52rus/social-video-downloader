"""Application-level video quality tier mapping."""

from dataclasses import dataclass
from enum import StrEnum

from social_video_downloader.domain.models import DownloadMode, QualityOption


class QualityTier(StrEnum):
    """Product quality tiers exposed above provider capabilities."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ResolutionConfidence(StrEnum):
    """Confidence level for quality resolution classification."""

    DIMENSIONS = "dimensions"
    SINGLE_DIMENSION = "single_dimension"


QUALITY_TIER_TARGETS: dict[QualityTier, int] = {
    QualityTier.LOW: 480,
    QualityTier.MEDIUM: 720,
    QualityTier.HIGH: 1080,
}


@dataclass(frozen=True, slots=True)
class ClassifiedQuality:
    """A quality option with the resolution metric used for tier mapping."""

    option: QualityOption
    resolution: int
    confidence: ResolutionConfidence


@dataclass(frozen=True, slots=True)
class QualityTierChoice:
    """A product tier mapped to an existing provider quality option."""

    tier: QualityTier
    target_resolution: int
    quality: QualityOption
    quality_resolution: int
    confidence: ResolutionConfidence

    @property
    def quality_id(self) -> str:
        return self.quality.id


@dataclass(frozen=True, slots=True)
class QualityTierPlan:
    """Transport-independent quality choices derived from provider options."""

    choices: tuple[QualityTierChoice, ...]

    @property
    def should_show_quality_screen(self) -> bool:
        return len(self.choices) > 1

    @property
    def single_choice(self) -> QualityTierChoice | None:
        if len(self.choices) != 1:
            return None
        return self.choices[0]


def classify_quality(option: QualityOption) -> ClassifiedQuality | None:
    """Classify a provider quality option with an orientation-independent metric."""
    if option.width is not None and option.height is not None:
        return ClassifiedQuality(
            option=option,
            resolution=min(option.width, option.height),
            confidence=ResolutionConfidence.DIMENSIONS,
        )

    if option.height is not None:
        return ClassifiedQuality(
            option=option,
            resolution=option.height,
            confidence=ResolutionConfidence.SINGLE_DIMENSION,
        )

    if option.width is not None:
        return ClassifiedQuality(
            option=option,
            resolution=option.width,
            confidence=ResolutionConfidence.SINGLE_DIMENSION,
        )

    return None


def build_quality_tier_plan(qualities: tuple[QualityOption, ...]) -> QualityTierPlan:
    """Map video quality options to collapsed Low / Medium / High tier choices."""
    classified = tuple(
        item
        for option in qualities
        if option.mode in {DownloadMode.VIDEO_WITH_AUDIO, DownloadMode.VIDEO_ONLY}
        if (item := classify_quality(option)) is not None
    )
    if not classified:
        return QualityTierPlan(())

    mapped_choices = tuple(
        _choice_for_tier(tier, target, classified) for tier, target in QUALITY_TIER_TARGETS.items()
    )
    return QualityTierPlan(_collapse_duplicate_choices(mapped_choices))


def _choice_for_tier(
    tier: QualityTier,
    target: int,
    classified: tuple[ClassifiedQuality, ...],
) -> QualityTierChoice:
    lower_or_equal = tuple(item for item in classified if item.resolution <= target)
    if lower_or_equal:
        selected = min(
            lower_or_equal,
            key=lambda item: (-item.resolution, item.option.id, item.option.label),
        )
    else:
        selected = min(
            classified,
            key=lambda item: (item.resolution, item.option.id, item.option.label),
        )

    return QualityTierChoice(
        tier=tier,
        target_resolution=target,
        quality=selected.option,
        quality_resolution=selected.resolution,
        confidence=selected.confidence,
    )


def _collapse_duplicate_choices(
    choices: tuple[QualityTierChoice, ...],
) -> tuple[QualityTierChoice, ...]:
    by_quality: dict[tuple[DownloadMode, str], QualityTierChoice] = {}

    for choice in choices:
        key = (choice.quality.mode, choice.quality.id)
        current = by_quality.get(key)
        if current is None or _duplicate_rank(choice) < _duplicate_rank(current):
            by_quality[key] = choice

    return tuple(
        sorted(
            by_quality.values(),
            key=lambda choice: (
                list(QUALITY_TIER_TARGETS).index(choice.tier),
                choice.quality_resolution,
                choice.quality.id,
            ),
        )
    )


def _duplicate_rank(choice: QualityTierChoice) -> tuple[int, int, int]:
    target_delta = abs(choice.quality_resolution - choice.target_resolution)
    target_is_below_quality = int(choice.target_resolution < choice.quality_resolution)
    tier_index = list(QUALITY_TIER_TARGETS).index(choice.tier)
    return target_delta, target_is_below_quality, tier_index
