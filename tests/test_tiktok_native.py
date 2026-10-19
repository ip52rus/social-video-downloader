"""Synthetic wire, pinned transport faults and local FFmpeg only; no external I/O."""

import http.client
import io
import json
import os
import signal
import socket
import ssl
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from time import monotonic
from types import SimpleNamespace

import pytest

from scripts import tiktok_native as n
from tests.integration.test_video_preparation import generate

A = "https://www.tiktok.com/@fixture/video/11111111"
B = "https://www.tiktok.com/@fixture/video/22222222"
EMBED = "https://www.tiktok.com/embed/v2/11111111"
MEDIA = "https://v77.tiktokcdn.com/opaque/resource?signature=PRIVATE_SIGNED%2B%2F&x=1&x=2"
OTHER = "https://v16-webapp-prime.tiktok.com/opaque"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("External sockets forbidden")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)


def page(identity="11111111", video=None):
    item = {"id": identity, "desc": "PRIVATE_DESCRIPTION", "video": video or {"playAddr": MEDIA}}
    state = {"source": {"data": {"/embed/v2/11111111": {"videoData": {"itemInfos": item}}}}}
    return (
        '<script id="__FRONTITY_CONNECT_STATE__" type="application/json">'
        + json.dumps(state)
        + "</script>"
    ).encode()


class Wire:
    """Real HTTPResponse parses response framing; capture the actual HTTP request."""

    def __init__(self, routes):
        self.routes, self.requests = routes, []

    def connect(self, connection):
        wire = self

        class Socket:
            def __init__(self):
                self.sent = bytearray()

            def sendall(self, data):
                self.sent.extend(data)

            def makefile(self, *args):
                line, rest = bytes(self.sent).split(b"\r\n", 1)
                method, path, _ = line.decode().split(" ")
                headers = http.client.parse_headers(io.BytesIO(rest))
                wire.requests.append((connection.host, method, path, headers))
                status, body, fields = wire.routes[(connection.host, path)]
                fields = list(fields.items()) if isinstance(fields, dict) else fields
                packet = (
                    f"HTTP/1.1 {status} Synthetic\r\n"
                    + "".join(f"{k}: {v}\r\n" for k, v in fields)
                    + "\r\n"
                ).encode() + body
                return io.BytesIO(packet)

            def close(self):
                pass

        connection.sock = Socket()


def install(routes):
    wire = Wire(routes)
    n._Pinned.connect = lambda conn: wire.connect(conn)
    return wire


def network(monkeypatch, routes):
    wire = Wire(routes)
    monkeypatch.setattr(n._Pinned, "connect", lambda conn: wire.connect(conn))
    return wire


def response(body, content_type="text/html", fields=()):
    return 200, body, [("Content-Type", content_type), ("Content-Length", str(len(body))), *fields]


def key(url):
    p = n._url(url)
    return p.hostname, p.path + ("?" + p.query if p.query else "")


def session():
    return n.Session("11111111", A, monotonic() + 30, n._budget())


@pytest.mark.parametrize(
    "url",
    [
        "http://www.tiktok.com/@u/video/11111111",
        "https://evil.invalid/@u/video/11111111",
        "https://other@www.tiktok.com/@u/video/11111111",
        "https://www.tiktok.com:443/@u/video/11111111",
        "https://www.tiktok.com/@u/photo/11111111",
        "https://www.tiktok.com/@u/video/not-id",
        "https://www.tiktok.com/@u/video/11111111?story_type=1",
        "https://vm.tiktok.com/Short",
    ],
)
def test_invalid_input_before_network(url):
    assert not n.run([url])["success"]


@pytest.mark.parametrize(
    "body,error",
    [
        (b"<html>PRIVATE_HTML</html>", "missing_embed_state"),
        (page(identity="22222222"), "source_identity_mismatch"),
        (page(identity=None), "source_identity_mismatch"),
        (page().replace(b'"id":', b'"id":"11111111", "id":'), "ambiguous_metadata"),
    ],
)
def test_embed_identity_and_schema_fail_closed(body, error):
    with pytest.raises(n.Refusal, match=error):
        n.resolve(body, "11111111")


