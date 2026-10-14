"""Internal Telegram pending-interaction state and callback payload helpers."""

import secrets
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from threading import Lock

from social_video_downloader.services.choice_model import ChoicePlan

DEFAULT_INTERACTION_TTL = timedelta(minutes=15)
TELEGRAM_CALLBACK_DATA_LIMIT = 64
CALLBACK_PREFIX = "dl"
CALLBACK_VERSION = "v1"
INTERACTION_ID_BYTES = 16

Clock = Callable[[], datetime]
InteractionIdFactory = Callable[[], str]


class PendingInteractionStep(StrEnum):
    """Current callback step for a pending Telegram interaction."""

    MODE = "mode"
    QUALITY = "quality"


class CallbackAction(StrEnum):
    """Supported callback action tokens."""

    MODE = "m"
    QUALITY = "q"


class CallbackParseStatus(StrEnum):
    """Internal callback parsing outcomes."""

    VALID = "valid"
    MALFORMED = "malformed"
    UNSUPPORTED_VERSION = "unsupported_version"
    UNSUPPORTED_ACTION = "unsupported_action"


class PendingInteractionStatus(StrEnum):
    """Internal pending-interaction lookup and mutation outcomes."""

    FOUND = "found"
    UNKNOWN = "unknown"
    EXPIRED = "expired"
    WRONG_OWNER = "wrong_owner"
    WRONG_CHAT = "wrong_chat"
    WRONG_MESSAGE = "wrong_message"
    CONSUMED = "consumed"
    INVALID_CHOICE = "invalid_choice"


@dataclass(frozen=True, slots=True)
class ParsedCallback:
    """Parsed callback payload, if valid."""

    action: CallbackAction
    interaction_id: str
    choice_index: int


@dataclass(frozen=True, slots=True)
class CallbackParseResult:
    """Safe parser result for Telegram callback data."""

    status: CallbackParseStatus
    callback: ParsedCallback | None = None


@dataclass(frozen=True, slots=True)
class PendingInteraction:
    """Transient interaction state for resolving Telegram callbacks."""

    interaction_id: str
    owner_user_id: int
    chat_id: int
    message_id: int | None
    url: str
    plan: ChoicePlan
    created_at: datetime
    expires_at: datetime
    consumed: bool = False
    active_step: PendingInteractionStep | None = None
    selected_mode_index: int | None = None

    def __post_init__(self) -> None:
        if not self.interaction_id:
            raise ValueError("interaction_id must not be empty.")
        if not self.url.strip():
            raise ValueError("url must not be empty.")
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at.")
        if self.selected_mode_index is not None and self.selected_mode_index < 0:
            raise ValueError("selected_mode_index must not be negative.")


@dataclass(frozen=True, slots=True)
class PendingInteractionResult:
    """Internal store result for lookup, transition, and consume operations."""

    status: PendingInteractionStatus
    interaction: PendingInteraction | None = None


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(UTC)


def generate_interaction_id() -> str:
    """Generate a short opaque interaction ID for Telegram callback data."""
    return secrets.token_urlsafe(INTERACTION_ID_BYTES)


def build_callback_data(
    action: CallbackAction,
    interaction_id: str,
    choice_index: int,
) -> str:
    """Serialize callback data for a mode or quality choice."""
    if not isinstance(action, CallbackAction):
        raise TypeError("action must be a CallbackAction value.")
    if not interaction_id or ":" in interaction_id:
        raise ValueError("interaction_id must be non-empty and must not contain ':'.")
    if choice_index < 0:
        raise ValueError("choice_index must not be negative.")

    payload = f"{CALLBACK_PREFIX}:{CALLBACK_VERSION}:{interaction_id}:{action.value}:{choice_index}"
    if len(payload.encode("utf-8")) >= TELEGRAM_CALLBACK_DATA_LIMIT:
        raise ValueError("callback payload exceeds Telegram callback-data limit.")
    return payload


def build_mode_callback_data(interaction_id: str, mode_index: int) -> str:
    """Serialize callback data for a mode choice."""
    return build_callback_data(CallbackAction.MODE, interaction_id, mode_index)


def build_quality_callback_data(interaction_id: str, quality_index: int) -> str:
    """Serialize callback data for a quality choice."""
    return build_callback_data(CallbackAction.QUALITY, interaction_id, quality_index)


def parse_callback_data(payload: str) -> CallbackParseResult:
    """Parse callback data without invoking provider or application policy."""
    if not isinstance(payload, str):
        return CallbackParseResult(status=CallbackParseStatus.MALFORMED)

    parts = payload.split(":")
    if len(parts) != 5 or parts[0] != CALLBACK_PREFIX or not parts[2]:
        return CallbackParseResult(status=CallbackParseStatus.MALFORMED)

    if parts[1] != CALLBACK_VERSION:
        return CallbackParseResult(status=CallbackParseStatus.UNSUPPORTED_VERSION)

    try:
        action = CallbackAction(parts[3])
    except ValueError:
        return CallbackParseResult(status=CallbackParseStatus.UNSUPPORTED_ACTION)

    try:
        choice_index = int(parts[4])
    except ValueError:
        return CallbackParseResult(status=CallbackParseStatus.MALFORMED)

    if choice_index < 0:
        return CallbackParseResult(status=CallbackParseStatus.MALFORMED)

    return CallbackParseResult(
        status=CallbackParseStatus.VALID,
        callback=ParsedCallback(
            action=action,
            interaction_id=parts[2],
            choice_index=choice_index,
        ),
    )


