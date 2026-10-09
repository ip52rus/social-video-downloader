import pytest

from social_video_downloader.domain.errors import (
    InvalidMediaURLError,
    UnsupportedPlatformError,
)
from social_video_downloader.domain.models import Platform
from social_video_downloader.domain.urls import detect_platform, normalize_media_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "  https://WWW.YouTube.com/watch?v=abc#t=20  ",
            "https://www.youtube.com/watch?v=abc",
        ),
        (
            "youtu.be/abc?si=share123",
            "https://youtu.be/abc?si=share123",
        ),
        (
            "http://instagram.com/p/example/",
            "http://instagram.com/p/example/",
        ),
        (
            "https://tiktok.com/@creator/video/123#comments",
            "https://tiktok.com/@creator/video/123",
        ),
        (
            "https://example.com:443/video",
            "https://example.com/video",
        ),
        (
            "http://example.com:80/video",
            "http://example.com/video",
        ),
        (
            "https://example.com:8443/video",
            "https://example.com:8443/video",
        ),
    ],
)
def test_normalize_media_url(url, expected):
    assert normalize_media_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        "ftp://youtube.com/watch?v=abc",
        "javascript://youtube.com/watch?v=abc",
        "https://",
        "https://user:password@youtube.com/watch?v=abc",
        "https://example.com:99999/video",
    ],
)
def test_normalize_media_url_rejects_invalid_urls(url):
    with pytest.raises(InvalidMediaURLError):
        normalize_media_url(url)


@pytest.mark.parametrize(
    ("url", "expected_platform"),
    [
        ("https://youtube.com/watch?v=abc", Platform.YOUTUBE),
        ("https://www.youtube.com/shorts/abc", Platform.YOUTUBE),
        ("https://youtu.be/abc", Platform.YOUTUBE),
        ("https://m.youtube-nocookie.com/embed/abc", Platform.YOUTUBE),
        ("https://instagram.com/p/abc", Platform.INSTAGRAM),
        ("https://www.instagram.com/reel/abc", Platform.INSTAGRAM),
        ("https://tiktok.com/@creator/video/123", Platform.TIKTOK),
        ("https://vm.tiktok.com/example", Platform.TIKTOK),
    ],
)
def test_detect_platform(url, expected_platform):
    assert detect_platform(url) is expected_platform


@pytest.mark.parametrize(
    "url",
    [
        "https://youtube.com.example.org/watch?v=abc",
        "https://notyoutube.com/watch?v=abc",
        "https://example.com/video",
    ],
)
def test_detect_platform_rejects_unsupported_domains(url):
    with pytest.raises(UnsupportedPlatformError):
        detect_platform(url)