def test_embed_real_schema_candidates_and_separate_audio():
    video = {
        "playAddr": {"urlList": ["https://untrusted.invalid/file"]},
        "bitrateInfo": [{"PlayAddr": {"UrlList": [MEDIA]}}],
        "downloadAddr": OTHER,
        "audioAddr": {"urlList": ["https://untrusted.invalid/audio"]},
    }
    resolved = n.resolve(page(video=video), "11111111")
    assert resolved.url == MEDIA and resolved.candidates == 3 and resolved.separate_audio
    assert n.resolve(page(video={"urls": [MEDIA]}), "11111111").url == MEDIA
    assert n.publication(A + "?utm_source=share#harmless") == ("11111111", A)


@pytest.mark.parametrize("field", ["playAddr", "bitrateInfo", "downloadAddr", "urls"])
def test_selected_candidate_source_and_unique_count(field):
    value = [{"PlayAddr": [MEDIA, MEDIA]}] if field == "bitrateInfo" else [MEDIA, MEDIA]
    resolved = n.resolve(page(video={field: value}), "11111111")
    assert resolved.source == field and resolved.url == MEDIA and resolved.candidates == 1
    duplicate = n.resolve(page(video={"playAddr": MEDIA, "downloadAddr": MEDIA}), "11111111")
    assert duplicate.source == "playAddr" and duplicate.candidates == 1


def photo_page(location, field, value, *, video=True, identity="11111111"):
    state = json.loads(page(identity=identity).decode().split(">", 1)[1].rsplit("<", 1)[0])
    data = state["source"]["data"]["/embed/v2/11111111"]["videoData"]
    target = data["itemInfos"] if location == "itemInfos" else data
    target[field] = value
    if not video:
        data["itemInfos"].pop("video")
    return ('<script id="__FRONTITY_CONNECT_STATE__">' + json.dumps(state) + "</script>").encode()


@pytest.mark.parametrize("location", ["itemInfos", "videoData"])
@pytest.mark.parametrize("field", ["imagePost", "imagePostInfo"])
@pytest.mark.parametrize("value", [None, {}, []])
def test_empty_photo_placeholders_require_valid_video(location, field, value):
    assert n.resolve(photo_page(location, field, value), "11111111").url == MEDIA
    with pytest.raises(n.Refusal, match="^metadata_schema$"):
        n.resolve(photo_page(location, field, value, video=False), "11111111")


@pytest.mark.parametrize("location", ["itemInfos", "videoData"])
@pytest.mark.parametrize("field", ["imagePost", "imagePostInfo"])
def test_populated_photo_data_still_refused(location, field):
    value = {"images": [{"imageURL": {"urlList": ["https://images.invalid/private"]}}]}
    with pytest.raises(n.Refusal, match="^unsupported_photo$"):
        n.resolve(photo_page(location, field, value), "11111111")


@pytest.mark.parametrize(
    "value",
    [
        False,
        0,
        "",
        "PRIVATE",
        ["PRIVATE"],
        {"images": []},
        {"images": [None]},
        {"unknown": "PRIVATE"},
    ],
)
def test_unknown_photo_structures_fail_closed(value):
    with pytest.raises(n.Refusal, match="^metadata_schema$"):
        n.resolve(photo_page("itemInfos", "imagePost", value), "11111111")


def test_empty_photo_does_not_bypass_identity_or_candidate_validation():
    with pytest.raises(n.Refusal, match="^source_identity_mismatch$"):
        n.resolve(photo_page("videoData", "imagePostInfo", {}, identity="22222222"), "11111111")
    body = photo_page("itemInfos", "imagePost", {}).replace(
        MEDIA.encode(), b"https://evil.invalid/x"
    )
    with pytest.raises(n.Refusal, match="^forbidden_media_destination$"):
        n.resolve(body, "11111111")


