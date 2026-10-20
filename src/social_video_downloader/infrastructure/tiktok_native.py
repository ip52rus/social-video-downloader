"""Shared experimental embed-based TikTok engine, independent of Telegram transport.

Embed/address approach and HTTP UA adapted from tt-dlp (MIT); see
licenses/tt-dlp-MIT.txt and docs/PHASE6C_TIKTOK_NATIVE.md. No live use without approval.
"""

import http.client
import ipaddress
import json
import os
import re
import resource
import selectors
import shutil
import signal
import socket
import ssl
import subprocess
import sys
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from html.parser import HTMLParser
from http.cookiejar import CookieJar, DefaultCookiePolicy
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from urllib.parse import parse_qsl, urljoin, urlsplit
from urllib.request import Request

from social_video_downloader.infrastructure.telegram_media import (
    inspect_telegram_video,
    prepare_telegram_video,
    telegram_video_upload_parameters,
)

SECONDS = 180
FILE_BYTES = 25 * 1024**2
TOTAL_BYTES = 50 * 1024**2
HTML_BYTES = 2 * 1024**2
WORKSPACE_BYTES = 128 * 1024**2
ROOTS = {"tiktok.com", "tiktokcdn.com", "tiktokcdn-us.com", "tiktokcdn-eu.com"}
VIDEO_HOST = re.compile(
    r"(?:v[0-9]{1,3}[a-z]?(?:-[a-z0-9]{1,16}){0,6}\."
    r"(?:tiktokcdn\.com|tiktokcdn-us\.com|tiktokcdn-eu\.com)"
    r"|v[0-9]{1,3}-web(?:app)?(?:-prime)?\.tiktok\.com)"
)
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
)


class Refusal(Exception):
    """Only fixed technical categories cross the reporting boundary."""


def _url(value):
    if (
        not isinstance(value, str)
        or not 0 < len(value) <= 8192
        or any(not 33 <= ord(c) <= 126 for c in value)
        or "\\" in value
        or re.search(r"%(?![0-9a-fA-F]{2})", value)
    ):
        raise Refusal("invalid_url")
    p = urlsplit(value)
    if p.scheme != "https" or not p.hostname or p.netloc.lower() != p.hostname:
        raise Refusal("invalid_url")
    return p


def publication(value):
    p = _url(value)
    match = re.fullmatch(r"/@[A-Za-z0-9_.]{1,64}/video/([0-9]{5,30})/?", p.path)
    if p.hostname != "www.tiktok.com" or not match:
        raise Refusal("full_video_url_required")
    if any(
        key.lower() in {"story_type", "aweme_type", "img_index", "item_id"}
        for key, _ in parse_qsl(p.query, max_num_fields=64)
    ):
        raise Refusal("unsupported_selector")
    return match[1], f"https://www.tiktok.com{p.path.rstrip('/')}"


def media_url(value):
    p = _url(value)
    if (
        not VIDEO_HOST.fullmatch(p.hostname)
        or not p.path.startswith("/")
        or p.fragment
        or p.path.lower().endswith((".m3u8", ".mpd"))
    ):
        raise Refusal("forbidden_media_destination")
    return value  # Signed path/query are never reconstructed or decoded.


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Refusal("ambiguous_metadata")
        result[key] = value
    return result


class _State(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = self.done = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if any(k == "id" and v == "__FRONTITY_CONNECT_STATE__" for k, v in attrs):
            if tag != "script" or self.done or self.active or len(dict(attrs)) != len(attrs):
                raise Refusal("ambiguous_metadata")
            self.active = True

    def handle_endtag(self, tag):
        if tag == "script" and self.active:
            self.active, self.done = False, True

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)


@dataclass(frozen=True, repr=False)
class Resolved:
    url: str
    candidates: int
    separate_audio: bool
    source: str | None = None


