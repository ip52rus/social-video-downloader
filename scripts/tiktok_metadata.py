"""Isolated TikTok metadata experiment. Never imported by the application runtime."""

import io
import json
import math
import os
import re
import selectors
import signal
import subprocess
import sys
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from time import monotonic, sleep
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

import yt_dlp
from yt_dlp.extractor.tiktok import TikTokIE, TikTokVMIE
from yt_dlp.networking.common import Response
from yt_dlp.utils import determine_protocol


@dataclass(frozen=True)
class Limits:
    max_urls: int = 3
    max_extractions: int = 4
    max_requests: int = 8
    max_seconds: float = 180
    max_response_bytes: int = 2 * 1024**2
    max_total_bytes: int = 8 * 1024**2

    def __post_init__(self):
        for name, value in asdict(self).items():
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError("Invalid limits")
            if name != "max_seconds" and not isinstance(value, int):
                raise ValueError("Invalid limits")
        if self.max_seconds > 180 or self.max_urls > 3 or self.max_extractions > 4:
            raise ValueError("Experiment bounds cannot be expanded")
        if self.max_requests > 8 or self.max_response_bytes > 2 * 1024**2:
            raise ValueError("Experiment bounds cannot be expanded")
        if self.max_total_bytes > 8 * 1024**2:
            raise ValueError("Experiment bounds cannot be expanded")


class Stop(BaseException):
    """Must escape upstream retry/fallback handlers without leaking upstream text."""


def _url(raw):
    if (
        not isinstance(raw, str)
        or len(raw) > 4096
        or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in raw)
    ):
        raise Stop("invalid_url")
    try:
        p = urlsplit(raw)
        if (
            p.scheme != "https"
            or p.username is not None
            or p.password is not None
            or p.port is not None
            or p.netloc.lower() != p.hostname
        ):
            raise Stop("invalid_url")
    except ValueError:
        raise Stop("invalid_url") from None
    if p.hostname == "www.tiktok.com":
        if p.path == "/login":
            raise Stop("login_required")
        if not re.fullmatch(r"/@[A-Za-z0-9_.-]+/video/[0-9]+/?", p.path):
            raise Stop("forbidden_destination")
        kind = "full"
    elif p.hostname in {"vm.tiktok.com", "vt.tiktok.com"}:
        if not re.fullmatch(r"/[A-Za-z0-9_-]+/?", p.path):
            raise Stop("forbidden_destination")
        kind = "short"
    else:
        raise Stop("forbidden_destination")
    return kind, f"https://{p.hostname}{p.path.rstrip('/')}"


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _opener():
    # No CookieProcessor, environment proxies, browser TLS impersonation or auth handler.
    return build_opener(ProxyHandler({}), _NoRedirect())


