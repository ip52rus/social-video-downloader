from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

from social_video_downloader.domain.models import DownloadMode, DownloadOptions, QualityOption
from social_video_downloader.services.choice_model import (
    ChoicePlan,
    ChoicePlanState,
    ModeChoice,
    QualityChoice,
    UserChoiceKind,
)
from social_video_downloader.services.quality_tiers import QualityTier
from social_video_downloader.telegram_interactions import (
    TELEGRAM_CALLBACK_DATA_LIMIT,
    CallbackAction,
    CallbackParseStatus,
    InMemoryPendingInteractionStore,
    PendingInteractionStatus,
    PendingInteractionStep,
    build_mode_callback_data,
    build_quality_callback_data,
    generate_interaction_id,
    parse_callback_data,
)


class FakeClock:
    def __init__(self, initial: datetime) -> None:
        self.current = initial

    def __call__(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta


def _quality_choice(quality_id: str, tier: QualityTier) -> QualityChoice:
    return QualityChoice(
        tier=tier,
        quality=QualityOption(
            id=quality_id,
            label=quality_id,
            mode=DownloadMode.VIDEO_WITH_AUDIO,
            width=1280,
            height=720,
        ),
        final_options=DownloadOptions(
            mode=DownloadMode.VIDEO_WITH_AUDIO,
            quality_id=quality_id,
        ),
    )


def _choice_plan() -> ChoicePlan:
    quality_choices = (
        _quality_choice("quality-480", QualityTier.LOW),
        _quality_choice("quality-720", QualityTier.MEDIUM),
    )
    return ChoicePlan(
        state=ChoicePlanState.CHOOSE_MODE,
        technical_modes=(DownloadMode.VIDEO_WITH_AUDIO, DownloadMode.AUDIO_ONLY),
        hidden_modes=(),
        unavailable_choices=(),
        mode_choices=(
            ModeChoice(
                kind=UserChoiceKind.VIDEO,
                mode=DownloadMode.VIDEO_WITH_AUDIO,
                final_options=None,
                quality_choices=quality_choices,
            ),
            ModeChoice(
                kind=UserChoiceKind.AUDIO,
                mode=DownloadMode.AUDIO_ONLY,
                final_options=DownloadOptions(mode=DownloadMode.AUDIO_ONLY),
            ),
        ),
    )


def _store(clock: FakeClock | None = None) -> InMemoryPendingInteractionStore:
    return InMemoryPendingInteractionStore(
        clock=clock or FakeClock(datetime(2026, 1, 1, tzinfo=UTC)),
    )


def test_interaction_creation_stores_minimal_pending_state() -> None:
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, tzinfo=UTC))
    plan = _choice_plan()
    store = _store(clock)

    interaction = store.create(
        owner_user_id=123,
        chat_id=456,
        message_id=789,
        url="https://www.youtube.com/watch?v=example",
        plan=plan,
        active_step=PendingInteractionStep.MODE,
    )

    assert interaction.owner_user_id == 123
    assert interaction.chat_id == 456
    assert interaction.message_id == 789
    assert interaction.url == "https://www.youtube.com/watch?v=example"
    assert interaction.plan is plan
    assert interaction.created_at == clock.current
    assert interaction.expires_at == clock.current + timedelta(minutes=15)
    assert interaction.consumed is False
    assert interaction.active_step is PendingInteractionStep.MODE
    assert interaction.selected_mode_index is None


def test_generated_interaction_ids_are_opaque_unique_and_short() -> None:
    interaction_ids = {generate_interaction_id() for _ in range(200)}

    assert len(interaction_ids) == 200
    assert all(":" not in interaction_id for interaction_id in interaction_ids)
    assert all(10 <= len(interaction_id) <= 32 for interaction_id in interaction_ids)


def test_mode_callback_serializes_and_parses() -> None:
    payload = build_mode_callback_data("opaque-id", 3)

    result = parse_callback_data(payload)

    assert result.status is CallbackParseStatus.VALID
    assert result.callback is not None
    assert result.callback.action is CallbackAction.MODE
    assert result.callback.interaction_id == "opaque-id"
    assert result.callback.choice_index == 3