def resolve(body, post_id):
    try:
        parser = _State()
        parser.feed(body.decode("utf-8"))
        parser.close()
        if not parser.done or parser.active:
            raise Refusal("missing_embed_state")
        state = json.loads("".join(parser.parts), object_pairs_hook=_unique)
        sources = state["source"]["data"]
        path = f"/embed/v2/{post_id}"
        matches = [sources[k] for k in (path, path + "/") if k in sources]
        if len(matches) != 1:
            raise Refusal("ambiguous_metadata")
        data = matches[0]
        video_data = data["videoData"]
        item = video_data["itemInfos"]
        identity = item.get("id")
        if type(identity) not in (str, int) or str(identity) != post_id:
            raise Refusal("source_identity_mismatch")
        if data.get("statusCode", 0) != 0 or any(
            item.get(key) for key in ("privateItem", "isPrivate", "isDRM")
        ):
            raise Refusal("non_public_or_drm")
        photo = False
        for obj in (item, video_data):
            for key in ("imagePost", "imagePostInfo"):
                value = obj.get(key)
                if value is None or (isinstance(value, (dict, list)) and not value):
                    continue  # Empty placeholders do not establish either photos or video.
                images = value.get("images") if isinstance(value, dict) else None
                if not (
                    isinstance(images, list)
                    and images
                    and all(isinstance(image, dict) and image for image in images)
                ):
                    raise Refusal("metadata_schema")
                photo = True
        if photo:
            raise Refusal("unsupported_photo")
        video = item["video"]
        addresses = [("playAddr", video.get("playAddr"))]
        bitrate = video.get("bitrateInfo", [])
        if isinstance(bitrate, dict):
            bitrate = [bitrate]
        for entry in bitrate:
            addresses.append(("bitrateInfo", entry.get("PlayAddr", entry.get("playAddr"))))
        addresses.extend([("downloadAddr", video.get("downloadAddr")), ("urls", video.get("urls"))])
        candidates, sources = [], {}
        for field, address in addresses:
            if isinstance(address, dict):
                address = address.get("urlList", address.get("UrlList", address.get("urls", [])))
            if isinstance(address, str):
                address = [address]
            if address is None:
                continue
            if not isinstance(address, list) or any(not isinstance(u, str) for u in address):
                raise Refusal("metadata_schema")
            candidates.extend(address)
            for candidate in address:
                sources.setdefault(candidate, field)
        if not 0 < len(candidates) <= 32:
            raise Refusal("no_bounded_candidates")
        separate = any(
            obj.get(k) for obj in (video, item) for k in ("audio", "audioInfo", "audioAddr")
        )
        for url in dict.fromkeys(candidates):
            try:
                return Resolved(media_url(url), len(set(candidates)), bool(separate), sources[url])
            except Refusal:
                continue  # Offline admission only, never a network fallback.
        raise Refusal("forbidden_media_destination")
    except Refusal:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError):
        raise Refusal("metadata_schema") from None


class _Cookies(DefaultCookiePolicy):
    def __init__(self):
        super().__init__(strict_ns_domain=self.DomainStrictNonDomain, strict_domain=True)

    def set_ok(self, cookie, request):
        domain = cookie.domain.lstrip(".").lower()
        return (
            domain in ROOTS or domain == "www.tiktok.com" or bool(VIDEO_HOST.fullmatch(domain))
        ) and super().set_ok(cookie, request)


class _Pinned(http.client.HTTPSConnection):
    def connect(self):
        answers = socket.getaddrinfo(self.host, 443, socket.AF_INET, socket.SOCK_STREAM)
        addresses = [answer[4][0] for answer in answers]
        if not addresses or any(
            not ipaddress.ip_address(a).is_global
            or ipaddress.ip_address(a).is_multicast
            or ipaddress.ip_address(a).is_reserved
            for a in addresses
        ):
            raise Refusal("unsafe_dns")
        raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            raw.settimeout(self.timeout)
            raw.connect((addresses[0], 443))
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def _length(response, media):
    lengths = response.headers.get_all("Content-Length", [])
    transfer = response.headers.get_all("Transfer-Encoding", [])
    if transfer and (media or lengths or transfer != ["chunked"]):
        raise Refusal("unsupported_http_framing")
    if len(lengths) > 1 or (lengths and not re.fullmatch(r"[0-9]{1,12}", lengths[0].strip())):
        raise Refusal("invalid_content_length")
    if media and (not lengths or int(lengths[0]) == 0):
        raise Refusal("content_length_required")
    return int(lengths[0]) if lengths else None


