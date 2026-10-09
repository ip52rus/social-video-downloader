"""Environment-based application configuration."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit


class ConfigurationError(ValueError):
    """Raised when required or invalid application configuration is encountered."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated settings required to start the Telegram application."""

    telegram_bot_token: str = field(repr=False)
    app_env: str = "development"
    log_level: str = "INFO"
    telegram_api_base_url: str | None = None

    def __post_init__(self) -> None:
        if not self.telegram_bot_token.strip():
            raise ConfigurationError("TELEGRAM_BOT_TOKEN must not be empty.")

        if self.app_env not in {"development", "test", "production"}:
            raise ConfigurationError("APP_ENV must be one of: development, test, production.")

        normalized_log_level = self.log_level.upper()
        if normalized_log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ConfigurationError(
                "LOG_LEVEL must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL."
            )

        object.__setattr__(self, "log_level", normalized_log_level)

        if self.telegram_api_base_url is not None:
            base_url = self.telegram_api_base_url.strip().rstrip("/")
            parsed_url = urlsplit(base_url)
            if (
                parsed_url.scheme not in {"http", "https"}
                or not parsed_url.hostname
                or parsed_url.username is not None
                or parsed_url.password is not None
                or parsed_url.query
                or parsed_url.fragment
            ):
                raise ConfigurationError(
                    "TELEGRAM_API_BASE_URL must be an HTTP(S) base URL without credentials, "
                    "query, or fragment."
                )
            object.__setattr__(self, "telegram_api_base_url", base_url)

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        """Build settings from an environment mapping or the process environment."""
        source = os.environ if environ is None else environ
        token = source.get("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise ConfigurationError(
                "TELEGRAM_BOT_TOKEN is required. Set it in the process environment."
            )

        api_base_url = source.get("TELEGRAM_API_BASE_URL", "").strip() or None
        return cls(
            telegram_bot_token=token,
            app_env=source.get("APP_ENV", "development").strip().lower(),
            log_level=source.get("LOG_LEVEL", "INFO").strip(),
            telegram_api_base_url=api_base_url,
        )