def test_conflicting_photo_fields_fail_closed():
    body = photo_page("itemInfos", "imagePost", {"images": [{"imageURL": {"urlList": [MEDIA]}}]})
    body = body.replace(b'"videoData": {', b'"videoData": {"imagePostInfo": {"unknown": true},')
    with pytest.raises(n.Refusal, match="^metadata_schema$"):
        n.resolve(body, "11111111")


def test_empty_photo_inspection_uses_only_existing_metadata_request(monkeypatch):
    wire = network(monkeypatch, {key(EMBED): response(photo_page("videoData", "imagePost", {}))})
    s = session()
    assert n.resolve(s.metadata(), "11111111").url == MEDIA
    assert len(wire.requests) == s.budget["metadata_requests"] == 1
    assert s.budget["media_requests"] == s.budget["acquisitions"] == 0


def test_unknown_photo_stops_after_metadata_without_leaking(monkeypatch, tmp_path):
    body = photo_page("itemInfos", "imagePost", {"unknown": "PRIVATE_PHOTO"})
    wire = network(monkeypatch, {key(EMBED): response(body)})
    result = n._execute([A, B], tmp_path, monotonic() + 10)
    assert result["error"] == "metadata_schema"
    assert len(wire.requests) == result["metadata_requests"] == 1
    assert result["media_requests"] == result["acquisitions"] == 0
    assert len(result["results"]) == 1 and not list(tmp_path.iterdir())
    assert all(private not in json.dumps(result) for private in [A, MEDIA, "PRIVATE_PHOTO"])


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/file",
        "https://localhost/file",
        "https://evil.invalid/file",
        "https://v77.tiktokcdn.com.evil.invalid/file",
        "https://arbitrary.tiktokcdn.com/file",
        "https://v77.extra.tiktokcdn.com/file",
        "https://v77.tiktokcdn.com/file.m3u8",
    ],
)
def test_media_destination_requires_constrained_video_host(url):
    with pytest.raises(n.Refusal):
        n.resolve(page(video={"playAddr": url}), "11111111")


def test_forbidden_redirect_stops_before_connection(monkeypatch):
    wire = network(
        monkeypatch, {key(MEDIA): (302, b"", {"Location": "https://127.0.0.1/internal"})}
    )
    s = session()
    with pytest.raises(n.Refusal), s.open(MEDIA, "media"):
        pytest.fail("Redirect must not be yielded")
    assert len(wire.requests) == s.budget["media_requests"] == 1


def test_pinning_uses_checked_ip_and_original_tls_hostname(monkeypatch):
    calls = []
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))],
    )

    class Raw:
        def settimeout(self, value):
            pass

        def connect(self, address):
            calls.append(address)

        def close(self):
            pass

    raw = Raw()
    monkeypatch.setattr(socket, "socket", lambda *args: raw)
    conn = n._Pinned("v77.tiktokcdn.com", context=ssl.create_default_context(), timeout=1)
    assert conn._context.check_hostname and conn._context.verify_mode == ssl.CERT_REQUIRED
    conn._context = SimpleNamespace(
        wrap_socket=lambda sock, server_hostname: calls.append(server_hostname) or sock
    )
    conn.connect()
    assert calls == [("8.8.8.8", 443), "v77.tiktokcdn.com"]


@pytest.mark.parametrize(
    "ip", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "192.0.2.1", "224.0.0.1"]
)
def test_mixed_dns_answers_fail_before_connect(monkeypatch, ip):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, 443)) for a in ["8.8.8.8", ip]
        ],
    )
    with pytest.raises(n.Refusal, match="unsafe_dns"):
        n._Pinned("v77.tiktokcdn.com", context=ssl.create_default_context()).connect()


