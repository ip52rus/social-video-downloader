"""One-process admission leases for Telegram requests, not a download queue."""

import shutil
from collections.abc import Callable
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from tempfile import gettempdir
from time import monotonic

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, Message

from social_video_downloader.domain.errors import DownloadCleanupError, DownloaderError
from social_video_downloader.domain.urls import detect_platform, normalize_media_url
from social_video_downloader.resource_limits import DownloadLimits
from social_video_downloader.telegram_i18n import get_i18n, tr

ACTIVE_MESSAGE = (
    "You already have an active request. Wait for it to finish, or use /cancel while choosing."
)
RATE_MESSAGE = "Please wait a few seconds before sending another link."
BUSY_MESSAGE = "The bot is busy. Try again later."
STALE_MESSAGE = "This choice is no longer available. Send the link again."


@dataclass(slots=True, repr=False)
class WaitingChoice:
    key: tuple[str, str]
    expires_at: datetime
    invalidate: Callable[[], object] = field(repr=False)


@dataclass(slots=True, repr=False)
class RequestLease:
    user_id: int = field(repr=False)
    limits: DownloadLimits
    contexts: int = 1
    pending: WaitingChoice | None = None
    callback_active: bool = False
    quarantined: bool = False
    working: bool = True


_current: ContextVar[RequestLease | None] = ContextVar("download_request", default=None)


def retain_current_request():
    """Fail closed when owned work/cleanup is not confirmed complete."""
    if (lease := _current.get()) is not None:
        lease.quarantined = True


def hold_choice(platform, token, expires_at, invalidate):
    if (lease := _current.get()) is not None:
        lease.pending = WaitingChoice((platform, token), expires_at, invalidate)


def consume_choice(platform, token):
    if (
        (lease := _current.get()) is not None
        and lease.pending is not None
        and lease.pending.key == (platform, token)
    ):
        lease.pending = None


def current_limits():
    lease = _current.get()
    return lease.limits if lease is not None else None


def check_delivery_file(path):
    if (lease := _current.get()) is not None:
        lease.limits.check_file(path)


@contextmanager
def protected_cleanup(manager):
    """Never delete an uncertain owned worker's workspace; retain failed cleanup."""
    directory = manager.__enter__()
    try:
        yield directory
    except DownloadCleanupError:
        retain_current_request()
        finalizer = getattr(manager, "_finalizer", None)
        if finalizer is not None:
            finalizer.detach()
        raise
    except BaseException as error:
        try:
            suppressed = manager.__exit__(type(error), error, error.__traceback__)
        except BaseException as cleanup_error:
            if cleanup_error is not error:
                retain_current_request()
            raise
        if not suppressed:
            raise
    else:
        try:
            manager.__exit__(None, None, None)
        except BaseException:
            retain_current_request()
            raise


