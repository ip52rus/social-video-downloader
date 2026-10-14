"""Tests for application-level download choice planning."""

from pathlib import Path

from social_video_downloader.domain.models import (
    DownloadedMedia,
    DownloadMode,
    DownloadOptions,
    MediaMetadata,
    Platform,
    QualityOption,
)
from social_video_downloader.services.choice_model import (
    HIDDEN_VIDEO_ONLY_REASON,
    NO_USEFUL_MODES_REASON,
    SAFE_QUALITY_MAPPING_UNAVAILABLE_REASON,
    ChoicePlanState,
    UserChoiceKind,
)
from social_video_downloader.services.download import DownloadService
from social_video_downloader.services.quality_tiers import QualityTier


class FakeProvider:
    """Provider stub that exposes deterministic capabilities without network access."""

    def __init__(
        self,
        *,
        platform: Platform = Platform.YOUTUBE,
        modes: tuple[DownloadMode, ...],
        qualities: tuple[QualityOption, ...] = (),
    ) -> None:
        self.platform = platform
        self._modes = modes
        self._qualities = qualities
        self.supported_mode_urls: list[str] = []
        self.quality_requests: list[tuple[str, DownloadMode]] = []

    def can_handle(self, url: str) -> bool:
        return True

    def extract_metadata(self, url: str) -> MediaMetadata:
        return MediaMetadata(
            title="Example",
            source_url=url,
            platform=self.platform,
        )

    def get_supported_modes(self, url: str) -> tuple[DownloadMode, ...]:
        self.supported_mode_urls.append(url)
        return self._modes

    def get_available_qualities(
        self,
        url: str,
        mode: DownloadMode,
    ) -> tuple[QualityOption, ...]:
        self.quality_requests.append((url, mode))
        if mode is not DownloadMode.VIDEO_WITH_AUDIO:
            return ()
        return self._qualities

    def download(
        self,
        url: str,
        output_dir: Path,
        options: DownloadOptions | None = None,
    ) -> DownloadedMedia:
        return DownloadedMedia(
            file_path=output_dir / "media.mp4",
            metadata=MediaMetadata(
                title="Example",
                source_url=url,
                platform=self.platform,
            ),
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


def create_plan(
    provider: FakeProvider,
    url: str = "https://www.youtube.com/watch?v=example",
):
    service = DownloadService([provider])
    return service.create_choice_plan(url)


def test_direct_single_automatic_video_path_uses_provider_default_quality() -> None:
    provider = FakeProvider(
        platform=Platform.INSTAGRAM,
        modes=(DownloadMode.VIDEO_WITH_AUDIO,),
    )

    plan = create_plan(provider, "https://www.instagram.com/reel/example/")

    assert plan.state is ChoicePlanState.DIRECT_DOWNLOAD
    assert plan.automatic_options == DownloadOptions(mode=DownloadMode.VIDEO_WITH_AUDIO)
    assert plan.mode_choices[0].final_options == plan.automatic_options
    assert plan.quality_choices == ()
    assert provider.supported_mode_urls == ["https://www.instagram.com/reel/example/"]
    assert provider.quality_requests == [
        ("https://www.instagram.com/reel/example/", DownloadMode.VIDEO_WITH_AUDIO)
    ]


def test_video_and_audio_require_mode_selection_with_actionable_audio_choice() -> None:
    provider = FakeProvider(
        modes=(
            DownloadMode.VIDEO_WITH_AUDIO,
            DownloadMode.AUDIO_ONLY,
        ),
        qualities=(
            video_quality("480", width=854, height=480),
            video_quality("720", width=1280, height=720),
            video_quality("1080", width=1920, height=1080),
        ),
    )

    plan = create_plan(provider)

    assert plan.state is ChoicePlanState.CHOOSE_MODE
    assert [choice.kind for choice in plan.mode_choices] == [
        UserChoiceKind.VIDEO,
        UserChoiceKind.AUDIO,
    ]

    audio_choice = plan.mode_choices[1]
    assert audio_choice.final_options == DownloadOptions(mode=DownloadMode.AUDIO_ONLY)
    assert audio_choice.quality_choices == ()


def test_video_only_mode_is_hidden_from_normal_user_choices() -> None:
    provider = FakeProvider(
        modes=(
            DownloadMode.VIDEO_WITH_AUDIO,
            DownloadMode.VIDEO_ONLY,
            DownloadMode.AUDIO_ONLY,
        ),
        qualities=(video_quality("720", width=1280, height=720),),
    )

    plan = create_plan(provider)

    assert plan.hidden_modes == ((DownloadMode.VIDEO_ONLY, HIDDEN_VIDEO_ONLY_REASON),)
    assert [choice.mode for choice in plan.mode_choices] == [
        DownloadMode.VIDEO_WITH_AUDIO,
        DownloadMode.AUDIO_ONLY,
    ]


def test_video_with_three_distinct_tiers_exposes_quality_choices() -> None:
    provider = FakeProvider(
        modes=(DownloadMode.VIDEO_WITH_AUDIO,),
        qualities=(
            video_quality("480", width=854, height=480),
            video_quality("720", width=1280, height=720),
            video_quality("1080", width=1920, height=1080),
        ),
    )

    plan = create_plan(provider)

    assert plan.state is ChoicePlanState.CHOOSE_QUALITY
    assert [(choice.tier, choice.final_options.quality_id) for choice in plan.quality_choices] == [
        (QualityTier.LOW, "480"),
        (QualityTier.MEDIUM, "720"),
        (QualityTier.HIGH, "1080"),
    ]
    assert all(
        choice.final_options.mode is DownloadMode.VIDEO_WITH_AUDIO
        for choice in plan.quality_choices
    )
    assert plan.automatic_options is None


def test_video_with_two_collapsed_tiers_exposes_only_meaningful_choices() -> None:
    provider = FakeProvider(
        modes=(DownloadMode.VIDEO_WITH_AUDIO,),
        qualities=(
            video_quality("480", width=854, height=480),
            video_quality("900", width=1600, height=900),
        ),
    )

    plan = create_plan(provider)

    assert plan.state is ChoicePlanState.CHOOSE_QUALITY
    assert [(choice.tier, choice.final_options.quality_id) for choice in plan.quality_choices] == [
        (QualityTier.LOW, "480"),
        (QualityTier.HIGH, "900"),
    ]


def test_one_distinct_video_tier_skips_quality_screen_and_preserves_quality_id() -> None:
    provider = FakeProvider(
        modes=(DownloadMode.VIDEO_WITH_AUDIO,),
        qualities=(video_quality("height-720", width=1280, height=720),),
    )

    plan = create_plan(provider)

    assert plan.state is ChoicePlanState.DIRECT_DOWNLOAD
    assert plan.automatic_options == DownloadOptions(
        mode=DownloadMode.VIDEO_WITH_AUDIO,
        quality_id="height-720",
    )
    assert plan.mode_choices[0].final_options == plan.automatic_options
    assert [
        (choice.tier, choice.final_options.quality_id)
        for choice in plan.mode_choices[0].quality_choices
    ] == [(QualityTier.MEDIUM, "height-720")]


def test_unclassifiable_video_qualities_do_not_become_automatic_best() -> None:
    provider = FakeProvider(
        modes=(DownloadMode.VIDEO_WITH_AUDIO,),
        qualities=(video_quality("unknown"),),
    )

    plan = create_plan(provider)

    assert plan.state is ChoicePlanState.BLOCKED
    assert plan.automatic_options is None
    assert plan.blocked_reason == SAFE_QUALITY_MAPPING_UNAVAILABLE_REASON
    assert plan.unavailable_choices == (
        (UserChoiceKind.VIDEO, SAFE_QUALITY_MAPPING_UNAVAILABLE_REASON),
    )


def test_no_useful_modes_are_blocked() -> None:
    provider = FakeProvider(modes=())

    plan = create_plan(provider)

    assert plan.state is ChoicePlanState.BLOCKED
    assert plan.blocked_reason == NO_USEFUL_MODES_REASON
    assert plan.automatic_options is None
    assert plan.mode_choices == ()


def test_plan_is_deterministic_independent_of_provider_mode_ordering() -> None:
    qualities = (
        video_quality("720", width=1280, height=720),
        video_quality("480", width=854, height=480),
    )
    first = create_plan(
        FakeProvider(
            modes=(
                DownloadMode.AUDIO_ONLY,
                DownloadMode.VIDEO_ONLY,
                DownloadMode.VIDEO_WITH_AUDIO,
            ),
            qualities=qualities,
        )
    )
    second = create_plan(
        FakeProvider(
            modes=(
                DownloadMode.VIDEO_WITH_AUDIO,
                DownloadMode.VIDEO_ONLY,
                DownloadMode.AUDIO_ONLY,
            ),
            qualities=qualities,
        )
    )

    assert first == second


def test_resulting_plan_contains_actionable_options_without_external_policy_logic() -> None:
    provider = FakeProvider(
        modes=(
            DownloadMode.VIDEO_WITH_AUDIO,
            DownloadMode.AUDIO_ONLY,
        ),
        qualities=(
            video_quality("480", width=854, height=480),
            video_quality("720", width=1280, height=720),
            video_quality("1080", width=1920, height=1080),
        ),
    )

    plan = create_plan(provider)

    terminal_options = [
        choice.final_options
        for mode_choice in plan.mode_choices
        for choice in mode_choice.quality_choices
    ]
    terminal_options.extend(
        choice.final_options for choice in plan.mode_choices if choice.final_options is not None
    )

    assert terminal_options == [
        DownloadOptions(mode=DownloadMode.VIDEO_WITH_AUDIO, quality_id="480"),
        DownloadOptions(mode=DownloadMode.VIDEO_WITH_AUDIO, quality_id="720"),
        DownloadOptions(mode=DownloadMode.VIDEO_WITH_AUDIO, quality_id="1080"),
        DownloadOptions(mode=DownloadMode.AUDIO_ONLY),
    ]