class _Transport:
    def __init__(self, limits, deadline, emit):
        self.limits, self.deadline, self.emit = limits, deadline, emit
        self.requests = self.received = self.extractions = 0
        self.expected = None
        self.opener = _opener()

    def progress(self):
        return {
            "requests": self.requests,
            "metadata_bytes": self.received,
            "extractions": self.extractions,
        }

    def check(self):
        if monotonic() >= self.deadline:
            raise Stop("deadline")

    def open(self, request):
        self.check()
        kind, url = _url(request.url)
        method = request.method
        if url != self.expected or method != ("HEAD" if kind == "short" else "GET"):
            raise Stop("unexpected_request")
        if request.data is not None or any(
            name.lower() in {"cookie", "authorization", "proxy-authorization"}
            for name in request.headers
        ):
            raise Stop("credentials_forbidden")
        if request.extensions.get("impersonate"):
            raise Stop("impersonation_forbidden")
        seen = set()
        for _ in range(3):  # At most two redirects, checked BEFORE opening their targets.
            self.check()
            if url in seen:
                raise Stop("redirect_loop")
            seen.add(url)
            if self.requests >= self.limits.max_requests:
                raise Stop("request_limit")
            self.requests += 1
            self.emit(self.progress())
            try:
                response = self.opener.open(
                    Request(
                        url,
                        method=method,
                        headers={
                            "User-Agent": "social-video-downloader-metadata-check/1",
                            "Accept-Encoding": "identity",
                        },
                    ),
                    timeout=min(10, self.deadline - monotonic()),
                )
            except HTTPError as error:
                response = error
            except Exception:
                raise Stop("network_error") from None
            with response:
                self.check()
                if response.geturl() != url:
                    raise Stop("unexpected_redirect")
                if response.headers.get_all("Set-Cookie"):
                    raise Stop("cookies_forbidden")
                if response.code in {301, 302, 303, 307, 308}:
                    target_kind, target = _url(urljoin(url, response.headers.get("Location", "")))
                    if kind == "full" and (
                        target_kind != "full" or target.rsplit("/", 1)[-1] != url.rsplit("/", 1)[-1]
                    ):
                        raise Stop("identity_changed")
                    kind, url = target_kind, target
                    continue
                if response.code != 200:
                    raise Stop(
                        f"http_{response.code}" if response.code in {403, 429} else "http_error"
                    )
                if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                    raise Stop("encoded_response")
                body = bytearray()
                if method == "GET":
                    if response.headers.get_content_type() != "text/html":
                        raise Stop("non_html_response")
                    while True:
                        self.check()
                        remaining = min(
                            self.limits.max_response_bytes - len(body),
                            self.limits.max_total_bytes - self.received,
                        )
                        if remaining <= 0:
                            raise Stop("response_limit")
                        chunk = response.read(min(65536, remaining))
                        self.received += len(chunk)
                        self.emit(self.progress())
                        self.check()
                        if len(chunk) > remaining:
                            raise Stop("response_limit")
                        if not chunk:
                            break
                        body.extend(chunk)
                return Response(io.BytesIO(body), url, dict(response.headers), status=200)
        raise Stop("redirect_limit")


class _Quiet:
    def debug(self, *args):
        pass

    warning = error = debug


class _MetadataIE(TikTokIE):
    @classmethod
    def ie_key(cls):
        return TikTokIE.ie_key()

    def _generate_blockbuster_headers(self, **kwargs):
        return {}

    def _download_webpage_handle(self, *args, **kwargs):
        kwargs["impersonate"] = False
        return super()._download_webpage_handle(*args, **kwargs)

    def _solve_challenge_and_set_cookies(self, *args):
        raise Stop("challenge_forbidden")

    def _set_cookie(self, *args, **kwargs):
        raise Stop("cookies_forbidden")

    def raise_login_required(self, *args, **kwargs):
        raise Stop("login_required")

    def _call_api(self, *args, **kwargs):
        raise Stop("mobile_api_forbidden")

    def _parse_aweme_video_web(self, aweme_detail, webpage_url, video_id, extract_flat=False):
        # Upstream replaces itemStruct.id with video_id in the mapped result.
        source_id = aweme_detail.get("id")
        if not isinstance(source_id, str) or not re.fullmatch(r"[0-9]+", source_id):
            raise Stop("invalid_identity")
        kind, canonical = _url(webpage_url)
        if (
            kind != "full"
            or canonical != self._downloader.transport.expected
            or source_id != video_id
            or source_id != canonical.rsplit("/", 1)[-1]
        ):
            raise Stop("identity_changed")
        return super()._parse_aweme_video_web(
            aweme_detail,
            webpage_url,
            video_id,
            extract_flat=extract_flat,
        )


class _YDL(yt_dlp.YoutubeDL):
    def __init__(self, transport):
        self.transport = transport
        super().__init__(
            {
                "quiet": True,
                "logger": _Quiet(),
                "cachedir": False,
                "retries": 0,
                "extractor_retries": 0,
                "fragment_retries": 0,
                "check_formats": False,
                "writesubtitles": False,
                "writeautomaticsub": False,
                "getcomments": False,
                "geo_bypass": False,
            },
            auto_init=False,
        )
        self.add_info_extractor(_MetadataIE(self))
        self.add_info_extractor(TikTokVMIE(self))

    def urlopen(self, request):
        return self.transport.open(request)

    def process_ie_result(self, *args, **kwargs):
        raise Stop("processing_forbidden")

    def download(self, *args, **kwargs):
        raise Stop("acquisition_forbidden")