class Session:
    """One publication, no global/client/browser cookie or session state."""

    def __init__(self, post_id, referer, deadline, budget):
        self.path = f"/embed/v2/{post_id}"
        self.referer, self.deadline, self.budget = referer, deadline, budget
        self.jar = CookieJar(policy=_Cookies())
        self.media_http, self.codecs = [], {}
        self.observed = {}

    def remaining(self):
        if (seconds := self.deadline - monotonic()) <= 0:
            raise Refusal("deadline")
        return seconds

    def _admit(self, url, phase):
        if phase == "media":
            media_url(url)
        else:
            p = _url(url)
            if (
                p.hostname != "www.tiktok.com"
                or p.path not in (self.path, self.path + "/")
                or p.query
                or p.fragment
            ):
                raise Refusal("forbidden_metadata_destination")

    @contextmanager
    def open(self, url, phase):
        for hop in range(3):
            self._admit(url, phase)
            name = phase + "_requests"
            if self.budget[name] >= 6:
                raise Refusal("request_limit")
            self.budget[name] += 1
            req = Request(
                url,
                headers={
                    "User-Agent": UA,
                    "Accept": "*/*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "identity",
                    "Referer": self.referer,
                },
            )
            self.jar.add_cookie_header(req)
            if any(any(not 32 <= ord(c) < 127 for c in v) for _, v in req.header_items()):
                raise Refusal("invalid_session_header")
            p = _url(url)
            conn = _Pinned(
                p.hostname, timeout=min(10, self.remaining()), context=ssl.create_default_context()
            )
            diagnostic = None
            if phase == "media":
                diagnostic = {
                    "cdn_family": next(root for root in ROOTS if p.hostname.endswith("." + root)),
                    "has_query": bool(p.query),
                    "cookie_sent": None,
                    "status": None,
                }
                self.media_http.append(diagnostic)
            try:
                conn.request(
                    "GET",
                    p.path + ("?" + p.query if p.query else ""),
                    headers=dict(req.header_items()),
                )
                if diagnostic is not None:
                    diagnostic["cookie_sent"] = bool(req.get_header("Cookie"))
                response = conn.getresponse()
                try:
                    if diagnostic is not None:
                        diagnostic["status"] = response.status
                    if sum(len(k) + len(v) for k, v in response.headers.items()) > 65536:
                        raise Refusal("header_limit")
                    if response.status not in (200, 301, 302, 303, 307, 308):
                        raise Refusal("http_" + str(response.status))
                    self.jar.extract_cookies(response, req)
                    if (
                        len(self.jar) > 32
                        or sum(len(c.name) + len(c.value or "") for c in self.jar) > 16384
                    ):
                        raise Refusal("cookie_limit")
                    if response.status != 200:
                        targets = response.headers.get_all("Location", [])
                        if len(targets) != 1 or hop == 2:
                            raise Refusal("redirect_limit")
                        url = urljoin(url, targets[0])
                        self._admit(url, phase)
                        continue
                    if response.headers.get_all("Content-Encoding", ["identity"]) != ["identity"]:
                        raise Refusal("encoded_response")
                    yield response
                    return
                finally:
                    response.close()
            finally:
                conn.close()

    def read(self, response, phase, output=None):
        media = phase == "media"
        expected = _length(response, media)
        cap = min(
            FILE_BYTES if media else HTML_BYTES,
            (TOTAL_BYTES if media else 2 * HTML_BYTES) - self.budget[phase + "_bytes"],
        )
        if expected is not None and expected > cap:
            raise Refusal("byte_limit")
        received, body = 0, bytearray()
        while expected is None or received < expected:
            self.remaining()
            remaining = cap - received
            if remaining <= 0:
                raise Refusal("byte_limit")
            try:
                chunk = response.read(min(65536, remaining))
            except http.client.IncompleteRead as exc:
                self.budget[phase + "_bytes"] += len(exc.partial)
                raise Refusal("incomplete_response") from None
            self.budget[phase + "_bytes"] += len(chunk)
            received += len(chunk)
            if not chunk:
                break
            if output is None:
                body.extend(chunk)
            else:
                output.write(chunk)
        if expected is not None and received != expected:
            raise Refusal("incomplete_response")
        return bytes(body)

    def metadata(self):
        with self.open("https://www.tiktok.com" + self.path, "metadata") as response:
            if response.headers.get_content_type() != "text/html":
                raise Refusal("metadata_content_type")
            return self.read(response, "metadata")

    def acquire(self, resolved, destination):
        self.budget["acquisitions"] += 1
        try:
            with self.open(resolved.url, "media") as response:
                if response.headers.get_content_type() not in {
                    "video/mp4",
                    "application/octet-stream",
                    "binary/octet-stream",
                }:
                    raise Refusal("media_content_type")
                with destination.open("xb") as output:
                    self.read(response, "media", output)
                if not 0 < destination.stat().st_size <= FILE_BYTES:
                    raise Refusal("file_size")
            with destination.open("rb") as source:
                if source.read(12)[4:8] != b"ftyp":
                    raise Refusal("not_mp4")
        except BaseException:
            destination.unlink(missing_ok=True)
            raise


