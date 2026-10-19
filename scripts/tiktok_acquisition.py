"""Bounded two-video experiment, separate from the metadata-only CLI and bot."""

import http.client
import ipaddress
import json
import math
import re
import resource
import shutil
import signal
import socket
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import tiktok_metadata as meta  # noqa: E402
from social_video_downloader.infrastructure.telegram_media import (  # noqa: E402
    inspect_telegram_video,
    prepare_telegram_video,
)

MEDIA_HOSTS = frozenset({"v16-webapp-prime.tiktok.com", "v19-webapp-prime.tiktok.com"})


@dataclass(frozen=True)
class Limits:
    max_urls: int = 2
    # Deliberately tighter than the authorized 360 s ceiling: retain the existing
    # hard 180 s metadata supervisor bound across the entire experiment.
    max_seconds: float = 180
    max_file_bytes: int = 25 * 1024**2
    max_total_bytes: int = 50 * 1024**2
    max_workspace_bytes: int = 128 * 1024**2

    def __post_init__(self):
        ceilings = (2, 180, 25 * 1024**2, 50 * 1024**2, 128 * 1024**2)
        for (name, value), ceiling in zip(asdict(self).items(), ceilings, strict=True):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0 < value <= ceiling
                or (name != "max_seconds" and not isinstance(value, int))
            ):
                raise ValueError("Invalid acquisition limits")


def _media_url(raw):
    if (
        not isinstance(raw, str)
        or len(raw) > 16384
        or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in raw)
    ):
        raise meta.Stop("invalid_media_url")
    try:
        p = urlsplit(raw)
        if (
            p.scheme != "https"
            or p.hostname not in MEDIA_HOSTS
            or p.netloc != p.hostname
            or p.port is not None
            or p.username is not None
            or p.password is not None
            or p.fragment
            or not p.path.startswith("/video/")
            or not re.fullmatch(r"/video/[A-Za-z0-9_.~/-]+", p.path)
            or any(part in {".", ".."} for part in p.path.split("/"))
            or "\\" in raw
        ):
            raise meta.Stop("media_destination_forbidden")
    except ValueError:
        raise meta.Stop("invalid_media_url") from None
    return raw


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        if self._tunnel_host or self.port != 443:
            raise meta.Stop("proxy_forbidden")
        # IPv4 only. Resolve once, reject mixed public/private answers, then connect
        # the exact vetted sockaddr without a second hostname lookup.
        answers = socket.getaddrinfo(self.host, 443, socket.AF_INET, socket.SOCK_STREAM)
        if not answers:
            raise meta.Stop("dns_forbidden")
        for family, kind, _, _, address in answers:
            ip = ipaddress.ip_address(address[0])
            if (
                family != socket.AF_INET
                or kind != socket.SOCK_STREAM
                or ip.version != 4
                or not ip.is_global
                or ip.is_multicast
                or ip.is_reserved
                or address[1] != 443
            ):
                raise meta.Stop("dns_forbidden")
        family, kind, protocol, _, address = answers[0]
        raw = socket.socket(family, kind, protocol)
        try:
            raw.settimeout(self.timeout)
            raw.connect(address)
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


class _PinnedHTTPS(HTTPSHandler):
    def https_open(self, request):
        host = urlsplit(request.full_url).hostname
        if host == "www.tiktok.com":
            if meta._url(request.full_url)[0] != "full":
                raise meta.Stop("forbidden_destination")
        else:
            _media_url(request.full_url)
        return self.do_open(_PinnedHTTPSConnection, request, context=self._context)


def _opener():
    return build_opener(ProxyHandler({}), meta._NoRedirect(), _PinnedHTTPS())