def test_cookie_scope_redirect_and_session_isolation(monkeypatch):
    wire = network(
        monkeypatch,
        {
            key(EMBED): response(
                page(),
                fields=[
                    ("Set-Cookie", "hostonly=PRIVATE_COOKIE; Secure; Path=/"),
                    ("Set-Cookie", "domain=PRIVATE_COOKIE; Domain=.tiktok.com; Secure; Path=/"),
                    ("Set-Cookie", "narrow=x; Domain=.tiktok.com; Path=/embed"),
                    ("Set-Cookie", "bad=x; Domain=.com; Path=/"),
                ],
            ),
            key(OTHER): (302, b"", {"Location": MEDIA}),
            key(MEDIA): response(b"fake", "video/mp4"),
        },
    )
    s = session()
    n.resolve(s.metadata(), "11111111")
    with s.open(OTHER, "media"):
        pass
    assert wire.requests[0][3].get("Cookie") is None
    assert wire.requests[1][3].get("Cookie") == "domain=PRIVATE_COOKIE"
    assert wire.requests[2][3].get("Cookie") is None
    assert not list(session().jar)
    assert {c.name for c in s.jar} == {"hostonly", "domain", "narrow"}


@pytest.mark.parametrize(
    "framing,body,error",
    [
        ([], b"abc", "content_length_required"),
        ([("Content-Length", "20")], b"abc", "incomplete_response"),
        ([("Content-Length", "3"), ("Content-Length", "3")], b"abc", "invalid_content_length"),
        ([("Transfer-Encoding", "chunked")], b"3\r\nabc\r\n0\r\n\r\n", "unsupported_http_framing"),
    ],
)
def test_actual_http_parser_rejects_incomplete_or_ambiguous_download(
    monkeypatch, tmp_path, framing, body, error
):
    wire = network(
        monkeypatch, {key(MEDIA): (200, body, [("Content-Type", "video/mp4"), *framing])}
    )
    s = session()
    path = tmp_path / "partial.mp4"
    with pytest.raises(n.Refusal, match=error):
        s.acquire(n.Resolved(MEDIA, 1, False), path)
    assert not path.exists() and len(wire.requests) == s.budget["acquisitions"] == 1
    assert s.budget["media_bytes"] == (len(body) if error == "incomplete_response" else 0)


def test_limits_apply_during_read_and_stop_series_before_b(monkeypatch, tmp_path):
    monkeypatch.setattr(n, "HTML_BYTES", 128)
    network(monkeypatch, {key(EMBED): (200, b"x" * 129, {"Content-Type": "text/html"})})
    result = n._execute([A, B], tmp_path, monotonic() + 10)
    assert not result["success"] and result["error"] == "byte_limit"
    assert result["metadata_bytes"] == 128 and result["metadata_requests"] == 1
    assert result["media_requests"] == 0 and len(result["results"]) == 1
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("total", [False, True])
def test_media_file_and_total_limits_before_write(monkeypatch, tmp_path, total):
    wire = network(monkeypatch, {key(MEDIA): response(b"x" * 65, "video/mp4")})
    s = session()
    if total:
        monkeypatch.setattr(n, "TOTAL_BYTES", 128)
        s.budget["media_bytes"] = 64
    else:
        monkeypatch.setattr(n, "FILE_BYTES", 64)
    with pytest.raises(n.Refusal, match="byte_limit"):
        s.acquire(n.Resolved(MEDIA, 1, False), tmp_path / "partial.mp4")
    assert not list(tmp_path.iterdir()) and len(wire.requests) == 1
    assert s.budget["media_bytes"] == (64 if total else 0)


def test_identity_mismatch_never_opens_media(monkeypatch, tmp_path):
    wire = network(monkeypatch, {key(EMBED): response(page(identity="22222222"))})
    result = n._execute([A, B], tmp_path, monotonic() + 5)
    assert result["error"] == "source_identity_mismatch"
    assert len(wire.requests) == 1 and result["media_requests"] == result["acquisitions"] == 0


