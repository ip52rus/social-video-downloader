"""Opt-in Instagram Reel and post entry points; no alternate polling loop."""

import asyncio
import os
import shutil
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic
from urllib.parse import urlsplit

import yt_dlp
from aiogram.exceptions import TelegramAPIError
from aiogram.types import FSInputFile, Message

from social_video_downloader.domain.errors import (
    DownloaderError,
    DownloadFailedError,
    DownloadTimeoutError,
    InvalidMediaURLError,
    MediaProcessingError,
)
from social_video_downloader.domain.urls import has_instagram_item_reference
from social_video_downloader.infrastructure.telegram_media import (
    inspect_telegram_video,
    prepare_telegram_video,
    telegram_video_upload_parameters,
)
from social_video_downloader.operation_logging import Operation
from social_video_downloader.providers.instagram import InstagramProvider

_MAX_BYTES = 25 * 1024**2
_WORK_SECONDS = 180
_SEND_SECONDS = 120
_FFMPEG_LIMIT = (
    "import os,resource,sys; "
    "n=int(sys.argv[1]); resource.setrlimit(resource.RLIMIT_FSIZE,(n,n)); "
    "os.execvp(sys.argv[2],sys.argv[2:])"
)


def _reel_url(raw: str) -> str:
    canonical = InstagramProvider._media_url(raw)
    if not urlsplit(canonical).path.startswith("/reel/"):
        raise InvalidMediaURLError("Reel URLs only.")
    if has_instagram_item_reference(raw):
        raise InvalidMediaURLError("Item references are unsupported.")
    return canonical


class _PreparationStopped(BaseException):
    """A write/deadline/cancellation limit must not trigger conversion fallback."""


class _Guard:
    def __init__(self, cancelled, *, max_bytes=_MAX_BYTES, seconds=_WORK_SECONDS):
        self.cancelled = cancelled
        self.started = monotonic()
        self.deadline = self.started + seconds
        self.max_bytes = max_bytes
        self.received = 0

    def check(self, *_):
        if self.cancelled.is_set() or monotonic() >= self.deadline:
            raise DownloadTimeoutError("Reel operation stopped.")

    def wrap(self, response):
        read = response.read

        def bounded_read(size=-1):
            self.check()
            remaining = self.max_bytes - self.received
            if remaining <= 0:
                response.close()
                raise DownloadFailedError("Reel media limit reached.")
            chunk = read(min(64 * 1024, remaining, size if size >= 0 else remaining))
            self.received += len(chunk)
            self.check()
            if len(chunk) > remaining:
                raise DownloadFailedError("Media response exceeded its bounded read.")
            return chunk

        response.read = bounded_read
        return response

    def ydl(self, factory, options):
        self.check()
        downloading = "outtmpl" in options
        if downloading:
            options = {
                **options,
                "max_filesize": self.max_bytes,
                "progress_hooks": [self.check],
                "buffersize": 64 * 1024,
                "noresizebuffer": True,
                "continuedl": False,
                "http_chunk_size": 0,
                "fixup": "never",
                "postprocessors": [],
                "external_downloader": None,
            }
        ydl = factory(options)
        original_open = ydl.urlopen
        opened = False

        def checked_open(request):
            nonlocal opened
            self.check()
            if downloading and opened:
                raise DownloadFailedError("Repeated Reel acquisition is not permitted.")
            opened = True
            response = original_open(request)
            try:
                self.check()
            except DownloaderError:
                response.close()
                raise
            return self.wrap(response) if downloading else response

        ydl.urlopen = checked_open
        return ydl

    def run(self, command, **kwargs):
        try:
            self.check()
            command = [command[0], "-protocol_whitelist", "file,pipe", *command[1:]]
            if command[0] == "ffmpeg":
                # exec keeps the subprocess PID: run(timeout=...) kills the actual
                # FFmpeg writer, not a wrapper that leaves a writer behind.
                command = [sys.executable, "-c", _FFMPEG_LIMIT, str(self.max_bytes), *command]
            result = subprocess.run(
                command, timeout=max(0.001, self.deadline - monotonic()), **kwargs
            )
            self.check()
            return result
        except (DownloaderError, OSError, subprocess.SubprocessError):
            # Fail closed; do not reinterpret timeout/size stops as permission to
            # attempt another preparation command through the helper's fallback.
            raise _PreparationStopped from None


