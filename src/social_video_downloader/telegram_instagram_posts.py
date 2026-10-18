"""Bounded Telegram /p/ integration using the existing Instagram pipelines."""

import asyncio
from contextlib import suppress
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from aiogram.exceptions import TelegramAPIError
from aiogram.types import FSInputFile, Message

from social_video_downloader.domain.carousel import CarouselIssue, CarouselPlanState
from social_video_downloader.domain.errors import DownloaderError, MediaProcessingError
from social_video_downloader.infrastructure.telegram_carousel import (
    CarouselDeliveryError,
    CarouselDeliveryLimits,
    TelegramCarouselDelivery,
)
from social_video_downloader.providers.instagram import InstagramProvider
from social_video_downloader.services.instagram_acquisition import (
    CarouselAcquisitionLimits,
    InstagramCarouselAcquisition,
)
from social_video_downloader.services.instagram_carousel import InstagramCarouselService
from social_video_downloader.telegram_instagram import _SEND_SECONDS, _Guard, _owned_worker

# Conservative initial opt-in gate. Refuse an oversized publication; never truncate it.
_ACQUISITION_LIMITS = CarouselAcquisitionLimits(
    max_videos=10,
    max_file_bytes=25 * 1024**2,
    max_total_bytes=100 * 1024**2,
    max_temp_bytes=130 * 1024**2,
    max_seconds=300,
)
_DELIVERY_LIMITS = CarouselDeliveryLimits(
    max_videos=10,
    max_upload_file_bytes=25 * 1024**2,
    max_upload_total_bytes=100 * 1024**2,
    max_workspace_bytes=400 * 1024**2,
    max_workspace_entries=256,
    max_prepare_seconds=180,
    max_send_seconds=120,
)


class InstagramPostHandler:
    """One /p/ request shares the Reel handler's active slot and single-file worker."""

    def __init__(self, reel_handler):
        self._reel_handler = reel_handler

    async def _send_single(self, message: Message, url: str) -> None:
        """Keep the existing single-file acquisition and Telegram video preparation."""
        sending = False
        try:
            await message.answer("Одиночное видео Instagram распознано. Начинаю скачивание…")
            with TemporaryDirectory(prefix="instagram-post-") as directory:
                cancelled = Event()
                guard = _Guard(cancelled)
                task = asyncio.get_running_loop().run_in_executor(
                    None, self._reel_handler._prepare, url, Path(directory).resolve(), guard
                )
                prepared, parameters = await _owned_worker(task, cancelled)
                sending = True
                async with asyncio.timeout(_SEND_SECONDS):
                    sent = await message.answer_video(
                        FSInputFile(prepared),
                        **parameters,
                        supports_streaming=True,
                    )
                if not isinstance(sent, Message) or sent.video is None:
                    raise MediaProcessingError("Unconfirmed Telegram video response.")
        except (DownloaderError, TelegramAPIError, TimeoutError):
            text = (
                "Не удалось подтвердить отправку видео. Автоматического повтора не будет."
                if sending
                else "Не удалось скачать или подготовить публикацию в пределах лимитов."
            )
            with suppress(TelegramAPIError):
                await message.answer(text)

    async def handle(self, message: Message, raw_url: str, canonical: str) -> None:
        owner = self._reel_handler
        if owner._active:
            await message.answer("Уже обрабатываю Instagram-ссылку. Отправь следующую позже.")
            return
        owner._active = True
        try:
            # The service validates the RAW query and fragment before using canonical identity.
            # The metadata extractor runs outside the event loop; cancellation waits for it.
            provider = InstagramProvider(owner._ydl_factory)
            service = InstagramCarouselService(provider)
            task = asyncio.get_running_loop().run_in_executor(
                None, service.create_selection_plan, raw_url
            )
            plan = await _owned_worker(task, Event())
            if plan.state is CarouselPlanState.BLOCKED:
                if plan.issue is CarouselIssue.UNSUPPORTED_CONTENT:
                    # A genuine single-video /p/ is not a playlist. The existing
                    # single-file provider independently rejects every collection.
                    await self._send_single(message, canonical)
                elif plan.issue in {
                    CarouselIssue.ITEM_REFERENCE_UNSUPPORTED,
                    CarouselIssue.AMBIGUOUS_REFERENCE,
                }:
                    await message.answer(
                        "Нужна ссылка на публикацию целиком без выбора отдельных элементов "
                        "и неизвестных параметров."
                    )
                elif plan.issue is CarouselIssue.NO_VIDEOS:
                    await message.answer("В публикации нет доступных видео. Фото не скачиваются.")
                else:
                    await message.answer(
                        "Невозможно безопасно скачать всю карусель: один или несколько "
                        "элементов недоступны или не распознаны."
                    )
                return

            await message.answer("Карусель распознана. Подготавливаю видео к отправке…")
            with TemporaryDirectory(prefix="instagram-carousel-") as directory:
                workspace = Path(directory).resolve()
                collection = await InstagramCarouselAcquisition(
                    _ACQUISITION_LIMITS
                ).acquire(plan, workspace)
                progress = await TelegramCarouselDelivery(
                    message.bot, _DELIVERY_LIMITS
                ).deliver(
                    collection, plan=plan, workspace=workspace, chat_id=message.chat.id
                )
                if not progress.complete:
                    raise MediaProcessingError("Unconfirmed complete carousel delivery.")
        except CarouselDeliveryError as error:
            progress = error.progress
            confirmed = len(progress.confirmed_positions)
            if progress.uncertain_positions:
                text = (
                    "Не удалось подтвердить отправку всей карусели. "
                    "Часть видео могла быть доставлена; автоматического повтора не будет."
                )
            elif confirmed:
                text = (
                    f"Подтверждена отправка {confirmed} из {progress.total_videos} видео. "
                    "Остальные не отправлены; автоматического повтора не будет."
                )
            else:
                text = "Не удалось подготовить или отправить карусель. Автоповтора не будет."
            with suppress(TelegramAPIError):
                await message.answer(text)
        except (DownloaderError, TelegramAPIError, TimeoutError, OSError):
            with suppress(TelegramAPIError):
                await message.answer(
                    "Не удалось скачать или подготовить публикацию в пределах лимитов. "
                    "Неполные карусели намеренно не отправляются."
                )
        finally:
            owner._active = False
