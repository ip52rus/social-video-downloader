"""Bounded, best-effort events; never serialize external objects or exceptions."""

import asyncio
import json
import logging
import math
from contextlib import contextmanager
from time import monotonic

from aiogram.exceptions import (
    TelegramAPIError,
    TelegramConflictError,
    TelegramEntityTooLarge,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramUnauthorizedError,
)

from social_video_downloader.domain.errors import (
    DownloadCleanupError,
    DownloaderError,
    DownloadFailedError,
    DownloadTimeoutError,
    InvalidMediaURLError,
    MediaProcessingError,
    MetadataExtractionError,
    UnsupportedDownloadModeError,
    UnsupportedPlatformError,
    UnsupportedQualityError,
)

LOGGER_NAME = "social_video_downloader.operations"
PLATFORMS = {"youtube", "instagram", "tiktok", "service"}
EVENTS = {"operation_started", "operation_completed", "operation_failed"}
PHASES = {
    "metadata",
    "download",
    "prepare",
    "download_prepare",
    "prepare_upload",
    "upload",
    "cleanup",
    "notification",
    "polling",
    "session_close",
    "unknown",
}
CATEGORIES = {
    "none",
    "cancelled",
    "timeout",
    "cleanup_failed",
    "invalid_url",
    "unsupported",
    "metadata_unavailable",
    "download_failed",
    "media_processing",
    "unconfirmed_upload",
    "telegram_api",
    "telegram_conflict",
    "telegram_unauthorized",
    "telegram_network",
    "telegram_rate_limit",
    "telegram_size",
    "filesystem",
    "unexpected",
    "refused",
}


def error_category(error, phase):
    """Classify by trusted types only, never str(error), repr, causes or class names."""
    if isinstance(error, asyncio.CancelledError):
        return "cancelled"
    if isinstance(error, DownloadCleanupError) or phase in {"cleanup", "session_close"}:
        return "cleanup_failed"
    if isinstance(error, (TimeoutError, DownloadTimeoutError)):
        return "timeout"
    if isinstance(error, TelegramEntityTooLarge):
        return "telegram_size"
    for error_type, category in (
        (TelegramConflictError, "telegram_conflict"),
        (TelegramUnauthorizedError, "telegram_unauthorized"),
        (TelegramRetryAfter, "telegram_rate_limit"),
        (TelegramNetworkError, "telegram_network"),
    ):
        if isinstance(error, error_type):
            return category
    if isinstance(error, TelegramAPIError):
        return "telegram_api"
    if isinstance(error, InvalidMediaURLError):
        return "invalid_url"
    if isinstance(
        error, (UnsupportedPlatformError, UnsupportedQualityError, UnsupportedDownloadModeError)
    ):
        return "unsupported"
    if isinstance(error, MetadataExtractionError):
        return "metadata_unavailable"
    if isinstance(error, MediaProcessingError):
        return "unconfirmed_upload" if phase == "upload" else "media_processing"
    if isinstance(error, DownloadFailedError):
        return "download_failed"
    if isinstance(error, DownloaderError):
        return "refused"
    if isinstance(error, OSError):
        return "filesystem"
    return "unexpected"


def _now():
    try:
        return monotonic()
    except Exception:
        return None


def safe_payload(payload):
    """Reconstruct only the fixed wire schema, including when formatting a record."""
    if type(payload) is not dict:
        return None
    fields = {"platform": PLATFORMS, "event": EVENTS, "phase": PHASES, "category": CATEGORIES}
    result = {}
    for field, choices in fields.items():
        value = payload.get(field)
        if type(value) is not str or value not in choices:
            return None
        result[field] = value
    value = payload.get("elapsed_ms")
    result["elapsed_ms"] = (
        round(value, 3)
        if type(value) in (int, float) and 0 <= value <= 604800000 and math.isfinite(value)
        else None
    )
    return result


def emit(platform, event, phase, category="none", elapsed_ms=None):
    try:
        payload = safe_payload(
            dict(
                platform=platform,
                event=event,
                phase=phase,
                category=category,
                elapsed_ms=elapsed_ms,
            )
        )
        if payload is not None:
            logging.getLogger(LOGGER_NAME).log(
                logging.WARNING if event == "operation_failed" else logging.INFO,
                json.dumps(payload, sort_keys=True),
                extra={"safe_event": payload},
            )
    except Exception:
        # A failed sink is never permission to retry a download/upload or skip cleanup.
        pass


def report_failure(platform, phase, error):
    """Ancillary failures have no measured start time; duration is explicitly null."""
    emit(platform, "operation_failed", phase, error_category(error, phase))


class Operation:
    """Observe an existing lifecycle without changing its exceptions or ownership."""

    def __init__(self, platform, phase):
        self.platform, self.phase = platform, phase
        self.started = None
        self.failure = None
        self._error = None

    def __enter__(self):
        self.started = _now()
        emit(self.platform, "operation_started", self.phase, elapsed_ms=0)
        return self

    def fail(self, error=None, *, category=None):
        if error is not None and error is self._error:
            return
        self._error = error
        phase = "cleanup" if isinstance(error, DownloadCleanupError) else self.phase
        self.failure = (phase, category or error_category(error, phase))

    @contextmanager
    def at(self, phase):
        self.phase = phase
        try:
            yield
        except BaseException as error:
            self.fail(error)
            raise

    def __exit__(self, _, error, __):
        if error is not None:
            self.fail(error)
        finished = _now()
        elapsed = (
            (finished - self.started) * 1000
            if finished is not None and self.started is not None
            else None
        )
        phase, category = self.failure or (self.phase, "none")
        emit(
            self.platform,
            "operation_failed" if self.failure else "operation_completed",
            phase,
            category,
            elapsed,
        )
        return False