def _codec_name(stream):
    # A finite diagnostic vocabulary prevents arbitrary probe strings leaking data.
    value = stream.get("codec_name")
    return (
        value
        if isinstance(value, str)
        and value
        in {
            "h264",
            "hevc",
            "av1",
            "vp8",
            "vp9",
            "mpeg4",
            "mjpeg",
            "aac",
            "mp3",
            "opus",
            "vorbis",
            "ac3",
            "eac3",
            "flac",
            "alac",
            "pcm_s16le",
        }
        else None
    )


def verify(path, session, separate_audio, require_audio):
    def runner(command, **kwargs):
        if command[0] == "ffprobe":
            command = [command[0], "-protocol_whitelist", "file,pipe", *command[1:]]
        else:
            # Existing preparation may request conversion; this experiment never does it.
            raise Refusal("preparation_requires_conversion")
        return subprocess.run(command, timeout=min(20, session.remaining()), **kwargs)

    info = inspect_telegram_video(path, runner)
    streams = info.get("streams", [])
    videos = [s for s in streams if s.get("codec_type") == "video"]
    audios = [s for s in streams if s.get("codec_type") == "audio"]
    session.observed.update(video_streams=len(videos), audio_streams=len(audios))
    if len(videos) != 1 or len(audios) > 1:
        raise Refusal("unsupported_streams")
    session.codecs.update(
        video_codec=_codec_name(videos[0]),
        audio_codec=_codec_name(audios[0]) if audios else "absent",
    )
    if not audios and separate_audio:
        raise Refusal("separate_streams_unsupported")
    if require_audio and not audios:
        raise Refusal("audio_required")
    parameters = telegram_video_upload_parameters(info)
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-xerror",
            "-protocol_whitelist",
            "file,pipe",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-f",
            "null",
            "-",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=min(30, session.remaining()),
    )
    session.observed["decoded"] = True
    if prepare_telegram_video(path, runner, allow_silent=True) != path:
        raise Refusal("preparation_not_passthrough")
    session.observed["preparation"] = "passthrough"
    return {
        "bytes": path.stat().st_size,
        "container": "mp4",
        **session.codecs,
        "video_streams": 1,
        "audio_streams": len(audios),
        **parameters,
        "decoded": True,
        "preparation": "passthrough",
    }


def _budget():
    return dict.fromkeys(
        ["metadata_requests", "media_requests", "metadata_bytes", "media_bytes", "acquisitions"], 0
    )


def _series_limit(budget, deadline):
    if monotonic() >= deadline:
        return "deadline"
    if budget["metadata_requests"] >= 6 or budget["media_requests"] >= 6:
        return "request_limit"
    if budget["metadata_bytes"] >= 2 * HTML_BYTES or budget["media_bytes"] >= TOTAL_BYTES:
        return "byte_limit"
    return None


