"""Real extractor/urllib paths with synthetic HTTPS; external sockets forbidden."""

import io
import json
import os
import signal
import socket
import subprocess
import sys
from email.message import Message
from time import monotonic
from urllib.request import HTTPSHandler, ProxyHandler, build_opener
from urllib.response import addinfourl

import pytest
from yt_dlp.networking import Request

from scripts import tiktok_metadata as h

FULL = "https://www.tiktok.com/@fixture/video/123456789"
SHORT = "https://vm.tiktok.com/Fixture"
MEDIA = "https://media.invalid/fixture.mp4"


@pytest.fixture(autouse=True)
def no_sockets(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("External sockets are forbidden")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)


def page(*, status=0, video=None):
    item = {
        "id": "123456789",
        "desc": "PRIVATE DESCRIPTION MUST NOT LEAK",
        "author": {"uniqueId": "PRIVATE_USERNAME"},
        "video": video
        if video is not None
        else {
            "playAddr": MEDIA,
            "downloadAddr": MEDIA + "?download=1",
            "width": 720,
            "height": 960,
            "duration": 5,
        },
    }
    data = {
        "__DEFAULT_SCOPE__": {
            "webapp.video-detail": {
                "statusCode": status,
                "itemInfo": {"itemStruct": item},
            }
        }
    }
    return (
        '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'
        + json.dumps(data)
        + "</script>"
    ).encode()


class Network(HTTPSHandler):
    """Keep urllib's real redirect/error handlers, replace only socket I/O."""

    def __init__(self, routes):
        super().__init__()
        self.routes, self.calls = routes, []

    def https_open(self, request):
        self.calls.append((request.get_method(), request.full_url, dict(request.header_items())))
        key = (request.get_method(), request.full_url)
        assert key in self.routes, "Unexpected request"
        route = self.routes[key]
        code, body, headers = route() if callable(route) else route
        message = Message()
        for name, value in {"Content-Type": "text/html", **headers}.items():
            message[name] = value
        response = addinfourl(io.BytesIO(body), message, request.full_url, code)
        response.msg = "Synthetic"
        return response


def network(monkeypatch, routes):
    net = Network(routes)
    monkeypatch.setattr(
        h,
        "_opener",
        lambda: build_opener(
            ProxyHandler({}),
            h._NoRedirect(),
            net,
        ),
    )
    return net


def execute(urls, limits=None):
    limits = limits or h.Limits()
    return h._execute(urls, limits, h.monotonic() + limits.max_seconds, lambda event: None)


def test_real_mapper_full_and_short_series_no_probes_or_private_output(monkeypatch):
    net = network(
        monkeypatch,
        {
            ("GET", FULL): (200, page(), {}),
            ("HEAD", SHORT): (302, b"ignored", {"Location": FULL + "?tracking=discard"}),
            ("HEAD", FULL): (200, b"ignored", {}),
        },
    )
    result = execute([FULL + "?tracking=discard#anchor", SHORT, FULL])
    assert result["success"]
    assert result["extractions"] == 4
    assert result["requests"] == 5
    assert [r["result_id"] for r in result["results"]] == ["result-1"] * 3
    assert all(r["format_count"] == 2 for r in result["results"])
    assert result["results"][0]["formats"][1]["marked_for_probe"]
    assert all(f["container"] == "mp4" for f in result["results"][0]["formats"])
    serialized = json.dumps(result)
    for private in (FULL, SHORT, MEDIA, "123456789", "PRIVATE_USERNAME", "PRIVATE DESCRIPTION"):
        assert private not in serialized
    assert len(net.calls) == 5
    assert all(
        "Cookie" not in headers and "Authorization" not in headers for _, _, headers in net.calls
    )


@pytest.mark.parametrize("short", [SHORT, "https://vt.tiktok.com/Fixture"])
def test_both_short_hosts(monkeypatch, short):
    network(
        monkeypatch,
        {
            ("HEAD", short): (302, b"", {"Location": FULL}),
            ("HEAD", FULL): (200, b"", {}),
            ("GET", FULL): (200, page(), {}),
        },
    )
    assert execute([short])["success"]


@pytest.mark.parametrize(
    ("target", "error"),
    [
        ("https://other.invalid/video/123", "forbidden_destination"),
        (MEDIA, "forbidden_destination"),
        ("http://www.tiktok.com/@fixture/video/123456789", "invalid_url"),
        ("https://www.tiktok.com/login", "login_required"),
        (SHORT, "redirect_loop"),
    ],
)
def test_redirect_rejected_before_target_request(monkeypatch, target, error):
    net = network(monkeypatch, {("HEAD", SHORT): (302, b"", {"Location": target})})
    result = execute([SHORT, FULL])
    assert result["error"] == error
    assert result["extractions"] == result["requests"] == len(net.calls) == 1
    assert len(result["results"]) == 1