@pytest.mark.parametrize("status", [403, 429])
def test_http_errors_do_not_retry_or_fallback(monkeypatch, tmp_path, status):
    wire = network(monkeypatch, {key(EMBED): (status, b"PRIVATE_ERROR", {})})
    result = n._execute([A, B], tmp_path, monotonic() + 10)
    assert result["error"] == f"http_{status}" and len(wire.requests) == 1
    assert "PRIVATE" not in json.dumps(result) and A not in json.dumps(result)


@pytest.mark.parametrize("redirect", [False, True])
def test_cdn_403_diagnostics_actual_requests_cookies_and_counts(monkeypatch, tmp_path, redirect):
    body = page(video={"downloadAddr": OTHER})
    wire = network(
        monkeypatch,
        {
            key(EMBED): response(
                body,
                fields=[("Set-Cookie", "scope=PRIVATE_COOKIE; Domain=.tiktok.com; Secure; Path=/")],
            ),
            key(OTHER): (302, b"", {"Location": MEDIA}) if redirect else (403, b"PRIVATE_HTML", {}),
            key(MEDIA): (403, b"PRIVATE_HTML", {}),
        },
    )
    result = n._execute([A, B], tmp_path, monotonic() + 10)
    entry = result["results"][0]
    expected = [
        {
            "cdn_family": "tiktok.com",
            "has_query": False,
            "cookie_sent": True,
            "status": 302 if redirect else 403,
        }
    ]
    if redirect:
        expected.append(
            {"cdn_family": "tiktokcdn.com", "has_query": True, "cookie_sent": False, "status": 403}
        )
    assert result["error"] == "http_403" and entry["media_http"] == expected
    assert entry["candidate_source"] == "downloadAddr" and entry["candidates"] == 1
    assert entry["counts"] == {
        "metadata_requests": 1,
        "media_requests": 1 + redirect,
        "metadata_bytes": len(body),
        "media_bytes": 0,
        "acquisitions": 1,
    }
    assert result["counts_exact"] and len(wire.requests) == 2 + redirect
    assert len(result["results"]) == 1 and not list(tmp_path.iterdir())
    assert wire.requests[1][3].get("Cookie") == "scope=PRIVATE_COOKIE"
    if redirect:
        assert wire.requests[2][3].get("Cookie") is None
    report = json.dumps(result)
    for private in [A, MEDIA, OTHER, "PRIVATE", "11111111", "v77.", "v16-webapp-prime."]:
        assert private not in report


def test_media_send_failure_does_not_invent_status_or_cookie_measurement(monkeypatch, tmp_path):
    wire = network(monkeypatch, {key(EMBED): response(page())})
    request = n._Pinned.request

    def fail_media(conn, *args, **kwargs):
        if conn.host != "www.tiktok.com":
            raise OSError("PRIVATE_EXCEPTION")
        return request(conn, *args, **kwargs)

    monkeypatch.setattr(n._Pinned, "request", fail_media)
    result = n._execute([A], tmp_path, monotonic() + 10)
    diagnostic = result["results"][0]["media_http"][0]
    assert diagnostic["cookie_sent"] is None and diagnostic["status"] is None
    assert len(wire.requests) == 1 and result["media_requests"] == 1
    assert "PRIVATE" not in json.dumps(result) and result["media_bytes"] == 0


@pytest.mark.parametrize(
    "video,audio,expected",
    [
        ("hevc", "opus", ("hevc", "opus")),
        (None, None, (None, None)),
        ("unknown", "future_codec", (None, None)),
        (23, [], (None, None)),
        ("PRIVATE_TOKEN", MEDIA * 10, (None, None)),
    ],
)
def test_verify_reports_only_bounded_actual_probe_codec_names(
    monkeypatch, tmp_path, video, audio, expected
):
    # Isolate reporting; existing preparation/decode are not changed by this test.
    streams = [{"codec_type": "video", "width": 16, "height": 16}, {"codec_type": "audio"}]
    for stream, value in zip(streams, (video, audio), strict=True):
        if value is not None:
            stream["codec_name"] = value
    monkeypatch.setattr(
        n, "inspect_telegram_video", lambda *args: {"streams": streams, "format": {"duration": "1"}}
    )
    commands = []
    monkeypatch.setattr(n.subprocess, "run", lambda command, **kwargs: commands.append(command))
    monkeypatch.setattr(n, "prepare_telegram_video", lambda path, runner, *, allow_silent: path)
    path = tmp_path / "fixture.mp4"
    path.write_bytes(b"synthetic")
    result = n.verify(path, session(), False, True)
    assert (result["video_codec"], result["audio_codec"]) == expected
    assert len(commands) == 1 and commands[0][0] == "ffmpeg"
    assert "PRIVATE" not in json.dumps(result) and MEDIA not in json.dumps(result)


