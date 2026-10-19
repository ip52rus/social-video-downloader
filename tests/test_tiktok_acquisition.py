"""Offline real mapper/urllib and local FFmpeg; no external socket connections."""

import hashlib
import http.client
import io
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
from contextlib import suppress
from dataclasses import replace
from pathlib import Path
from time import monotonic
from types import SimpleNamespace
from urllib.request import ProxyHandler, build_opener
from urllib.response import addinfourl

import pytest

from scripts import tiktok_acquisition as a
from scripts import tiktok_metadata as m
from tests.integration.test_video_preparation import generate
from tests.test_tiktok_metadata import Network, page

A = "https://www.tiktok.com/@fixture/video/123456789"
B = "https://www.tiktok.com/@fixture/video/987654321"
MEDIA = "https://v16-webapp-prime.tiktok.com/video/synthetic/"
OTHER = "https://v19-webapp-prime.tiktok.com/video/synthetic/"


@pytest.fixture(autouse=True)
def no_sockets(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("External sockets forbidden")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)


def routes(first=b"x", second=b"y", identity="123456789", media_url=MEDIA):
    return {
        ("GET", A): (200, page(identity=identity, video={"playAddr": media_url}), {}),
        ("GET", B): (200, page(identity="987654321", video={"playAddr": OTHER}), {}),
        ("GET", media_url): (
            200,
            first,
            {"Content-Type": "video/mp4", "Content-Length": str(len(first))},
        ),
        ("GET", OTHER): (
            200,
            second,
            {"Content-Type": "video/mp4", "Content-Length": str(len(second))},
        ),
    }


class FramedNetwork(Network):
    """Actual HTTPResponse framing; replace only socket I/O, never read()."""

    def https_open(self, request):
        self.calls.append((request.get_method(), request.full_url, dict(request.header_items())))
        code, body, headers = self.routes[(request.get_method(), request.full_url)]
        fields = list(headers.items()) if isinstance(headers, dict) else headers
        wire = (
            f"HTTP/1.1 {code} Synthetic\r\nContent-Type: text/html\r\n"
            + "".join(f"{name}: {value}\r\n" for name, value in fields)
            + "\r\n"
        ).encode() + body
        raw = http.client.HTTPResponse(SimpleNamespace(makefile=lambda *args: io.BytesIO(wire)))
        raw.begin()
        response = addinfourl(raw, raw.headers, request.full_url, code)
        response.msg = "Synthetic"
        return response


def install(data, network_type=Network):
    net = network_type(data)
    a._opener = lambda: build_opener(ProxyHandler({}), m._NoRedirect(), net)
    return net


def network(monkeypatch, data):
    # Patching only this experiment's opener leaves metadata CLI admission intact.
    net = Network(data)
    monkeypatch.setattr(a, "_opener", lambda: build_opener(ProxyHandler({}), m._NoRedirect(), net))
    return net


@pytest.fixture
def media_files(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("Local FFmpeg/ffprobe required")
    sound, silent = tmp_path / "sound.mp4", tmp_path / "silent.mp4"
    generate(sound, audio=True)
    generate(silent)
    return sound, silent


@pytest.fixture
def workers(monkeypatch):
    original, owned = subprocess.Popen, []

    def spawn(*args, **kwargs):
        process = original(*args, **kwargs)
        if kwargs.get("start_new_session"):
            owned.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", spawn)
    yield owned
    for process in owned:
        if process.returncode is None:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)


@pytest.mark.parametrize("overflow", [False, True])
def test_real_mapping_probe_decode_and_parent_cleanup(monkeypatch, media_files, workers, overflow):
    source, silent = media_files
    hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in media_files]
    commands, workspaces = a._command, []

    def command(workspace):
        workspaces.append(Path(workspace))
        original = commands(workspace)
        bootstrap = (
            "import sys,socket; "
            "socket.socket.connect=socket.socket.connect_ex="
            "lambda *a,**k: (_ for _ in ()).throw(AssertionError('No sockets')); "
            "from tests.test_tiktok_acquisition import install,routes; "
            "from pathlib import Path; "
            f"sound=Path({str(source)!r}).read_bytes(); "
            f"silent=Path({str(silent)!r}).read_bytes(); install(routes(sound,silent)); "
            "from scripts import tiktok_acquisition as patched; import runpy; "
            "worker=runpy.run_path(sys.argv[1])['_worker_main']; "
            "worker.__globals__['_opener']=patched._opener; worker()"
        )
        return [*original[:2], bootstrap, *original[3:]]

    monkeypatch.setattr(a, "_command", command)
    limits = a.Limits(max_file_bytes=1024) if overflow else a.Limits()
    result = a.run([A + "?tracking=discard", B], limits)
    assert result["workspace_cleaned"] and not workspaces[0].exists()
    assert all(process.returncode is not None for process in workers)
    assert hashes == [hashlib.sha256(p.read_bytes()).hexdigest() for p in media_files]
    if overflow:
        assert not result["success"] and result["error"] == "media_byte_limit"
        assert result["media_bytes"] == 1024
        assert result["acquisitions"] == result["extractions"] == 1
        return
    assert result["success"], result
    assert result["extractions"] == result["acquisitions"] == result["media_requests"] == 2
    assert result["requests"] == 2
    assert result["media_bytes"] == sum(p.stat().st_size for p in media_files)
    assert all(e["decoded"] and e["preparation"] == "passthrough" for e in result["results"])
    assert [e["probe"]["audio_streams"] for e in result["results"]] == [1, 0]
    assert all(e["probe"]["video_codec"] == "h264" for e in result["results"])
    assert all(e["probe"]["width"] == 64 for e in result["results"])
    assert all(secret not in json.dumps(result) for secret in (A, B, MEDIA, "123456789"))


