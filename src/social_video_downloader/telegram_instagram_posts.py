"""Bounded Telegram /p/ integration using the existing Instagram pipelines."""

import asyncio
from contextlib import suppress
from dataclasses import replace
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic

from aiogram.exceptions import TelegramAPIError
from aiogram.types import FSInputFile, Message

from social_video_downloader.domain.carousel import CarouselIssue, CarouselPlanState
from social_video_downloader.domain.errors import DownloaderError, MediaProcessingError
from social_video_downloader.domain.models import MediaMetadata
from social_video_downloader.infrastructure.telegram_carousel import (
    CarouselDeliveryCancelled,
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
from social_video_downloader.telegram_instagram import (
    _SEND_SECONDS,
    _WORK_SECONDS,
    _Guard,
    _owned_worker,
)

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


def _remaining(guard):
    guard.check()
    return max(0, guard.deadline - monotonic())


class InstagramPostHandler:
    """One /p/ request shares the Reel handler's active slot and single-file worker."""

    def __init__(self, reel_handler):
        self._reel_handler = reel_handler

    async def _send_single(self, message: Message, metadata, provider, guard) -> None:
        """Consume the positively inspected snapshot through the existing worker."""
        sending = False
        operation_deadline = guard.deadline
        # Preserve the 180-second work cap and 120-second send cap. Both consume
        # the same operation window, rather than starting a new timer after inspection.
        guard.deadline = min(guard.deadline, guard.started + _WORK_SECONDS)
        try:
            guard.check()
            async with asyncio.timeout(_remaining(guard)):
                await message.answer("Одиночное видео Instagram распознано. Начинаю скачивание…")
            guard.check()
            with TemporaryDirectory(prefix="instagram-post-") as directory:
                async with asyncio.timeout(_remaining(guard)):
                    task = asyncio.get_running_loop().run_in_executor(
                        None,
                        partial(
                            self._reel_handler._prepare,
                            metadata.source_url,
                            Path(directory).resolve(),
                            guard,
                            provider=provider,
                        ),
                    )
                    prepared, parameters = await _owned_worker(task, guard.cancelled)
                guard.check()
                guard.deadline = operation_deadline
                send_seconds = min(_SEND_SECONDS, _remaining(guard))
                sending = True
                async with asyncio.timeout(send_seconds):
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

    async def _send_carousel(self, message, plan, guard):
        interrupted_delivery = None
        with TemporaryDirectory(prefix="instagram-carousel-") as directory:
            workspace = Path(directory).resolve()
            try:
                async with asyncio.timeout(_remaining(guard)):
                    limits = replace(_ACQUISITION_LIMITS, max_seconds=_remaining(guard))
                    collection = await InstagramCarouselAcquisition(limits).acquire(plan, workspace)
                    guard.check()
                    try:
                        progress = await TelegramCarouselDelivery(
                            message.bot, _DELIVERY_LIMITS
                        ).deliver(
                            collection, plan=plan, workspace=workspace, chat_id=message.chat.id
                        )
                    except CarouselDeliveryCancelled as error:
                        interrupted_delivery = error.progress
                        raise
                    if not progress.complete:
                        raise MediaProcessingError("Unconfirmed complete carousel delivery.")
            except TimeoutError:
                # The shared deadline may interrupt an upload. Retain the transport's
                # uncertainty instead of describing this as a pre-delivery failure.
                if interrupted_delivery is not None:
                    raise CarouselDeliveryError("deadline", interrupted_delivery) from None
                raise

    async def handle(self, message: Message, raw_url: str, canonical: str) -> None:
        owner = self._reel_handler
        if owner._active:
            await message.answer("Уже обрабатываю Instagram-ссылку. Отправь следующую позже.")
            return
        owner._active = True
        guard = _Guard(Event(), seconds=_ACQUISITION_LIMITS.max_seconds)
        try:
            # The service validates the RAW query and fragment before using canonical identity.
            # The metadata extractor runs outside the event loop; cancellation waits for it.
            provider = InstagramProvider(lambda options: guard.ydl(owner._ydl_factory, options))
            service = InstagramCarouselService(provider)
            async with asyncio.timeout(_remaining(guard)):
                task = asyncio.get_running_loop().run_in_executor(
                    None, service.inspect_publication, raw_url
                )
                plan = await _owned_worker(task, guard.cancelled)
            guard.check()
            if isinstance(plan, MediaMetadata):
                await self._send_single(message, plan, provider, guard)
                return
            if plan.state is CarouselPlanState.BLOCKED:
                if plan.issue in {
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

            if len(plan.selected_videos) > _ACQUISITION_LIMITS.max_videos:
                await message.answer(
                    f"В публикации {len(plan.selected_videos)} видео. Сейчас лимит — "
                    f"{_ACQUISITION_LIMITS.max_videos}; пропускать остальные не будем."
                )
                return

            guard.check()
            async with asyncio.timeout(_remaining(guard)):
                await message.answer("Карусель распознана. Подготавливаю видео к отправке…")
            guard.check()
            await self._send_carousel(message, plan, guard)
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