def _codec(value, *, audio=False):
    if value is None:
        return "unknown"
    if not isinstance(value, str):
        return "invalid"
    v = value.lower()
    if v == "none":
        return "absent"
    prefixes = (
        ("aac", "mp4a", "mp3", "opus", "vorbis")
        if audio
        else ("h264", "avc1", "h265", "hev1", "hvc1", "vp8", "vp9", "av01", "av1", "bytevc2")
    )
    return next((prefix for prefix in prefixes if v.startswith(prefix)), "other")


def _formats(raw):
    formats = raw.get("formats")
    if not isinstance(formats, list) or len(formats) > 128:
        raise Stop("invalid_formats")
    result = []
    for index, f in enumerate(formats, 1):
        if not isinstance(f, dict):
            raise Stop("invalid_formats")
        try:
            protocol = determine_protocol(f)
        except Exception:
            protocol = None
        result.append(
            {
                "index": index,
                "protocol": protocol
                if protocol in {"http", "https", "m3u8_native", "http_dash_segments"}
                else "unknown",
                "container": f.get("ext")
                if isinstance(f.get("ext"), str) and f["ext"] in {"mp4", "m4a", "mp3", "webm"}
                else "unknown",
                "video_codec": _codec(f.get("vcodec")),
                "audio_metadata": _codec(f.get("acodec"), audio=True),
                "marked_for_probe": bool(f.get("__needs_testing")),
            }
        )
    return result


def _execute(urls, limits, deadline, emit):
    transport = _Transport(limits, deadline, emit)
    results, identities = [], {}
    error = None
    with _YDL(transport) as ydl:
        for index, raw_url in enumerate(urls, 1):
            entry = {"case": index, "url_category": "invalid", "success": False}
            results.append(entry)
            try:
                kind, url = _url(raw_url)
                entry["url_category"] = kind
                for _ in range(2):
                    transport.check()
                    if transport.extractions >= limits.max_extractions:
                        raise Stop("extraction_limit")
                    transport.extractions += 1
                    transport.expected = url
                    emit(transport.progress())
                    info = ydl.extract_info(
                        url,
                        download=False,
                        process=False,
                        ie_key="TikTok" if kind == "full" else "TikTokVM",
                    )
                    if kind == "full":
                        break
                    kind, url = _url(info["url"])
                    if kind != "full":
                        raise Stop("unresolved_short_url")
                if info.get("_type", "video") != "video" or "entries" in info:
                    raise Stop("unexpected_result")
                if info.get("id") != url.rsplit("/", 1)[-1]:
                    raise Stop("identity_changed")
                formats = _formats(info)
                identity = identities.setdefault(info["id"], f"result-{len(identities) + 1}")
                transport.check()
                entry.update(
                    success=True,
                    result_type="video",
                    result_id=identity,
                    format_count=len(formats),
                    formats=formats,
                )
            except Stop as exc:
                error = str(exc)
            except Exception:
                error = "extraction_error"
            if error:
                entry.update(success=False, error=error)
                break  # No retries and no later cases after any failure.
    return {
        "success": error is None,
        "results": results,
        "error": error,
        **transport.progress(),
        "counts_exact": True,
    }


def _worker_main():
    request = json.loads(sys.stdin.read(16385))
    limits = Limits(**request["limits"])

    def emit(progress):
        print(json.dumps({"progress": progress}), flush=True)

    result = _execute(request["urls"], limits, request["deadline"], emit)
    print(json.dumps({"result": result}), flush=True)


def _command():
    return [
        sys.executable,
        "-c",
        "import runpy,sys; runpy.run_path(sys.argv[1])['_worker_main']()",
        str(Path(__file__).resolve()),
    ]


def _exchange(process, payload, deadline, output):
    """Exchange pipes without reaping the leader, keeping its group ID reserved."""
    pending = memoryview(payload.encode())
    with selectors.DefaultSelector() as selector:
        for stream, event in (
            (process.stdin, selectors.EVENT_WRITE),
            (process.stdout, selectors.EVENT_READ),
        ):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, event)
        while selector.get_map():
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired("metadata-worker", 0)
            for key, _ in selector.select(remaining):
                if key.fileobj is process.stdin:
                    try:
                        pending = pending[os.write(key.fd, pending) :]
                    except BrokenPipeError:
                        pending = pending[len(pending) :]
                    if not pending:
                        selector.unregister(key.fileobj)
                        process.stdin.close()
                        process.stdin = None
                else:
                    chunk = os.read(key.fd, 65536)
                    if chunk:
                        output.extend(chunk)
                    else:
                        selector.unregister(key.fileobj)
    # WNOWAIT observes exit without freeing/reusing the leader PID/PGID.
    while os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOWAIT | os.WNOHANG) is None:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired("metadata-worker", 0)
        sleep(min(0.01, remaining))


