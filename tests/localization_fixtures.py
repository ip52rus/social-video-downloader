"""Explicit Russian presentation for legacy direct-handler safety regressions.

These tests bypass dispatcher middleware. The real language-code routing is covered
separately by synthetic Update integration tests; safety assertions stay unchanged.
"""

import pytest

from social_video_downloader.telegram_i18n import get_i18n


@pytest.fixture(autouse=True)
def russian_presentation():
    with get_i18n().use_locale("ru"):
        yield