@pytest.mark.parametrize("truncated", [False, True])
def test_real_http_framing_before_probe_and_second_video(
    monkeypatch, tmp_path, media_files, workers, truncated
):
    source = tmp_path / "fragmented.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=s=64x96:r=10",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440",
            "-t",
            "2.2",
            "-c:v",
            "libx264",
            "-g",
            "5",
            "-c:a",
            "aac",
            "-movflags",
            "frag_keyframe+empty_moov",
            str(source),
        ],
        check=True,
        capture_output=True,
        timeout=15,
    )
    body = source.read_bytes()
    end = 0
    while end < len(body):
        size = int.from_bytes(body[end : end + 4], "big")
        assert size >= 8
        kind = body[end + 4 : end + 8]
        end += size
        if kind == b"mdat":
            break
    assert end < len(body)
    prefix = tmp_path / "playable-prefix.mp4"
    prefix.write_bytes(body[:end])
    # Prove that local validation alone cannot establish HTTP completeness.
    probe = a._validate(prefix, monotonic() + 15)
    a._prepare_and_decode(prefix, probe, 1, monotonic() + 15)
    original_command, workspaces = a._command, []

    def command(workspace):
        workspaces.append(Path(workspace))
        original = original_command(workspace)
        bootstrap = (
            "import sys,socket; "
            "socket.socket.connect=socket.socket.connect_ex="
            "lambda *a,**k: (_ for _ in ()).throw(AssertionError('No sockets')); "
            "from tests.test_tiktok_acquisition import install,routes,FramedNetwork,MEDIA; "
            "from pathlib import Path; "
            f"body=Path({str(source)!r}).read_bytes(); "
            f"prefix=Path({str(prefix)!r}).read_bytes(); "
            f"silent=Path({str(media_files[1])!r}).read_bytes(); "
            "data=routes(body,silent); "
            + (
                "data[('GET',MEDIA)]=(200,prefix,{'Content-Length':str(len(body))}); "
                if truncated
                else ""
            )
            + "install(data,FramedNetwork); "
            "from scripts import tiktok_acquisition as patched; import runpy; "
            "worker=runpy.run_path(sys.argv[1])['_worker_main']; "
            "worker.__globals__['_opener']=patched._opener; worker()"
        )
        return [*original[:2], bootstrap, *original[3:]]

    monkeypatch.setattr(a, "_command", command)
    result = a.run([A, B])
    assert result["workspace_cleaned"] and not workspaces[0].exists()
    assert result["counts_exact"]
    assert all(p.returncode is not None for p in workers)
    assert source.read_bytes() == body and prefix.read_bytes() == body[:end]
    if truncated:
        assert not result["success"] and result["error"] == "incomplete_media_response"
        assert result["media_bytes"] == end
        assert result["extractions"] == result["acquisitions"] == result["media_requests"] == 1
        assert len(result["results"]) == 1 and "probe" not in result["results"][0]
    else:
        assert result["success"] and result["extractions"] == result["acquisitions"] == 2
        assert all(e["decoded"] for e in result["results"])


