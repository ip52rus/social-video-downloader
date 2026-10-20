"""Synthetic short redirects, real HTTP parser and owned workers; no external I/O."""

import asyncio
import json
import signal
import socket
import ssl
from pathlib import Path
from threading import Event, Thread
from time import monotonic

import pytest

from social_video_downloader import telegram_tiktok as t
from social_video_downloader.domain.errors import DownloadTimeoutError
from social_video_downloader.domain.urls import detect_platform
from social_video_downloader.infrastructure import tiktok_native as n
from social_video_downloader.infrastructure import tiktok_short_links as short
from social_video_downloader.providers.tiktok import TikTokProvider
from tests.integration.test_video_preparation import generate
from tests.test_telegram_carousel import response as telegram_response
from tests.test_tiktok_integration import FixtureProvider, message
from tests.test_tiktok_native import MEDIA, A, B, key, network, response
from tests.test_tiktok_native import offline as offline
from tests.test_tiktok_native import workers as workers
from tests.test_tiktok_public_page import html

VM = "https://vm.tiktok.com/Synthetic01/"
VT = "https://vt.tiktok.com/Synthetic02/"


@pytest.mark.parametrize("url", [VM, VT, VM.rstrip("/"), A + "?is_from_webapp=1&sender_device=pc"])
def test_reference_admission_and_planning_are_local(monkeypatch, url):
    monkeypatch.setattr(n, "_Pinned", lambda *a, **k: pytest.fail("No HTTP before admission"))
    provider = TikTokProvider()
    assert provider.can_handle(url) and detect_platform(url) == provider.platform
    assert provider.extract_metadata(url).source_url == short.reference(url)
    assert provider.get_supported_modes(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://vm.tiktok.com/Synthetic01/",
        "https://vm.tiktok.com.evil.invalid/Synthetic01/",
        "https://vm.tiktok.com./Synthetic01/",
        "https://www.vm.tiktok.com/Synthetic01/",
        "https://vm.tiktok.com:443/Synthetic01/",
        "https://user@vm.tiktok.com/Synthetic01/",
        "https://vm.tiktok.com/",
        VM + "extra/",
        VM + "?tracking=1",
        VM + "?",
        VM + "#fragment",
        VM + "#",
        VM.replace("Synthetic01", "%53ynthetic01"),
        VM.replace("Synthetic01", "invalid_token"),
        VM.replace("Synthetic01", "a" * 65),
        VM + "\r\nInjected: value",
        VM.replace("/Synthetic01", "/../Synthetic01"),
    ],
)
def test_invalid_short_input_never_connects(monkeypatch, url):
    monkeypatch.setattr(n, "_Pinned", lambda *a, **k: pytest.fail("Unexpected HTTP"))
    assert not TikTokProvider().can_handle(url)


@pytest.mark.parametrize("url,chain", [(VM, False), (VT, False), (VM, True)])
def test_redirects_stop_before_canonical_page_get(monkeypatch, url, chain):
    routes = {key(url): (302, b"UNREAD_HTML", {"Location": VT if chain else A})}
    if chain:
        routes[key(VT)] = (307, b"UNREAD_HTML", {"Location": A + "?sender_device=pc"})
    wire = network(monkeypatch, routes)
    session = short.ShortLinkSession(monotonic() + 30, n._budget())
    assert session.resolve(url) == A
    assert session.budget["metadata_requests"] == len(wire.requests) == (2 if chain else 1)
    assert session.budget["metadata_bytes"] == session.budget["media_requests"] == 0
    assert all(request[0] in short.SHORT_HOSTS for request in wire.requests)
    for _, method, _, headers in wire.requests:
        assert method == "GET" and headers["User-Agent"] == n.UA
        assert headers["Accept-Encoding"] == "identity" and headers["Cookie"] is None


@pytest.mark.parametrize(
    "target",
    [
        "https://external.invalid/video/11111111",
        "https://127.0.0.1/video/11111111",
        "https://169.254.169.254/metadata",
        "https://[::1]/video/11111111",
        "http://www.tiktok.com/@fixture/video/11111111",
        A.replace("/video/", "/photo/"),
        "https://www.tiktok.com/login",
        MEDIA,
        A + "?img_index=1",
        VT + "?url=https://external.invalid/",
    ],
)
def test_bad_redirect_is_refused_before_destination_connect(monkeypatch, target):
    wire = network(monkeypatch, {key(VM): (302, b"", {"Location": target})})
    session = short.ShortLinkSession(monotonic() + 30, n._budget())
    with pytest.raises(n.Refusal):
        session.resolve(VM)
    assert len(wire.requests) == session.budget["metadata_requests"] == 1


