"""Inactive Telegram localization foundation; no network or dispatcher registration."""

import re
from pathlib import Path
from typing import Literal, cast

from aiogram.types import CallbackQuery, Message, TelegramObject
from aiogram.utils.i18n import I18n, I18nMiddleware
from babel import Locale, UnknownLocaleError

LocaleCode = Literal["en", "ru", "es"]
DEFAULT_LOCALE: LocaleCode = "en"
SUPPORTED_LOCALES = frozenset({"en", "ru", "es"})
MAX_LANGUAGE_TAG_LENGTH = 64
_LANGUAGE_TAG = re.compile(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*")


def resolve_locale(language_code: object) -> LocaleCode:
    """Resolve supported Babel-parsable IETF tags; all other inputs use English.

    This is not a general BCP 47 parser. Valid extensions unsupported by Babel
    also fall back; never guess or reconstruct a malformed language tag.
    """
    if (
        type(language_code) is not str
        or not 0 < len(language_code) <= MAX_LANGUAGE_TAG_LENGTH
        or _LANGUAGE_TAG.fullmatch(language_code) is None
    ):
        return DEFAULT_LOCALE
    try:
        language = Locale.parse(language_code, sep="-").language
    except (UnknownLocaleError, ValueError, TypeError):
        return DEFAULT_LOCALE
    if language in SUPPORTED_LOCALES:
        return cast(LocaleCode, language)
    return DEFAULT_LOCALE


def validate_locale(locale: object) -> LocaleCode:
    """Validate a resolved presentation value without coercion."""
    if type(locale) is not str or locale not in SUPPORTED_LOCALES:
        raise ValueError("Unsupported resolved presentation locale.")
    return cast(LocaleCode, locale)


def locale_for_event(event: Message | CallbackQuery) -> LocaleCode:
    """Use the event sender, never callback.message.from_user."""
    return resolve_locale(getattr(event.from_user, "language_code", None))


def create_i18n() -> I18n:
    """Load compiled package resources only on explicit activation."""
    engine = I18n(path=Path(__file__).with_name("locales"), default_locale=DEFAULT_LOCALE)
    if set(engine.available_locales) != SUPPORTED_LOCALES:
        raise RuntimeError("Compiled translation catalogs are incomplete.")
    return engine


class RequestLocaleMiddleware(I18nMiddleware):
    """Prepared sender context; not installed in the existing dispatcher.

    After existing store validation, future handlers can enter the stored locale
    with i18n.use_locale(interaction.locale). This layer makes no access decision.
    """

    async def get_locale(self, event: TelegramObject, data: dict) -> str:
        if isinstance(event, (Message, CallbackQuery)):
            return locale_for_event(event)
        return resolve_locale(getattr(data.get("event_from_user"), "language_code", None))