class _SourceIE(meta._MetadataIE):
    def _parse_aweme_video_web(self, aweme_detail, webpage_url, video_id, extract_flat=False):
        if any(aweme_detail.get(key) for key in ("imagePost", "image_post_info", "images")):
            raise meta.Stop("unsupported_publication")
        video = aweme_detail.get("video")
        if not isinstance(video, dict):
            raise meta.Stop("invalid_source")
        urls = []
        play = video.get("playAddr")
        if isinstance(play, str):
            urls.append(play)
        elif isinstance(play, list):
            urls.extend(
                x["src"] for x in play if isinstance(x, dict) and isinstance(x.get("src"), str)
            )
        for bitrate in video.get("bitrateInfo") or []:
            if isinstance(bitrate, dict) and isinstance(bitrate.get("PlayAddr"), dict):
                values = bitrate["PlayAddr"].get("UrlList")
                if isinstance(values, list):
                    urls.extend(x for x in values if isinstance(x, str))
        # Compact immutable provenance, before upstream mapping; no second extraction.
        self._downloader.source_urls = frozenset(
            "https:" + value if value.startswith("//") else value for value in urls
        )
        return super()._parse_aweme_video_web(aweme_detail, webpage_url, video_id, extract_flat)


def _candidate(info, source_urls):
    if info.get("_type", "video") != "video" or "entries" in info:
        raise meta.Stop("unsupported_publication")
    for f in info.get("formats") or []:
        if (
            isinstance(f, dict)
            and f.get("ext") == "mp4"
            and f.get("vcodec") == "h264"
            and f.get("acodec") == "aac"
            and not f.get("__needs_testing")
            and meta.determine_protocol(f) == "https"
        ):
            if f.get("url") not in source_urls:
                raise meta.Stop("unconfirmed_media_source")
            return _media_url(f["url"])
    raise meta.Stop("no_safe_format")


class _Media:
    def __init__(self, limits, deadline, workspace, emit):
        self.limits, self.deadline, self.workspace, self.emit = limits, deadline, workspace, emit
        self.received = self.requests = self.attempts = 0
        self.opener = _opener()

    def progress(self):
        return {
            "media_bytes": self.received,
            "media_requests": self.requests,
            "acquisitions": self.attempts,
        }

    def check(self):
        if monotonic() >= self.deadline:
            raise meta.Stop("deadline")
        size = sum(f.stat().st_size for f in self.workspace.iterdir() if f.is_file())
        if size > self.limits.max_workspace_bytes:
            raise meta.Stop("workspace_limit")
        return size

    def acquire(self, url, path):
        _media_url(url)
        if path.parent != self.workspace or path.exists() or path.is_symlink():
            raise meta.Stop("invalid_workspace")
        if self.attempts >= self.limits.max_urls:
            raise meta.Stop("acquisition_limit")
        self.attempts += 1
        self.emit(self.progress())
        seen = set()
        for _ in range(3):
            self.check()
            _media_url(url)
            if url in seen:
                raise meta.Stop("redirect_loop")
            seen.add(url)
            self.requests += 1
            self.emit(self.progress())
            try:
                response = self.opener.open(
                    Request(
                        url,
                        headers={"Accept-Encoding": "identity", "User-Agent": "metadata-check/1"},
                    ),
                    timeout=min(10, self.deadline - monotonic()),
                )
            except HTTPError as error:
                response = error
            except Exception:
                raise meta.Stop("media_network_error") from None
            with response:
                self.check()
                if response.geturl() != url:
                    raise meta.Stop("unexpected_redirect")
                del response.headers["Set-Cookie"]
                if response.code in {301, 302, 303, 307, 308}:
                    url = _media_url(urljoin(url, response.headers.get("Location", "")))
                    continue
                if response.code != 200:
                    raise meta.Stop(
                        f"media_http_{response.code}"
                        if response.code in {403, 429}
                        else "media_http_error"
                    )
                if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                    raise meta.Stop("encoded_response")
                with path.open("xb") as output:
                    while True:
                        used = self.check()
                        remaining = min(
                            self.limits.max_file_bytes - output.tell(),
                            self.limits.max_total_bytes - self.received,
                            self.limits.max_workspace_bytes - used,
                        )
                        if remaining <= 0:
                            raise meta.Stop("media_byte_limit")
                        chunk = response.read(min(65536, remaining))
                        self.received += len(chunk)
                        self.emit(self.progress())
                        self.check()
                        if len(chunk) > remaining:
                            raise meta.Stop("invalid_response_reader")
                        if not chunk:
                            break
                        output.write(chunk)
                        output.flush()
                    if output.tell() == 0 or path.stat().st_size != output.tell():
                        raise meta.Stop("invalid_file")
                return
        raise meta.Stop("redirect_limit")