def test_quality_callback_serializes_and_parses() -> None:
    payload = build_quality_callback_data("opaque-id", 2)

    result = parse_callback_data(payload)

    assert result.status is CallbackParseStatus.VALID
    assert result.callback is not None
    assert result.callback.action is CallbackAction.QUALITY
    assert result.callback.interaction_id == "opaque-id"
    assert result.callback.choice_index == 2


def test_malformed_callback_is_rejected() -> None:
    assert parse_callback_data("not-callback").status is CallbackParseStatus.MALFORMED
    assert parse_callback_data("dl:v1::m:0").status is CallbackParseStatus.MALFORMED
    assert parse_callback_data("dl:v1:abc:m:not-int").status is CallbackParseStatus.MALFORMED
    assert parse_callback_data("dl:v1:abc:m:-1").status is CallbackParseStatus.MALFORMED


def test_unsupported_callback_version_and_action_are_rejected() -> None:
    assert (
        parse_callback_data("dl:v2:opaque-id:m:0").status is CallbackParseStatus.UNSUPPORTED_VERSION
    )
    assert (
        parse_callback_data("dl:v1:opaque-id:x:0").status is CallbackParseStatus.UNSUPPORTED_ACTION
    )


def test_callback_payload_excludes_url_and_remains_under_telegram_limit() -> None:
    interaction_id = generate_interaction_id()
    payload = build_quality_callback_data(interaction_id, 123456)

    assert "youtube" not in payload
    assert "watch" not in payload
    assert "quality-720" not in payload
    assert len(payload.encode("utf-8")) < TELEGRAM_CALLBACK_DATA_LIMIT


def test_lookup_accepts_correct_owner_and_chat() -> None:
    store = _store()
    interaction = store.create(
        owner_user_id=123,
        chat_id=456,
        message_id=789,
        url="https://www.youtube.com/watch?v=example",
        plan=_choice_plan(),
    )

    result = store.lookup(
        interaction.interaction_id, owner_user_id=123, chat_id=456, message_id=789
    )

    assert result.status is PendingInteractionStatus.FOUND
    assert result.interaction == interaction


def test_lookup_rejects_wrong_owner() -> None:
    store = _store()
    interaction = store.create(
        owner_user_id=123,
        chat_id=456,
        message_id=789,
        url="https://www.youtube.com/watch?v=example",
        plan=_choice_plan(),
    )

    result = store.lookup(interaction.interaction_id, owner_user_id=999, chat_id=456)

    assert result.status is PendingInteractionStatus.WRONG_OWNER


def test_lookup_rejects_wrong_chat() -> None:
    store = _store()
    interaction = store.create(
        owner_user_id=123,
        chat_id=456,
        message_id=789,
        url="https://www.youtube.com/watch?v=example",
        plan=_choice_plan(),
    )

    result = store.lookup(interaction.interaction_id, owner_user_id=123, chat_id=999)

    assert result.status is PendingInteractionStatus.WRONG_CHAT


def test_lookup_rejects_wrong_message() -> None:
    store = _store()
    interaction = store.create(
        owner_user_id=123,
        chat_id=456,
        message_id=789,
        url="https://www.youtube.com/watch?v=example",
        plan=_choice_plan(),
    )

    result = store.lookup(
        interaction.interaction_id,
        owner_user_id=123,
        chat_id=456,
        message_id=111,
    )

    assert result.status is PendingInteractionStatus.WRONG_MESSAGE


def test_expiry_at_15_minute_boundary_and_lazy_removal() -> None:
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, tzinfo=UTC))
    store = _store(clock)
    interaction = store.create(
        owner_user_id=123,
        chat_id=456,
        message_id=789,
        url="https://www.youtube.com/watch?v=example",
        plan=_choice_plan(),
    )

    clock.advance(timedelta(minutes=15) - timedelta(microseconds=1))
    before_expiry = store.lookup(
        interaction.interaction_id, owner_user_id=123, chat_id=456, message_id=789
    )
    assert before_expiry.status is PendingInteractionStatus.FOUND

    clock.advance(timedelta(microseconds=1))
    expired = store.lookup(
        interaction.interaction_id, owner_user_id=123, chat_id=456, message_id=789
    )
    assert expired.status is PendingInteractionStatus.EXPIRED

    removed = store.lookup(
        interaction.interaction_id, owner_user_id=123, chat_id=456, message_id=789
    )
    assert removed.status is PendingInteractionStatus.UNKNOWN


