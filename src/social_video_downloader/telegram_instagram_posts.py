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
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from social_video_downloader.domain.carousel import (
    CarouselIssue,
    CarouselItemKind,
    CarouselPlanState,
)
from social_video_downloader.domain.errors import (
    DownloadCleanupError,
    DownloaderError,
    InvalidMediaURLError,
    MediaProcessingError,
)
from social_video_downloader.domain.models import MediaMetadata
from social_video_downloader.domain.urls import instagram_item_position
from social_video_downloader.infrastructure.telegram_carousel import (
    CarouselDeliveryCancelled,
    CarouselDeliveryError,
    CarouselDeliveryLimits,
    TelegramCarouselDelivery,
)
from social_video_downloader.infrastructure.workspace import quarantinable_workspace
from social_video_downloader.operation_logging import Operation
from social_video_downloader.providers.instagram import InstagramProvider
from social_video_downloader.services.instagram_acquisition import (
    CarouselAcquisitionLimits,
    InstagramCarouselAcquisition,
    validate_plan,
)
from social_video_downloader.services.instagram_carousel import InstagramCarouselService
from social_video_downloader.telegram_instagram import (
    _SEND_SECONDS,
    _WORK_SECONDS,
    _Guard,
    _owned_worker,
)
from social_video_downloader.telegram_instagram_interactions import (
    InstagramChoiceStore,
    parse_instagram_callback,
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
        self._choices = InstagramChoiceStore()

    async def _offer_choice(self, message, plan, position):
        validate_plan(plan, _ACQUISITION_LIMITS)
        if position > len(plan.items):
            await message.answer("Такого элемента в публикации нет. Проверь номер в ссылке.")
            return
        item = plan.items[position - 1]
        plans = (plan,)
        if item.kind is CarouselItemKind.VIDEO:
            plans += (InstagramCarouselService.select_video(plan, position),)
            text = f"Ты выбрал видео №{position} из Instagram-карусели. Что скачать?"
        else:
            text = (
                f"Элемент №{position} — фотография. Фото пока не скачиваются. "
                "Можно скачать все видео из этой публикации."
            )
        user_id = getattr(message.from_user, "id", None)
        if type(user_id) is not int:
            await message.answer("Не удалось определить владельца выбора.")
            return
        choice = self._choices.create(user_id, message.chat.id, plans)
        if choice is None:
            await message.answer("Бот занят, попробуйте позже.")
            return
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=label, callback_data=f"ig:v1:{choice.token}:{index}")]
                for index, label in enumerate(
                    ("Все видео из карусели", f"Только видео №{position}")[: len(plans)]
                )
            ]
        )
        try:
            sent = await message.answer(text, reply_markup=keyboard)
            if (
                not isinstance(sent, Message)
                or sent.chat.id != message.chat.id
                or not self._choices.bind(choice.token, sent.message_id)
            ):
                self._choices.remove(choice.token)
        except BaseException:
            self._choices.remove(choice.token)
            raise

    async def handle_callback(self, callback):
        parsed = parse_instagram_callback(callback.data)
        message = callback.message
        if parsed is None or not isinstance(message, Message):
            with suppress(TelegramAPIError, TimeoutError):
                await callback.answer("Выбор устарел. Отправь ссылку заново.")
            return
        token, index = parsed
        args = (token, index, callback.from_user.id, message.chat.id, message.message_id)
        if self._choices.resolve(*args) is None:
            with suppress(TelegramAPIError, TimeoutError):
                await callback.answer("Выбор устарел или принадлежит другому пользователю.")
            return
        owner = self._reel_handler
        if owner._active:
            with suppress(TelegramAPIError, TimeoutError):
                await callback.answer("Бот занят, попробуйте позже.")
            return  # The choice remains pending; never consume a busy request.
        owner._active = True  # No await between admission check and reservation.
        with Operation("instagram", "download") as operation:
            try:
                guard = _Guard(Event(), seconds=_ACQUISITION_LIMITS.max_seconds)
                try:
                    async with asyncio.timeout(10):
                        await callback.answer("Начинаю скачивание…")
                except (TelegramAPIError, TimeoutError) as error:
                    operation.fail(error)
                    return  # Keep the choice available if acknowledgement failed.
                plan = self._choices.resolve(*args, consume=True)
                if plan is None:
                    operation.fail(category="refused")
                    return
                with suppress(TelegramAPIError, TimeoutError):
                    async with asyncio.timeout(10):
                        await message.edit_reply_markup(reply_markup=None)
                await self._send_carousel(message, plan, guard, operation)
            except DownloadCleanupError as error:
                owner._blocked = True
                operation.fail(error)
                with suppress(TelegramAPIError):
                    await message.answer("Instagram временно недоступен. Попробуй позже.")
            except CarouselDeliveryError as error:
                operation.fail(error)
                with suppress(TelegramAPIError):
                    await message.answer(
                        "Не удалось подтвердить отправку видео. Автоматического повтора не будет."
                    )
            except (DownloaderError, TelegramAPIError, TimeoutError, OSError) as error:
                operation.fail(error)
                with suppress(TelegramAPIError):
                    await message.answer(
                        "Не удалось скачать или подготовить видео. "
                        "Автоматического повтора не будет."
                    )
            finally:
                if not owner._blocked:
                    owner._active = False

    async def _send_single(self, message: Message, metadata, provider, guard, operation) -> None:
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
                try:
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
                    operation.phase = "upload"
                    sending = True
                    async with asyncio.timeout(send_seconds):
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
                else "Не удалось скачать или подготовить публикацию в пределах лимитов."
            )
            with suppress(TelegramAPIError):
                await message.answer(text)

    async def _send_carousel(self, message, plan, guard, operation):
        interrupted_delivery = None
        with quarantinable_workspace() as directory:
            workspace = directory.resolve()
            try:
                async with asyncio.timeout(_remaining(guard)):
                    limits = replace(_ACQUISITION_LIMITS, max_seconds=_remaining(guard))
                    collection = await InstagramCarouselAcquisition(limits).acquire(plan, workspace)
                    guard.check()
                    operation.phase = "prepare_upload"
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
            except TimeoutError as error:
                # The shared deadline may interrupt an upload. Retain the transport's
                # uncertainty instead of describing this as a pre-delivery failure.
                if interrupted_delivery is not None:
                    failure = CarouselDeliveryError("deadline", interrupted_delivery)
                    operation.fail(failure)
                    raise failure from None
                operation.fail(error)
                raise
            except BaseException as error:
                operation.fail(error)
                raise
            finally:
                operation.phase = "cleanup"

    async def handle(self, message: Message, raw_url: str, canonical: str) -> None:
        try:
            position = instagram_item_position(raw_url)
        except InvalidMediaURLError:
            await message.answer(
                "Некорректный или неоднозначный номер элемента Instagram. "
                "Нужна ссылка с одним img_index."
            )
            return
        owner = self._reel_handler
        if owner._active:
            await message.answer("Уже обрабатываю Instagram-ссылку. Отправь следующую позже.")
            return
        owner._active = True
        with Operation("instagram", "metadata") as operation:
            guard = _Guard(Event(), seconds=_ACQUISITION_LIMITS.max_seconds)
            try:
                # The service validates the RAW query and fragment before using canonical identity.
                # The metadata extractor runs outside the event loop; cancellation waits for it.
                provider = InstagramProvider(lambda options: guard.ydl(owner._ydl_factory, options))
                service = InstagramCarouselService(provider)
                async with asyncio.timeout(_remaining(guard)):
                    task = asyncio.get_running_loop().run_in_executor(
                        None,
                        service.inspect_publication
                        if position is None
                        else service.inspect_item_reference,
                        raw_url,
                    )
                    plan = await _owned_worker(task, guard.cancelled)
                guard.check()
                if isinstance(plan, MediaMetadata):
                    operation.phase = "download_prepare"
                    await self._send_single(message, plan, provider, guard, operation)
                    return
                if plan.state is CarouselPlanState.BLOCKED:
                    operation.fail(category="refused")
                    if plan.issue in {
                        CarouselIssue.ITEM_REFERENCE_UNSUPPORTED,
                        CarouselIssue.AMBIGUOUS_REFERENCE,
                    }:
                        await message.answer(
                            "Нужна ссылка на публикацию целиком без выбора отдельных элементов "
                            "и неизвестных параметров."
                        )
                    elif plan.issue is CarouselIssue.NO_VIDEOS:
                        await message.answer(
                            "В публикации нет доступных видео. Фото не скачиваются."
                        )
                    else:
                        await message.answer(
                            "Невозможно безопасно скачать всю карусель: один или несколько "
                            "элементов недоступны или не распознаны."
                        )
                    return

                if position is not None:
                    async with asyncio.timeout(_remaining(guard)):
                        await self._offer_choice(message, plan, position)
                    return

                if len(plan.selected_videos) > _ACQUISITION_LIMITS.max_videos:
                    operation.fail(category="refused")
                    await message.answer(
                        f"В публикации {len(plan.selected_videos)} видео. Сейчас лимит — "
                        f"{_ACQUISITION_LIMITS.max_videos}; пропускать остальные не будем."
                    )
                    return

                guard.check()
                async with asyncio.timeout(_remaining(guard)):
                    await message.answer("Карусель распознана. Подготавливаю видео к отправке…")
                guard.check()
                operation.phase = "download"
                await self._send_carousel(message, plan, guard, operation)
            except DownloadCleanupError as error:
                owner._blocked = True
                operation.fail(error)
                with suppress(TelegramAPIError):
                    await message.answer("Instagram временно недоступен. Попробуй позже.")
            except CarouselDeliveryError as error:
                operation.fail(error)
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
            except (DownloaderError, TelegramAPIError, TimeoutError, OSError) as error:
                operation.fail(error)
                with suppress(TelegramAPIError):
                    await message.answer(
                        "Не удалось скачать или подготовить публикацию в пределах лимитов. "
                        "Неполные карусели намеренно не отправляются."
                    )
            finally:
                if not owner._blocked:
                    owner._active = False
