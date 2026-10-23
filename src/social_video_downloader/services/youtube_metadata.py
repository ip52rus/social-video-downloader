"""Single-slot POSIX YouTube metadata ownership, private IPC and fail-closed reap."""

import asyncio
import os
import secrets
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from contextvars import copy_context
from functools import partial
from pathlib import Path
from threading import Lock
from time import monotonic

from social_video_downloader.domain.errors import (
    MetadataBusyError,
    MetadataCleanupError,
    MetadataExtractionError,
    MetadataTimeoutError,
)
from social_video_downloader.domain.models import Platform
from social_video_downloader.infrastructure.youtube_snapshot import (
    REQUEST_BYTES,
    RESPONSE_BYTES,
    decode,
    encode,
    request,
    response,
    validate_response,
)
from social_video_downloader.operation_logging import report_failure
from social_video_downloader.providers.youtube import YouTubeProvider
from social_video_downloader.services.choice_model import build_choice_plan


class _Choices:
    """A private immutable-in-use view; planning cannot miss a consumed shared cache."""

    platform = Platform.YOUTUBE

    def __init__(self, info):
        self.info = info

    def get_supported_modes(self, _url):
        return YouTubeProvider._supported_modes_from_info(self.info)

    def get_available_qualities(self, _url, mode):
        return YouTubeProvider._qualities_from_info(self.info, mode)


def _environment():
    # No Telegram credentials, cookies, HOME, proxy settings or inherited bot flags.
    env = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL") if key in os.environ}
    source = str(Path(__file__).resolve().parents[2])
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (source, os.environ.get("PYTHONPATH", ""))))
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
    return env


def _command():
    return [sys.executable, "-m", "social_video_downloader.infrastructure.youtube_metadata_worker"]