@pytest.mark.parametrize(
    ("headers", "body", "error"),
    [
        ([], b"x", "unverifiable_media_framing"),
        ([("Content-Length", "-1")], b"x", "invalid_media_framing"),
        ([("Content-Length", "invalid")], b"x", "invalid_media_framing"),
        ([("Content-Length", "1, 1")], b"x", "invalid_media_framing"),
        ([("Content-Length", "1"), ("content-length", "1")], b"x", "invalid_media_framing"),
        ([("Content-Length", "1"), ("Content-Length", "2")], b"x", "invalid_media_framing"),
        ([("Content-Length", "1"), ("Transfer-Encoding", "chunked")], b"", "invalid_media_framing"),
        ([("Transfer-Encoding", "chunked")], b"1\r\nx\r\n0\r\n\r\n", "unsupported_media_framing"),
        ([("transfer-encoding", "chunked")], b"1\r\nx\r\n", "unsupported_media_framing"),
        ([("Transfer-Encoding", "gzip")], b"x", "unsupported_media_framing"),
    ],
)
def test_real_parser_rejects_ambiguous_or_unverifiable_framing(
    monkeypatch, tmp_path, headers, body, error
):
    data = routes()
    data[("GET", MEDIA)] = (200, body, headers)
    net = FramedNetwork(data)
    monkeypatch.setattr(a, "_opener", lambda: build_opener(ProxyHandler({}), m._NoRedirect(), net))
    result = a._execute([A, B], a.Limits(), monotonic() + 10, tmp_path, lambda e: None)
    assert not result["success"] and result["error"] == error
    assert result["media_bytes"] == 0
    assert result["extractions"] == result["acquisitions"] == result["media_requests"] == 1
    assert len(net.calls) == 2 and len(result["results"]) == 1
    assert "probe" not in result["results"][0] and not list(tmp_path.iterdir())


def test_complete_real_parser_body_can_use_exact_byte_budget(monkeypatch, tmp_path):
    net = FramedNetwork({("GET", MEDIA): (200, b"video", {"Content-Length": "5"})})
    monkeypatch.setattr(a, "_opener", lambda: build_opener(ProxyHandler({}), m._NoRedirect(), net))
    media = a._Media(
        a.Limits(max_file_bytes=5, max_total_bytes=5), monotonic() + 10, tmp_path, lambda e: None
    )
    path = tmp_path / "video.mp4"
    media.acquire(MEDIA, path)
    assert media.received == path.stat().st_size == 5


@pytest.mark.parametrize("bad", ["source", "host", "provenance", "probe_required"])
def test_untrusted_selection_stops_before_media_get(monkeypatch, tmp_path, bad):
    data = routes(
        identity="987654321" if bad == "source" else "123456789",
        media_url="https://outside.invalid/video/a/" if bad == "host" else MEDIA,
    )
    net = network(monkeypatch, data)
    if bad in {"provenance", "probe_required"}:
        original = a._SourceIE._parse_aweme_video_web

        def altered(self, *args, **kwargs):
            result = original(self, *args, **kwargs)
            if bad == "provenance":
                result["formats"][0]["url"] = OTHER
            else:
                result["formats"][0]["__needs_testing"] = True
            return result

        monkeypatch.setattr(a._SourceIE, "_parse_aweme_video_web", altered)
    result = a._execute([A, B], a.Limits(), monotonic() + 10, tmp_path, lambda e: None)
    assert not result["success"] and result["acquisitions"] == 0
    assert result["media_requests"] == 0 and len(net.calls) == 1
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "target",
    [
        "https://outside.invalid/video/a/",
        "https://127.0.0.1/video/a/",
        "http://v16-webapp-prime.tiktok.com/video/a/",
        "https://v16-webapp-prime.tiktok.com@outside.invalid/video/a/",
        "https://v16-webapp-prime.tiktok.com:443/video/a/",
    ],
)
def test_redirect_policy_blocks_before_target_connection(monkeypatch, tmp_path, target):
    net = network(monkeypatch, {("GET", MEDIA): (302, b"", {"Location": target})})
    media = a._Media(a.Limits(), monotonic() + 10, tmp_path, lambda e: None)
    with pytest.raises(m.Stop):
        media.acquire(MEDIA, tmp_path / "video.mp4")
    assert len(net.calls) == media.requests == 1


def test_approved_redirect_cookies_discarded_and_no_cookie_sent(monkeypatch, tmp_path):
    net = network(
        monkeypatch,
        {
            ("GET", MEDIA): (302, b"", {"Location": OTHER, "Set-Cookie": "fixture=discard"}),
            ("GET", OTHER): (
                200,
                b"video",
                {"Set-Cookie": "fixture=discard", "Content-Length": "5"},
            ),
        },
    )
    media = a._Media(a.Limits(), monotonic() + 10, tmp_path, lambda e: None)
    media.acquire(MEDIA, tmp_path / "video.mp4")
    assert media.requests == 2 and media.attempts == 1
    assert not any(name.lower() == "cookie" for _, _, sent in net.calls for name in sent)


