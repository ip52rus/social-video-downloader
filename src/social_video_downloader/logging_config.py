"""Allowlisted application events only; suppress unstructured library diagnostics."""

import json
import logging

from social_video_downloader.config import Settings
from social_video_downloader.operation_logging import LOGGER_NAME, error_category, safe_payload


class SafeEventFilter(logging.Filter):
    def filter(self, record):
        # One exact aiogram 3.x error template: retain polling failure types, never its
        # exception text, bot identity, backoff details, or arbitrary library records.
        if (
            record.name == "aiogram.dispatcher"
            and record.msg == "Failed to fetch updates - %s: %s"
            and type(record.args) is tuple
            and len(record.args) == 2
            and isinstance(record.args[1], Exception)
        ):
            record.safe_event = dict(
                platform="service",
                event="operation_failed",
                phase="polling",
                category=error_category(record.args[1], "polling"),
                elapsed_ms=None,
            )
            return True
        return (
            record.name == LOGGER_NAME
            and safe_payload(getattr(record, "safe_event", None)) is not None
        )


class SafeEventFormatter(logging.Formatter):
    def format(self, record):
        # Do not call getMessage/formatException: even a library traceback may contain secrets.
        return json.dumps(safe_payload(getattr(record, "safe_event", None)), sort_keys=True)


class SafeEventHandler(logging.StreamHandler):
    def handleError(self, record):
        # StreamHandler's default debug traceback can expose local paths on sink failure.
        pass


def configure_logging(settings: Settings) -> None:
    handler = SafeEventHandler()
    handler.addFilter(SafeEventFilter())
    handler.setFormatter(SafeEventFormatter())
    logging.basicConfig(level=settings.log_level, handlers=[handler], force=True)
