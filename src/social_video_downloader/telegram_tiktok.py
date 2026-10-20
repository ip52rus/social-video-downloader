"""Restricted TikTok experiment on the existing bot, without another poller."""

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
from social_video_downloader.providers.tiktok import TikTokProvider

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
    def __init__(self, allowed_user_ids=frozenset(), *, provider=None):
        self._allowed = frozenset(allowed_user_ids)
        self._provider = provider or TikTokProvider()
        self._active = False
        self._blocked = False

    def allows(self, message):
        user_id = getattr(getattr(message, "from_user", None), "id", None)
        return type(user_id) is int and user_id in self._allowed

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
            await _notice(message, "Загрузка TikTok сейчас недоступна для этого аккаунта.")
            return
        try:
            url = self._provider.canonical_url(raw_url)
        except DownloaderError:
            await _notice(message, "Отправь полную ссылку на отдельное публичное TikTok-видео.")
            return
        if self._blocked:
            await _notice(
                message, "Загрузка TikTok приостановлена после ошибки завершения операции."
            )
            return
        if self._active:
            await _notice(message, "Уже обрабатываю TikTok-видео. Дождись завершения.")
            return
        self._active = True
        sending = False
        directory = None
        quarantine = False
        try:
            await _notice(message, "Ссылка TikTok распознана. Начинаю скачивание…")
            directory = TemporaryDirectory(prefix="telegram-tiktok-")
            cancelled = Event()
            # Executor Future is shielded directly, rather than a cancellable
            # to_thread Task whose thread could outlive workspace ownership.
            future = asyncio.get_running_loop().run_in_executor(
                None, self._prepare, url, Path(directory.name).resolve(), cancelled
            )
            try:
                path, parameters = await _owned_worker(future, cancelled)
                sending = True
                async with asyncio.timeout(SEND_SECONDS):
                    sent = await message.answer_video(
                        FSInputFile(path),
                        caption="TikTok video",
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
        except DownloadCleanupError:
            quarantine = self._blocked = True
            await _notice(
                message, "Не удалось безопасно завершить операцию. Загрузка TikTok приостановлена."
            )
        except (DownloaderError, TelegramAPIError, TimeoutError, OSError):
            await _notice(
                message,
                "Не удалось подтвердить отправку видео. Автоматического повтора не будет."
                if sending
                else "Не удалось скачать или подготовить TikTok-видео. Попробуй другую ссылку.",
            )
        except Exception:
            await _notice(message, "Не удалось обработать TikTok-видео.")
        finally:
            if directory is not None:
                if quarantine:
                    directory._finalizer.detach()
                else:
                    try:
                        directory.cleanup()
                    except OSError:
                        self._blocked = True
                        directory._finalizer.detach()
                        await _notice(
                            message, "Ошибка очистки файлов. Загрузка TikTok приостановлена."
                        )
            self._active = False
