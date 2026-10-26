"""Synthetic actual writes, native yt-dlp and owned processes; no LIVE requests."""

import asyncio
import errno
import io
import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest
import yt_dlp
from yt_dlp.networking.common import Response

from social_video_downloader.config import Settings
from social_video_downloader.domain.errors import DownloadCleanupError, MediaProcessingError
from social_video_downloader.domain.models import DownloadOptions
from social_video_downloader.infrastructure import youtube_bounded as bounded
from social_video_downloader.infrastructure.youtube_write_budget import (
    BudgetExceeded,
    YouTubeWriteBudget,
)
from social_video_downloader.providers.youtube import YouTubeProvider
from social_video_downloader.resource_limits import MIB, DownloadLimits
from tests.test_youtube_provider import VIDEO_INFO

URL = "https://www.youtube.com/watch?v=abcdefghijk"


def run_guard(tmp_path, body, workspace_bytes=256 * 1024):
    owned = tmp_path / "owned"
    owned.mkdir()
    script = (
        "import os,json,io; from pathlib import Path; "
        "from social_video_downloader.resource_limits import DownloadLimits; "
        "from social_video_downloader.infrastructure.youtube_write_budget "
        "import YouTubeWriteBudget,BudgetExceeded; "
        f"root=Path({str(owned)!r}); "
        f"budget=YouTubeWriteBudget(root,DownloadLimits(65536,65536,{workspace_bytes},1))\n" + body
    )
    result = subprocess.run([sys.executable, "-B", "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("kind", ["buffered", "pathlib", "raw_fd", "append_fd", "truncate", "seek"])
def test_actual_write_refusal_precedes_file_growth(tmp_path, kind):
    result = run_guard(
        tmp_path,
        f"""
path=root/'media.part'
try:
 with budget.install_in_child():
  if {kind!r} == 'buffered':
   with open(path,'wb') as f: f.write(b'x'*60000); f.write(b'x'*60000)
  elif {kind!r} == 'pathlib': path.write_bytes(b'x'*70000)
  elif {kind!r} in ('raw_fd','append_fd'):
   fd=os.open(path,os.O_CREAT|os.O_WRONLY|(os.O_APPEND if {kind!r}=='append_fd' else 0),0o600)
   try:
    os.write(fd,b'x'*60000); os.lseek(fd,0,0); os.write(fd,b'x'*70000)
   finally: os.close(fd)
  elif {kind!r}=='truncate':
   with open(path,'wb') as f: f.truncate(70000)
  else:
   with open(path,'wb') as f: f.seek(70000); f.write(b'x')
except BudgetExceeded: pass
else: raise AssertionError('Missing refusal')
print(json.dumps({{'size':path.stat().st_size,'stopped':budget.marker.read_bytes()==b'1'}}))
""",
    )
    assert result["stopped"] and result["size"] <= 65536


def test_aggregate_includes_stream_partials_and_fragment_copies(tmp_path):
    result = run_guard(
        tmp_path,
        """
try:
 with budget.install_in_child():
  (root/'video.part').write_bytes(b'x'*60000)
  (root/'audio.part').write_bytes(b'x'*60000)
  (root/'assembled.part').write_bytes(b'x'*60000)
except BudgetExceeded: pass
else: raise AssertionError('Missing aggregate refusal')
print(json.dumps({'used':budget.usage(),'stopped':budget.marker.read_bytes()==b'1'}))
""",
        workspace_bytes=150 * 1024,
    )
    assert result["stopped"] and result["used"] <= 150 * 1024


def test_full_read_contract_and_aggregate_response_cap(tmp_path):
    result = run_guard(
        tmp_path,
        """
from types import SimpleNamespace
response=budget.wrap_response(SimpleNamespace(read=io.BytesIO(b'x'*60000).read,close=lambda:None))
assert len(response.read(amt=None))==60000
response=budget.wrap_response(SimpleNamespace(read=io.BytesIO(b'y'*60000).read,close=lambda:None))
try: response.read()
except BudgetExceeded: pass
else: raise AssertionError('Missing response cap')
print(json.dumps({'stopped':budget.marker.read_bytes()==b'1'}))
""",
    )
    assert result["stopped"]


@pytest.mark.parametrize("local", [False, True])
def test_youtube_default_is_endpoint_cap_not_instagram_cap(local):
    settings = Settings(
        "synthetic", telegram_api_base_url="http://local.invalid" if local else None
    )
    assert settings.youtube_limits.max_file_bytes == (2_000_000_000 if local else 50_000_000)
    assert settings.download_limits.max_file_bytes == (512 * MIB if local else 50_000_000)


def fixture_child(media_path=None, sparse_bytes=None):
    original = yt_dlp.YoutubeDL

    class LocalYDL(original):
        def __init__(self, options):
            super().__init__(options, auto_init=False)

        def extract_info(self, *args, **kwargs):
            raise AssertionError("Consumed valid snapshot must not be extracted again")

        def urlopen(self, request):
            counter = (
                Path(self.params["outtmpl"]["default"]).parent.parent / "synthetic-request-count"
            )
            count = int(counter.read_text()) if counter.exists() else 0
            counter.write_text(str(count + 1))
            path = media_path
            if isinstance(media_path, dict):
                path = media_path[request.url.rsplit("/", 1)[-1]]
            return Response(io.BytesIO(Path(path).read_bytes()), request.url, {})

        def process_ie_result(self, info, *args, **kwargs):
            if sparse_bytes is not None:
                path = Path(
                    self.params["outtmpl"]["default"]
                    % {"id": "synthetic", "format_id": "18", "ext": "mp4"}
                )
                with path.open("wb") as stream:
                    stream.truncate(sparse_bytes)
                return {"filepath": str(path)}
            return super().process_ie_result(info, *args, **kwargs)

    yt_dlp.YoutubeDL = LocalYDL


def install_child(monkeypatch, media_path=None, sparse_bytes=None):
    paths = media_path if isinstance(media_path, dict) else str(media_path)
    script = (
        "from tests.test_youtube_write_budget import fixture_child; "
        f"fixture_child({paths!r},sparse_bytes={sparse_bytes!r}); "
        "from social_video_downloader.infrastructure.youtube_bounded import main; main()"
    )
    monkeypatch.setattr(bounded, "_command", lambda: [sys.executable, "-B", "-c", script])


def provider():
    info = deepcopy(VIDEO_INFO)
    info["id"] = "abcdefghijk"
    info["formats"] = [dict(info["formats"][0], url="https://media.invalid/synthetic.mp4")]
    result = YouTubeProvider()
    result._remember_info(URL, info)
    return result


@pytest.mark.asyncio
async def test_youtube_above_512_mib_is_not_rejected(monkeypatch, tmp_path):
    install_child(monkeypatch, sparse_bytes=600 * MIB)
    source = provider()
    limits = Settings("synthetic", telegram_api_base_url="http://local.invalid").youtube_limits
    media = await bounded.acquire(
        source, URL, tmp_path, DownloadOptions(quality_id="video-640x360"), limits
    )
    assert media.file_path.stat().st_size == 600 * MIB
    assert not source._inspection_cache


@pytest.mark.asyncio
@pytest.mark.parametrize("oversized", [False, True])
async def test_real_yt_dlp_stream_has_actual_write_cap(monkeypatch, tmp_path, oversized):
    media = tmp_path / "source.mp4"
    media.write_bytes(b"x" * (200000 if oversized else 10000))
    owned = tmp_path / "owned"
    owned.mkdir()
    install_child(monkeypatch, media_path=media)
    source = provider()
    limits = DownloadLimits(65536, 131072, 262144, 1)
    if oversized:
        with pytest.raises(MediaProcessingError):
            await bounded.acquire(
                source, URL, owned, DownloadOptions(quality_id="video-640x360"), limits
            )
        assert (owned / ".youtube-resource-control/stopped").read_bytes() == b"1"
        assert all(
            p.stat().st_size <= limits.max_file_bytes for p in owned.rglob("*") if p.is_file()
        )
    else:
        result = await bounded.acquire(
            source, URL, owned, DownloadOptions(quality_id="video-640x360"), limits
        )
        assert result.file_path.read_bytes() == media.read_bytes()
    assert not source._inspection_cache
    assert (owned / "synthetic-request-count").read_text() == "1"


@pytest.mark.parametrize("exhaust", ["file", "workspace"])
def test_ffmpeg_os_cap_blocks_new_http_or_fallback(tmp_path, monkeypatch, exhaust):
    binaries = tmp_path / "binaries"
    binaries.mkdir()
    binary = binaries / "ffmpeg"
    binary.write_text(
        f"#!{sys.executable}\nimport sys\n"
        "with open(sys.argv[-1].removeprefix('file:'),'wb') as f:\n"
        " f.write(b'x'*1000000)\n"
    )
    binary.chmod(0o700)
    monkeypatch.setenv("PATH", str(binaries) + os.pathsep + os.environ["PATH"])
    owned = tmp_path / "owned"
    owned.mkdir()
    limits = DownloadLimits(65536, 65536, 131072, 1)
    budget = YouTubeWriteBudget(owned, limits)
    if exhaust == "workspace":
        (owned / "video.part").write_bytes(b"x" * 40000)
        (owned / "audio.part").write_bytes(b"x" * 40000)
    output = owned / "merged.mp4"
    with pytest.raises(BudgetExceeded):
        budget.run(["ffmpeg", str(output)], capture_output=True, check=True)
    assert output.stat().st_size <= limits.max_file_bytes
    assert budget.usage() <= limits.max_workspace_bytes
    from social_video_downloader.infrastructure import youtube_write_budget as guard

    token = guard._ACTIVE.set(budget)
    wire = Mock()
    try:
        ydl = guard.guard_ydl(type("SyntheticYDL", (), {"urlopen": wire})())
        with pytest.raises(BudgetExceeded):
            ydl.urlopen("synthetic")
        wire.assert_not_called()
    finally:
        guard._ACTIVE.reset(token)


@pytest.mark.asyncio
async def test_spawn_failure_is_not_cleanup_quarantine(monkeypatch, tmp_path):
    monkeypatch.setattr(bounded, "_command", lambda: [str(tmp_path / "absent")])
    with pytest.raises(OSError):
        await bounded.acquire(
            provider(), URL, tmp_path, DownloadOptions(quality_id="video-640x360"), DownloadLimits()
        )


@pytest.mark.asyncio
async def test_repeated_cancellation_reaps_child(monkeypatch, tmp_path):
    marker = tmp_path / "entered"
    script = (
        "import time; from pathlib import Path; "
        f"Path({str(marker)!r}).write_text('ready'); time.sleep(60)"
    )
    monkeypatch.setattr(bounded, "_command", lambda: [sys.executable, "-B", "-c", script])
    children = []
    original = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        child = await original(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    task = asyncio.create_task(
        bounded.acquire(
            provider(), URL, tmp_path, DownloadOptions(quality_id="video-640x360"), DownloadLimits()
        )
    )
    try:
        async with asyncio.timeout(5):
            while not marker.exists():
                await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert children and all(child.returncode is not None for child in children)
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_unknown_cleanup_stays_typed(monkeypatch, tmp_path):
    install_child(monkeypatch, sparse_bytes=10000)
    original = bounded._cleanup

    async def failed(creation, process):
        await original(creation, process)
        raise DownloadCleanupError("synthetic cleanup uncertainty")

    monkeypatch.setattr(bounded, "_cleanup", failed)
    with pytest.raises(DownloadCleanupError):
        await bounded.acquire(
            provider(), URL, tmp_path, DownloadOptions(quality_id="video-640x360"), DownloadLimits()
        )


@pytest.mark.asyncio
async def test_real_separate_streams_and_ffmpeg_merge(monkeypatch, tmp_path):
    from social_video_downloader.infrastructure.telegram_media import inspect_telegram_video
    from tests.integration.test_video_preparation import generate

    video, audio = tmp_path / "source.mp4", tmp_path / "source.m4a"
    generate(video)
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000",
            "-t",
            "0.6",
            "-c:a",
            "aac",
            str(audio),
        ],
        check=True,
        capture_output=True,
        timeout=15,
    )
    install_child(monkeypatch, media_path={"video.mp4": str(video), "audio.m4a": str(audio)})
    info = deepcopy(VIDEO_INFO)
    info["id"] = "abcdefghijk"
    info["formats"] = [
        {
            "format_id": "137",
            "ext": "mp4",
            "width": 64,
            "height": 96,
            "vcodec": "avc1",
            "acodec": "none",
            "url": "https://media.invalid/video.mp4",
        },
        {
            "format_id": "140",
            "ext": "m4a",
            "vcodec": "none",
            "acodec": "mp4a.40.2",
            "abr": 128,
            "url": "https://media.invalid/audio.m4a",
        },
    ]
    source = YouTubeProvider()
    source._remember_info(URL, info)
    owned = tmp_path / "owned"
    owned.mkdir()
    result = await bounded.acquire(
        source,
        URL,
        owned,
        DownloadOptions(quality_id="video-64x96"),
        DownloadLimits(2 * MIB, 4 * MIB, 8 * MIB, 1),
    )
    codecs = {
        s["codec_type"]: s["codec_name"]
        for s in inspect_telegram_video(result.file_path)["streams"]
    }
    assert codecs == {"video": "h264", "audio": "aac"}
    assert (owned / "synthetic-request-count").read_text() == "2"
    assert not source._inspection_cache
    assert (owned / ".youtube-resource-control/stopped").read_bytes() == b"0"


def test_preparation_resource_stop_never_falls_back(tmp_path, monkeypatch):
    from social_video_downloader.infrastructure.telegram_media import prepare_telegram_video
    from tests.integration.test_video_preparation import generate

    source = tmp_path / "source.mkv"
    generate(source, audio=True)
    budget = YouTubeWriteBudget(tmp_path, DownloadLimits(65536, 65536, 262144, 1))
    calls = []
    real_run = budget.run

    def runner(command, **kwargs):
        if command[0] == "ffmpeg":
            calls.append(command)
            budget.marker.write_bytes(b"1")
        return real_run(command, **kwargs)

    with pytest.raises(BudgetExceeded):
        prepare_telegram_video(source, runner=runner)
    assert len(calls) == 1 and "copy" in calls[0]
    assert not list(tmp_path.glob("*.telegram-compatible.mp4"))


@pytest.mark.parametrize("code", [errno.ENOSPC, errno.EFBIG, errno.EDQUOT])
def test_raw_write_resource_error_is_sticky(tmp_path, monkeypatch, code):
    from social_video_downloader.infrastructure import youtube_write_budget as guard

    budget = YouTubeWriteBudget(tmp_path, DownloadLimits(65536, 65536, 262144, 1))

    def failed(*args):
        raise OSError(code, "synthetic resource refusal")

    monkeypatch.setattr(guard, "_OS_WRITE", failed)
    with pytest.raises(BudgetExceeded):
        budget.os_write(999, b"x")
    with pytest.raises(BudgetExceeded):
        budget.check()