def test_expired_interaction_cannot_transition_to_quality_without_prior_lookup() -> None:
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, tzinfo=UTC))
    store = _store(clock)
    interaction = store.create(
        owner_user_id=123,
        chat_id=456,
        message_id=789,
        url="https://www.youtube.com/watch?v=example",
        plan=_choice_plan(),
        active_step=PendingInteractionStep.MODE,
    )

    clock.advance(timedelta(minutes=15))
    expired = store.transition_to_quality(
        interaction.interaction_id,
        owner_user_id=123,
        chat_id=456,
        message_id=789,
        mode_index=0,
    )
    removed = store.lookup(
        interaction.interaction_id, owner_user_id=123, chat_id=456, message_id=789
    )

    assert expired.status is PendingInteractionStatus.EXPIRED
    assert removed.status is PendingInteractionStatus.UNKNOWN


def test_expired_interaction_cannot_be_consumed_without_prior_lookup() -> None:
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, tzinfo=UTC))
    store = _store(clock)
    interaction = store.create(
        owner_user_id=123,
        chat_id=456,
        message_id=789,
        url="https://www.youtube.com/watch?v=example",
        plan=_choice_plan(),
    )

    clock.advance(timedelta(minutes=15))
    expired = store.consume_terminal(
        interaction.interaction_id,
        owner_user_id=123,
        chat_id=456,
    )
    removed = store.lookup(
        interaction.interaction_id, owner_user_id=123, chat_id=456, message_id=789
    )

    assert expired.status is PendingInteractionStatus.EXPIRED
    assert removed.status is PendingInteractionStatus.UNKNOWN


def test_mode_to_quality_transition_persists_selected_mode_index() -> None:
    store = _store()
    interaction = store.create(
        owner_user_id=123,
        chat_id=456,
        message_id=789,
        url="https://www.youtube.com/watch?v=example",
        plan=_choice_plan(),
        active_step=PendingInteractionStep.MODE,
    )

    result = store.transition_to_quality(
        interaction.interaction_id,
        owner_user_id=123,
        chat_id=456,
        message_id=789,
        mode_index=0,
    )

    assert result.status is PendingInteractionStatus.FOUND
    assert result.interaction is not None
    assert result.interaction.active_step is PendingInteractionStep.QUALITY
    assert result.interaction.selected_mode_index == 0
    assert result.interaction.plan.mode_choices[0].quality_choices


def test_terminal_consume_succeeds_once_then_reports_consumed() -> None:
    store = _store()
    interaction = store.create(
        owner_user_id=123,
        chat_id=456,
        message_id=789,
        url="https://www.youtube.com/watch?v=example",
        plan=_choice_plan(),
    )

    first = store.consume_terminal(
        interaction.interaction_id, owner_user_id=123, chat_id=456, message_id=789
    )
    second = store.consume_terminal(
        interaction.interaction_id, owner_user_id=123, chat_id=456, message_id=789
    )
    lookup = store.lookup(
        interaction.interaction_id, owner_user_id=123, chat_id=456, message_id=789
    )

    assert first.status is PendingInteractionStatus.FOUND
    assert first.interaction is not None
    assert first.interaction.consumed is True
    assert second.status is PendingInteractionStatus.CONSUMED
    assert lookup.status is PendingInteractionStatus.CONSUMED


def test_unknown_interaction_returns_unknown() -> None:
    result = _store().lookup("missing", owner_user_id=123, chat_id=456, message_id=789)

    assert result.status is PendingInteractionStatus.UNKNOWN


def test_two_thread_terminal_consume_allows_exactly_one_success() -> None:
    store = _store()
    interaction = store.create(
        owner_user_id=123,
        chat_id=456,
        message_id=789,
        url="https://www.youtube.com/watch?v=example",
        plan=_choice_plan(),
    )
    barrier = Barrier(2)

    def consume() -> PendingInteractionStatus:
        barrier.wait(timeout=5)
        return store.consume_terminal(
            interaction.interaction_id,
            owner_user_id=123,
            chat_id=456,
            message_id=789,
        ).status

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(consume) for _ in range(2)]
        statuses = [future.result(timeout=5) for future in futures]

    assert statuses.count(PendingInteractionStatus.FOUND) == 1
    assert statuses.count(PendingInteractionStatus.CONSUMED) == 1