def _execute(urls, workspace, deadline, expectations=None, keep_file=False, public_page=False):
    benchmark = expectations is not None
    detailed = benchmark or public_page
    budget, results, first_error, stop_reason = _budget(), [], None, None
    for index, url in enumerate(urls):
        if benchmark and (stop_reason := _series_limit(budget, deadline)):
            break
        error, path = None, None
        entry = {"case": index + 1, "success": False}
        if detailed:
            entry.update(metadata=False, source_identity=None, decoded=None, preparation=None)
        results.append(entry)
        session = None
        previous = budget.copy()
        try:
            post_id, canonical = publication(url)
            if public_page:
                from social_video_downloader.infrastructure.tiktok_public_page import (
                    _PublicPageMediaSession,
                    resolve_public_page,
                )

                session = _PublicPageMediaSession(post_id, canonical, deadline, budget)
                resolved = resolve_public_page(session.metadata(), canonical)
            else:
                session = Session(post_id, canonical, deadline, budget)
                resolved = resolve(session.metadata(), post_id)
            entry.update(
                metadata=True,
                candidates=resolved.candidates,
                candidate_source=resolved.source,
                separate_audio=resolved.separate_audio,
            )
            if detailed:
                entry["source_identity"] = True
            if public_page and resolved.separate_audio:
                raise Refusal("separate_streams_unsupported")
            path = workspace / f"case-{index + 1}.mp4"
            session.acquire(resolved, path)
            if detailed:
                entry.update(bytes=path.stat().st_size, http_complete=True)
            if sum(p.stat().st_size for p in workspace.rglob("*") if p.is_file()) > WORKSPACE_BYTES:
                raise Refusal("workspace_limit")
            require_audio = (
                False if public_page else expectations[index] if benchmark else index == 0
            )
            entry.update(
                verify(path, session, resolved.separate_audio, require_audio), success=True
            )
            if not keep_file:
                path.unlink()
        except Refusal as exc:
            error = str(exc)
        except subprocess.TimeoutExpired:
            error = "subprocess_deadline"
        except Exception:
            error = "operation_failed"
        finally:
            if session is not None:
                entry.update(session.codecs, media_http=session.media_http)
                if detailed:
                    entry.update(session.observed)
                session.jar.clear()
            if detailed and path is not None and not keep_file:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    error = stop_reason = "case_cleanup_failed"
            entry["counts"] = {name: budget[name] - previous[name] for name in budget}
        if error:
            entry["error"] = error
            first_error = first_error or error
            if detailed:
                entry["success"] = False
            if detailed and error == "source_identity_mismatch":
                entry["source_identity"] = False
            if not benchmark or stop_reason:
                break
    error = stop_reason or first_error
    return {
        "success": error is None,
        "error": error,
        "results": results,
        **budget,
        "counts_exact": True,
        **({"requested_cases": len(urls), "stop_reason": stop_reason} if benchmark else {}),
    }


def _worker_main():
    request = json.loads(sys.stdin.read(16385))
    resource.setrlimit(resource.RLIMIT_FSIZE, (FILE_BYTES, FILE_BYTES))
    print(
        json.dumps(
            _execute(
                request["urls"],
                Path(sys.argv[2]),
                request["deadline"],
                request.get("expectations"),
                request.get("keep_file", False),
                request.get("public_page", False),
            )
        ),
        flush=True,
    )


def _command(workspace):
    return [
        sys.executable,
        "-c",
        "from social_video_downloader.infrastructure import tiktok_native; "
        "tiktok_native._worker_main()",
        str(Path(__file__).resolve()),
        str(workspace),
    ]


