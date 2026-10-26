"""Owned, short-lived YouTube acquisition using the unchanged provider/selector."""

import asyncio
import contextlib
import json
import math
import os
import signal
import sys
from dataclasses import asdict
from pathlib import Path
from time import monotonic

from social_video_downloader.domain.errors import (
    DownloadCleanupError,
    DownloadFailedError,
    MediaProcessingError,
)
from social_video_downloader.domain.models import (
    DownloadedMedia,
    DownloadMode,
    DownloadOptions,
    MediaMetadata,
    Platform,
)
from social_video_downloader.infrastructure.youtube_snapshot import (
    decode,
    encode,
    request,
    response,
    validate_response,
)
from social_video_downloader.infrastructure.youtube_write_budget import (
    BudgetExceeded,
    YouTubeWriteBudget,
)
from social_video_downloader.resource_limits import DownloadLimits

_REQUEST_BYTES = 3 * 1024**2
_RESULT_BYTES = 64 * 1024


def _command():
    return [sys.executable, "-B", "-m", __name__]


def _environment(workspace):
    keys = (
        "PATH",
        "LANG",
        "LC_ALL",
        "HOME",
        "XDG_CACHE_HOME",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
    )
    env = {key: os.environ[key] for key in keys if key in os.environ}
    source = str(Path(__file__).resolve().parents[2])
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (source, os.environ.get("PYTHONPATH", ""))))
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", TMPDIR=str(workspace))
    return env


async def _stop(creation, process):
    if process is None:
        try:
            child = await creation
        except Exception:
            return  # Confirmed spawn failure, not an uncertain live writer.
    else:
        child = process
    with contextlib.suppress(ProcessLookupError):
        os.killpg(child.pid, signal.SIGKILL)
    await child.wait()
    deadline = monotonic() + 2
    while True:
        try:
            os.killpg(child.pid, 0)
        except ProcessLookupError:
            return
        except PermissionError:
            pass  # Unknown is not proof that a writer is gone.
        if monotonic() >= deadline:
            raise DownloadCleanupError("YouTube resource worker group is still present.")
        await asyncio.sleep(0.01)


async def _cleanup(creation, process):
    task = asyncio.create_task(_stop(creation, process))
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
        except Exception:
            break
    try:
        task.result()
    except Exception:
        raise DownloadCleanupError("YouTube resource worker cleanup is unconfirmed.") from None
    return cancelled


async def acquire(provider, url, workspace, options, limits):
    if os.name != "posix":
        raise DownloadFailedError("Bounded YouTube acquisition requires POSIX.")
    workspace = Path(workspace).resolve(strict=True)
    limits.check_workspace(workspace)
    # Consume the original cache entry exactly once. Its timestamp is not renewed.
    with provider._cache_lock:
        cached = provider._inspection_cache.get(url)
        info = provider._take_cached_info(url)
    snapshot = (
        None if info is None else response(request(url, "resource-acquisition"), info, cached[0])
    )
    wire = encode(
        {
            "url": url,
            "workspace": str(workspace),
            "snapshot": snapshot,
            "options": {"mode": options.mode.value, "quality_id": options.quality_id},
            "limits": asdict(limits),
        },
        _REQUEST_BYTES,
    )
    process = None
    creation = asyncio.create_task(
        asyncio.create_subprocess_exec(
            *_command(),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
            env=_environment(workspace),
            limit=64 * 1024,
        )
    )
    try:
        process = await asyncio.shield(creation)
        process.stdin.write(wire)
        await process.stdin.drain()
        process.stdin.close()
        raw = bytearray()
        while True:
            chunk = await process.stdout.read(min(65536, _RESULT_BYTES + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
            if len(raw) > _RESULT_BYTES:
                raise MediaProcessingError("YouTube resource worker response exceeded its budget.")
        await process.wait()
        result = json.loads(raw)
        if process.returncode != 0 or result.get("error"):
            raise MediaProcessingError("YouTube acquisition stopped within its resource limits.")
        name = result["name"]
        if type(name) is not str or Path(name).name != name or name in {".", ".."}:
            raise ValueError
        path = workspace / name
        limits.check_file(path)
        limits.check_workspace(workspace)
        title, duration = result["title"], result["duration"]
        if type(title) is not str or len(title) > 16 * 1024:
            raise ValueError
        if duration is not None and (
            type(duration) not in (float, int) or not math.isfinite(duration)
        ):
            raise ValueError
        return DownloadedMedia(path, MediaMetadata(title, url, Platform.YOUTUBE, duration))
    except (ValueError, KeyError, TypeError):
        raise MediaProcessingError("YouTube resource worker response was refused.") from None
    finally:
        interrupted = await _cleanup(creation, process)
        if interrupted:
            raise asyncio.CancelledError


def main():
    from social_video_downloader.providers.youtube import YouTubeProvider

    try:
        wire = sys.stdin.buffer.read(_REQUEST_BYTES + 1)
        if len(wire) > _REQUEST_BYTES:
            raise ValueError
        data = decode(wire, _REQUEST_BYTES)
        url = YouTubeProvider._normalize_youtube_url(data["url"])
        limits = DownloadLimits(**data["limits"])
        workspace = Path(data["workspace"]).resolve(strict=True)
        options = DownloadOptions(
            DownloadMode(data["options"]["mode"]), data["options"]["quality_id"]
        )
        provider = YouTubeProvider()
        if data["snapshot"] is not None:
            snapshot = validate_response(data["snapshot"], request(url, "resource-acquisition"))
            provider._store_info(url, snapshot.info, snapshot.created_at)
        budget = YouTubeWriteBudget(workspace, limits)
        import resource

        resource.setrlimit(resource.RLIMIT_FSIZE, (limits.max_file_bytes,) * 2)
        with (
            open(os.devnull, "w") as sink,
            contextlib.redirect_stdout(sink),
            contextlib.redirect_stderr(sink),
            budget.install_in_child(),
        ):
            media = provider.download(url, workspace, options)
            limits.check_file(media.file_path)
            result = {
                "name": media.file_path.name,
                "title": media.metadata.title,
                "duration": media.metadata.duration_seconds,
            }
        encoded = json.dumps(result).encode()
        if len(encoded) > _RESULT_BYTES:
            raise ValueError
        sys.stdout.buffer.write(encoded)
    except (Exception, BudgetExceeded):
        print('{"error":"resource_acquisition_failed"}')
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