class YouTubeMetadata:
    """No queue; uncertain spawn/group cleanup permanently quarantines this slot."""

    def __init__(self, seconds=60.0, cleanup_seconds=5.0):
        if not 0 < cleanup_seconds < seconds:
            raise ValueError("Metadata deadline must include a cleanup reserve.")
        self.seconds, self.cleanup_seconds = seconds, cleanup_seconds
        self.active = False
        self.blocked = False
        self._admission = Lock()
        self._late_spawns = set()
        self._quarantined = set()
        # One finite CPU job at a time, admitted before submit. Keep codec/cache
        # validation independent of potentially hung legacy download executor work.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="youtube-metadata")

    def close(self):
        if self.active or self._late_spawns:
            raise RuntimeError("Metadata owner is still active.")
        self._executor.shutdown(wait=True)

    async def _cpu(self, function, *args):
        future = asyncio.wrap_future(
            self._executor.submit(partial(copy_context().run, function, *args))
        )
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            while not future.done():
                with suppress(asyncio.CancelledError, Exception):
                    await asyncio.shield(future)
            if not future.cancelled():
                future.exception()
            raise

    async def plan(self, provider, url):
        if self.active or self.blocked:
            raise MetadataBusyError("YouTube metadata admission unavailable.")
        if os.name != "posix":
            raise MetadataExtractionError("YouTube metadata requires POSIX ownership.")
        if not self._admission.acquire(blocking=False):
            raise MetadataBusyError("YouTube metadata admission unavailable.")
        self.active = True  # No wait/queue; also safe across concurrent service callers.
        deadline = monotonic() + self.seconds
        try:
            async with asyncio.timeout(self.seconds):
                canonical = provider._normalize_youtube_url(url)
                cached = await self._cpu(provider._planning_snapshot, canonical)
                req = request(canonical, secrets.token_urlsafe(24))
                if cached is not None:
                    stamp, info = cached
                    return await self._cpu(self._cached_plan, req, stamp, info)
                wire = encode(req, REQUEST_BYTES)
                raw = await self._exchange(wire, deadline)
                snapshot, plan = await self._cpu(self._decode_plan, raw, req)
                await self._cpu(provider._publish_snapshot, snapshot)
                return plan
        except asyncio.CancelledError:
            raise
        except MetadataExtractionError:
            raise
        except TimeoutError:
            raise MetadataTimeoutError("YouTube metadata deadline expired.") from None
        except Exception:
            raise MetadataExtractionError("YouTube metadata operation failed.") from None
        finally:
            self.active = False
            if not self.blocked:
                self._admission.release()

    @staticmethod
    def _cached_plan(req, stamp, info):
        snapshot = validate_response(response(req, info, stamp), req)
        return build_choice_plan(_Choices(snapshot.info), snapshot.url)

    @staticmethod
    def _decode_plan(raw, req):
        snapshot = validate_response(decode(raw), req)
        return snapshot, build_choice_plan(_Choices(snapshot.info), snapshot.url)

    async def _exchange(self, wire, deadline):
        creation = asyncio.create_task(
            asyncio.create_subprocess_exec(
                *_command(),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                start_new_session=True,
                env=_environment(),
                limit=64 * 1024,
            )
        )
        process = None
        cancellation = [False]
        try:
            async with asyncio.timeout(max(0, deadline - self.cleanup_seconds - monotonic())):
                process = await asyncio.shield(creation)
                process.stdin.write(wire)
                await process.stdin.drain()
                process.stdin.close()
                output = bytearray()
                while True:
                    chunk = await process.stdout.read(min(65536, RESPONSE_BYTES + 1 - len(output)))
                    if not chunk:
                        break
                    output.extend(chunk)
                    if len(output) > RESPONSE_BYTES:
                        raise MetadataExtractionError("YouTube metadata response exceeded budget.")
                await process.wait()
                if process.returncode != 0:
                    raise MetadataExtractionError("YouTube metadata worker failed.")
                return bytes(output)
        except asyncio.CancelledError:
            cancellation[0] = True
            raise
        finally:
            # Cleanup is in the owner itself, not a separately cancellable Task.
            try:
                await self._finish(creation, process, deadline, cancellation)
            except MetadataExtractionError:
                if cancellation[0]:
                    raise asyncio.CancelledError from None
                raise
            if cancellation[0]:
                raise asyncio.CancelledError

    async def _finish(self, creation, process, deadline, cancellation):
        if process is None:
            while not creation.done() and monotonic() < deadline:
                try:
                    async with asyncio.timeout(max(0, deadline - monotonic())):
                        await asyncio.shield(creation)
                except asyncio.CancelledError:
                    cancellation[0] = True
                except (TimeoutError, Exception):
                    break
            if not creation.done() or creation.cancelled():
                self.blocked = True
                self._quarantined.add(creation)
                if not creation.cancelled():
                    task = asyncio.create_task(self._late_spawn(creation))
                    self._late_spawns.add(task)
                    task.add_done_callback(self._late_spawns.discard)
                error = MetadataCleanupError("YouTube metadata spawn cleanup unconfirmed.")
                report_failure("youtube", "cleanup", error)
                raise error
            try:
                process = creation.result()
            except Exception:
                return  # Confirmed spawn failure: there is no process to own.
        try:
            await self._stop_group(process, deadline, cancellation)
        except BaseException:
            self.blocked = True
            self._quarantined.add(process)
            error = MetadataCleanupError("YouTube metadata process cleanup unconfirmed.")
            report_failure("youtube", "cleanup", error)
            raise error from None

    async def _late_spawn(self, creation):
        process = None
        try:
            process = await asyncio.shield(creation)
            await self._stop_group(process, monotonic() + self.cleanup_seconds, [False])
        except BaseException:
            if process is not None:
                self._quarantined.add(process)
            pass  # Quarantine remains; no exception/payload escapes as an unowned Task.

    @staticmethod
    def _group_exists(pid):
        try:
            os.killpg(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            # Darwin may deny probing a transient zombie-only group. Keep it
            # present/unknown and retry after reap; never interpret EPERM as absence.
            return True
        return True

    async def _stop_group(self, process, deadline, cancellation):
        with suppress(Exception):
            process.stdin.close()
        if self._group_exists(process.pid):
            with suppress(ProcessLookupError, PermissionError):
                os.killpg(process.pid, signal.SIGTERM)
        grace = min(deadline, monotonic() + 0.5)
        killed = False
        while True:
            group = self._group_exists(process.pid)
            if not group and process.returncode is not None:
                # An oversized/cancelled exchange may have paused its pipe reader.
                # Discard bounded chunks after group death so pipe transports reach
                # EOF too; communicate() would allocate the entire rejected reply.
                for stream in (process.stdout, process.stderr):
                    if stream is None:
                        continue
                    while not stream.at_eof():
                        try:
                            async with asyncio.timeout(max(0, deadline - monotonic())):
                                if not await stream.read(65536):
                                    break
                        except asyncio.CancelledError:
                            cancellation[0] = True
                await process.wait()  # Already reaped by asyncio's child watcher.
                return
            now = monotonic()
            if now >= grace and not killed:
                with suppress(ProcessLookupError, PermissionError):
                    os.killpg(process.pid, signal.SIGKILL)
                killed = True
            if now >= deadline:
                raise MetadataExtractionError("YouTube metadata group termination unconfirmed.")
            try:
                await asyncio.sleep(min(0.01, deadline - now))
            except asyncio.CancelledError:
                cancellation[0] = True