@pytest.mark.parametrize("kind", ["self", "cycle", "hops", "ambiguous", "body", "http_429"])
def test_short_failures_have_no_retry_or_body_read(monkeypatch, kind):
    third = VM.replace("Synthetic01", "Synthetic03")
    routes = {key(VM): (302, b"PRIVATE_HTML", {"Location": VT})}
    if kind == "self":
        routes[key(VM)] = (302, b"", {"Location": VM})
    elif kind == "cycle":
        routes[key(VT)] = (302, b"", {"Location": VM})
    elif kind == "hops":
        routes[key(VT)] = (302, b"", {"Location": third})
        routes[key(third)] = (302, b"", {"Location": A})
    elif kind == "ambiguous":
        routes[key(VM)] = (302, b"", [("Location", A), ("Location", B)])
    elif kind == "body":
        routes[key(VM)] = response(b"PRIVATE_HTML" * 100000)
    else:
        routes[key(VM)] = (429, b"PRIVATE_HTML", {})
    wire = network(monkeypatch, routes)
    session = short.ShortLinkSession(monotonic() + 30, n._budget())
    with pytest.raises(n.Refusal) as error:
        session.resolve(VM)
    assert len(wire.requests) <= 3 and session.budget["metadata_bytes"] == 0
    assert "PRIVATE" not in str(error.value) and "Synthetic" not in str(error.value)


def test_short_deadline_and_shared_request_budget_prevent_connect(monkeypatch):
    monkeypatch.setattr(n, "_Pinned", lambda *a, **k: pytest.fail("Unexpected HTTP"))
    session = short.ShortLinkSession(monotonic() - 1, n._budget())
    with pytest.raises(n.Refusal, match="deadline"):
        session.resolve(VM)
    budget = n._budget()
    budget["metadata_requests"] = 6
    session = short.ShortLinkSession(monotonic() + 30, budget)
    with pytest.raises(n.Refusal, match="request_limit"):
        session.resolve(VM)


def test_short_mode_cannot_enable_embed_or_cli_resolution(monkeypatch, tmp_path):
    monkeypatch.setattr(n, "_Pinned", lambda *a, **k: pytest.fail("Unexpected HTTP"))
    monkeypatch.setattr(n.subprocess, "Popen", lambda *a, **k: pytest.fail("Unexpected worker"))
    assert n.run([VM], public_page=True)["error"] == "invalid_input"
    assert n.run([VM], short_links=True, output_dir=tmp_path)["error"] == "invalid_input"
    result = n._execute([VM], tmp_path, monotonic() + 10, short_links=True)
    assert result["error"] == "invalid_input" and result["metadata_requests"] == 0


@pytest.mark.parametrize("full", [False, True])
def test_short_cookie_scope_counters_and_cleanup_without_full_link_overhead(
    monkeypatch, tmp_path, full
):
    sessions, original = [], short.ShortLinkSession

    def tracked(*args):
        session = original(*args)
        sessions.append(session)
        return session

    monkeypatch.setattr(short, "ShortLinkSession", tracked)
    wire = network(
        monkeypatch,
        {
            key(VM): (
                302,
                b"UNREAD_HTML",
                [
                    ("Location", A),
                    ("Set-Cookie", "anon=PRIVATE_COOKIE; Domain=.tiktok.com; Path=/; Secure"),
                    ("Set-Cookie", "bad=PRIVATE_COOKIE; Domain=.com; Path=/; Secure"),
                ],
            ),
            key(A): response(html()),
            key(MEDIA): (403, b"PRIVATE_HTML", {}),
        },
    )
    result = n._execute(
        [A if full else VM], tmp_path, monotonic() + 30, public_page=True, short_links=True
    )
    assert result["error"] == "http_403" and result["counts_exact"]
    assert result["metadata_requests"] == (1 if full else 2)
    assert result["metadata_bytes"] == len(html())
    assert result["media_requests"] == result["acquisitions"] == 1
    assert result["media_bytes"] == 0 and not list(tmp_path.iterdir())
    assert len(wire.requests) == (2 if full else 3)
    assert wire.requests[-2][3].get("Cookie") == (None if full else "anon=PRIVATE_COOKIE")
    assert wire.requests[-1][3].get("Cookie") is None
    assert len(sessions) == int(not full) and all(not list(s.jar) for s in sessions)
    assert not any(secret in json.dumps(result) for secret in (VM, MEDIA, "PRIVATE", "11111111"))


