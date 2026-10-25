"""Synthetic refusals through native export, provider and private production sink."""

import io
import json
import logging
from pathlib import Path
from threading import Event
from time import monotonic

import pytest

from social_video_downloader import tiktok_diagnostics as d
from social_video_downloader.domain.errors import (
    DownloadCleanupError,
    DownloadFailedError,
    DownloadTimeoutError,
    MetadataExtractionError,
)
from social_video_downloader.infrastructure import tiktok_native as n
from social_video_downloader.logging_config import (
    SafeEventFilter,
    SafeEventFormatter,
    SafeEventHandler,
)
from social_video_downloader.providers.tiktok import TikTokProvider
from social_video_downloader.telegram_tiktok import TelegramTikTokHandler
from tests.test_tiktok_integration import message
from tests.test_tiktok_native import MEDIA, A, key, network, response
from tests.test_tiktok_native import offline as offline
from tests.test_tiktok_native import workers as workers
from tests.test_tiktok_public_acquisition import synthetic_worker
from tests.test_tiktok_public_page import html


@pytest.fixture
def sink():
    stream = io.StringIO()
    logger = logging.getLogger(d.LOGGER_NAME)
    handler = SafeEventHandler(stream)
    handler.addFilter(SafeEventFilter())
    handler.setFormatter(SafeEventFormatter())
    old_level = logger.level
    logger.setLevel(logging.WARNING)
    logger.addHandler(handler)
    try:
        yield stream
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)


def event(sink):
    lines = sink.getvalue().splitlines()
    assert len(lines) == 1  # One event per failure, not per phase/request.
    return json.loads(lines[0])


CASES = [
    ((403, b"PRIVATE_BODY", {}), "http_error", "metadata_fetch", 403, DownloadFailedError),
    ((429, b"PRIVATE_BODY", {}), "http_error", "metadata_fetch", 429, DownloadFailedError),
    (
        response(b"PRIVATE_BODY", "application/json"),
        "metadata_content_type",
        "metadata_fetch",
        200,
        MetadataExtractionError,
    ),
    (
        response(b"<html>PRIVATE_BODY</html>"),
        "missing_public_state",
        "metadata_parse",
        200,
        MetadataExtractionError,
    ),
    (
        response(html().replace(b'"itemInfo":', b'"broken":')),
        "metadata_schema",
        "metadata_parse",
        200,
        MetadataExtractionError,
    ),
    (
        response(
            b'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">{bad</script>'
        ),
        "metadata_schema",
        "metadata_parse",
        200,
        MetadataExtractionError,
    ),
    (
        response(html("22222222")),
        "source_identity_mismatch",
        "metadata_parse",
        200,
        MetadataExtractionError,
    ),
    (
        response(html(isPrivate=True)),
        "non_public_or_unavailable",
        "metadata_parse",
        200,
        MetadataExtractionError,
    ),
    (
        response(html(video={"playAddr": {}})),
        "unsupported_page_video",
        "metadata_parse",
        200,
        MetadataExtractionError,
    ),
    (
        response(html(imagePost={"images": [{"imageURL": "PRIVATE_IMAGE"}]})),
        "unsupported_photo",
        "metadata_parse",
        200,
        MetadataExtractionError,
    ),
    (
        response(html() + html()),
        "ambiguous_metadata",
        "metadata_parse",
        200,
        MetadataExtractionError,
    ),
]


@pytest.mark.parametrize("metadata,reason,stage,status,error_type", CASES)
def test_wire_failure_to_provider_and_production_sink(
    monkeypatch, tmp_path, sink, metadata, reason, stage, status, error_type
):
    wire = network(monkeypatch, {key(A): metadata})

    def run(urls, **kwargs):
        assert urls == [A] and kwargs["public_page"] is True
        return n._execute(urls, tmp_path, monotonic() + 30, public_page=True)

    monkeypatch.setattr(n, "run", run)
    with pytest.raises(error_type, match="TikTok operation could not complete safely."):
        TikTokProvider().download(A, tmp_path)
    data = event(sink)
    assert (data["reason"], data["stage"], data["metadata_http_status"]) == (reason, stage, status)
    assert data["metadata_requests"] == 1 and data["media_requests"] == 0
    assert data["counts_exact"] is True
    assert data["metadata_bytes"] == (len(metadata[1]) if stage == "metadata_parse" else 0)
    assert len(wire.requests) == 1 and list(tmp_path.iterdir()) == []
    assert all(secret not in sink.getvalue() for secret in (A, MEDIA, "PRIVATE", "11111111"))


