"""Tests for safe filename generation."""

import pytest

from social_video_downloader.infrastructure.filenames import safe_filename


def test_preserves_readable_unicode_title() -> None:
    assert safe_filename("Привет, мир — видео") == "Привет, мир — видео"


def test_replaces_path_separators_and_invalid_characters() -> None:
    assert safe_filename("folder/name: clip?.mp4") == "folder_name_ clip_.mp4"


def test_replaces_control_characters() -> None:
    assert safe_filename("line\nbreak\tname") == "line_break_name"


@pytest.mark.parametrize("title", ["", "   ", "...", "   ...   "])
def test_uses_fallback_for_empty_or_dot_only_title(title: str) -> None:
    assert safe_filename(title) == "media"


@pytest.mark.parametrize("title", ["CON", "NUL.txt", "aux", "COM1.mp4", "LPT9"])
def test_protects_reserved_windows_device_names(title: str) -> None:
    assert safe_filename(title).startswith("_")


def test_normalizes_extension() -> None:
    assert safe_filename("My video", extension=".MP4") == "My video.mp4"


@pytest.mark.parametrize("extension", ["", "../mp4", "mp4?", "longextension123"])
def test_rejects_invalid_extensions(extension: str) -> None:
    with pytest.raises(ValueError):
        safe_filename("My video", extension=extension)


def test_respects_utf8_byte_limit_including_extension() -> None:
    result = safe_filename("я" * 100, extension="mp4", max_bytes=20)

    assert result == "я" * 8 + ".mp4"
    assert len(result.encode("utf-8")) <= 20


def test_rejects_byte_limit_too_small_for_fallback_and_extension() -> None:
    with pytest.raises(ValueError):
        safe_filename("video", extension="mp4", max_bytes=8)


def test_rejects_non_string_title() -> None:
    with pytest.raises(TypeError):
        safe_filename(None)  # type: ignore[arg-type]


def test_rejects_boolean_byte_limit() -> None:
    with pytest.raises(TypeError):
        safe_filename("video", max_bytes=True)
