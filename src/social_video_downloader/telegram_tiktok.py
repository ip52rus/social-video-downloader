"""Opt-in public TikTok delivery with bounded admission on the existing bot."""

import asyncio
from contextlib import suppress
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from aiogram.exceptions import TelegramAPIError
from aiogram.types import FSInputFile, Message

from social_video_downloader.domain.errors import (
    DownloadCleanupError,
    DownloaderError,
    MediaProcessingError,
)
from social_video_downloader.infrastructure.tiktok_native import FILE_BYTES
from social_video_downloader.operation_logging import Operation
from social_video_downloader.providers.tiktok import TikTokProvider
from social_video_downloader.telegram_i18n import tr

SEND_SECONDS = 120


async def _owned_worker(future, cancelled):
    """Do not abandon an executor thread when its awaiting handler is cancelled."""
    interrupted = False
    while not future.done():
        try:
            await asyncio.shield(future)
        except asyncio.CancelledError:
            cancelled.set()
            interrupted = True
        except Exception:
            break
    if interrupted:
        if not future.cancelled():
            error = future.exception()
            if isinstance(error, DownloadCleanupError):
                raise error
        raise asyncio.CancelledError
    return future.result()


async def _notice(message, text):
    with suppress(TelegramAPIError, TimeoutError):
        async with asyncio.timeout(10):
            await message.answer(text)


class TelegramTikTokHandler:
    def __init__(self, *, max_concurrent=2, provider=None):
        if type(max_concurrent) is not int or not 1 <= max_concurrent <= 8:
            raise ValueError("TikTok concurrency must be an integer from 1 to 8.")
        self._max_concurrent = max_concurrent
        self._provider = provider or TikTokProvider()
        self._active_users: set[int] = set()
        self._blocked = False

    def allows(self, message):
        user_id = getattr(getattr(message, "from_user", None), "id", None)
        return type(user_id) is int and 0 < user_id < 2**63

    def _prepare(self, url, workspace, cancelled):
        media, parameters = self._provider.download_prepared(url, workspace, cancelled=cancelled)
        path = media.file_path
        if (
            path.is_symlink()
            or not path.is_file()
            or path.resolve().parent != workspace
            or not 0 < path.stat().st_size <= FILE_BYTES
        ):
            raise MediaProcessingError("Invalid prepared TikTok output.")
        safe_parameters = {
            key: value
            for key, value in parameters.items()
            if key in {"width", "height", "duration"} and type(value) is int and value > 0
        }
        if not {"width", "height"} <= safe_parameters.keys():
            raise MediaProcessingError("Missing TikTok display dimensions.")
        return path, safe_parameters

    async def handle(self, message: Message, raw_url: str) -> None:
        if not self.allows(message):
            await _notice(
                message, tr("TikTok downloads aren't available for this account right now.")
            )
            return
        try:
            url = self._provider.canonical_url(raw_url)
        except DownloaderError:
            await _notice(message, tr("Send a full or short link to a public TikTok video."))
            return
        if self._blocked:
            await _notice(
                message, tr("TikTok downloads are paused after an operation cleanup error.")
            )
            return
        user_id = message.from_user.id
        # One dispatcher/event loop owns admission. No await between checking
        # capacity/user ownership and reserving: no waiters, queue or extra tasks.
        if user_id in self._active_users or len(self._active_users) >= self._max_concurrent:
            await _notice(message, tr("The bot is busy. Try again later."))
            return
        self._active_users.add(user_id)
        with Operation("tiktok", "download_prepare") as operation:
            sending = False
            directory = None
            quarantine = False
            cleanup_failed = False
            try:
                await _notice(message, tr("TikTok link recognized. Starting download…"))
                directory = TemporaryDirectory(prefix="telegram-tiktok-")
                cancelled = Event()
                # Executor Future is shielded directly, rather than a cancellable
                # to_thread Task whose thread could outlive workspace ownership.
                future = asyncio.get_running_loop().run_in_executor(
                    None, self._prepare, url, Path(directory.name).resolve(), cancelled
                )
                try:
                    path, parameters = await _owned_worker(future, cancelled)
                    operation.phase = "upload"
                    sending = True
                    async with asyncio.timeout(SEND_SECONDS):
                        sent = await message.answer_video(
                            FSInputFile(path),
                            caption=tr("TikTok video"),
                            supports_streaming=True,
                            **parameters,
                        )
                    if (
                        not isinstance(sent, Message)
                        or sent.video is None
                        or sent.message_id <= 0
                        or sent.chat.id != message.chat.id
                    ):
                        raise MediaProcessingError("Unconfirmed Telegram response.")
                finally:
                    cancelled.set()
                    if not future.done():
                        await _owned_worker(future, cancelled)
            except DownloadCleanupError as error:
                operation.fail(error)
                quarantine = self._blocked = True
                await _notice(
                    message,
                    tr("Couldn't safely finish the operation. TikTok downloads are paused."),
                )
            except (DownloaderError, TelegramAPIError, TimeoutError, OSError) as error:
                operation.fail(error)
                await _notice(
                    message,
                    tr("Couldn't confirm video delivery. There will be no automatic retry.")
                    if sending
                    else tr("Couldn't download or prepare the TikTok video. Try another link."),
                )
            except Exception as error:
                operation.fail(error)
                await _notice(message, tr("Couldn't process the TikTok video."))
            except BaseException as error:
                operation.fail(error)
                raise
            finally:
                operation.phase = "cleanup"
                if directory is not None:
                    if quarantine:
                        directory._finalizer.detach()
                    else:
                        try:
                            directory.cleanup()
                        except Exception as error:
                            operation.fail(error)
                            cleanup_failed = quarantine = self._blocked = True
                            directory._finalizer.detach()
                # Failed cleanup keeps its reservation, even if the notification is
                # cancelled. Another admitted operation retains its own lifecycle.
                if not quarantine:
                    self._active_users.remove(user_id)
                if cleanup_failed:
                    await _notice(
                        message, tr("Operation cleanup failed. TikTok downloads are paused.")
                    )