@pytest.mark.parametrize("metadata,reason,stage,status,error_type", CASES[:7])
def test_owned_worker_report_survives_ipc_without_extra_requests(
    monkeypatch, tmp_path, workers, sink, metadata, reason, stage, status, error_type
):
    workspaces = synthetic_worker(monkeypatch, metadata)
    with pytest.raises(error_type):
        TikTokProvider().download(A, tmp_path)
    data = event(sink)
    assert (data["reason"], data["stage"], data["metadata_http_status"]) == (reason, stage, status)
    assert data["metadata_requests"] == 1 and data["media_requests"] == 0
    assert all(worker.returncode == 0 for worker in workers)
    assert all(not p.exists() for p in workspaces) and list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_handler_keeps_user_copy_no_upload_and_releases_reservation(monkeypatch, sink):
    wire = network(monkeypatch, {key(A): response(b"<html>PRIVATE_BODY</html>")})

    def run(urls, **kwargs):
        return n._execute(urls, Path(kwargs["output_dir"]), monotonic() + 30, public_page=True)

    monkeypatch.setattr(n, "run", run)
    msg = message()
    handler = TelegramTikTokHandler()
    await handler.handle(msg, A)
    msg.answer_video.assert_not_awaited()
    assert msg.answer.await_args.args == (
        "Couldn't download or prepare the TikTok video. Try another link.",
    )
    assert not handler._active_users and not handler._blocked
    assert len(wire.requests) == 1 and event(sink)["reason"] == "missing_public_state"


@pytest.mark.parametrize(
    "code", ["deadline", "cancelled", "cleanup_failed", "workspace_cleanup_failed"]
)
def test_supervisor_unknowns_preserve_domain_failure_without_stale_worker_fields(
    monkeypatch, tmp_path, sink, code
):
    monkeypatch.setattr(
        n,
        "run",
        lambda *a, **k: dict(
            success=False,
            error=code,
            counts_exact=False,
            metadata_requests=0,
            results=[
                dict(
                    error="missing_public_state",
                    failure_stage="metadata_parse",
                    metadata_http_status=200,
                )
            ],
        ),
    )
    error_type = DownloadCleanupError if "cleanup" in code else DownloadTimeoutError
    with pytest.raises(error_type):
        TikTokProvider().download(A, tmp_path)
    data = event(sink)
    assert data["reason"] == code and data["stage"] == "unknown"
    assert data["metadata_http_status"] is None and data["metadata_requests"] is None
    assert data["metadata_bytes"] is None and data["media_requests"] is None


def test_pre_cancelled_native_does_not_spawn_worker(monkeypatch, tmp_path, sink):
    cancelled = Event()
    cancelled.set()
    monkeypatch.setattr(n.subprocess, "Popen", lambda *a, **k: pytest.fail("Unexpected worker"))
    with pytest.raises(DownloadTimeoutError):
        TikTokProvider().download_prepared(A, tmp_path, cancelled=cancelled)
    data = event(sink)
    assert data["reason"] == "cancelled" and data["counts_exact"] is False
    assert data["metadata_requests"] is None


@pytest.mark.parametrize("value", [None, [], {}, True, -1, 1e100, "PRIVATE", "http_403 PRIVATE"])
def test_untrusted_values_are_unknown_not_external_text(sink, value):
    d.emit_refusal(
        dict(
            error=value,
            counts_exact=True,
            metadata_requests=value,
            media_requests=value,
            metadata_bytes=value,
            results=[dict(error=value, failure_stage=value, metadata_http_status=value)],
        )
    )
    data = event(sink)
    assert data["reason"] == data["stage"] == "unknown"
    assert all(
        data[k] is None
        for k in ("metadata_http_status", "metadata_requests", "media_requests", "metadata_bytes")
    )
    assert "PRIVATE" not in sink.getvalue()


@pytest.mark.parametrize(
    "field,value",
    [
        ("metadata_http_status", 99),
        ("metadata_http_status", 600),
        ("metadata_bytes", 4194305),
        ("metadata_requests", 7),
        ("media_requests", 7),
        ("metadata_bytes", True),
        ("counts_exact", 1),
    ],
)
def test_sink_revalidates_numeric_bounds_and_drops_extra_fields(sink, field, value):
    payload = dict(
        platform="tiktok",
        event="native_refusal",
        reason="metadata_schema",
        stage="metadata_parse",
        counts_exact=True,
        metadata_http_status=200,
        metadata_bytes=1,
        metadata_requests=1,
        media_requests=0,
        url=MEDIA,
        exception="PRIVATE_EXCEPTION",
    )
    payload[field] = value
    record = logging.LogRecord(
        d.LOGGER_NAME,
        logging.WARNING,
        "PRIVATE_PATH",
        1,
        "PRIVATE_TEXT",
        (),
        (RuntimeError, RuntimeError(MEDIA), None),
    )
    record.safe_tiktok_event = payload
    logging.getLogger(d.LOGGER_NAME).handle(record)
    data = event(sink)
    assert data[field] is (False if field == "counts_exact" else None)
    assert "PRIVATE" not in sink.getvalue() and MEDIA not in sink.getvalue()
    assert set(data) == {
        "platform",
        "event",
        "reason",
        "stage",
        "counts_exact",
        "metadata_http_status",
        "metadata_bytes",
        "metadata_requests",
        "media_requests",
    }


