import logging

from social_video_downloader.config import Settings
from social_video_downloader.logging_config import configure_logging


def test_configure_logging_uses_configured_level_and_safe_format(monkeypatch):
    calls = []
    monkeypatch.setattr(logging, "basicConfig", lambda **kwargs: calls.append(kwargs))
    settings = Settings.from_env(
        {"TELEGRAM_BOT_TOKEN": "must-not-appear-in-logs", "LOG_LEVEL": "debug"}
    )

    configure_logging(settings)

    assert calls == [
        {
            "level": "DEBUG",
            "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        }
    ]
    assert "must-not-appear-in-logs" not in repr(calls)