def run(urls, limits=None):
    """The supported entry point: own one worker/process group through reap."""
    started = monotonic()
    limits = limits or Limits()
    result = {
        "success": False,
        "error": "invalid_input",
        "results": [],
        "requests": 0,
        "metadata_bytes": 0,
        "extractions": 0,
        "counts_exact": True,
        "seconds": 0,
    }
    if not isinstance(urls, list) or not 0 < len(urls) <= limits.max_urls:
        return result
    try:
        for url in urls:
            _url(url)
    except Stop as exc:
        result["error"] = str(exc)
        return result
    if os.name != "posix" or not all(hasattr(os, name) for name in ("waitid", "WNOWAIT")):
        result["error"] = "posix_required"
        return result
    deadline = started + limits.max_seconds
    process, output = None, bytearray()
    result["error"] = "worker_start_error"
    try:
        # Do not allow a terminal interrupt between spawning and taking ownership.
        previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
        try:
            process = subprocess.Popen(
                _command(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                start_new_session=True,
            )
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)
        result["error"] = "worker_error"
        _exchange(
            process,
            json.dumps({"urls": urls, "limits": asdict(limits), "deadline": deadline}),
            deadline,
            output,
        )
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
        result.update(
            error="deadline" if isinstance(exc, subprocess.TimeoutExpired) else "interrupted",
            counts_exact=False,
        )
    except Exception:
        result["counts_exact"] = False
    finally:
        # Repeated terminal interrupts cannot abandon the owned worker during reap.
        previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
        try:
            if process is not None:
                cleanup_deadline = monotonic() + 5
                # Never poll/wait/reap before signaling: the unreaped leader anchors PGID.
                kill_failed, group_signaled = False, False
                for _ in range(2):
                    try:
                        with suppress(ProcessLookupError):
                            os.killpg(process.pid, signal.SIGKILL)
                        group_signaled = True
                        break
                    except OSError:
                        kill_failed = True
                try:
                    tail, _ = process.communicate(timeout=max(0, cleanup_deadline - monotonic()))
                    output.extend(tail.encode())
                except (Exception, KeyboardInterrupt):
                    result.update(error="cleanup_failed", counts_exact=False)
                    # Pipe cleanup failure must not prevent direct-worker reap.
                    with suppress(Exception, KeyboardInterrupt):
                        process.wait(timeout=max(0, cleanup_deadline - monotonic()))
                    for stream in (process.stdin, process.stdout):
                        if stream is not None:
                            with suppress(OSError):
                                stream.close()
                if kill_failed and not group_signaled and process.returncode is not None:
                    # Darwin may report EPERM for a zombie-only group. Once reaped,
                    # only probe absence: never terminate a potentially reused PGID.
                    try:
                        os.killpg(process.pid, 0)
                    except ProcessLookupError:
                        kill_failed = False
                    except OSError:
                        pass
                if kill_failed:
                    result.update(error="cleanup_failed", counts_exact=False)
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)
    completed = False
    try:
        for line in output.decode(errors="replace").splitlines():
            event = json.loads(line)
            if "progress" in event:
                result.update(event["progress"])
            if "result" in event and result["counts_exact"] and process and process.returncode == 0:
                result = event["result"]
                completed = True
    except (ValueError, TypeError):
        result.update(success=False, error="worker_error")
    if not completed:
        result["counts_exact"] = False
    result["seconds"] = round(monotonic() - started, 3)
    return result


def main():
    def interrupted(*args):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        raw = sys.stdin.read(16385)
        urls = json.loads(raw) if len(raw) <= 16384 else None
        result = run(urls)
    except (Exception, KeyboardInterrupt):
        result = {"success": False, "error": "harness_error"}
    print(json.dumps(result))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