def _probe_runner(deadline):
    def runner(command, **kwargs):
        if command[0] != "ffprobe":
            raise meta.Stop("conversion_forbidden")
        left = deadline - monotonic()
        if left <= 0:
            raise meta.Stop("deadline")
        result = subprocess.run(
            [
                command[0],
                "-protocol_whitelist",
                "file,pipe",
                "-format_whitelist",
                "mov",
                *command[1:],
            ],
            timeout=min(20, left),
            **kwargs,
        )
        if result.stderr.strip():
            raise meta.Stop("probe_error")
        return result

    return runner


def _validate(path, deadline):
    data = inspect_telegram_video(path, runner=_probe_runner(deadline))
    streams = data.get("streams", [])
    videos = [s for s in streams if s.get("codec_type") == "video"]
    audios = [s for s in streams if s.get("codec_type") == "audio"]
    duration = float(data.get("format", {}).get("duration", 0))
    if len(videos) != 1 or len(audios) > 1 or not math.isfinite(duration) or duration <= 0:
        raise meta.Stop("invalid_streams")
    video = videos[0]
    report = {
        "container": "mp4"
        if "mp4" in data.get("format", {}).get("format_name", "").split(",")
        else "other",
        "video_codec": video.get("codec_name")
        if video.get("codec_name") in {"h264", "hevc", "vp8", "vp9", "av1", "mpeg4"}
        else "other",
        "audio_codec": meta._codec(audios[0].get("codec_name"), audio=True) if audios else "absent",
        "width": video.get("width"),
        "height": video.get("height"),
        "duration": duration,
        "video_streams": len(videos),
        "audio_streams": len(audios),
    }
    return report


def _prepare_and_decode(path, probe, index, deadline):
    if (
        probe["container"] != "mp4"
        or probe["video_codec"] != "h264"
        or probe["audio_codec"] not in {"aac", "absent"}
    ):
        raise meta.Stop("incompatible_media")
    if index == 1 and not probe["audio_streams"]:
        raise meta.Stop("audio_required")
    if any(type(probe[k]) is not int or probe[k] <= 0 for k in ("width", "height")):
        raise meta.Stop("invalid_dimensions")

    size = path.stat().st_size
    if (
        prepare_telegram_video(path, runner=_probe_runner(deadline), allow_silent=True) != path
        or path.stat().st_size != size
    ):
        raise meta.Stop("unexpected_derivative")
    left = deadline - monotonic()
    if left <= 0:
        raise meta.Stop("deadline")
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-xerror",
            "-nostdin",
            "-threads",
            "1",
            "-protocol_whitelist",
            "file,pipe",
            "-format_whitelist",
            "mov",
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
        capture_output=True,
        timeout=min(30, left),
    )