@pytest.mark.parametrize("audio", [False, True])
def test_native_pipeline_real_file_probe_decode_preparation(monkeypatch, tmp_path, audio):
    source = tmp_path / "fixture.mp4"
    generate(source, audio=audio)
    body = source.read_bytes()
    wire = network(
        monkeypatch, {key(EMBED): response(page()), key(MEDIA): response(body, "video/mp4")}
    )
    workspace = tmp_path / "owned"
    workspace.mkdir()
    result = n._execute([A], workspace, monotonic() + 30)
    if audio:
        assert result["success"], result
        entry = result["results"][0]
        assert (entry["video_codec"], entry["audio_codec"]) == ("h264", "aac")
        assert entry["candidate_source"] == "playAddr"
        assert entry["media_http"] == [
            {"cdn_family": "tiktokcdn.com", "has_query": True, "cookie_sent": False, "status": 200}
        ]
        assert entry["counts"]["media_bytes"] == len(body)
        assert (
            result["results"][0]["decoded"] and result["results"][0]["preparation"] == "passthrough"
        )
    else:
        assert result["error"] == "audio_required"
        path = workspace / "case-1.mp4"
        with pytest.raises(n.Refusal, match="separate_streams_unsupported"):
            n.verify(path, session(), True, False)
        assert n.verify(path, session(), False, False)["audio_codec"] == "absent"
    assert source.read_bytes() == body
    assert wire.requests[1][2] == key(MEDIA)[1]
    for private in [A, MEDIA, "PRIVATE_DESCRIPTION", "PRIVATE_SIGNED", "11111111"]:
        assert private not in json.dumps(result)


@pytest.fixture
def workers(monkeypatch):
    popen, owned = subprocess.Popen, []

    def spawn(*args, **kwargs):
        process = popen(*args, **kwargs)
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


@pytest.mark.parametrize("failure", ["missing_embed_state", "http_403"])
def test_public_worker_failure_cleans_only_owned_workspace(monkeypatch, tmp_path, workers, failure):
    foreign = tmp_path / "foreign"
    foreign.write_text("keep")
    original, workspaces = n._command, []

    def command(workspace):
        workspaces.append(Path(workspace))
        argv = original(workspace)
        routes = (
            "{key(EMBED):response(page()),key(MEDIA):(403,b'PRIVATE_HTML',{})}"
            if failure == "http_403"
            else "{key(EMBED):(200,b'PRIVATE_HTML',{'Content-Type':'text/html'})}"
        )
        bootstrap = (
            "import socket,runpy,sys; "
            "socket.socket.connect=socket.socket.connect_ex=lambda *a,**k: "
            '(_ for _ in ()).throw(AssertionError("No sockets")); '
            "from tests.test_tiktok_native import install,key,EMBED,MEDIA,page,response; "
            f"install({routes}); "
            "from scripts import tiktok_native as patched; "
            'worker=runpy.run_path(sys.argv[1])["_worker_main"]; '
            'worker.__globals__["_Pinned"]=patched._Pinned; worker()'
        )
        return [*argv[:2], bootstrap, *argv[3:]]

    monkeypatch.setattr(n, "_command", command)
    result = n.run([A, B])
    assert result["error"] == failure and result["workspace_cleaned"]
    if failure == "http_403":
        assert result["results"][0]["media_http"][0]["status"] == 403
        assert result["metadata_requests"] == result["media_requests"] == 1
        assert result["media_bytes"] == 0 and result["counts_exact"]
        assert "PRIVATE" not in json.dumps(result)
    assert all(not p.exists() for p in workspaces) and foreign.read_text() == "keep"
    assert workers[0].returncode == 0