class InMemoryPendingInteractionStore:
    """Single-process in-memory store for short-lived Telegram interactions."""

    def __init__(
        self,
        *,
        ttl: timedelta = DEFAULT_INTERACTION_TTL,
        clock: Clock = utc_now,
        id_factory: InteractionIdFactory = generate_interaction_id,
    ) -> None:
        if ttl <= timedelta(0):
            raise ValueError("ttl must be positive.")

        self._ttl = ttl
        self._clock = clock
        self._id_factory = id_factory
        self._interactions: dict[str, PendingInteraction] = {}
        self._lock = Lock()

    def create(
        self,
        *,
        owner_user_id: int,
        chat_id: int,
        url: str,
        plan: ChoicePlan,
        message_id: int | None = None,
        active_step: PendingInteractionStep | None = None,
    ) -> PendingInteraction:
        """Create and store a pending interaction."""
        now = self._clock()
        with self._lock:
            self._remove_expired(now)
            interaction_id = self._new_unique_interaction_id()
            interaction = PendingInteraction(
                interaction_id=interaction_id,
                owner_user_id=owner_user_id,
                chat_id=chat_id,
                message_id=message_id,
                url=url,
                plan=plan,
                created_at=now,
                expires_at=now + self._ttl,
                active_step=active_step,
            )
            self._interactions[interaction_id] = interaction
            return interaction

    def lookup(
        self,
        interaction_id: str,
        *,
        owner_user_id: int,
        chat_id: int,
        message_id: int | None = None,
    ) -> PendingInteractionResult:
        """Return a pending interaction after ownership and freshness checks."""
        with self._lock:
            return self._validated_result(
                interaction_id,
                owner_user_id=owner_user_id,
                chat_id=chat_id,
                message_id=message_id,
                now=self._clock(),
            )

    def transition_to_quality(
        self,
        interaction_id: str,
        *,
        owner_user_id: int,
        chat_id: int,
        mode_index: int,
        message_id: int | None = None,
    ) -> PendingInteractionResult:
        """Record the selected mode before rendering its quality choices."""
        with self._lock:
            result = self._validated_result(
                interaction_id,
                owner_user_id=owner_user_id,
                chat_id=chat_id,
                message_id=message_id,
                now=self._clock(),
            )
            if result.status is not PendingInteractionStatus.FOUND:
                return result

            interaction = result.interaction
            if interaction is None:
                raise RuntimeError("found interaction result without interaction.")
            if mode_index < 0 or mode_index >= len(interaction.plan.mode_choices):
                return PendingInteractionResult(status=PendingInteractionStatus.INVALID_CHOICE)

            mode_choice = interaction.plan.mode_choices[mode_index]
            if not mode_choice.quality_choices:
                return PendingInteractionResult(status=PendingInteractionStatus.INVALID_CHOICE)

            updated = replace(
                interaction,
                active_step=PendingInteractionStep.QUALITY,
                selected_mode_index=mode_index,
            )
            self._interactions[interaction_id] = updated
            return PendingInteractionResult(
                status=PendingInteractionStatus.FOUND,
                interaction=updated,
            )

    def consume_terminal(
        self,
        interaction_id: str,
        *,
        owner_user_id: int,
        chat_id: int,
        message_id: int | None = None,
    ) -> PendingInteractionResult:
        """Atomically mark a terminal interaction consumed before download starts."""
        with self._lock:
            result = self._validated_result(
                interaction_id,
                owner_user_id=owner_user_id,
                chat_id=chat_id,
                message_id=message_id,
                now=self._clock(),
            )
            if result.status is not PendingInteractionStatus.FOUND:
                return result

            interaction = result.interaction
            if interaction is None:
                raise RuntimeError("found interaction result without interaction.")

            consumed = replace(interaction, consumed=True)
            self._interactions[interaction_id] = consumed
            return PendingInteractionResult(
                status=PendingInteractionStatus.FOUND,
                interaction=consumed,
            )

    def remove(self, interaction_id: str) -> bool:
        """Remove an interaction if present."""
        with self._lock:
            return self._interactions.pop(interaction_id, None) is not None

    def _new_unique_interaction_id(self) -> str:
        for _ in range(10):
            interaction_id = self._id_factory()
            if (
                interaction_id
                and ":" not in interaction_id
                and interaction_id not in self._interactions
            ):
                return interaction_id
        raise RuntimeError("could not generate a unique interaction ID.")

    def _validated_result(
        self,
        interaction_id: str,
        *,
        owner_user_id: int,
        chat_id: int,
        message_id: int | None,
        now: datetime,
    ) -> PendingInteractionResult:
        interaction = self._interactions.get(interaction_id)
        if interaction is None:
            return PendingInteractionResult(status=PendingInteractionStatus.UNKNOWN)

        if now >= interaction.expires_at:
            self._interactions.pop(interaction_id, None)
            return PendingInteractionResult(status=PendingInteractionStatus.EXPIRED)

        if owner_user_id != interaction.owner_user_id:
            return PendingInteractionResult(status=PendingInteractionStatus.WRONG_OWNER)

        if chat_id != interaction.chat_id:
            return PendingInteractionResult(status=PendingInteractionStatus.WRONG_CHAT)

        if (
            message_id is not None
            and interaction.message_id is not None
            and message_id != interaction.message_id
        ):
            return PendingInteractionResult(status=PendingInteractionStatus.WRONG_MESSAGE)

        if interaction.consumed:
            return PendingInteractionResult(
                status=PendingInteractionStatus.CONSUMED,
                interaction=interaction,
            )

        return PendingInteractionResult(
            status=PendingInteractionStatus.FOUND,
            interaction=interaction,
        )

    def _remove_expired(self, now: datetime) -> None:
        expired_ids = [
            interaction_id
            for interaction_id, interaction in self._interactions.items()
            if now >= interaction.expires_at
        ]
        for interaction_id in expired_ids:
            self._interactions.pop(interaction_id, None)
