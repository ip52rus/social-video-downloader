"""Explicit public-page mode: synthetic HTTP parser, local MP4 and owned workers."""

import json
import signal
import threading
from pathlib import Path
from time import monotonic

import pytest

from social_video_downloader.infrastructure import tiktok_native as n
from tests.integration.test_video_preparation import generate
from tests.test_tiktok_native import MEDIA, A, B, key, network, response
from tests.test_tiktok_native import offline as offline
from tests.test_tiktok_native import workers as workers
from tests.test_tiktok_public_page import html


def synthetic_worker(monkeypatch, metadata, media=None, fixture=None, stall=False):
    original, workspaces = n._command, []

    def command(workspace):
        workspaces.append(Path(workspace))
        argv = original(workspace)
        media_expression = (
            f"response(Path({str(fixture)!r}).read_bytes(), 'video/mp4')"
            if fixture is not None
            else repr(media)
        )
        bootstrap = (
            "import sys,socket; from pathlib import Path; "
            "socket.socket.connect=socket.socket.connect_ex=lambda *a,**k: "
            "(_ for _ in ()).throw(AssertionError('No sockets')); "
            "from tests.test_tiktok_native import install,key,A,MEDIA,response; "
            f"wire=install({{key(A):{metadata!r},key(MEDIA):{media_expression}}}); "
        )
        if stall:
            bootstrap += (
                "from social_video_downloader.infrastructure import tiktok_native as n; "
                "import time; original=n.Session.read; "
                "n.Session.read=lambda self,r,phase,*args: "
                "time.sleep(60) if phase=='media' else original(self,r,phase,*args); "
            )
        bootstrap += (
            argv[2] + "; "
            "assert len(wire.requests)<=2; "
            "assert all('/embed/v2/' not in r[2] for r in wire.requests)"
        )
        return [*argv[:2], bootstrap, *argv[3:]]

    monkeypatch.setattr(n, "_command", command)
    return workspaces


@pytest.mark.parametrize("audio", [True, False])
def test_public_mode_real_worker_mp4_decode_preparation_and_cleanup(
    monkeypatch, tmp_path, workers, audio
):
    source = tmp_path / "fixture.mp4"
    generate(source, audio=audio)
    workspaces = synthetic_worker(monkeypatch, response(html()), fixture=source)
    result = n.run([A + "?is_from_webapp=1&sender_device=pc"], public_page=True)
    assert result["success"], result
    case = result["results"][0]
    assert case["source_identity"] and case["candidate_source"] == "playAddr"
    assert case["candidates"] == 1 and not case["separate_audio"]
    assert case["http_complete"] and case["bytes"] == source.stat().st_size
    assert case["video_streams"] == 1 and case["audio_streams"] == int(audio)
    assert case["video_codec"] == "h264" and case["audio_codec"] == ("aac" if audio else "absent")
    assert case["decoded"] and case["preparation"] == "passthrough"
    assert result["metadata_requests"] == result["media_requests"] == result["acquisitions"] == 1
    assert result["metadata_bytes"] == len(html()) and result["media_bytes"] == case["bytes"]
    assert case["counts"] == {k: result[k] for k in n._budget()}
    assert result["counts_exact"] and result["workspace_cleaned"]
    assert all(not p.exists() for p in workspaces) and all(p.returncode == 0 for p in workers)
    assert list(tmp_path.iterdir()) == [source]  # Caller-owned file survives.
    assert not any(
        value in json.dumps(result) for value in (A, MEDIA, "PRIVATE_SIGNED", "11111111")
    )


@pytest.mark.parametrize(
    "metadata,error",
    [
        ((403, b"PRIVATE_HTML", {}), "http_403"),
        ((429, b"PRIVATE_HTML", {}), "http_429"),
        (response(b"<html>PRIVATE_HTML</html>"), "missing_public_state"),
        (response(html().replace(b'"itemInfo":', b'"broken":')), "metadata_schema"),
        (response(html("22222222")), "source_identity_mismatch"),
        (response(html(video={"downloadAddr": MEDIA})), "metadata_schema"),
        (
            response(html(video={"playAddr": "https://external.invalid/PRIVATE_URL"})),
            "forbidden_media_destination",
        ),
        (
            response(html(video={"playAddr": MEDIA, "audioAddr": "PRIVATE_AUDIO"})),
            "separate_streams_unsupported",
        ),
    ],
)
def test_public_metadata_refusals_never_get_media(monkeypatch, tmp_path, metadata, error):
    wire = network(monkeypatch, {key(A): metadata})
    result = n._execute([A], tmp_path, monotonic() + 10, public_page=True)
    assert result["error"] == error and not result["success"]
    assert (
        result["metadata_requests"] == 1 and result["media_requests"] == result["acquisitions"] == 0
    )
    assert len(wire.requests) == 1 and not list(tmp_path.iterdir())
    assert result["counts_exact"]
    assert not any(
        secret in json.dumps(result) for secret in (A, MEDIA, "PRIVATE", "11111111", "22222222")
    )


