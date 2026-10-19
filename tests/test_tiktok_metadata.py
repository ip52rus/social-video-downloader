"""Real extractor/urllib paths with synthetic HTTPS; external sockets forbidden."""

import io
import json
import os
import signal
import socket
import subprocess
import sys
import time
from contextlib import suppress
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
MISSING = object()


@pytest.fixture(autouse=True)
def no_sockets(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("External sockets are forbidden")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)


def page(*, status=0, video=None, identity="123456789"):
    item = {
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
    if identity is not MISSING:
        item["id"] = identity
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
        message["Content-Type"] = "text/html"
        for name, value in headers.items() if isinstance(headers, dict) else headers:
            if name.lower() == "content-type":
                del message[name]
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


@pytest.fixture
def owned_workers(monkeypatch):
    """Emergency cleanup is independent of assertions and the tested supervisor."""
    real_popen, owned = subprocess.Popen, []

    def create(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        owned.append(process)
        return process

    monkeypatch.setattr(h.subprocess, "Popen", create)
    yield owned
    for process in owned:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def assert_absent(pid):
    deadline = monotonic() + 3
    while monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.01)
    pytest.fail("Operation-owned test process survived cleanup")


@pytest.mark.parametrize("short", [False, True])
@pytest.mark.parametrize("identity", ["123456789", "987654321"])
def test_source_identity_before_real_mapper(monkeypatch, short, identity):
    routes = {("GET", FULL): (200, page(identity=identity), {})}
    if short:
        routes.update(
            {("HEAD", SHORT): (302, b"", {"Location": FULL}), ("HEAD", FULL): (200, b"", {})}
        )
    net = network(monkeypatch, routes)
    original, mapped = h.TikTokIE._parse_aweme_video_web, []

    def real_mapper(self, *args, **kwargs):
        mapped.append(True)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(h.TikTokIE, "_parse_aweme_video_web", real_mapper)
    result = execute([SHORT if short else FULL])
    assert result["success"] == (identity == "123456789")
    assert len(mapped) == int(result["success"])
    assert result["extractions"] == (2 if short else 1)
    assert result["requests"] == len(net.calls) == (3 if short else 1)
    if not result["success"]:
        assert result["error"] == "identity_changed"
        assert "formats" not in result["results"][0]
    assert identity not in json.dumps(result)


@pytest.mark.parametrize("identity", [MISSING, None, True, 123456789, "", "bad", {}, []])
def test_unconfirmed_source_identity_stops_series(monkeypatch, identity):
    net = network(monkeypatch, {("GET", FULL): (200, page(identity=identity), {})})
    result = execute([FULL, FULL])
    assert result["error"] == "invalid_identity"
    assert not result["success"] and len(result["results"]) == 1
    assert result["extractions"] == result["requests"] == len(net.calls) == 1


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
        (200, page(), {"Content-Encoding": "gzip"}, "encoded_response"),
        (200, b"media", {"Content-Type": "video/mp4"}, "non_html_response"),
    ],
)
def test_forbidden_paths_no_retry(monkeypatch, code, body, headers, error):
    headers = {**headers, "Set-Cookie": "private=secret"}
    net = network(monkeypatch, {("GET", FULL): (code, body, headers)})
    result = execute([FULL, FULL])
    assert result["error"] == error
    assert result["requests"] == result["extractions"] == len(net.calls) == 1
    assert len(result["results"]) == 1


def test_login_status_real_extractor_no_retry(monkeypatch):
    net = network(
        monkeypatch,
        {("GET", FULL): (200, page(status=10216), {"Set-Cookie": "private=secret"})},
    )
    result = execute([FULL, FULL])
    assert not result["success"] and result["error"] == "login_required"
    assert len(net.calls) == result["extractions"] == 1


@pytest.mark.parametrize(
    "headers",
    [
        [("Set-Cookie", "private=secret; Path=/")],
        [
            ("Set-Cookie", "private=secret; Path=/"),
            ("sEt-CoOkIe", "another=secret; Path=/"),
        ],
    ],
)
@pytest.mark.parametrize("short", [False, True])
def test_response_cookies_discarded_before_real_extractor_and_later_requests(
    monkeypatch, headers, short
):
    net = network(
        monkeypatch,
        {
            ("HEAD", SHORT): (302, b"", [("Location", FULL), *headers]),
            ("HEAD", FULL): (200, b"", headers),
            ("GET", FULL): (200, page(), headers),
        },
    )
    original, jars, responses = h._YDL.urlopen, [], []

    def inspect_response(self, request):
        response = original(self, request)
        responses.append(response)
        jars.append(self.cookiejar)
        assert not any(name.lower() == "set-cookie" for name in response.headers)
        assert not list(self.cookiejar)
        return response

    monkeypatch.setattr(h._YDL, "urlopen", inspect_response)
    result = execute([SHORT if short else FULL, FULL])
    assert result["success"] and len(result["results"]) == 2
    assert result["requests"] == len(net.calls) == (4 if short else 2)
    assert result["extractions"] == len(responses) == (3 if short else 2)
    assert all(not list(jar) for jar in jars)
    assert all(name.lower() != "cookie" for _, _, sent in net.calls for name in sent)
    assert "secret" not in json.dumps(result)