def test_resolved_publication_still_requires_matching_source_identity(monkeypatch, tmp_path):
    wire = network(
        monkeypatch, {key(VM): (302, b"", {"Location": A}), key(A): response(html("22222222"))}
    )
    result = n._execute([VM], tmp_path, monotonic() + 10, public_page=True, short_links=True)
    assert result["error"] == "source_identity_mismatch"
    assert result["metadata_requests"] == len(wire.requests) == 2
    assert result["media_requests"] == result["acquisitions"] == 0


@pytest.mark.parametrize("host", ["vm.tiktok.com", "vt.tiktok.com"])
def test_short_hosts_use_existing_pinned_tls_and_reject_unsafe_dns(monkeypatch, host):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443))],
    )
    conn = n._Pinned(host, context=ssl.create_default_context())
    assert conn._context.check_hostname and conn._context.verify_mode == ssl.CERT_REQUIRED
    with pytest.raises(n.Refusal, match="unsafe_dns"):
        conn.connect()


def synthetic_short_worker(monkeypatch, fixture, *, entered=None):
    original = n._command
    private = []

    def command(workspace):
        private.append(Path(workspace))
        argv = original(workspace)
        if entered is not None:
            bootstrap = (
                "from pathlib import Path; import time; "
                "from social_video_downloader.infrastructure import tiktok_native as n; "
                "n._Pinned.connect=lambda conn: "
                f"(Path({str(entered)!r}).write_text('entered'),time.sleep(60))[1]; " + argv[2]
            )
            return [*argv[:2], bootstrap, *argv[3:]]
        bootstrap = (
            "import socket,sys,time; from pathlib import Path; "
            "socket.socket.connect=socket.socket.connect_ex=lambda *a,**k: "
            "(_ for _ in ()).throw(AssertionError('No sockets')); "
            "from tests.test_tiktok_native import install,key,A,MEDIA,response; "
            "from tests.test_tiktok_public_page import html; "
            "from tests.test_tiktok_short_links import VM,VT; "
            "wire=install({key(VM):(302,b'',{'Location':A}),key(VT):(302,b'',{'Location':A}),"
            "key(A):response(html()),key(MEDIA):response("
            f"Path({str(fixture)!r}).read_bytes(),'video/mp4')}}); "
        )
        bootstrap += argv[2] + "; assert len(wire.requests)==3"
        return [*argv[:2], bootstrap, *argv[3:]]

    monkeypatch.setattr(n, "_command", command)
    return private


@pytest.mark.parametrize("url", [VM, VT])
@pytest.mark.asyncio
async def test_short_handler_real_worker_to_video_and_cleanup(monkeypatch, tmp_path, workers, url):
    fixture = tmp_path / "source.mp4"
    generate(fixture, audio=True)
    private = synthetic_short_worker(monkeypatch, fixture)
    reports, original = [], n.run

    def record(*a, **k):
        assert k["public_page"] and k["short_links"]
        result = original(*a, **k)
        reports.append(result)
        return result

    monkeypatch.setattr(n, "run", record)
    msg = message()
    msg.text = url
    paths = []

    async def upload(video, **kwargs):
        path = Path(video.path)
        paths.append(path)
        assert path.read_bytes() == fixture.read_bytes()
        assert all(p.returncode == 0 for p in workers)
        await asyncio.sleep(0)
        assert path.is_file()
        return telegram_response(1)

    msg.answer_video.side_effect = upload
    handler = t.TelegramTikTokHandler()
    await handler.handle(msg, url)
    msg.answer_video.assert_awaited_once()
    assert msg.answer.await_count == 1
    assert len(reports) == 1 and reports[0]["success"]
    report = reports[0]
    assert (
        report["metadata_requests"] == 2 and report["media_requests"] == report["acquisitions"] == 1
    )
    assert report["counts_exact"] and report["workspace_cleaned"]
    assert report["results"][0]["source_identity"] and report["results"][0]["http_complete"]
    assert all(not p.exists() for p in private) and all(not p.parent.exists() for p in paths)
    assert not handler._active_users and not handler._blocked
    assert not any(
        secret in json.dumps(report) + repr(msg.answer.await_args_list)
        for secret in (VM, VT, "Synthetic01", A, MEDIA, "11111111", "PRIVATE")
    )