@pytest.mark.parametrize(
    "media,error,received",
    [
        ((403, b"PRIVATE_HTML", {}), "http_403", 0),
        (
            (200, b"0000ftypPARTIAL", {"Content-Type": "video/mp4", "Content-Length": "21750"}),
            "incomplete_response",
            15,
        ),
        (
            (200, b"", {"Content-Type": "video/mp4", "Content-Length": str(n.FILE_BYTES + 1)}),
            "byte_limit",
            0,
        ),
    ],
)
def test_public_worker_media_failures_clean_partial_no_retry(
    monkeypatch, tmp_path, workers, media, error, received
):
    foreign = tmp_path / "foreign"
    foreign.write_text("keep")
    workspaces = synthetic_worker(monkeypatch, response(html()), media=media)
    result = n.run([A], public_page=True)
    assert result["error"] == error and not result["success"]
    assert result["metadata_requests"] == result["media_requests"] == result["acquisitions"] == 1
    assert result["media_bytes"] == received and result["counts_exact"]
    assert result["workspace_cleaned"] and all(not p.exists() for p in workspaces)
    assert all(p.returncode == 0 for p in workers) and foreign.read_text() == "keep"
    assert "PRIVATE" not in json.dumps(result)


def test_public_request_exact_signed_query_headers_and_scoped_cookies(monkeypatch, tmp_path):
    media_redirect = MEDIA.replace("/opaque/", "/redirected/")
    wire = network(
        monkeypatch,
        {
            key(A): response(
                html(), fields=[("Set-Cookie", "public=PRIVATE_COOKIE; Path=/; Secure")]
            ),
            key(MEDIA): (302, b"", {"Location": media_redirect}),
            key(media_redirect): (403, b"PRIVATE_HTML", {}),
        },
    )
    result = n._execute([A], tmp_path, monotonic() + 10, public_page=True)
    assert result["error"] == "http_403" and result["acquisitions"] == 1
    assert [r[2] for r in wire.requests] == [key(A)[1], key(MEDIA)[1], key(media_redirect)[1]]
    for _, method, _, headers in wire.requests:
        assert method == "GET" and headers["User-Agent"] == n.UA
        assert headers["Referer"] == A and headers["Accept-Encoding"] == "identity"
        assert headers["Cookie"] is None and headers["Range"] is None
    assert result["metadata_requests"] == 1 and result["media_requests"] == 2
    assert not list(tmp_path.iterdir()) and "PRIVATE" not in json.dumps(result)


@pytest.mark.parametrize("cancel", [False, True])
def test_public_stalled_stream_deadline_or_cancellation_reaps_worker(
    monkeypatch, tmp_path, workers, cancel
):
    source = tmp_path / "fixture.mp4"
    generate(source, audio=False)
    workspaces = synthetic_worker(monkeypatch, response(html()), fixture=source, stall=True)
    event = threading.Event()
    timer = threading.Timer(1, event.set)
    if cancel:
        timer.start()
    else:
        monkeypatch.setattr(n, "SECONDS", 1)
    try:
        result = n.run([A], public_page=True, cancelled=event)
    finally:
        timer.cancel()
        if cancel:
            timer.join()
    assert result["error"] == ("cancelled" if cancel else "deadline")
    assert result["workspace_cleaned"] and not result["counts_exact"]
    assert len(workers) == 1 and workers[0].returncode == -signal.SIGKILL
    assert all(not p.exists() for p in workspaces) and list(tmp_path.iterdir()) == [source]


@pytest.mark.parametrize(
    "urls,options", [([A, B], {}), ([A], {"benchmark": True}), ([A], {"output_dir": "."})]
)
def test_public_mode_is_one_explicit_diagnostic_only(monkeypatch, urls, options):
    monkeypatch.setattr(n.subprocess, "Popen", lambda *a, **k: pytest.fail("Unexpected worker"))
    assert n.run(urls, public_page=True, **options) == {"success": False, "error": "invalid_input"}


def test_public_cli_selects_explicit_supervised_mode(monkeypatch, capsys):
    import io
    import sys

    seen = []
    monkeypatch.setattr(n.signal, "signal", lambda *args: None)
    monkeypatch.setattr(sys, "argv", ["tiktok_native.py", "--public-page"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps([A])))
    monkeypatch.setattr(
        n, "run", lambda urls, **kwargs: seen.append((urls, kwargs)) or {"success": True}
    )
    assert n.main() == 0 and json.loads(capsys.readouterr().out) == {"success": True}
    assert seen == [([A], {"benchmark": False, "public_page": True})]