def _execute(urls, limits, deadline, workspace, emit):
    transport = meta._Transport(meta.Limits(), min(deadline, monotonic() + 180), emit)
    transport.opener = _opener()
    media = _Media(limits, deadline, workspace, emit)
    results, error = [], None
    try:
        if list(workspace.iterdir()):
            raise meta.Stop("invalid_workspace")
        with meta._YDL(transport) as ydl:
            ydl.add_info_extractor(_SourceIE(ydl))
            for index, raw in enumerate(urls, 1):
                entry = {"case": index, "success": False}
                results.append(entry)
                started = monotonic()
                try:
                    media.check()
                    transport.check()
                    if transport.extractions >= transport.limits.max_extractions:
                        raise meta.Stop("extraction_limit")
                    _, url = meta._url(raw)
                    transport.expected = url
                    ydl.source_urls = frozenset()
                    transport.extractions += 1
                    emit(transport.progress())
                    info = ydl.extract_info(url, download=False, process=False, ie_key="TikTok")
                    transport.check()
                    if info.get("id") != url.rsplit("/", 1)[-1]:
                        raise meta.Stop("identity_changed")
                    chosen = _candidate(info, ydl.source_urls)
                    path = workspace / f"case-{index}.mp4"
                    media.acquire(chosen, path)
                    entry["bytes"] = path.stat().st_size
                    entry["probe"] = _validate(path, deadline)
                    _prepare_and_decode(path, entry["probe"], index, deadline)
                    media.check()
                    entry.update(success=True, preparation="passthrough", decoded=True)
                except meta.Stop as exc:
                    error = str(exc)
                except subprocess.TimeoutExpired:
                    error = "subprocess_deadline"
                except Exception:
                    error = "inspection_or_media_error"
                entry["seconds"] = round(monotonic() - started, 3)
                if error:
                    entry["error"] = error
                    break
    except meta.Stop as exc:
        error = str(exc)
    return {
        "success": error is None,
        "error": error,
        "results": results,
        **transport.progress(),
        **media.progress(),
        "counts_exact": True,
    }


def _worker_main():
    request = json.loads(sys.stdin.read(16385))
    limits = Limits(**request["limits"])
    resource.setrlimit(resource.RLIMIT_FSIZE, (limits.max_file_bytes, limits.max_file_bytes))
    result = _execute(
        request["urls"],
        limits,
        request["deadline"],
        Path(sys.argv[2]),
        lambda progress: print(json.dumps({"progress": progress}), flush=True),
    )
    print(json.dumps({"result": result}), flush=True)


def _command(workspace):
    return [
        sys.executable,
        "-c",
        "import runpy,sys; runpy.run_path(sys.argv[1])['_worker_main']()",
        str(Path(__file__).resolve()),
        str(workspace),
    ]


def run(urls, limits=None):
    limits = limits or Limits()
    try:
        if not isinstance(urls, list) or len(urls) != 2:
            raise meta.Stop("two_full_urls_required")
        canonical = [meta._url(url) for url in urls]
        if (
            any(kind != "full" for kind, _ in canonical)
            or len({url.rsplit("/", 1)[-1] for _, url in canonical}) != 2
        ):
            raise meta.Stop("two_unique_full_urls_required")
    except meta.Stop as exc:
        return {"success": False, "error": str(exc)}
    if not all(shutil.which(name) for name in ("ffmpeg", "ffprobe")):
        return {"success": False, "error": "ffmpeg_required"}
    temporary = TemporaryDirectory(prefix="tiktok-acquisition-")
    result = None
    try:
        result = meta._supervise(urls, limits, lambda: _command(temporary.name))
    finally:
        previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
        try:
            if result is not None and result.get("error") == "cleanup_failed":
                # Keep ownership visible; never delete under an unconfirmed worker.
                temporary._finalizer.detach()
            else:
                try:
                    temporary.cleanup()
                except OSError:
                    temporary._finalizer.detach()
                    result = {"success": False, "error": "workspace_cleanup_failed"}
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)
    result["workspace_cleaned"] = not Path(temporary.name).exists()
    return result


def main():
    def interrupted(*args):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        raw = sys.stdin.read(16385)
        result = run(json.loads(raw) if len(raw) <= 16384 else None)
    except (Exception, KeyboardInterrupt):
        result = {"success": False, "error": "harness_error"}
    print(json.dumps(result))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