def test_two_video_public_worker_probe_decode_cleanup(monkeypatch, tmp_path, workers):
    sound, silent = tmp_path / "sound.mp4", tmp_path / "silent.mp4"
    generate(sound, audio=True)
    generate(silent, audio=False)
    original, workspaces = n._command, []

    def command(workspace):
        workspaces.append(Path(workspace))
        argv = original(workspace)
        bootstrap = (
            "import socket,runpy,sys; from pathlib import Path; "
            "socket.socket.connect=socket.socket.connect_ex=lambda *a,**k: "
            '(_ for _ in ()).throw(AssertionError("No sockets")); '
            "from tests.test_tiktok_native import install,key,EMBED,MEDIA,OTHER,page,response; "
            f"data={{key(EMBED):response(page()),key(MEDIA):response(Path({str(sound)!r}).read_bytes(),'video/mp4'),"
            "('www.tiktok.com','/embed/v2/22222222'):response(page().replace(b'11111111',b'22222222').replace(MEDIA.encode(),OTHER.encode())),"
            f"key(OTHER):response(Path({str(silent)!r}).read_bytes(),'video/mp4')}}; "
            "install(data); "
            "from scripts import tiktok_native as patched; "
            'worker=runpy.run_path(sys.argv[1])["_worker_main"]; '
            'worker.__globals__["_Pinned"]=patched._Pinned; worker()'
        )
        return [*argv[:2], bootstrap, *argv[3:]]

    monkeypatch.setattr(n, "_command", command)
    result = n.run([A, B])
    assert result["success"], result
    assert result["counts_exact"] and result["workspace_cleaned"]
    assert result["metadata_requests"] == result["media_requests"] == result["acquisitions"] == 2
    assert result["media_bytes"] == sound.stat().st_size + silent.stat().st_size
    assert [entry["audio_streams"] for entry in result["results"]] == [1, 0]
    assert all(
        entry["decoded"] and entry["preparation"] == "passthrough" for entry in result["results"]
    )
    assert all(not path.exists() for path in workspaces)
    assert workers[0].returncode == 0


def test_deadline_kills_exited_leader_descendant(monkeypatch, tmp_path, workers):
    pidfile = tmp_path / "pid"
    monkeypatch.setattr(n, "SECONDS", 0.2)
    code = (
        "import subprocess,sys; from pathlib import Path; "
        'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"]); '
        f"Path({str(pidfile)!r}).write_text(str(p.pid))"
    )
    monkeypatch.setattr(n, "_command", lambda workspace: [sys.executable, "-c", code])
    try:
        result = n.run([A])
        assert result["error"] == "deadline" and result["workspace_cleaned"]
        assert workers[0].returncode is not None
        pid = int(pidfile.read_text())
        until = monotonic() + 3
        while monotonic() < until:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
        else:
            pytest.fail("Descendant survived")
    finally:
        if pidfile.exists():
            with suppress(ProcessLookupError):
                os.kill(int(pidfile.read_text()), signal.SIGKILL)


def test_interrupt_terminates_worker_and_cleans_workspace(monkeypatch, workers):
    monkeypatch.setattr(
        n, "_command", lambda workspace: [sys.executable, "-c", "import time; time.sleep(30)"]
    )

    def interrupted(*args):
        raise KeyboardInterrupt

    monkeypatch.setattr(n, "_exchange", interrupted)
    result = n.run([A])
    assert result["error"] == "interrupted" and result["workspace_cleaned"]
    assert not result["counts_exact"] and workers[0].returncode is not None