def _exchange(process, payload, deadline, output, cancelled=None):
    # Adapted from PR #59's reviewed ownership pattern, not its extractor/transport.
    pending = memoryview(payload.encode())
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdin, selectors.EVENT_WRITE)
        selector.register(process.stdout, selectors.EVENT_READ)
        for stream in (process.stdin, process.stdout):
            os.set_blocking(stream.fileno(), False)
        while selector.get_map():
            if cancelled is not None and cancelled.is_set():
                raise Refusal("cancelled")
            if (remaining := deadline - monotonic()) <= 0:
                raise subprocess.TimeoutExpired("native-worker", 0)
            for key, _ in selector.select(
                min(remaining, 0.1) if cancelled is not None else remaining
            ):
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
                        if len(output) > 65536:
                            raise Refusal("worker_output_limit")
                    else:
                        selector.unregister(key.fileobj)
    while os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOWAIT | os.WNOHANG) is None:
        if cancelled is not None and cancelled.is_set():
            raise Refusal("cancelled")
        if monotonic() >= deadline:
            raise subprocess.TimeoutExpired("native-worker", 0)
        sleep(0.01)


def run(urls, *, benchmark=False, output_dir=None, cancelled=None, public_page=False):
    started = monotonic()
    expectations = None
    try:
        if public_page and (benchmark or not isinstance(urls, list) or len(urls) != 1):
            raise Refusal("one_public_page_url_required")
        if not isinstance(urls, list) or not 0 < len(urls) <= (4 if benchmark else 2):
            raise Refusal("one_or_two_full_urls_required")
        if benchmark:
            if any(
                not isinstance(case, dict)
                or set(case) != {"url", "require_audio"}
                or type(case["require_audio"]) is not bool
                for case in urls
            ):
                raise Refusal("invalid_benchmark_cases")
            expectations = [case["require_audio"] for case in urls]
            urls = [case["url"] for case in urls]
        if len({publication(u)[0] for u in urls}) != len(urls):
            raise Refusal("duplicate_publication")
        if output_dir is not None:
            if benchmark or len(urls) != 1 or Path(output_dir).is_symlink():
                raise Refusal("invalid_workspace")
            output_dir = Path(output_dir).resolve(strict=True)
            if not output_dir.is_dir():
                raise Refusal("invalid_workspace")
            expectations = [False]  # Exported standard video can be silent.
    except Exception:
        return {"success": False, "error": "invalid_input"}
    if (
        os.name != "posix"
        or not hasattr(os, "WNOWAIT")
        or not all(shutil.which(n) for n in ("ffmpeg", "ffprobe"))
    ):
        return {"success": False, "error": "posix_ffmpeg_required"}
    if cancelled is not None and cancelled.is_set():
        return {"success": False, "error": "cancelled", "counts_exact": False}
    temporary = TemporaryDirectory(prefix="tiktok-native-", dir=output_dir)
    published = None
    process, output, result = (
        None,
        bytearray(),
        {"success": False, "error": "worker_failed", "counts_exact": False},
    )
    try:
        previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
        try:
            process = subprocess.Popen(
                _command(temporary.name),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                start_new_session=True,
            )
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)
        _exchange(
            process,
            json.dumps(
                {
                    "urls": urls,
                    "deadline": started + SECONDS,
                    **({"public_page": True} if public_page else {}),
                    **({"expectations": expectations} if benchmark else {}),
                    **({"expectations": expectations, "keep_file": True} if output_dir else {}),
                }
            ),
            started + SECONDS,
            output,
            *([cancelled] if cancelled is not None else []),
        )
        result = json.loads(output)
    except subprocess.TimeoutExpired:
        result = {"success": False, "error": "deadline", "counts_exact": False}
    except KeyboardInterrupt:
        result = {"success": False, "error": "interrupted", "counts_exact": False}
    except Refusal as exc:
        result = {
            "success": False,
            "error": "cancelled" if str(exc) == "cancelled" else "worker_failed",
            "counts_exact": False,
        }
    except Exception:
        result = {"success": False, "error": "worker_failed", "counts_exact": False}
    finally:
        previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
        cleanup_failed = False
        try:
            if process is not None:
                cleanup_deadline = monotonic() + 5
                signaled = False
                for _ in range(2):
                    try:
                        with suppress(ProcessLookupError):
                            os.killpg(process.pid, signal.SIGKILL)
                        signaled = True
                        break
                    except OSError:
                        pass
                try:
                    process.communicate(timeout=max(0, cleanup_deadline - monotonic()))
                except (Exception, KeyboardInterrupt):
                    cleanup_failed = True
                    with suppress(Exception, KeyboardInterrupt):
                        process.wait(timeout=max(0, cleanup_deadline - monotonic()))
                if not signaled:
                    # Darwin can deny kill of a zombie-only group. Reap, then probe only.
                    try:
                        os.killpg(process.pid, 0)
                    except ProcessLookupError:
                        signaled = True
                    except OSError:
                        pass
                cleanup_failed |= not signaled or process.returncode is None
                if process.returncode not in (0, -signal.SIGKILL):
                    result = {"success": False, "error": "worker_failed", "counts_exact": False}
            if cleanup_failed:
                temporary._finalizer.detach()
                result = {"success": False, "error": "cleanup_failed", "counts_exact": False}
            else:
                if output_dir is not None and result.get("success"):
                    try:
                        if cancelled is not None and cancelled.is_set():
                            raise Refusal("cancelled")
                        source = Path(temporary.name) / "case-1.mp4"
                        report = result["results"][0]
                        if (
                            source.is_symlink()
                            or not source.is_file()
                            or not 0 < source.stat().st_size <= FILE_BYTES
                            or source.stat().st_size != report["bytes"]
                            or not report.get("http_complete")
                            or not report.get("decoded")
                            or report.get("preparation") != "passthrough"
                        ):
                            raise Refusal("invalid_native_output")
                        destination = output_dir / "tiktok.mp4"
                        os.link(source, destination, follow_symlinks=False)
                        published = destination
                    except Exception as exc:
                        result = {
                            "success": False,
                            "error": "cancelled"
                            if isinstance(exc, Refusal) and str(exc) == "cancelled"
                            else "export_failed",
                            "counts_exact": False,
                        }
                try:
                    temporary.cleanup()
                except OSError:
                    temporary._finalizer.detach()
                    result = {
                        "success": False,
                        "error": "workspace_cleanup_failed",
                        "counts_exact": False,
                    }
            if published is not None and not result.get("success"):
                try:
                    published.unlink()
                except OSError:
                    result = {
                        "success": False,
                        "error": "workspace_cleanup_failed",
                        "counts_exact": False,
                    }
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)
    result.update(
        seconds=round(monotonic() - started, 3), workspace_cleaned=not Path(temporary.name).exists()
    )
    return result


