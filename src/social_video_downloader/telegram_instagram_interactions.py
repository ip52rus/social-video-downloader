"""Bounded Instagram choices; no URLs/identities in opaque Telegram payloads."""

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from re import fullmatch
from threading import Lock

from social_video_downloader.domain.carousel import CarouselScope, CarouselSelectionPlan
from social_video_downloader.services.instagram_acquisition import plan_payload
from social_video_downloader.telegram_i18n import DEFAULT_LOCALE, validate_locale
from social_video_downloader.telegram_interactions import (
    DEFAULT_INTERACTION_TTL,
    generate_interaction_id,
    utc_now,
)


@dataclass(frozen=True, slots=True, repr=False)
class InstagramChoice:
    token: str
    user_id: int
    chat_id: int
    plans: tuple[CarouselSelectionPlan, ...] = field(repr=False)
    expires_at: datetime
    message_id: int | None = None
    locale: str = field(default=DEFAULT_LOCALE, kw_only=True)

    def __post_init__(self):
        validate_locale(self.locale)


@dataclass(frozen=True, slots=True, repr=False)
class InstagramSelection:
    plan: CarouselSelectionPlan
    locale: str


def parse_instagram_callback(data):
    if not isinstance(data, str) or len(data) > 64:
        return None
    match = fullmatch(r"ig:v1:([A-Za-z0-9_-]{22}):([01])", data)
    return (match[1], int(match[2])) if match else None


class InstagramChoiceStore:
    """One process; lock-protected owner/message binding and destructive one-shot take."""

    def __init__(self, *, clock=utc_now, ttl=DEFAULT_INTERACTION_TTL, capacity=128):
        if not isinstance(ttl, timedelta) or ttl.total_seconds() <= 0 or capacity <= 0:
            raise ValueError("Invalid Instagram choice limits.")
        self._clock, self._ttl, self._capacity = clock, ttl, capacity
        self._choices: dict[str, InstagramChoice] = {}
        self._lock = Lock()

    def create(self, user_id, chat_id, plans, *, locale=DEFAULT_LOCALE):
        validate_locale(locale)
        if type(user_id) is not int or type(chat_id) is not int or not 1 <= len(plans) <= 2:
            raise ValueError("Invalid Instagram choice owner or plans.")
        for plan in plans:
            plan_payload(plan)  # Validate the complete contract before it can be offered.
        if plans[0].scope is not CarouselScope.PUBLICATION or (
            len(plans) == 2
            and (
                plans[1].scope is not CarouselScope.SINGLE_VIDEO
                or plans[1].items != plans[0].items
                or plans[1].publication_url != plans[0].publication_url
                or plans[1].parent_identity != plans[0].parent_identity
            )
        ):
            raise ValueError("Invalid Instagram actions.")
        with self._lock:
            now = self._clock()
            self._choices = {k: v for k, v in self._choices.items() if now < v.expires_at}
            if len(self._choices) >= self._capacity:
                return None
            token = generate_interaction_id()
            if token in self._choices:
                return None
            choice = InstagramChoice(
                token, user_id, chat_id, tuple(plans), now + self._ttl, locale=locale
            )
            self._choices[token] = choice
            return choice

    def bind(self, token, message_id):
        with self._lock:
            choice = self._choices.get(token)
            if (
                choice is None
                or choice.message_id is not None
                or type(message_id) is not int
                or message_id <= 0
                or self._clock() >= choice.expires_at
            ):
                self._choices.pop(token, None)
                return False
            self._choices[token] = replace(choice, message_id=message_id)
            return True

    def resolve(self, token, index, user_id, chat_id, message_id, *, consume=False):
        selection = self.resolve_selection(
            token, index, user_id, chat_id, message_id, consume=consume
        )
        return selection.plan if selection is not None else None

    def resolve_selection(self, token, index, user_id, chat_id, message_id, *, consume=False):
        with self._lock:
            choice = self._choices.get(token)
            if choice is None:
                return None
            if self._clock() >= choice.expires_at:
                self._choices.pop(token, None)
                return None
            if (
                type(user_id) is not int
                or type(chat_id) is not int
                or type(message_id) is not int
                or choice.message_id is None
                or (user_id, chat_id, message_id)
                != (choice.user_id, choice.chat_id, choice.message_id)
                or type(index) is not int
                or not 0 <= index < len(choice.plans)
            ):
                return None
            if consume:
                self._choices.pop(token)
            return InstagramSelection(choice.plans[index], choice.locale)

    def remove(self, token):
        with self._lock:
            self._choices.pop(token, None)