@pytest.mark.parametrize("cancel", [False, True])
def test_stalled_short_resolution_is_owned_until_reaped(monkeypatch, tmp_path, workers, cancel):
    entered, caller = tmp_path / "stage", tmp_path / "caller"
    caller.mkdir()
    synthetic_short_worker(monkeypatch, None, entered=entered)
    monkeypatch.setattr(n, "SECONDS", 3 if not cancel else 5)
    cancelled = Event()
    stop = Event()

    def cancel_after_resolution_started():
        while not entered.exists():
            if stop.wait(0.01):
                return
        cancelled.set()

    if cancel:
        thread = Thread(target=cancel_after_resolution_started)
        thread.start()
    try:
        report = n.run(
            [VM], output_dir=caller, public_page=True, short_links=True, cancelled=cancelled
        )
    finally:
        stop.set()
        if cancel:
            thread.join(timeout=1)
            assert not thread.is_alive()
    assert entered.is_file()  # Prove the test reached short HTTP resolution, not just startup.
    assert report["error"] == ("cancelled" if cancel else "deadline")
    assert report["workspace_cleaned"] and not report["counts_exact"]
    assert len(workers) == 1 and workers[0].returncode == -signal.SIGKILL
    assert not list(caller.iterdir())


@pytest.mark.asyncio
async def test_short_network_starts_after_slot_and_cancel_isolated_from_other_user(monkeypatch):
    entered, released, saw_cancel = Event(), Event(), Event()
    second_upload, finish_upload = asyncio.Event(), asyncio.Event()
    provider = FixtureProvider()
    original = provider.download_prepared
    handler = t.TelegramTikTokHandler(provider=provider)

    def download(url, workspace, options=None, *, cancelled=None):
        # This stands at the short-resolution worker boundary, after admission.
        assert handler._active_users and Path(workspace).is_dir()
        if url == VM:
            assert 7 in handler._active_users
            entered.set()
            assert cancelled.wait(5)
            saw_cancel.set()
            assert released.wait(5)
            raise DownloadTimeoutError("PRIVATE_SHORT_TOKEN")
        assert 8 in handler._active_users and not cancelled.is_set()
        return original(url, workspace, options, cancelled=cancelled)

    provider.download_prepared = download
    first, second = message(7), message(8)

    async def upload(video, **kwargs):
        second_upload.set()
        await finish_upload.wait()
        assert Path(video.path).is_file()
        return telegram_response(1)

    second.answer_video.side_effect = upload
    tasks = [
        asyncio.create_task(handler.handle(first, VM)),
        asyncio.create_task(handler.handle(second, VT)),
    ]
    try:
        await asyncio.wait_for(second_upload.wait(), 3)
        assert entered.is_set() and handler._active_users == {7, 8}
        for user in (7, 9):
            blocked = message(user)
            await handler.handle(blocked, VM)
            blocked.answer_video.assert_not_awaited()
            assert blocked.answer.call_args.args == ("Бот занят, попробуйте позже.",)
        tasks[0].cancel()
        async with asyncio.timeout(3):
            while not saw_cancel.is_set():
                await asyncio.sleep(0.005)
        tasks[0].cancel()
        await asyncio.sleep(0)
        assert not tasks[0].done() and handler._active_users == {7, 8}
        released.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(tasks[0], 3)
        assert handler._active_users == {8} and not tasks[1].done()
        finish_upload.set()
        await asyncio.wait_for(tasks[1], 3)
        assert second.answer.await_count == 1
    finally:
        released.set()
        finish_upload.set()
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    assert not handler._active_users and not handler._blocked
    assert all(not path.parent.exists() for path in provider.paths)


@pytest.mark.asyncio
async def test_two_users_resolve_in_real_independent_workers(monkeypatch, tmp_path, workers):
    fixture = tmp_path / "source.mp4"
    generate(fixture, audio=False)
    private = synthetic_short_worker(monkeypatch, fixture)
    handler = t.TelegramTikTokHandler()
    ready = [asyncio.Event(), asyncio.Event()]
    release = asyncio.Event()
    paths = []

    def upload(index):
        async def send(video, **kwargs):
            paths.append(Path(video.path))
            ready[index].set()
            await release.wait()
            assert Path(video.path).read_bytes() == fixture.read_bytes()
            return telegram_response(1)

        return send

    messages = [message(7), message(8)]
    for index, msg in enumerate(messages):
        msg.answer_video.side_effect = upload(index)
    tasks = [
        asyncio.create_task(handler.handle(msg, url))
        for msg, url in zip(messages, (VM, VT), strict=True)
    ]
    try:
        await asyncio.wait_for(asyncio.gather(*(event.wait() for event in ready)), 10)
        assert handler._active_users == {7, 8}
        assert len({p.parent for p in paths}) == 2 and len(workers) == 2
    finally:
        release.set()
        await asyncio.gather(*tasks)
    assert all(msg.answer.await_count == 1 for msg in messages)
    assert all(p.returncode == 0 for p in workers)
    assert all(not p.exists() for p in private) and all(not p.parent.exists() for p in paths)
    assert not handler._active_users