@pytest.mark.parametrize(
    "addresses",
    [
        ["127.0.0.1"],
        ["10.0.0.1"],
        ["169.254.169.254"],
        ["0.0.0.0"],
        ["224.0.0.1"],
        ["192.0.2.1"],
        ["8.8.8.8", "192.168.0.1"],
    ],
)
def test_private_reserved_and_mixed_dns_answers_never_connect(monkeypatch, addresses):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)) for ip in addresses
        ],
    )
    monkeypatch.setattr(
        socket, "socket", lambda *a: pytest.fail("Connection before DNS validation")
    )
    connection = a._PinnedHTTPSConnection("v16-webapp-prime.tiktok.com", timeout=1)
    with pytest.raises(m.Stop, match="dns_forbidden"):
        connection.connect()


def test_public_ip_is_pinned_without_second_dns_lookup_and_tls_keeps_hostname(monkeypatch):
    calls, connected, tls = [], [], []

    def resolve(*args):
        calls.append(args)
        assert len(calls) == 1, "DNS rebinding through a second lookup"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]

    raw = SimpleNamespace(settimeout=lambda t: None, connect=connected.append, close=lambda: None)
    connection = a._PinnedHTTPSConnection("v16-webapp-prime.tiktok.com", timeout=1)
    assert connection._context.check_hostname
    assert connection._context.verify_mode == 2  # ssl.CERT_REQUIRED
    connection._context = SimpleNamespace(
        wrap_socket=lambda sock, **kwargs: tls.append(kwargs) or raw
    )
    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    monkeypatch.setattr(socket, "socket", lambda *a: raw)
    connection.connect()
    assert connected == [("8.8.8.8", 443)]
    assert tls == [{"server_hostname": "v16-webapp-prime.tiktok.com"}]


@pytest.mark.parametrize("headers", [{}, {"Content-Length": "100000000"}])
def test_actual_25_mib_cap_independent_of_size_header(monkeypatch, tmp_path, headers):
    cap = a.Limits().max_file_bytes
    net = FramedNetwork({("GET", MEDIA): (200, b"x" * (cap + 1), headers)})
    monkeypatch.setattr(a, "_opener", lambda: build_opener(ProxyHandler({}), m._NoRedirect(), net))
    media = a._Media(a.Limits(), monotonic() + 10, tmp_path, lambda e: None)
    output = tmp_path / "video.mp4"
    with pytest.raises(
        m.Stop, match="media_byte_limit" if headers else "unverifiable_media_framing"
    ):
        media.acquire(MEDIA, output)
    if headers:
        assert media.received == output.stat().st_size == cap
    else:
        assert media.received == 0 and not output.exists()
    assert media.attempts == media.requests == 1


@pytest.mark.parametrize("budget", ["aggregate", "workspace"])
def test_aggregate_and_partial_workspace_budgets(monkeypatch, tmp_path, budget):
    net = FramedNetwork({("GET", MEDIA): (200, b"x" * 8, {"Content-Length": "8"})})
    monkeypatch.setattr(a, "_opener", lambda: build_opener(ProxyHandler({}), m._NoRedirect(), net))
    limits = (
        a.Limits(max_total_bytes=12) if budget == "aggregate" else a.Limits(max_workspace_bytes=12)
    )
    media = a._Media(limits, monotonic() + 10, tmp_path, lambda e: None)
    media.acquire(MEDIA, tmp_path / "first.mp4")
    with pytest.raises(m.Stop, match="media_byte_limit"):
        media.acquire(MEDIA, tmp_path / "second.mp4")
    assert media.received == sum(p.stat().st_size for p in tmp_path.iterdir()) == 12


@pytest.mark.parametrize("code", [403, 429, 404])
def test_media_http_errors_no_retry_fallback_or_second_video(monkeypatch, tmp_path, code):
    data = routes()
    data[("GET", MEDIA)] = (code, b"error", {})
    net = network(monkeypatch, data)
    result = a._execute([A, B], a.Limits(), monotonic() + 10, tmp_path, lambda e: None)
    assert not result["success"] and result["acquisitions"] == result["media_requests"] == 1
    assert result["extractions"] == 1 and len(net.calls) == 2
    assert len(result["results"]) == 1 and not list(tmp_path.iterdir())