def test_redirect_changes_identity_after_short_resolution(monkeypatch):
    net = network(
        monkeypatch,
        {
            ("HEAD", SHORT): (302, b"", {"Location": FULL}),
            ("HEAD", FULL): (302, b"", {"Location": FULL.replace("123456789", "987654321")}),
        },
    )
    assert execute([SHORT])["error"] == "identity_changed"
    assert len(net.calls) == 2


@pytest.mark.parametrize(
    "url",
    [
        "https://www.tiktok.com.evil.invalid/@fixture/video/123456789",
        "https://user:pass@www.tiktok.com/@fixture/video/123456789",
        "https://www.tiktok.com:443/@fixture/video/123456789",
        "https://www.tiktok.com:0/@fixture/video/123456789",
        "https://www.tiktok.com/@fixture/photo/123456789",
        "https://www.tiktok.com/@fixture/live",
        "https://www.tiktok.com/t/Fixture",
        FULL + "/extra",
        FULL + "\n",
        "https://[broken",
        "file:///tmp/file",
    ],
)
def test_invalid_input_no_worker_or_network(monkeypatch, url):
    monkeypatch.setattr(h.subprocess, "Popen", lambda *a, **k: pytest.fail("No worker allowed"))
    result = h.run([url])
    assert not result["success"]
    assert result["requests"] == result["extractions"] == 0


def test_request_and_extractor_budgets(monkeypatch):
    net = network(monkeypatch, {("GET", FULL): (200, page(), {})})
    result = execute([FULL, FULL], h.Limits(max_requests=1))
    assert result["error"] == "request_limit" and len(net.calls) == 1
    result = execute([FULL, FULL], h.Limits(max_extractions=1))
    assert result["error"] == "extraction_limit" and result["extractions"] == 1
    assert h.run([FULL] * 4)["error"] == "invalid_input"