def test_cookie_from_yt_dlp_internal_headers_blocked_before_network(monkeypatch):
    net = network(monkeypatch, {})

    def attempted_cookie(self, url):
        return self._downloader.urlopen(Request(url, headers={"cOoKiE": "private=secret"}))

    monkeypatch.setattr(h._MetadataIE, "_real_extract", attempted_cookie)
    result = execute([FULL, FULL])
    assert not result["success"] and result["error"] == "credentials_forbidden"
    assert result["requests"] == len(net.calls) == 0
    assert result["extractions"] == len(result["results"]) == 1


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
def test_parent_terminates_and_reaps_stalled_worker(monkeypatch, owned_workers, interrupt):
    monkeypatch.setattr(
        h, "_command", lambda: [sys.executable, "-c", "import time; time.sleep(30)"]
    )
    create = subprocess.Popen
    exchange = h._exchange

    def popen(*args, **kwargs):
        process = create(*args, **kwargs)
        if interrupt == "during_spawn":
            os.kill(os.getpid(), signal.SIGINT)
        return process

    def interrupted(*args):
        if interrupt is True:
            raise KeyboardInterrupt
        return exchange(*args)

    monkeypatch.setattr(h, "_exchange", interrupted)
    monkeypatch.setattr(h.subprocess, "Popen", popen)
    result = h.run([FULL], h.Limits(max_seconds=0.2))
    assert result["error"] == ("interrupted" if interrupt else "deadline")
    assert not result["counts_exact"]
    assert owned_workers[0].returncode is not None
    assert_absent(owned_workers[0].pid)


def test_supervisor_success_and_worker_crash_are_sanitized(monkeypatch, owned_workers):
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


@pytest.mark.parametrize("holds_stdout", [True, False])
def test_exited_leader_descendant_terminated(monkeypatch, tmp_path, owned_workers, holds_stdout):
    pidfile = tmp_path / "descendant.pid"
    body = f"""
import os,time,pathlib
child = os.fork()
if child == 0:
    if not {holds_stdout!r}:
        os.close(1)
    time.sleep(30)
    os._exit(0)
pathlib.Path({str(pidfile)!r}).write_text(str(child))
os._exit(0)
"""
    monkeypatch.setattr(h, "_command", lambda: [sys.executable, "-c", body])
    kill, signaled = os.killpg, []

    def owned_group_only(pgid, sig):
        if sig == signal.SIGKILL:
            assert pgid == owned_workers[0].pid
            assert owned_workers[0].returncode is None  # Leader is still an unreaped anchor.
            signaled.append(pgid)
        return kill(pgid, sig)

    with monkeypatch.context() as scoped:
        scoped.setattr(h.os, "killpg", owned_group_only)
        result = h.run([FULL], h.Limits(max_seconds=0.5))
    assert result["error"] == ("deadline" if holds_stdout else "worker_error")
    assert not result["success"] and not result["counts_exact"]
    assert owned_workers[0].returncode == 0
    assert signaled == [owned_workers[0].pid]
    assert_absent(int(pidfile.read_text()))


@pytest.mark.parametrize("fault", ["kill", "communicate"])
def test_cleanup_exception_is_explicit_and_worker_reaped(monkeypatch, owned_workers, fault):
    monkeypatch.setattr(
        h, "_command", lambda: [sys.executable, "-c", "import time; time.sleep(30)"]
    )
    kill, create = os.killpg, subprocess.Popen
    calls = []

    def faulty_kill(*args):
        calls.append(True)
        if fault == "kill" and len(calls) == 1:
            raise OSError("Synthetic cleanup failure")
        return kill(*args)

    def faulty_create(*args, **kwargs):
        process = create(*args, **kwargs)
        if fault == "communicate":

            def failed(*args, **kwargs):
                raise OSError("Synthetic pipe cleanup failure")

            process.communicate = failed
        return process

    monkeypatch.setattr(h.os, "killpg", faulty_kill)
    monkeypatch.setattr(h.subprocess, "Popen", faulty_create)
    result = h.run([FULL], h.Limits(max_seconds=0.2))
    assert result["error"] == "cleanup_failed" and not result["counts_exact"]
    assert owned_workers[0].returncode is not None
    assert_absent(owned_workers[0].pid)


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize("repeat_cleanup", [False, True])
def test_cli_signal_cleanup(monkeypatch, tmp_path, owned_workers, signum, repeat_cleanup):
    pidfile = tmp_path / "worker.pid"
    worker_code = (
        f"import os,time,pathlib; pathlib.Path({str(pidfile)!r})"
        ".write_text(str(os.getpid())); time.sleep(30)"
    )
    worker = [sys.executable, "-c", worker_code]
    bootstrap = f"""
import runpy,sys,os,signal
m = runpy.run_path({str(h.Path(h.__file__).resolve())!r})
g = m['_command'].__globals__
g['_command'] = lambda: {worker!r}
kill = os.killpg
def during_cleanup(*args):
    kill(*args)
    if {repeat_cleanup!r}:
        os.kill(os.getpid(), signal.SIGINT)
        os.kill(os.getpid(), signal.SIGTERM)
os.killpg = during_cleanup
sys.exit(m['main']())
"""
    command = [
        sys.executable,
        "-c",
        (
            "import socket; socket.socket.connect = socket.socket.connect_ex = "
            "lambda *a, **k: (_ for _ in ()).throw(AssertionError('No sockets'));\n" + bootstrap
        ),
    ]
    controller = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        controller.stdin.write(json.dumps([FULL]))
        controller.stdin.close()
        controller.stdin = None
        deadline = monotonic() + 5
        while not pidfile.exists() and monotonic() < deadline:
            time.sleep(0.01)
        assert pidfile.exists()
        os.kill(controller.pid, signum)
        output, _ = controller.communicate(timeout=5)
        assert controller.returncode != 0
        if not repeat_cleanup:
            result = json.loads(output)
            assert result["error"] == "interrupted" and not result["counts_exact"]
        assert_absent(int(pidfile.read_text()))
    finally:
        if pidfile.exists():
            with suppress(ProcessLookupError):
                os.killpg(int(pidfile.read_text()), signal.SIGKILL)
