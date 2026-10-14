"""Application-level download choice planning."""

from dataclasses import dataclass
from enum import StrEnum

from social_video_downloader.domain.models import DownloadMode, DownloadOptions, QualityOption
from social_video_downloader.providers.base import MediaProvider
from social_video_downloader.services.quality_tiers import QualityTier, build_quality_tier_plan

HIDDEN_VIDEO_ONLY_REASON = "hidden_by_normal_policy"
SAFE_QUALITY_MAPPING_UNAVAILABLE_REASON = "safe_quality_mapping_unavailable"
NO_USEFUL_MODES_REASON = "no_useful_modes"


class ChoicePlanState(StrEnum):
    """State of an application-level download choice plan."""

    DIRECT_DOWNLOAD = "direct_download"
    CHOOSE_MODE = "choose_mode"
    CHOOSE_QUALITY = "choose_quality"
    BLOCKED = "blocked"


class UserChoiceKind(StrEnum):
    """Product-level user choice kinds independent of transport labels."""

    VIDEO = "video"
    AUDIO = "audio"


@dataclass(frozen=True, slots=True)
class QualityChoice:
    """A quality tier choice that already resolves to concrete download options."""

    tier: QualityTier
    quality: QualityOption
    final_options: DownloadOptions


@dataclass(frozen=True, slots=True)
class ModeChoice:
    """A user-facing mode choice that either terminates or opens quality choices."""

    kind: UserChoiceKind
    mode: DownloadMode
    final_options: DownloadOptions | None
    quality_choices: tuple[QualityChoice, ...] = ()


@dataclass(frozen=True, slots=True)
class ChoicePlan:
    """An actionable transport-independent choice plan for one media URL."""

    state: ChoicePlanState
    technical_modes: tuple[DownloadMode, ...]
    hidden_modes: tuple[tuple[DownloadMode, str], ...]
    unavailable_choices: tuple[tuple[UserChoiceKind, str], ...]
    mode_choices: tuple[ModeChoice, ...] = ()
    quality_choices: tuple[QualityChoice, ...] = ()
    automatic_options: DownloadOptions | None = None
    blocked_reason: str | None = None


def build_choice_plan(provider: MediaProvider, url: str) -> ChoicePlan:
    """Build an actionable product choice plan from provider capabilities."""
    technical_modes = _ordered_modes(provider.get_supported_modes(url))
    hidden_modes = _hidden_modes(technical_modes)

    mode_choices: list[ModeChoice] = []
    unavailable_choices: list[tuple[UserChoiceKind, str]] = []

    if DownloadMode.VIDEO_WITH_AUDIO in technical_modes:
        video_choice = _video_choice(provider, url)
        if video_choice is None:
            unavailable_choices.append(
                (UserChoiceKind.VIDEO, SAFE_QUALITY_MAPPING_UNAVAILABLE_REASON)
            )
        else:
            mode_choices.append(video_choice)

    if DownloadMode.AUDIO_ONLY in technical_modes:
        mode_choices.append(
            ModeChoice(
                kind=UserChoiceKind.AUDIO,
                mode=DownloadMode.AUDIO_ONLY,
                final_options=DownloadOptions(mode=DownloadMode.AUDIO_ONLY),
            )
        )

    if not mode_choices:
        return ChoicePlan(
            state=ChoicePlanState.BLOCKED,
            technical_modes=technical_modes,
            hidden_modes=hidden_modes,
            unavailable_choices=tuple(unavailable_choices),
            blocked_reason=(
                SAFE_QUALITY_MAPPING_UNAVAILABLE_REASON
                if unavailable_choices
                else NO_USEFUL_MODES_REASON
            ),
        )

    if len(mode_choices) == 1:
        only_choice = mode_choices[0]
        if only_choice.final_options is not None:
            return ChoicePlan(
                state=ChoicePlanState.DIRECT_DOWNLOAD,
                technical_modes=technical_modes,
                hidden_modes=hidden_modes,
                unavailable_choices=tuple(unavailable_choices),
                mode_choices=tuple(mode_choices),
                automatic_options=only_choice.final_options,
            )

        return ChoicePlan(
            state=ChoicePlanState.CHOOSE_QUALITY,
            technical_modes=technical_modes,
            hidden_modes=hidden_modes,
            unavailable_choices=tuple(unavailable_choices),
            mode_choices=tuple(mode_choices),
            quality_choices=only_choice.quality_choices,
        )

    return ChoicePlan(
        state=ChoicePlanState.CHOOSE_MODE,
        technical_modes=technical_modes,
        hidden_modes=hidden_modes,
        unavailable_choices=tuple(unavailable_choices),
        mode_choices=tuple(mode_choices),
    )


def _video_choice(provider: MediaProvider, url: str) -> ModeChoice | None:
    qualities = provider.get_available_qualities(url, DownloadMode.VIDEO_WITH_AUDIO)
    if not qualities:
        return ModeChoice(
            kind=UserChoiceKind.VIDEO,
            mode=DownloadMode.VIDEO_WITH_AUDIO,
            final_options=DownloadOptions(mode=DownloadMode.VIDEO_WITH_AUDIO),
        )

    tier_plan = build_quality_tier_plan(qualities)
    quality_choices = tuple(
        QualityChoice(
            tier=choice.tier,
            quality=choice.quality,
            final_options=DownloadOptions(
                mode=DownloadMode.VIDEO_WITH_AUDIO,
                quality_id=choice.quality_id,
            ),
        )
        for choice in tier_plan.choices
    )

    if not quality_choices:
        return None

    if len(quality_choices) == 1:
        return ModeChoice(
            kind=UserChoiceKind.VIDEO,
            mode=DownloadMode.VIDEO_WITH_AUDIO,
            final_options=quality_choices[0].final_options,
            quality_choices=quality_choices,
        )

    return ModeChoice(
        kind=UserChoiceKind.VIDEO,
        mode=DownloadMode.VIDEO_WITH_AUDIO,
        final_options=None,
        quality_choices=quality_choices,
    )


def _hidden_modes(
    technical_modes: tuple[DownloadMode, ...],
) -> tuple[tuple[DownloadMode, str], ...]:
    if DownloadMode.VIDEO_ONLY not in technical_modes:
        return ()
    return ((DownloadMode.VIDEO_ONLY, HIDDEN_VIDEO_ONLY_REASON),)


def _ordered_modes(modes: tuple[DownloadMode, ...]) -> tuple[DownloadMode, ...]:
    mode_order = {
        DownloadMode.VIDEO_WITH_AUDIO: 0,
        DownloadMode.VIDEO_ONLY: 1,
        DownloadMode.AUDIO_ONLY: 2,
    }
    return tuple(sorted(set(modes), key=lambda mode: mode_order[mode]))