def test_deadline_during_response_prevents_next_case(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(h, "monotonic", lambda: clock[0])

    def late():
        clock[0] = 2.0
        return 200, page(), {}

    net = network(monkeypatch, {("GET", FULL): late})
    result = execute([FULL, FULL], h.Limits(max_seconds=1))
    assert result["error"] == "deadline"
    assert result["extractions"] == len(net.calls) == 1


@pytest.mark.parametrize("headers", [{}, {"Content-Length": "1"}])
def test_actual_body_size_limit_not_content_length(monkeypatch, headers):
    network(monkeypatch, {("GET", FULL): (200, b"x" * 1000, headers)})
    result = execute([FULL], h.Limits(max_response_bytes=100))
    assert result["error"] == "response_limit"
    assert result["metadata_bytes"] == 100


def test_aggregate_body_budget(monkeypatch):
    body = page()
    network(monkeypatch, {("GET", FULL): (200, body, {})})
    result = execute([FULL, FULL], h.Limits(max_total_bytes=len(body) + 10))
    assert result["error"] == "response_limit"
    assert result["metadata_bytes"] == len(body) + 10


@pytest.mark.parametrize(
    ("code", "body", "headers", "error"),
    [
        (403, b"private", {}, "http_403"),
        (429, b"private", {}, "http_429"),
        (200, b"challenge", {}, "challenge_forbidden"),
        (200, page(), {"Set-Cookie": "private=secret"}, "cookies_forbidden"),
        (200, page(), {"Content-Encoding": "gzip"}, "encoded_response"),
        (200, b"media", {"Content-Type": "video/mp4"}, "non_html_response"),
    ],
)
def test_forbidden_paths_no_retry(monkeypatch, code, body, headers, error):
    net = network(monkeypatch, {("GET", FULL): (code, body, headers)})
    result = execute([FULL, FULL])
    assert result["error"] == error
    assert result["requests"] == result["extractions"] == len(net.calls) == 1
    assert len(result["results"]) == 1


def test_login_status_real_extractor_no_retry(monkeypatch):
    net = network(monkeypatch, {("GET", FULL): (200, page(status=10216), {})})
    result = execute([FULL, FULL])
    assert not result["success"] and result["error"] == "login_required"
    assert len(net.calls) == result["extractions"] == 1


def test_unsolicited_cdn_request_blocked_at_transport(monkeypatch):
    net = network(monkeypatch, {})

    def probe(self, url):
        return self._downloader.urlopen(Request(MEDIA))

    monkeypatch.setattr(h._MetadataIE, "_real_extract", probe)
    assert execute([FULL])["error"] == "forbidden_destination"
    assert not net.calls


def test_cookie_and_mobile_api_entrypoints_stop_before_network(monkeypatch):
    network(monkeypatch, {})
    ie = h._MetadataIE(h._YDL(h._Transport(h.Limits(), monotonic() + 10, lambda e: None)))
    for method, category in (
        (ie._set_cookie, "cookies_forbidden"),
        (ie._call_api, "mobile_api_forbidden"),
    ):
        with pytest.raises(h.Stop, match=category):
            method()


def test_absent_audio_metadata_is_unknown_not_silence():
    formats = h._formats(
        {
            "formats": [
                {"url": MEDIA, "ext": "mp4", "vcodec": "h264"},
                {"url": MEDIA, "acodec": "none"},
                {},
            ]
        }
    )
    assert [f["audio_metadata"] for f in formats] == ["unknown", "absent", "unknown"]
    assert formats[2]["container"] == formats[2]["protocol"] == "unknown"


def test_silent_format_real_mapper_metadata_no_probe(monkeypatch):
    video = {
        "bitrateInfo": [{"PlayAddr": {"UrlList": ["https://media.invalid/media-video-hvc1/"]}}]
    }
    net = network(monkeypatch, {("GET", FULL): (200, page(video=video), {})})
    result = execute([FULL])
    assert result["success"]
    assert result["results"][0]["formats"][0]["audio_metadata"] == "absent"
    assert result["results"][0]["formats"][0]["marked_for_probe"]
    assert len(net.calls) == 1


@pytest.mark.parametrize("seconds", [float("nan"), float("inf"), -1, 181])
def test_bounds_cannot_be_disabled(seconds):
    with pytest.raises(ValueError):
        h.Limits(max_seconds=seconds)


@pytest.mark.parametrize("interrupt", [False, True, "during_spawn"])
def test_parent_terminates_and_reaps_stalled_worker(monkeypatch, interrupt):
    monkeypatch.setattr(
        h, "_command", lambda: [sys.executable, "-c", "import time; time.sleep(30)"]
    )
    real_popen, owned = subprocess.Popen, []

    def popen(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        owned.append(process)
        if interrupt == "during_spawn":
            os.kill(os.getpid(), signal.SIGINT)
        elif interrupt:
            communicate = process.communicate
            first = [True]

            def interrupted(*args, **kwargs):
                if first.pop() if first else False:
                    raise KeyboardInterrupt
                return communicate(*args, **kwargs)

            process.communicate = interrupted
        return process

    monkeypatch.setattr(h.subprocess, "Popen", popen)
    result = h.run([FULL], h.Limits(max_seconds=0.2))
    assert result["error"] == ("interrupted" if interrupt else "deadline")
    assert not result["counts_exact"]
    assert owned[0].returncode is not None
    with pytest.raises(ProcessLookupError):
        os.kill(owned[0].pid, 0)


def test_supervisor_success_and_worker_crash_are_sanitized(monkeypatch):
    payload = {
        "success": True,
        "results": [],
        "error": None,
        "requests": 1,
        "metadata_bytes": 10,
        "extractions": 1,
        "counts_exact": True,
    }
    command = "import json; print(json.dumps(" + repr({"result": payload}) + "))"
    monkeypatch.setattr(h, "_command", lambda: [sys.executable, "-c", command])
    assert h.run([FULL])["success"]
    monkeypatch.setattr(h, "_command", lambda: [sys.executable, "-c", "print('private crash')"])
    result = h.run([FULL])
    assert result["error"] == "worker_error"
    assert not result["counts_exact"]
    assert "private crash" not in json.dumps(result)


def test_redirect_hop_bound_and_proxy_environment_ignored(monkeypatch):
    monkeypatch.setenv("https_proxy", "http://proxy.invalid:1234")
    next_short = "https://vt.tiktok.com/Next"
    last_short = "https://vm.tiktok.com/Last"
    net = network(
        monkeypatch,
        {
            ("HEAD", SHORT): (302, b"", {"Location": next_short}),
            ("HEAD", next_short): (302, b"", {"Location": last_short}),
            ("HEAD", last_short): (302, b"", {"Location": FULL}),
        },
    )
    assert execute([SHORT])["error"] == "redirect_limit"
    assert [url for _, url, _ in net.calls] == [SHORT, next_short, last_short]
    assert not any(
        isinstance(handler, ProxyHandler) and handler.proxies for handler in h._opener().handlers
    )


def test_real_worker_bootstrap_without_urls_or_network():
    # Exercise the actual subprocess entry point/imports without approving any URL.
    request = {"urls": [], "limits": h.asdict(h.Limits()), "deadline": monotonic() + 10}
    command = h._command()
    command[2] = (
        "import socket; "
        "socket.socket.connect = socket.socket.connect_ex = "
        "lambda *a, **k: (_ for _ in ()).throw(AssertionError('No sockets')); " + command[2]
    )
    process = subprocess.run(
        command,
        input=json.dumps(request),
        text=True,
        capture_output=True,
        timeout=10,
        check=True,
    )
    result = json.loads(process.stdout)["result"]
    assert result["success"] and result["results"] == []
    assert result["requests"] == result["extractions"] == result["metadata_bytes"] == 0
    assert not process.stderr