class DownloadAdmission:
    """Event-loop owned; synchronous mutations have no await/race window."""

    def __init__(
        self,
        *,
        limits=None,
        max_active=4,
        max_pending=128,
        youtube_limits=None,
        notice_interval=5,
        link_interval=3,
        clock=monotonic,
        utc_clock=lambda: datetime.now(UTC),
        free_bytes=None,
    ):
        if type(max_active) is not int or not 1 <= max_active <= 8:
            raise ValueError("Global admission must be from 1 to 8.")
        if not 0 <= link_interval <= 300:
            raise ValueError("Invalid link interval.")
        if type(max_pending) is not int or not 1 <= max_pending <= 1024:
            raise ValueError("Pending admission must be from 1 to 1024.")
        if type(notice_interval) is not int or not 1 <= notice_interval <= 300:
            raise ValueError("Invalid refusal notice interval.")
        self.max_pending = max_pending
        self.youtube_limits = youtube_limits or self._default_youtube_limits()
        self.notice_interval = notice_interval
        self.limits = limits or DownloadLimits()
        self.max_active = max_active
        self.link_interval = link_interval
        self._clock, self._utc_clock = clock, utc_clock
        self._free_bytes = free_bytes or (lambda: shutil.disk_usage(gettempdir()).free)
        self._leases: dict[int, RequestLease] = {}
        self._attempts: dict[int, float] = {}
        self._notices: dict[int, float] = {}

    @staticmethod
    def _default_youtube_limits():
        return DownloadLimits(2_000_000_000, 4 * 1024**3, 8 * 1024**3, 512 * 1024**2)

    def should_notify(self, user_id):
        now = self._clock()
        self._notices = {k: v for k, v in self._notices.items() if now - v < self.notice_interval}
        if user_id in self._notices:
            return False
        if len(self._notices) >= 4096:
            del self._notices[next(iter(self._notices))]
        self._notices[user_id] = now
        return True

    def _work_available(self, limits):
        working = [lease for lease in self._leases.values() if lease.working]
        if len(working) >= self.max_active:
            return False
        required = (
            limits.min_free_bytes
            + limits.max_workspace_bytes
            + sum(lease.limits.max_workspace_bytes for lease in working)
        )
        try:
            return self._free_bytes() >= required
        except OSError:
            return False

    def _expire(self):
        now = self._utc_clock()
        for user, lease in tuple(self._leases.items()):
            if (
                lease.contexts == 0
                and not lease.quarantined
                and lease.pending is not None
                and now >= lease.pending.expires_at
            ):
                lease.pending.invalidate()
                del self._leases[user]

    def admit(self, user_id, *, platform=None):
        self._expire()
        if user_id in self._leases:
            return None, ACTIVE_MESSAGE
        now = self._clock()
        self._attempts = {k: v for k, v in self._attempts.items() if now - v < self.link_interval}
        if user_id in self._attempts:
            return None, RATE_MESSAGE
        if len(self._attempts) >= 4096:
            return None, BUSY_MESSAGE
        self._attempts[user_id] = now
        limits = self.youtube_limits if platform == "youtube" else self.limits
        if len(self._leases) >= self.max_pending or not self._work_available(limits):
            return None, BUSY_MESSAGE
        lease = RequestLease(user_id, limits)
        self._leases[user_id] = lease
        return lease, None

    def enter_callback(self, user_id, key):
        self._expire()
        lease = self._leases.get(user_id)
        if lease is None or lease.pending is None or lease.pending.key != key:
            return None, STALE_MESSAGE
        if lease.quarantined or lease.callback_active:
            return None, BUSY_MESSAGE
        if not lease.working:
            if not self._work_available(lease.limits):
                return None, BUSY_MESSAGE
            lease.working = True
        lease.contexts += 1
        lease.callback_active = True
        return lease, None

    def leave(self, lease, *, callback=False):
        lease.contexts -= 1
        if callback:
            lease.callback_active = False
        if lease.contexts == 0 and not lease.quarantined:
            lease.working = False
        if (
            lease.contexts == 0
            and lease.pending is None
            and not lease.quarantined
            and self._leases.get(lease.user_id) is lease
        ):
            del self._leases[lease.user_id]

    def cancel_waiting(self, user_id):
        self._expire()
        lease = self._leases.get(user_id)
        if lease is None:
            return "There is no waiting choice to cancel."
        if lease.contexts or lease.quarantined or lease.pending is None:
            return (
                "This request is already running. Wait for it to finish; "
                "/cancel only cancels a waiting choice."
            )
        lease.pending.invalidate()
        del self._leases[user_id]
        return "Choice cancelled. You can send another link."


class DownloadProtectionMiddleware(BaseMiddleware):
    def __init__(self, admission, callback_choice):
        self.admission = admission
        self.callback_choice = callback_choice

    async def __call__(self, handler, event, data):
        data["download_admission"] = self.admission
        callback = isinstance(event, CallbackQuery)
        if callback:
            # Stores validate owner/chat/message/expiry first; no untrusted locale lookup.
            choice = self.callback_choice(event, data.get("instagram_reels"))
            if choice is None:
                return await handler(event, data)
            key, locale = choice
            lease, refusal = self.admission.enter_callback(event.from_user.id, key)
            if refusal:
                with get_i18n().use_locale(locale), suppress(TelegramAPIError, TimeoutError):
                    await event.answer(tr(refusal))
                return
        elif isinstance(event, Message):
            text = (event.text or "").strip()
            if any(c.isspace() for c in text):
                return await handler(event, data)
            try:
                platform = detect_platform(normalize_media_url(text))
            except DownloaderError:
                return await handler(event, data)
            if event.from_user is None:
                return
            lease, refusal = self.admission.admit(event.from_user.id, platform=platform.value)
            if refusal:
                if self.admission.should_notify(event.from_user.id):
                    await event.answer(tr(refusal))
                return
        else:
            return await handler(event, data)
        token = _current.set(lease)
        try:
            return await handler(event, data)
        except DownloadCleanupError:
            retain_current_request()
            raise
        finally:
            self.admission.leave(lease, callback=callback)
            _current.reset(token)