async def _owned_worker(task, cancelled):
    interrupted = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled.set()
            interrupted = True
        except Exception:
            break
    if interrupted:
        if not task.cancelled():
            task.exception()
        raise asyncio.CancelledError
    return task.result()


class InstagramReelHandler:
    """One active Reel per instance; worker ownership outlives handler cancellation."""

    def __init__(self, *, ydl_factory=None):
        self._ydl_factory = ydl_factory or yt_dlp.YoutubeDL
        self._active = False

    def _prepare(self, url, workspace, guard, *, provider=None):
        if os.name != "posix":
            raise MediaProcessingError("Limited Reel testing requires POSIX.")
        if shutil.disk_usage(workspace).free < 3 * guard.max_bytes:
            raise MediaProcessingError("Insufficient isolated Reel workspace space.")
        guard.check()
        provider = provider or InstagramProvider(
            lambda options: guard.ydl(self._ydl_factory, options)
        )
        downloaded = provider.download(url, workspace)
        guard.check()
        source = downloaded.file_path
        if source.is_symlink() or source.resolve().parent != workspace or not source.is_file():
            raise MediaProcessingError("Invalid Reel output path.")
        if not 0 < source.stat().st_size <= guard.max_bytes:
            raise MediaProcessingError("Reel file size exceeds the MVP limit.")
        try:
            prepared = prepare_telegram_video(source, runner=guard.run, allow_silent=True)
            data = inspect_telegram_video(prepared, runner=guard.run)
        except _PreparationStopped:
            raise MediaProcessingError("Reel preparation stopped within its limits.") from None
        guard.check()
        if (
            prepared.is_symlink()
            or prepared.resolve().parent != workspace
            or not 0 < prepared.stat().st_size <= guard.max_bytes
        ):
            raise MediaProcessingError("Invalid prepared Reel output.")
        return prepared, telegram_video_upload_parameters(data)

    async def handle(self, message: Message, raw_url: str) -> None:
        try:
            canonical = InstagramProvider._media_url(raw_url)
            if urlsplit(canonical).path.startswith("/p/"):
                # Import lazily: the /p/ handler reuses the Reel handler's bounded worker.
                from social_video_downloader.telegram_instagram_posts import InstagramPostHandler

                await InstagramPostHandler(self).handle(message, raw_url, canonical)
                return
            url = _reel_url(raw_url)
        except InvalidMediaURLError:
            await message.answer(
                "Поддерживаются публичные Reels и публикации /p/. "
                "Ссылки на отдельные элементы и другие страницы не поддерживаются."
            )
            return
        if self._active:
            await message.answer("Уже обрабатываю Reel. Дождись завершения и отправь ссылку позже.")
            return
        self._active = True
        with Operation("instagram", "download_prepare") as operation:
            sending = False
            try:
                await message.answer("Ссылка Reel распознана. Начинаю скачивание…")
                with TemporaryDirectory(prefix="instagram-reel-") as directory:
                    try:
                        cancelled = Event()
                        guard = _Guard(cancelled)
                        # An executor Future is shielded directly. A separate to_thread Task
                        # could itself be cancelled during shutdown while its thread survives.
                        task = asyncio.get_running_loop().run_in_executor(
                            None, self._prepare, url, Path(directory).resolve(), guard
                        )
                        prepared, parameters = await _owned_worker(task, cancelled)
                        operation.phase = "upload"
                        sending = True
                        async with asyncio.timeout(_SEND_SECONDS):
                            sent = await message.answer_video(
                                FSInputFile(prepared),
                                **parameters,
                                supports_streaming=True,
                            )
                        if not isinstance(sent, Message) or sent.video is None:
                            raise MediaProcessingError("Unconfirmed Telegram video response.")
                    except BaseException as error:
                        operation.fail(error)
                        raise
                    finally:
                        operation.phase = "cleanup"

            except (DownloaderError, TelegramAPIError, TimeoutError) as error:
                operation.fail(error)
                text = (
                    "Не удалось подтвердить отправку видео. Автоматического повтора не будет."
                    if sending
                    else "Не удалось скачать или подготовить Reel в пределах лимитов."
                )
                with suppress(TelegramAPIError):
                    await message.answer(text)
            finally:
                self._active = False
