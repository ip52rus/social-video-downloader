"""Shared resource policy and >25 MiB Instagram paths, entirely synthetic/offline."""

import io
import shutil
from dataclasses import asdict, replace
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from yt_dlp.networking.common import Response

from social_video_downloader.config import ConfigurationError, Settings
from social_video_downloader.domain.errors import DownloadFailedError, MediaProcessingError
from social_video_downloader.domain.models import DownloadedMedia, MediaMetadata, Platform
from social_video_downloader.infrastructure import telegram_carousel_preparation as preparation
from social_video_downloader.infrastructure.instagram_acquisition import _MediaBudget
from social_video_downloader.resource_limits import (
    CLOUD_API_FILE_BYTES,
    LOCAL_API_FILE_BYTES,
    MIB,
    DownloadLimits,
)
from social_video_downloader.services.instagram_acquisition import CarouselAcquisitionLimits
from social_video_downloader.telegram_instagram import (
    InstagramReelHandler,
    _Guard,
    _PreparationStopped,
)
from social_video_downloader.telegram_instagram_posts import InstagramPostHandler
from tests.test_telegram_carousel import collection, payload


@pytest.mark.parametrize("local", [False, True])
def test_configured_effective_api_limit_and_consistent_carousel_policy(local):
    settings = Settings(
        "synthetic", telegram_api_base_url="http://local.invalid" if local else None
    )
    limits = settings.download_limits
    assert limits.max_file_bytes == (512 * MIB if local else CLOUD_API_FILE_BYTES)
    post = InstagramPostHandler(InstagramReelHandler(limits=limits))
    assert post._acquisition_limits.max_file_bytes == limits.max_file_bytes
    assert post._delivery_limits.max_upload_file_bytes == limits.max_file_bytes
    assert post._acquisition_limits.max_total_bytes == post._delivery_limits.max_upload_total_bytes
    assert post._delivery_limits.max_workspace_bytes == limits.max_workspace_bytes
    assert post._acquisition_limits.max_videos == post._delivery_limits.max_videos == 10
    assert post._acquisition_limits.max_seconds == 300
    assert post._delivery_limits.max_prepare_seconds == 180
    assert post._delivery_limits.max_send_seconds == 120


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_file_bytes", 0),
        ("max_file_bytes", True),
        ("max_file_bytes", 2_000_000_001),
        ("max_request_bytes", 1),
        ("max_workspace_bytes", 1),
        ("min_free_bytes", 0),
        ("min_free_bytes", -1),
        ("min_free_bytes", 17 * 1024**3),
    ],
)
def test_invalid_shared_budgets_fail_before_polling(field, value):
    with pytest.raises(ValueError):
        replace(DownloadLimits(), **{field: value})


@pytest.mark.parametrize(
    "name,value",
    [
        ("DOWNLOAD_MAX_ACTIVE_REQUESTS", "0"),
        ("DOWNLOAD_MAX_ACTIVE_REQUESTS", "9"),
        ("DOWNLOAD_LINK_INTERVAL_SECONDS", "0"),
        ("DOWNLOAD_LINK_INTERVAL_SECONDS", "301"),
        ("DOWNLOAD_MAX_FILE_BYTES", "2000000001"),
        ("DOWNLOAD_MAX_REQUEST_BYTES", "1"),
        ("DOWNLOAD_MAX_WORKSPACE_BYTES", "1"),
        ("DOWNLOAD_MIN_FREE_BYTES", "-1"),
        ("DOWNLOAD_MIN_FREE_BYTES", "true"),
        ("DOWNLOAD_MIN_FREE_BYTES", "9" * 1000),
    ],
)
def test_invalid_environment_budgets_fail_closed(name, value):
    with pytest.raises(ConfigurationError):
        Settings.from_env({"TELEGRAM_BOT_TOKEN": "synthetic", name: value})


def test_custom_limits_are_loaded_without_new_runtime_configuration():
    settings = Settings.from_env(
        {
            "TELEGRAM_BOT_TOKEN": "synthetic",
            "TELEGRAM_API_BASE_URL": "http://local.invalid",
            "DOWNLOAD_MAX_FILE_BYTES": str(LOCAL_API_FILE_BYTES),
            "DOWNLOAD_MAX_REQUEST_BYTES": str(2 * 1024**3),
            "DOWNLOAD_MAX_WORKSPACE_BYTES": str(4 * 1024**3),
            "DOWNLOAD_MIN_FREE_BYTES": str(256 * MIB),
            "DOWNLOAD_MAX_ACTIVE_REQUESTS": "2",
            "DOWNLOAD_LINK_INTERVAL_SECONDS": "5",
        }
    )
    assert settings.download_limits == DownloadLimits(
        LOCAL_API_FILE_BYTES, 2 * 1024**3, 4 * 1024**3, 256 * MIB
    )
    assert settings.download_max_active_requests == 2
    assert settings.download_link_interval_seconds == 5


@pytest.mark.parametrize("headers", [{}, {"Content-Length": "1"}, {"Content-Length": "999999999"}])
@pytest.mark.parametrize("kind", ["reel", "carousel"])
def test_actual_stream_larger_than_25_mib_ignores_absent_or_false_size_header(headers, kind):
    data = b"x" * (26 * MIB)
    response = Response(io.BytesIO(data), "https://media.invalid/fixture", headers)
    if kind == "reel":
        guard = _Guard(Event())
        wrapped = guard.wrap(response)
    else:
        limits = InstagramPostHandler(InstagramReelHandler())._acquisition_limits
        budget = _MediaBudget(limits)
        wrapped = budget.wrap(response)
    received = 0
    while chunk := wrapped.read(64 * 1024):
        received += len(chunk)
    assert received == len(data)
    if kind == "reel":
        assert guard.received == received
    else:
        assert budget.total == received


