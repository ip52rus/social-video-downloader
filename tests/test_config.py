import pytest

from social_video_downloader.config import ConfigurationError, Settings


def test_settings_load_required_token_and_defaults():
    settings = Settings.from_env({"TELEGRAM_BOT_TOKEN": "test-token"})

    assert settings.telegram_bot_token == "test-token"
    assert settings.app_env == "development"
    assert settings.log_level == "INFO"
    assert settings.telegram_api_base_url is None


def test_settings_normalizes_app_env_and_log_level():
    settings = Settings.from_env(
        {
            "TELEGRAM_BOT_TOKEN": " test-token ",
            "APP_ENV": "TEST",
            "LOG_LEVEL": "warning",
        }
    )

    assert settings.telegram_bot_token == "test-token"
    assert settings.app_env == "test"
    assert settings.log_level == "WARNING"


def test_settings_normalizes_optional_telegram_api_base_url():
    settings = Settings.from_env(
        {
            "TELEGRAM_BOT_TOKEN": "test-token",
            "TELEGRAM_API_BASE_URL": " http://127.0.0.1:8081/ ",
        }
    )

    assert settings.telegram_api_base_url == "http://127.0.0.1:8081"


def test_settings_ignores_blank_optional_telegram_api_base_url():
    settings = Settings.from_env(
        {"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_API_BASE_URL": " "}
    )

    assert settings.telegram_api_base_url is None


@pytest.mark.parametrize(
    "base_url",
    [
        "localhost:8081",
        "ftp://127.0.0.1:8081",
        "http://",
        "http://user:password@127.0.0.1:8081",
        "http://127.0.0.1:8081?token=secret",
        "http://127.0.0.1:8081#fragment",
    ],
)
def test_settings_rejects_invalid_telegram_api_base_url(base_url):
    with pytest.raises(ConfigurationError, match="TELEGRAM_API_BASE_URL"):
        Settings.from_env(
            {"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_API_BASE_URL": base_url}
        )


@pytest.mark.parametrize("token", ["", " ", "\n"])
def test_settings_rejects_missing_or_blank_token(token):
    with pytest.raises(ConfigurationError, match="TELEGRAM_BOT_TOKEN"):
        Settings.from_env({"TELEGRAM_BOT_TOKEN": token})


@pytest.mark.parametrize("app_env", ["", "staging", "Production-ish"])
def test_settings_rejects_unknown_environment(app_env):
    with pytest.raises(ConfigurationError, match="APP_ENV"):
        Settings.from_env({"TELEGRAM_BOT_TOKEN": "test-token", "APP_ENV": app_env})


@pytest.mark.parametrize("log_level", ["", "TRACE", "VERBOSE", "20"])
def test_settings_rejects_invalid_log_level(log_level):
    with pytest.raises(ConfigurationError, match="LOG_LEVEL"):
        Settings.from_env({"TELEGRAM_BOT_TOKEN": "test-token", "LOG_LEVEL": log_level})


def test_settings_does_not_expose_token_in_repr():
    settings = Settings.from_env({"TELEGRAM_BOT_TOKEN": "do-not-print-this"})

    assert "do-not-print-this" not in repr(settings)


def test_settings_are_immutable():
    settings = Settings.from_env({"TELEGRAM_BOT_TOKEN": "test-token"})

    with pytest.raises(AttributeError):
        settings.app_env = "production"
