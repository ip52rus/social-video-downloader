"""Public-page provider export and existing fake Telegram handler; no real sockets."""

import io
import json
import sys
from pathlib import Path

import pytest

from social_video_downloader import telegram_tiktok as t
from social_video_downloader.domain.errors import (
    DownloaderError,
    DownloadFailedError,
    MediaProcessingError,
    MetadataExtractionError,
)
from social_video_downloader.domain.models import DownloadedMedia, Platform
from social_video_downloader.infrastructure import tiktok_native as n
from social_video_downloader.providers.tiktok import TikTokProvider
from tests.integration.test_video_preparation import generate
from tests.localization_fixtures import russian_presentation as russian_presentation
from tests.test_tiktok_integration import message
from tests.test_tiktok_native import MEDIA, A, response
from tests.test_tiktok_native import offline as offline
from tests.test_tiktok_native import workers as workers
from tests.test_tiktok_public_acquisition import synthetic_worker
from tests.test_tiktok_public_page import html


@pytest.mark.parametrize("audio", [False, True])
def test_public_provider_exports_verified_file_only_after_reap(
    monkeypatch, tmp_path, workers, audio
):
    source = tmp_path / "fixture.mp4"
    generate(source, audio=audio)
    caller = tmp_path / "caller"
    caller.mkdir()
    private = synthetic_worker(monkeypatch, response(html()), fixture=source)
    original_run, original_link, reports, linked = n.run, n.os.link, [], []

    def record(*args, **kwargs):
        assert kwargs["public_page"] is True
        report = original_run(*args, **kwargs)
        reports.append(report)
        return report

    def publish(src, dst, **kwargs):
        assert workers and all(p.returncode is not None for p in workers)
        assert Path(src).parent.parent == caller and not Path(dst).exists()
        linked.append(Path(dst))
        return original_link(src, dst, **kwargs)

    monkeypatch.setattr(n, "run", record)
    monkeypatch.setattr(n.os, "link", publish)
    media, parameters = TikTokProvider().download_prepared(
        A + "?is_from_webapp=1&sender_device=pc", caller
    )
    try:
        assert isinstance(media, DownloadedMedia) and media.file_path == caller / "tiktok.mp4"
        assert media.file_path.read_bytes() == source.read_bytes() and linked == [media.file_path]
        assert media.metadata.platform is Platform.TIKTOK and media.metadata.source_url == A
        assert media.metadata.duration_seconds == parameters["duration"]
        assert parameters == {"width": 64, "height": 96, "duration": 1}
        report = reports[0]
        case = report["results"][0]
        assert case["candidate_source"] == "playAddr" and case["source_identity"]
        assert case["video_codec"] == "h264" and case["audio_codec"] == (
            "aac" if audio else "absent"
        )
        assert case["video_streams"] == 1 and case["audio_streams"] == int(audio)
        assert case["http_complete"] and case["decoded"] and case["preparation"] == "passthrough"
        assert (
            report["metadata_requests"] == report["media_requests"] == report["acquisitions"] == 1
        )
        assert report["media_bytes"] == source.stat().st_size and report["counts_exact"]
        assert report["workspace_cleaned"] and all(not p.exists() for p in private)
        assert list(caller.iterdir()) == [media.file_path]
    finally:
        (caller / "tiktok.mp4").unlink(missing_ok=True)


