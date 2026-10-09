"""Environment-based application configuration."""

import os
from dataclasses import dataclass, field
from collections.abc import Mapping


class ConfigurationError(ValueError):
    """Raised when required or invalid application configuration is encountered."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated settings required to start the Telegram application."""

    telegram_bot_token: str = field(repr=False)
    app_env: str = "development"
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        if not self.telegram_bot_token.strip():
            raise ConfigurationError("TELEGRAM_BOT_TOKEN must not be empty.")

        if self.app_env not in {"development", "test", "production"}:
            raise ConfigurationError(
                "APP_ENV must be one of: development, test, production."
            )

        normalized_log_level = self.log_level.upper()
        if normalized_log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ConfigurationError(
                "LOG_LEVEL must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL."
            )

        object.__setattr__(self, "log_level", normalized_log_level)

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        """Build settings from an environment mapping or the process environment."""
        source = os.environ if environ is None else environ
        token = source.get("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise ConfigurationError(
                "TELEGRAM_BOT_TOKEN is required. Set it in the process environment."
            )

        return cls(
            telegram_bot_token=token,
            app_env=source.get("APP_ENV", "development").strip().lower(),
            log_level=source.get("LOG_LEVEL", "INFO").strip(),
        )