def test_unknown_logger_and_non_event_records_remain_suppressed(sink):
    record = logging.LogRecord(d.LOGGER_NAME, logging.WARNING, "", 1, "PRIVATE", (), None)
    handler = SafeEventHandler(sink)
    handler.addFilter(SafeEventFilter())
    handler.setFormatter(SafeEventFormatter())
    handler.handle(record)
    record.name += ".untrusted"
    record.safe_tiktok_event = dict(platform="tiktok", event="native_refusal")
    handler.handle(record)
    assert sink.getvalue() == ""


def test_failed_sink_does_not_change_refusal_or_trigger_retry(monkeypatch, tmp_path):
    calls = []

    def run(*args, **kwargs):
        calls.append(kwargs)
        return dict(success=False, error="metadata_schema")

    def broken(*args, **kwargs):
        raise OSError("PRIVATE_EXCEPTION")

    monkeypatch.setattr(n, "run", run)
    monkeypatch.setattr(logging.getLogger(d.LOGGER_NAME), "warning", broken)
    with pytest.raises(MetadataExtractionError):
        TikTokProvider().download(A, tmp_path)
    assert len(calls) == 1


def test_success_has_no_refusal_event(monkeypatch, tmp_path, sink):
    monkeypatch.setattr(
        n,
        "run",
        lambda *a, **k: dict(success=True, results=[dict(width=64, height=96, duration=1)]),
    )
    media, parameters = TikTokProvider().download_prepared(A, tmp_path)
    assert media.file_path == tmp_path / "tiktok.mp4" and parameters["width"] == 64
    assert sink.getvalue() == ""


@pytest.mark.parametrize("short_failure", [False, True])
def test_short_resolution_is_separate_and_shares_existing_request_budget(
    monkeypatch, tmp_path, sink, short_failure
):
    short = "https://vm.tiktok.com/Synthetic01/"
    wire = network(
        monkeypatch,
        {
            key(short): (200, b"PRIVATE_BODY", {})
            if short_failure
            else (301, b"", {"Location": A}),
            key(A): response(b"<html>PRIVATE_BODY</html>"),
        },
    )

    def run(urls, **kwargs):
        assert kwargs["short_links"] is True
        return n._execute(urls, tmp_path, monotonic() + 30, public_page=True, short_links=True)

    monkeypatch.setattr(n, "run", run)
    with pytest.raises(DownloadFailedError if short_failure else MetadataExtractionError):
        TikTokProvider().download(short, tmp_path)
    data = event(sink)
    assert data["reason"] == (
        "short_redirect_required" if short_failure else "missing_public_state"
    )
    assert data["stage"] == ("short_link" if short_failure else "metadata_parse")
    assert data["metadata_http_status"] == 200
    assert data["metadata_requests"] == len(wire.requests) == (1 if short_failure else 2)
    assert data["media_requests"] == 0
    assert "Synthetic01" not in sink.getvalue()


def test_media_failure_does_not_look_like_metadata_fetch_failure(monkeypatch, tmp_path, sink):
    wire = network(monkeypatch, {key(A): response(html()), key(MEDIA): (403, b"PRIVATE", {})})
    monkeypatch.setattr(
        n,
        "run",
        lambda urls, **kwargs: n._execute(urls, tmp_path, monotonic() + 30, public_page=True),
    )
    with pytest.raises(DownloadFailedError):
        TikTokProvider().download(A, tmp_path)
    data = event(sink)
    assert data["reason"] == "http_error" and data["stage"] == "media_acquire"
    # Explicitly metadata status, never mislabelled as the failed media status.
    assert data["metadata_http_status"] == 200
    assert data["metadata_requests"] == data["media_requests"] == 1
    assert len(wire.requests) == 2 and list(tmp_path.iterdir()) == []


def test_unexpected_transport_exception_does_not_expose_text(monkeypatch, tmp_path, sink):
    def fail(*args, **kwargs):
        raise OSError("PRIVATE_TOKEN_COOKIE_URL")

    monkeypatch.setattr(n._Pinned, "connect", fail)
    monkeypatch.setattr(
        n,
        "run",
        lambda urls, **kwargs: n._execute(urls, tmp_path, monotonic() + 30, public_page=True),
    )
    with pytest.raises(DownloadFailedError):
        TikTokProvider().download(A, tmp_path)
    data = event(sink)
    assert data["reason"] == "operation_failed" and data["stage"] == "metadata_fetch"
    assert data["metadata_http_status"] is None
    assert data["metadata_requests"] == 1 and data["media_requests"] == 0
    assert "PRIVATE" not in sink.getvalue()