@pytest.mark.parametrize("video", ["libx264", "mpeg4"])
def test_actual_audio_not_ytdlp_metadata_and_no_transcode(monkeypatch, tmp_path, video):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("Local FFmpeg/ffprobe required")
    path = tmp_path / "source.mp4"
    generate(path, video=video, audio=False)
    probe = a._validate(path, monotonic() + 15)
    assert probe["audio_codec"] == "absent" and probe["audio_streams"] == 0
    assert probe["video_codec"] == ("mpeg4" if video == "mpeg4" else "h264")
    with pytest.raises(
        m.Stop, match="incompatible_media" if video == "mpeg4" else "audio_required"
    ):
        a._prepare_and_decode(path, probe, 1, monotonic() + 15)
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("mode", ["failure", "timeout", "interrupt"])
def test_parent_cleans_partial_after_worker_failure_deadline_interrupt(
    monkeypatch, tmp_path, workers, mode
):
    foreign = tmp_path / "foreign.mp4"
    foreign.write_bytes(b"caller-owned")
    workspaces = []

    def command(workspace):
        workspaces.append(Path(workspace))
        code = (
            "import sys,pathlib,time,socket; "
            "socket.socket.connect=lambda *a: (_ for _ in ()).throw(AssertionError('No sockets')); "
            "pathlib.Path(sys.argv[1],'partial.mp4').write_bytes(b'partial'); "
            + ("sys.exit(1)" if mode == "failure" else "time.sleep(30)")
        )
        return [sys.executable, "-c", code, workspace]

    monkeypatch.setattr(a, "_command", command)
    if mode == "interrupt":

        def interrupted(process, *args):
            # Ensure the child created its partial file before cancellation.
            import time

            for _ in range(100):
                if (workspaces[0] / "partial.mp4").exists():
                    break
                time.sleep(0.005)
            raise KeyboardInterrupt

        monkeypatch.setattr(m, "_exchange", interrupted)
    result = a.run([A, B], a.Limits(max_seconds=0.5))
    assert not result["success"] and result["workspace_cleaned"]
    assert not workspaces[0].exists() and foreign.read_bytes() == b"caller-owned"
    assert all(p.returncode is not None for p in workers)


def test_subprocess_deadline_kills_and_reaps_local_probe(monkeypatch, tmp_path):
    if os.name != "posix":
        pytest.skip("POSIX experiment")
    tool = tmp_path / "ffprobe"
    tool.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(30)\n")
    tool.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path))
    original, children = subprocess.Popen, []

    def spawn(*args, **kwargs):
        p = original(*args, **kwargs)
        children.append(p)
        return p

    monkeypatch.setattr(subprocess, "Popen", spawn)
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            a._probe_runner(monotonic() + 0.1)(["ffprobe"], capture_output=True, text=True)
        assert children[0].returncode is not None
    finally:
        for child in children:
            if child.returncode is None:
                child.kill()
                child.wait(timeout=5)


def test_deadline_prevents_http_and_bounds_cannot_expand(monkeypatch, tmp_path):
    net = network(monkeypatch, {})
    with pytest.raises(m.Stop, match="deadline"):
        a._Media(a.Limits(), monotonic() - 1, tmp_path, lambda e: None).acquire(
            MEDIA, tmp_path / "v.mp4"
        )
    assert not net.calls
    for name, value in vars(a.Limits()).items():
        with pytest.raises(ValueError):
            replace(a.Limits(), **{name: value + 1})


def test_short_duplicate_and_media_inputs_rejected_without_worker(monkeypatch):
    monkeypatch.setattr(a, "_command", lambda *args: pytest.fail("Worker forbidden"))
    for urls in ([A, A], [A], [A, MEDIA], ["https://vm.tiktok.com/Fixture", B]):
        assert not a.run(urls)["success"]


@pytest.mark.parametrize("failure", ["worker", "workspace"])
def test_cleanup_failure_is_explicit_and_never_deletes_under_unconfirmed_worker(
    monkeypatch, failure
):
    owned = []

    def supervisor(urls, limits, command):
        workspace = Path(command()[-1])
        owned.append(workspace)
        (workspace / "partial.mp4").write_bytes(b"partial")
        return {
            "success": failure != "worker",
            "error": "cleanup_failed" if failure == "worker" else None,
        }

    monkeypatch.setattr(m, "_supervise", supervisor)
    if failure == "workspace":

        def denied(self):
            raise PermissionError("Synthetic filesystem cleanup failure")

        monkeypatch.setattr(a.TemporaryDirectory, "cleanup", denied)
    try:
        result = a.run([A, B])
        assert not result["success"] and not result["workspace_cleaned"]
        assert result["error"] == (
            "cleanup_failed" if failure == "worker" else "workspace_cleanup_failed"
        )
        assert (owned[0] / "partial.mp4").read_bytes() == b"partial"
    finally:
        for path in owned:
            shutil.rmtree(path)