@pytest.mark.parametrize(
    "metadata,media,error,domain,media_requests,received",
    [
        ((403, b"PRIVATE_HTML", {}), None, "http_403", DownloadFailedError, 0, 0),
        ((429, b"PRIVATE_HTML", {}), None, "http_429", DownloadFailedError, 0, 0),
        (response(b"PRIVATE_HTML"), None, "missing_public_state", MetadataExtractionError, 0, 0),
        (
            response(html().replace(b'"playAddr":', b'"playAddr":broken,')),
            None,
            "metadata_schema",
            MetadataExtractionError,
            0,
            0,
        ),
        (response(html(video={})), None, "metadata_schema", MetadataExtractionError, 0, 0),
        (
            response(html("22222222")),
            None,
            "source_identity_mismatch",
            MetadataExtractionError,
            0,
            0,
        ),
        (
            response(html().replace(b'"statusCode": 0', b'"statusCode": 10216')),
            None,
            "non_public_or_unavailable",
            MetadataExtractionError,
            0,
            0,
        ),
        (
            response(html(video={"playAddr": []})),
            None,
            "unsupported_page_video",
            MetadataExtractionError,
            0,
            0,
        ),
        (response(html() + html()), None, "ambiguous_metadata", MetadataExtractionError, 0, 0),
        (
            response(html(video={"playAddr": "https://external.invalid/PRIVATE_LOCATOR"})),
            None,
            "forbidden_media_destination",
            DownloadFailedError,
            0,
            0,
        ),
        (
            response(html(video={"playAddr": MEDIA, "audioAddr": "PRIVATE_AUDIO"})),
            None,
            "separate_streams_unsupported",
            MediaProcessingError,
            0,
            0,
        ),
        (response(html()), (403, b"PRIVATE_HTML", {}), "http_403", DownloadFailedError, 1, 0),
        (
            response(html()),
            (200, b"abcdftyp", {"Content-Type": "video/mp4", "Content-Length": "16"}),
            "incomplete_response",
            MediaProcessingError,
            1,
            8,
        ),
        (
            response(html()),
            (200, b"", {"Content-Type": "video/mp4", "Content-Length": str(n.FILE_BYTES + 1)}),
            "byte_limit",
            DownloadFailedError,
            1,
            0,
        ),
    ],
)
@pytest.mark.asyncio
async def test_public_faults_through_provider_and_handler_no_upload_retry_or_leak(
    monkeypatch, workers, metadata, media, error, domain, media_requests, received
):
    private = synthetic_worker(monkeypatch, metadata, media=media)
    original_run, temporary, reports, errors, callers = n.run, t.TemporaryDirectory, [], [], []

    def record(*args, **kwargs):
        assert kwargs["public_page"] is True
        result = original_run(*args, **kwargs)
        reports.append(result)
        return result

    def track(*args, **kwargs):
        directory = temporary(*args, **kwargs)
        callers.append(Path(directory.name))
        return directory

    class ObservedProvider(TikTokProvider):
        def download_prepared(self, *args, **kwargs):
            try:
                return super().download_prepared(*args, **kwargs)
            except DownloaderError as exc:
                errors.append(exc)
                raise

    monkeypatch.setattr(n, "run", record)
    monkeypatch.setattr(t, "TemporaryDirectory", track)
    msg = message()
    handler = t.TelegramTikTokHandler(provider=ObservedProvider())
    await handler.handle(msg, A)
    assert len(errors) == 1 and type(errors[0]) is domain
    assert len(reports) == 1 and reports[0]["error"] == error
    report = reports[0]
    assert report["metadata_requests"] == 1 and report["media_requests"] == media_requests
    assert report["acquisitions"] == media_requests and report["media_bytes"] == received
    assert report["counts_exact"] and report["workspace_cleaned"]
    assert len(workers) == 1 and workers[0].returncode == 0
    assert all(not p.exists() for p in private + callers)
    msg.answer_video.assert_not_awaited()
    assert not handler._active_users and not handler._blocked
    rendered = json.dumps(report) + str(errors[0]) + repr(msg.answer.await_args_list)
    assert not any(secret in rendered for secret in (A, MEDIA, "11111111", "22222222", "PRIVATE"))


@pytest.mark.parametrize(
    "arguments,data",
    [
        (["--public-page", "--output-dir", "PRIVATE_WORKSPACE"], [A]),
        (["--public-page"], [{"url": A, "output_dir": "PRIVATE_WORKSPACE"}]),
        (["--public-page"], {"urls": [A], "output_dir": "PRIVATE_WORKSPACE"}),
    ],
)
def test_public_cli_cannot_request_export(monkeypatch, capsys, arguments, data):
    monkeypatch.setattr(n.signal, "signal", lambda *args: None)
    monkeypatch.setattr(sys, "argv", ["tiktok_native.py", *arguments])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(data)))
    monkeypatch.setattr(n.subprocess, "Popen", lambda *a, **k: pytest.fail("Unexpected worker"))
    assert n.main() == 1
    assert json.loads(capsys.readouterr().out) == {"success": False, "error": "invalid_input"}
