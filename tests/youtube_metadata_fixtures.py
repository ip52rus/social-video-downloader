"""Lightweight, network-denied metadata child fixtures; no Telegram/app imports."""

import os
import signal
import socket
import subprocess
import sys
import time
from contextlib import suppress

from yt_dlp.utils.networking import HTTPHeaderDict

from social_video_downloader.infrastructure import youtube_snapshot as wire
from social_video_downloader.providers.youtube import YouTubeProvider


def info(video_id="abcdefghijk"):
    data = {
        "id": video_id,
        "title": "Test: video/short",
        "duration": 123,
        "uploader": "Test Channel",
        "extractor": "youtube",
        "_format_sort_fields": (
            "quality",
            "res",
            "fps",
            "hdr:12",
            "source",
            "vcodec",
            "channels",
            "acodec",
            "lang",
            "proto",
        ),
        "__post_extractor": None,
        "formats": [
            dict(
                format_id="18",
                ext="mp4",
                width=640,
                height=360,
                vcodec="avc1",
                acodec="mp4a",
                tbr=500,
            ),
            dict(
                format_id="137",
                ext="mp4",
                width=1920,
                height=1080,
                vcodec="avc1",
                acodec="none",
                tbr=4000,
            ),
            dict(
                format_id="136",
                ext="mp4",
                width=1280,
                height=720,
                vcodec="avc1",
                acodec="none",
                tbr=2500,
            ),
            dict(format_id="140", ext="m4a", vcodec="none", acodec="mp4a.40.2", abr=128, tbr=128),
            dict(format_id="251", ext="webm", vcodec="none", acodec="opus", abr=160, tbr=160),
        ],
    }
    for item in data["formats"]:
        item.update(url="https://media.invalid/" + item["format_id"], protocol="https")
    return data


def fmt(name, width=None, height=None, v="avc1.42001e", a="none", ext="mp4", rate=1000):
    return dict(
        format_id=name,
        width=width,
        height=height,
        vcodec=v,
        acodec=a,
        ext=ext,
        tbr=rate,
        abr=rate if v == "none" else None,
        url="https://media.invalid/" + name,
        protocol="https",
    )


def fixture_info(video_id):
    data = info(video_id)
    aac = fmt("140", v="none", a="mp4a.40.2", ext="m4a", rate=128)
    opus = fmt("251", v="none", a="opus", ext="webm", rate=160)
    cases = [
        [fmt("progressive", 640, 360, a="mp4a.40.2")],
        [fmt("adaptive", 1280, 720), aac],
        [fmt("low", 640, 360), fmt("medium", 1280, 720), fmt("high", 1920, 1080), aac],
        [fmt("portrait", 720, 1280), fmt("landscape", 1920, 1080), aac],
        [aac, opus],
        [opus],
        [
            fmt("avc", 1280, 720, rate=500),
            fmt("vp9", 1280, 720, v="vp9", ext="webm", rate=4000),
            aac,
            opus,
        ],
        [fmt("vp9", 1280, 720, v="vp9", ext="webm"), opus],
        data["formats"],
    ]
    case = int(video_id[-4:])
    data["formats"] = cases[case] if case < len(cases) else cases[1]
    if case == 9:
        data["http_headers"] = HTTPHeaderDict({"X-Synthetic": "header-value"})
        for item in data["formats"]:
            item["http_headers"] = data["http_headers"]
    if case == 10:
        data["formats"][0].update(
            protocol="http_dash_segments",
            fragments=[
                {"url": "https://media.invalid/adaptive/0", "duration": 0.125},
                {"url": "https://media.invalid/adaptive/1", "duration": 0.125},
            ],
        )
    if case == 11:
        data["description"] = "synthetic text " * 65536
        data["formats"] = cases[0]
    return data


def child(mode):
    # Even direct bootstrap children cannot open any IPv4/IPv6 connection.
    def deny(event, args):
        if event in {"socket.connect", "socket.sendto"} and args[0].family in (
            socket.AF_INET,
            socket.AF_INET6,
        ):
            raise RuntimeError("offline socket")
        if event.startswith("socket.get"):
            raise RuntimeError("offline DNS")

    sys.addaudithook(deny)
    assert not any(
        k in os.environ
        for k in (
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_API_ID",
            "TELEGRAM_API_HASH",
            "HTTPS_PROXY",
            "HOME",
        )
    )
    if mode == "production":
        from social_video_downloader.infrastructure.youtube_metadata_worker import main

        class FakeYDL:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def extract_info(self, url, *, download, process):
                assert download is False and process is False
                _, video_id = wire.target(url)
                if video_id.startswith("fixture"):
                    return fixture_info(video_id)
                return info(video_id)

        YouTubeProvider._new_ydl = lambda self, options: FakeYDL()
        raise SystemExit(main())
    req = wire.validate_request(
        wire.decode(sys.stdin.buffer.read(wire.REQUEST_BYTES + 1), wire.REQUEST_BYTES)
    )
    if mode == "crash":
        os._exit(7)
    if mode == "malformed":
        sys.stdout.buffer.write(b'{"private":"synthetic"}')
        return
    if mode == "partial":
        sys.stdout.buffer.write(b'["dict",[')
        return
    if mode == "oversize":
        sys.stdout.buffer.write(b"x" * (wire.RESPONSE_BYTES + 1))
        sys.stdout.buffer.flush()
        time.sleep(10)
    if mode in ("silent", "stubborn"):
        if mode == "stubborn":
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
        os.write(2, b"ready\n")
        time.sleep(10)
    if mode == "descendant":
        nested = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(30)"])
        assert os.getpgid(nested.pid) == os.getpgrp()

        def stop(*_):
            with suppress(ProcessLookupError):
                nested.terminate()
            nested.wait(timeout=2)
            raise SystemExit(0)

        signal.signal(signal.SIGTERM, stop)
        os.write(2, b"ready\n")
        time.sleep(30)
    if mode == "slow":
        os.write(2, b"ready\n")
        time.sleep(2)
    data = info(req["video_id"])
    if mode == "wrong_id":
        data["id"] = "lmnopqrstuv"
    if mode == "unsupported":
        data["deferred"] = lambda: None
    sys.stdout.buffer.write(wire.encode(wire.response(req, data, time.monotonic())))
    sys.stdout.buffer.flush()
