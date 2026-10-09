"""Helpers for generating safe, cross-platform filenames."""

import re
import unicodedata

_INVALID_FILENAME_CHARS = frozenset('<>:"/\\|?*')
_REPEATED_UNDERSCORES = re.compile(r"_+")
_VALID_EXTENSION = re.compile(r"[A-Za-z0-9]{1,12}")

_RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def safe_filename(
    title: str,
    *,
    extension: str | None = None,
    max_bytes: int = 240,
) -> str:
    """Return a safe filename, optionally adding a validated extension.

    The byte limit applies to the UTF-8 encoded filename, including its
    extension. Directory components and platform-specific invalid characters
    are replaced rather than interpreted as paths.
    """
    if not isinstance(title, str):
        raise TypeError("Filename title must be a string.")

    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int):
        raise TypeError("max_bytes must be an integer.")

    if max_bytes < 1:
        raise ValueError("max_bytes must be positive.")

    suffix = ""
    if extension is not None:
        if not isinstance(extension, str):
            raise TypeError("Filename extension must be a string.")

        normalized_extension = extension.removeprefix(".")
        if not _VALID_EXTENSION.fullmatch(normalized_extension):
            raise ValueError("Extension must contain 1 to 12 ASCII letters or digits.")

        suffix = f".{normalized_extension.lower()}"

    minimum_bytes = len(b"media") + len(suffix.encode("utf-8"))
    if max_bytes < minimum_bytes:
        raise ValueError(f"max_bytes must be at least {minimum_bytes} for this extension.")

    normalized_title = unicodedata.normalize("NFC", title)
    cleaned_characters = []

    for character in normalized_title:
        if character in _INVALID_FILENAME_CHARS or unicodedata.category(character).startswith("C"):
            cleaned_characters.append("_")
        else:
            cleaned_characters.append(character)

    name = "".join(cleaned_characters)
    name = _REPEATED_UNDERSCORES.sub("_", name).strip(" .")

    if not name:
        name = "media"

    reserved_name = name.split(".", maxsplit=1)[0].rstrip(" .").upper()
    if reserved_name in _RESERVED_WINDOWS_NAMES:
        name = f"_{name}"

    available_bytes = max_bytes - len(suffix.encode("utf-8"))
    if len(name.encode("utf-8")) > available_bytes:
        truncated_characters = []
        used_bytes = 0

        for character in name:
            character_bytes = len(character.encode("utf-8"))
            if used_bytes + character_bytes > available_bytes:
                break

            truncated_characters.append(character)
            used_bytes += character_bytes

        name = "".join(truncated_characters).rstrip(" .")

    if not name:
        name = "media"

    reserved_name = name.split(".", maxsplit=1)[0].rstrip(" .").upper()
    if reserved_name in _RESERVED_WINDOWS_NAMES:
        name = f"_{name}"

    return f"{name}{suffix}"
