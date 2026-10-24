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
from social_video_downloader.telegram_i18n import get_i18n, tr, trn
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
            await message.answer(
                tr("There is no such item in this post. Check the number in the link.")
            )
            return
        item = plan.items[position - 1]
        plans = (plan,)
        if item.kind is CarouselItemKind.VIDEO:
            plans += (InstagramCarouselService.select_video(plan, position),)
            text = tr(
                (
                    "You selected video #{position} in the Instagram carousel. What "
                    "would you like to download?"
                ),
                position=position,
            )
        else:
            text = tr(
                (
                    "Item #{position} is a photo. Photo downloads aren't supported yet."
                    " You can download all videos from this post."
                ),
                position=position,
            )
        user_id = getattr(message.from_user, "id", None)
        if type(user_id) is not int:
            await message.answer(tr("Couldn't identify the owner of this choice."))
            return
        choice = self._choices.create(
            user_id, message.chat.id, plans, locale=get_i18n().current_locale
        )
        if choice is None:
            await message.answer(tr("The bot is busy. Try again later."))
            return
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=label, callback_data=f"ig:v1:{choice.token}:{index}")]
                for index, label in enumerate(
                    (
                        tr("All videos in the carousel"),
                        tr("Only video #{position}", position=position),
                    )[: len(plans)]
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
                await callback.answer(tr("This choice has expired. Send the link again."))
            return
        token, index = parsed
        args = (token, index, callback.from_user.id, message.chat.id, message.message_id)
        selection = self._choices.resolve_selection(*args)
        if selection is None:
            with suppress(TelegramAPIError, TimeoutError):
                await callback.answer(tr("This choice has expired or belongs to another user."))
            return
        with get_i18n().use_locale(selection.locale):
            owner = self._reel_handler
            if owner._active:
                with suppress(TelegramAPIError, TimeoutError):
                    await callback.answer(tr("The bot is busy. Try again later."))
                return  # The choice remains pending; never consume a busy request.
            owner._active = True  # No await between admission check and reservation.
            with Operation("instagram", "download") as operation:
                try:
                    guard = _Guard(Event(), seconds=_ACQUISITION_LIMITS.max_seconds)
                    try:
                        async with asyncio.timeout(10):
                            await callback.answer(tr("Starting download…"))
                    except (TelegramAPIError, TimeoutError) as error:
                        operation.fail(error)
                        return  # Keep the choice available if acknowledgement failed.
                    selected = self._choices.resolve_selection(*args, consume=True)
                    if selected is None:
                        operation.fail(category="refused")
                        return
                    with suppress(TelegramAPIError, TimeoutError):
                        async with asyncio.timeout(10):
                            await message.edit_reply_markup(reply_markup=None)
                    await self._send_carousel(message, selected.plan, guard, operation)
                except DownloadCleanupError as error:
                    owner._blocked = True
                    operation.fail(error)
                    with suppress(TelegramAPIError):
                        await message.answer(
                            tr("Instagram is temporarily unavailable. Try again later.")
                        )
                except CarouselDeliveryError as error:
                    operation.fail(error)
                    with suppress(TelegramAPIError):
                        await message.answer(
                            tr("Couldn't confirm video delivery. There will be no automatic retry.")
                        )
                except (DownloaderError, TelegramAPIError, TimeoutError, OSError) as error:
                    operation.fail(error)
                    with suppress(TelegramAPIError):
                        await message.answer(
                            tr(
                                "Couldn't download or prepare the video. There will be no automatic"
                                " retry."
                            )
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
                await message.answer(tr("Single Instagram video recognized. Starting download…"))
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
                tr("Couldn't confirm video delivery. There will be no automatic retry.")
                if sending
                else tr("Couldn't download or prepare the post within the limits.")
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
                tr(
                    "Invalid or ambiguous Instagram item number. Use a link with "
                    "exactly one img_index."
                )
            )
            return
        owner = self._reel_handler
        if owner._active:
            await message.answer(
                tr("An Instagram link is already being processed. Send the next one later.")
            )
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
                            tr(
                                "Use a link to the whole post without individual item selectors or "
                                "unknown parameters."
                            )
                        )
                    elif plan.issue is CarouselIssue.NO_VIDEOS:
                        await message.answer(
                            tr("No videos are available in this post. Photos aren't downloaded.")
                        )
                    else:
                        await message.answer(
                            tr(
                                "Can't safely download the entire carousel: one or more items are "
                                "unavailable or unrecognized."
                            )
                        )
                    return

                if position is not None:
                    async with asyncio.timeout(_remaining(guard)):
                        await self._offer_choice(message, plan, position)
                    return

                if len(plan.selected_videos) > _ACQUISITION_LIMITS.max_videos:
                    operation.fail(category="refused")
                    await message.answer(
                        trn(
                            (
                                "This post has {count} video. The limit is {limit}; no videos will "
                                "be skipped."
                            ),
                            (
                                "This post has {count} videos. The limit is {limit}; no videos will"
                                " be skipped."
                            ),
                            count=len(plan.selected_videos),
                            limit=_ACQUISITION_LIMITS.max_videos,
                        )
                    )
                    return

                guard.check()
                async with asyncio.timeout(_remaining(guard)):
                    await message.answer(tr("Carousel recognized. Preparing videos to send…"))
                guard.check()
                operation.phase = "download"
                await self._send_carousel(message, plan, guard, operation)
            except DownloadCleanupError as error:
                owner._blocked = True
                operation.fail(error)
                with suppress(TelegramAPIError):
                    await message.answer(
                        tr("Instagram is temporarily unavailable. Try again later.")
                    )
            except CarouselDeliveryError as error:
                operation.fail(error)
                progress = error.progress
                confirmed = len(progress.confirmed_positions)
                if progress.uncertain_positions:
                    text = tr(
                        "Couldn't confirm delivery of the entire carousel. Some videos may "
                        "have been delivered; there will be no automatic retry."
                    )
                elif confirmed:
                    text = trn(
                        (
                            "Delivery confirmed: {count} video out of {total}. The rest were "
                            "not sent; there will be no automatic retry."
                        ),
                        (
                            "Delivery confirmed: {count} videos out of {total}. The rest were "
                            "not sent; there will be no automatic retry."
                        ),
                        count=confirmed,
                        total=progress.total_videos,
                    )
                else:
                    text = tr(
                        "Couldn't prepare or send the carousel. There will be no automatic retry."
                    )
                with suppress(TelegramAPIError):
                    await message.answer(text)
            except (DownloaderError, TelegramAPIError, TimeoutError, OSError) as error:
                operation.fail(error)
                with suppress(TelegramAPIError):
                    await message.answer(
                        tr(
                            "Couldn't download or prepare the post within the limits. "
                            "Incomplete carousels are not sent."
                        )
                    )
            finally:
                if not owner._blocked:
                    owner._active = False