@dataclass(frozen=True, repr=False)
class NativeVideo:
    file_path: Path
    parameters: dict


def download_video(url, output_dir, *, cancelled=None, public_page=False):
    """Publish one verified file into the caller's owned workspace, without upload.

    Only this operation's fixed destination is created, with exclusive hard-link
    publication after worker termination/reap. Existing files are never replaced.
    The caller must keep its workspace until delivery and then remove the file.
    ``public_page=True`` explicitly selects the verified page path, with no fallback.
    """
    result = run(
        [url],
        output_dir=output_dir,
        cancelled=cancelled,
        **({"public_page": True} if public_page else {}),
    )
    if not result.get("success"):
        raise Refusal(result.get("error", "worker_failed"))
    report = result["results"][0]
    parameters = {
        key: report[key]
        for key in ("width", "height", "duration")
        if type(report.get(key)) is int and report[key] > 0
    }
    return NativeVideo(Path(output_dir).resolve() / "tiktok.mp4", parameters)


def main():
    def interrupt(*args):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    try:
        if sys.argv[1:] not in ([], ["--benchmark"], ["--public-page"]):
            raise Refusal("invalid_input")
        raw = sys.stdin.read(16385)
        result = run(
            json.loads(raw) if len(raw) <= 16384 else None,
            benchmark=sys.argv[1:] == ["--benchmark"],
            **({"public_page": True} if sys.argv[1:] == ["--public-page"] else {}),
        )
    except (Exception, KeyboardInterrupt):
        result = {"success": False, "error": "invalid_input"}
    print(json.dumps(result))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