@pytest.mark.parametrize("kind", ["reel", "carousel"])
def test_actual_stream_limit_still_refuses_without_repeat_or_full_body_read(kind):
    body = Mock(wraps=io.BytesIO(b"x" * 100))
    response = SimpleNamespace(read=body.read, close=Mock())
    if kind == "reel":
        guard = _Guard(Event(), max_bytes=32)
        wrapped = guard.wrap(response)
    else:
        wrapped = _MediaBudget(CarouselAcquisitionLimits(max_file_bytes=32)).wrap(response)
    assert len(wrapped.read(100)) == 32
    with pytest.raises(DownloadFailedError):
        wrapped.read(100)
    assert body.read.call_count == 1
    response.close.assert_called_once()


def test_carousel_aggregate_budget_remains_enforced_across_items():
    budget = _MediaBudget(CarouselAcquisitionLimits(max_file_bytes=32, max_total_bytes=40))
    for amount in (32, 8):
        budget.current = 0
        response = Response(io.BytesIO(b"x" * 100), "https://media.invalid/fixture", {})
        assert len(budget.wrap(response).read(100)) == amount
    budget.current = 0
    with pytest.raises(DownloadFailedError):
        budget.wrap(Response(io.BytesIO(b"x"), "https://media.invalid/fixture", {})).read()
    assert budget.total == 40


@pytest.mark.parametrize("kind", ["reel", "carousel"])
def test_disk_reserve_exhaustion_stops_before_next_network_read(monkeypatch, tmp_path, kind):
    monkeypatch.setattr(shutil, "disk_usage", lambda _: SimpleNamespace(free=0))
    read = Mock(return_value=b"x")
    response = SimpleNamespace(read=read, close=Mock())
    if kind == "reel":
        guard = _Guard(Event())
        guard.workspace = tmp_path
        wrapped = guard.wrap(response)
        error = MediaProcessingError
    else:
        limits = CarouselAcquisitionLimits(min_free_bytes=1)
        wrapped = _MediaBudget(limits, tmp_path).wrap(response)
        error = DownloadFailedError
    with pytest.raises(error):
        wrapped.read()
    read.assert_not_called()


def test_reel_and_single_post_preparation_accept_large_file(tmp_path, monkeypatch):
    owner = InstagramReelHandler()
    path = tmp_path / "synthetic.mp4"
    with path.open("wb") as output:
        output.truncate(26 * MIB)
    provider = SimpleNamespace(
        download=Mock(
            return_value=DownloadedMedia(
                path,
                MediaMetadata("synthetic", "https://media.invalid/fixture", Platform.INSTAGRAM),
            )
        )
    )
    module = "social_video_downloader.telegram_instagram"
    monkeypatch.setattr(module + ".prepare_telegram_video", lambda p, **kw: p)
    monkeypatch.setattr(
        module + ".inspect_telegram_video",
        lambda *a, **kw: {"streams": [{"codec_type": "video", "width": 64, "height": 96}]},
    )
    prepared, _ = owner._prepare("synthetic", tmp_path, _Guard(Event()), provider=provider)
    assert prepared.stat().st_size > 25 * MIB
    provider.download.assert_called_once()


def test_preparation_stops_without_fallback_on_disk_or_workspace_limit(tmp_path, monkeypatch):
    guard = _Guard(Event(), limits=DownloadLimits(32, 64, 96, 1))
    guard.workspace = tmp_path
    (tmp_path / "too-large.partial").write_bytes(b"x" * 97)
    process = Mock()
    monkeypatch.setattr("social_video_downloader.telegram_instagram.subprocess.run", process)
    with pytest.raises(_PreparationStopped):
        guard.run(["ffmpeg", "-i", "synthetic", "out.mp4"])
    process.assert_not_called()


def test_carousel_preparation_and_upload_policy_accept_larger_than_25_mib(tmp_path, monkeypatch):
    acquired, _ = collection(tmp_path, 1)
    path = acquired.videos[0].media.file_path
    with path.open("wb") as output:
        output.truncate(26 * MIB)
    acquired = replace(acquired, total_bytes=path.stat().st_size)
    limits = InstagramPostHandler(InstagramReelHandler())._delivery_limits
    data = payload(acquired, tmp_path, limits)
    monkeypatch.setattr(
        preparation,
        "inspect_telegram_video",
        lambda *a, **kw: {
            "format": {"format_name": "mp4"},
            "streams": [{"codec_type": "video", "codec_name": "h264", "width": 64, "height": 96}],
        },
    )
    result = preparation.prepare_collection(data, prepare=lambda p, **kw: p)
    assert len(result) == 1
    assert result[0]["fingerprint"][2] == 26 * MIB
    assert asdict(limits)["max_upload_file_bytes"] > 25 * MIB


def test_shared_file_limit_and_workspace_limit_are_not_unbounded(tmp_path):
    limits = DownloadLimits(32, 64, 96, 1)
    path = tmp_path / "large.mp4"
    path.write_bytes(b"x" * 33)
    with pytest.raises(MediaProcessingError):
        limits.check_file(path)
    path.write_bytes(b"x" * 97)
    with pytest.raises(MediaProcessingError):
        limits.check_workspace(tmp_path)
