import io
import json
import logging

from social_video_downloader.config import Settings
from social_video_downloader.logging_config import (
    SafeEventFilter,
    SafeEventFormatter,
    SafeEventHandler,
    configure_logging,
)
from social_video_downloader.operation_logging import LOGGER_NAME


def test_configure_logging_installs_private_sink(monkeypatch):
    calls = []
    monkeypatch.setattr(logging, "basicConfig", lambda **kwargs: calls.append(kwargs))
    configure_logging(Settings.from_env({"TELEGRAM_BOT_TOKEN": "SECRET", "LOG_LEVEL": "debug"}))
    config = calls[0]
    assert config["level"] == "DEBUG" and config["force"] is True
    assert isinstance(config["handlers"][0].formatter, SafeEventFormatter)
    assert isinstance(config["handlers"][0].filters[0], SafeEventFilter)
    assert "SECRET" not in repr(calls)


def test_sink_drops_library_text_and_never_formats_exceptions():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(SafeEventFilter())
    handler.setFormatter(SafeEventFormatter())
    secret = "URL_TOKEN_COOKIE_USER_ID_PATH_HTML"
    record = logging.LogRecord("aiogram.event", logging.ERROR, secret, 1, secret, (), None)
    handler.handle(record)
    assert stream.getvalue() == ""
    record.name = LOGGER_NAME
    record.safe_event = dict(
        platform="youtube",
        event="operation_failed",
        phase="download",
        category="unexpected",
        elapsed_ms=1,
        url=secret,
    )
    record.exc_info = (RuntimeError, RuntimeError(secret), None)
    handler.handle(record)
    data = json.loads(stream.getvalue())
    assert data["category"] == "unexpected" and secret not in stream.getvalue()
    assert set(data) == {"platform", "event", "phase", "category", "elapsed_ms"}
    record.safe_event["category"] = secret
    handler.handle(record)
    assert len(stream.getvalue().splitlines()) == 1


def test_failed_output_sink_never_prints_logging_traceback(capsys):
    class BrokenStream:
        def write(self, text):
            raise OSError("PRIVATE_URL_COOKIE_PATH")

    handler = SafeEventHandler(BrokenStream())
    handler.addFilter(SafeEventFilter())
    handler.setFormatter(SafeEventFormatter())
    record = logging.LogRecord(LOGGER_NAME, logging.INFO, "PRIVATE_PATH", 1, "PRIVATE", (), None)
    record.safe_event = dict(
        platform="tiktok",
        event="operation_completed",
        phase="cleanup",
        category="none",
        elapsed_ms=1,
    )
    handler.handle(record)
    assert capsys.readouterr() == ("", "")


def test_polling_errors_keep_only_trusted_type_category():
    from aiogram.exceptions import TelegramConflictError
    from aiogram.methods import GetUpdates

    record = logging.LogRecord(
        "aiogram.dispatcher",
        logging.ERROR,
        "PRIVATE_PATH",
        1,
        "Failed to fetch updates - %s: %s",
        ("PRIVATE_CLASS", TelegramConflictError(method=GetUpdates(), message="PRIVATE_TOKEN_ID")),
        None,
    )
    assert SafeEventFilter().filter(record)
    text = SafeEventFormatter().format(record)
    assert "PRIVATE" not in text
    assert json.loads(text) == dict(
        platform="service",
        event="operation_failed",
        phase="polling",
        category="telegram_conflict",
        elapsed_ms=None,
    )
