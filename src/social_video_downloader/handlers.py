"""Telegram command and URL-intake handlers."""

import asyncio
from collections.abc import Callable
from contextlib import suppress
from contextvars import copy_context
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError, TelegramEntityTooLarge
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from social_video_downloader.domain.errors import (
    DownloaderError,
    DownloadFailedError,
    InvalidMediaURLError,
    MediaProcessingError,
    MetadataBusyError,
    MetadataExtractionError,
    UnsupportedPlatformError,
)
from social_video_downloader.domain.models import DownloadMode, DownloadOptions, Platform
from social_video_downloader.domain.urls import detect_platform, normalize_media_url
from social_video_downloader.infrastructure.telegram_audio import prepare_telegram_audio
from social_video_downloader.infrastructure.telegram_media import (
    inspect_telegram_video,
    prepare_telegram_video,
    telegram_video_upload_parameters,
)
from social_video_downloader.operation_logging import Operation, report_failure
from social_video_downloader.services.choice_model import (
    ChoicePlan,
    ChoicePlanState,
    ModeChoice,
    QualityChoice,
    UserChoiceKind,
)
from social_video_downloader.services.download import DownloadService
from social_video_downloader.services.quality_tiers import QualityTier
from social_video_downloader.telegram_i18n import get_i18n, tr
from social_video_downloader.telegram_interactions import (
    CallbackAction,
    CallbackParseStatus,
    InMemoryPendingInteractionStore,
    PendingInteraction,
    PendingInteractionStatus,
    PendingInteractionStep,
    build_mode_callback_data,
    build_quality_callback_data,
    parse_callback_data,
)

download_service = DownloadService()
pending_interaction_store = InMemoryPendingInteractionStore()

_PLATFORM_LABELS = {
    Platform.YOUTUBE: "YouTube",
    Platform.INSTAGRAM: "Instagram",
    Platform.TIKTOK: "TikTok",
}

_START_MESSAGE = (
    "Hi! Send a YouTube link to download an individual video or audio. "
    "Instagram and TikTok downloads aren't enabled here."
)

_MODE_LABELS = {
    UserChoiceKind.VIDEO: "🎬 Video",
    UserChoiceKind.AUDIO: "🎵 Audio",
}

_QUALITY_LABELS = {
    QualityTier.LOW: "Low",
    QualityTier.MEDIUM: "Medium",
    QualityTier.HIGH: "High",
}

_STALE_CALLBACK_MESSAGE = "This choice is no longer available. Send the link again."
_INVALID_CALLBACK_MESSAGE = "Couldn't process this choice. Send the link again."
_BLOCKED_CHOICE_MESSAGE = "No safe download option is available for this link."


def _download_error_message(error: DownloaderError) -> str:
    """Translate expected domain failures into safe, actionable user messages."""
    if isinstance(error, MetadataBusyError):
        return tr("YouTube processing is busy or temporarily unavailable. Try again later.")
    if isinstance(error, MetadataExtractionError):
        return tr(
            "Couldn't get video information. The video may be deleted, private or unavailable."
        )
    if isinstance(error, MediaProcessingError):
        return tr("The video download is incomplete or couldn't be processed. Try another link.")
    if isinstance(error, DownloadFailedError):
        return tr("Couldn't download the video. Try again later.")
    if isinstance(error, UnsupportedPlatformError):
        return tr("Downloads from this platform aren't enabled yet.")
    return tr("Couldn't process this link. Check it and try again.")


async def _notify_download_error(message: Message, error: DownloaderError) -> None:
    """Attempt an error response without replacing the original domain failure."""
    try:
        await message.answer(_download_error_message(error))
    except TelegramAPIError as notification_error:
        report_failure("youtube", "notification", notification_error)


async def handle_start(message: Message, instagram_reels=None, tiktok_videos=None) -> None:
    """Explain current capabilities and how to submit a link."""
    if tiktok_videos is not None and tiktok_videos.allows(message):
        text = (
            tr(
                "Send a YouTube link, a public Instagram Reel or /p/ link, or a "
                "public TikTok video link."
            )
            if instagram_reels is not None
            else tr("Send a YouTube link or a public TikTok video link.")
        )
        await message.answer(text)
        if instagram_reels is not None:
            await message.answer(
                tr("For /p/ links with img_index, choose all videos or the specified video.")
            )
    elif instagram_reels is None:
        await message.answer(tr(_START_MESSAGE))
    else:
        await message.answer(
            tr(
                "Send a YouTube link or a public Instagram Reel or /p/ link. Only "
                "videos are downloaded from carousels, in their original order; "
                "with img_index, choose all videos or the specified video."
            )
        )


async def handle_text(message: Message, instagram_reels=None, tiktok_videos=None) -> None:
    """Validate a submitted URL, download YouTube media, and deliver the file."""
    submitted_text = (message.text or "").strip()

    if any(character.isspace() for character in submitted_text):
        await message.answer(
            tr(
                "Couldn't recognize the link. Send a full HTTP or HTTPS link to "
                "YouTube, Instagram or TikTok."
            )
        )
        return

    try:
        normalized_url = normalize_media_url(submitted_text)
        platform = detect_platform(normalized_url)
    except InvalidMediaURLError:
        await message.answer(
            tr(
                "Couldn't recognize the link. Send a full HTTP or HTTPS link to "
                "YouTube, Instagram or TikTok."
            )
        )
        return
    except UnsupportedPlatformError:
        await message.answer(
            tr("This platform isn't supported yet. Send a YouTube, Instagram or TikTok link.")
        )
        return

    platform_label = _PLATFORM_LABELS[platform]
    if platform is Platform.TIKTOK and tiktok_videos is not None:
        await tiktok_videos.handle(message, submitted_text)
        return
    if platform is Platform.INSTAGRAM and instagram_reels is not None:
        await instagram_reels.handle(message, submitted_text)
        return
    if platform is not Platform.YOUTUBE:
        await message.answer(
            tr(
                (
                    "Recognized a {platform_label} link, but downloads from this "
                    "platform aren't enabled yet."
                ),
                platform_label=platform_label,
            )
        )
        return

    try:
        with Operation("youtube", "metadata"):
            plan = await download_service.create_choice_plan_async(normalized_url)
    except DownloaderError as error:
        await _notify_download_error(message, error)
        return
    except Exception:
        await message.answer(tr("Something went wrong. Try again later."))
        return

    if plan.state is ChoicePlanState.DIRECT_DOWNLOAD:
        if plan.automatic_options is None:
            await message.answer(tr(_BLOCKED_CHOICE_MESSAGE))
            return
        await message.answer(tr("Download request accepted. Results appear in separate messages."))
        await _download_and_deliver_media(message, normalized_url, plan.automatic_options)
        return

    if plan.state is ChoicePlanState.CHOOSE_MODE:
        await _send_mode_choices(message, normalized_url, plan)
        return

    if plan.state is ChoicePlanState.CHOOSE_QUALITY:
        await _send_quality_choices(message, normalized_url, plan)
        return

    await message.answer(tr(_BLOCKED_CHOICE_MESSAGE))


async def handle_choice_callback(callback: CallbackQuery) -> None:
    """Resolve mode and quality callbacks against stored pending interaction state."""
    parse_result = parse_callback_data(callback.data or "")
    if parse_result.status is not CallbackParseStatus.VALID or parse_result.callback is None:
        await callback.answer(tr(_INVALID_CALLBACK_MESSAGE))
        return

    message = callback.message
    owner_user_id = callback.from_user.id
    chat_id = _callback_chat_id(callback)
    if message is None or chat_id is None:
        await callback.answer(tr(_STALE_CALLBACK_MESSAGE))
        return

    message_id = getattr(message, "message_id", None)
    parsed_callback = parse_result.callback
    lookup = pending_interaction_store.lookup(
        parsed_callback.interaction_id,
        owner_user_id=owner_user_id,
        chat_id=chat_id,
        message_id=message_id,
    )
    if lookup.status is not PendingInteractionStatus.FOUND or lookup.interaction is None:
        await callback.answer(_callback_status_message(lookup.status))
        return

    if parsed_callback.action is CallbackAction.MODE:
        await _handle_mode_callback(callback, lookup.interaction, parsed_callback.choice_index)
        return

    await _handle_quality_callback(callback, lookup.interaction, parsed_callback.choice_index)


async def handle_instagram_callback(callback: CallbackQuery, instagram_reels=None) -> None:
    """A separate typed Instagram store; never route carousel plans into YouTube state."""
    handler = getattr(instagram_reels, "_post_handler", None)
    if handler is None:
        with suppress(TelegramAPIError):
            await callback.answer(tr("This choice has expired. Send the link again."))
        return
    await handler.handle_callback(callback)


async def _run_workspace_thread[**P, T](
    function: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs
) -> T:
    """Drain file work before propagating cancellation and releasing its workspace."""
    # Match to_thread's executor/context semantics, but retain a Future rather than
    # a Task that asyncio shutdown could cancel independently of the owning handler.
    worker = asyncio.get_running_loop().run_in_executor(
        None, partial(copy_context().run, function, *args, **kwargs)
    )
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        # shield alone only protects the worker, not the owner's cleanup ordering.
        # Further cancel() calls must not let the owner leave this drain early.
        while not worker.done():
            with suppress(asyncio.CancelledError, Exception):
                await asyncio.shield(worker)
        if not worker.cancelled():
            worker.exception()  # Retrieve a late failure; cancellation stays authoritative.
        raise


async def _download_and_deliver_media(
    message: Message,
    url: str,
    options: DownloadOptions,
) -> None:
    """Download media with selected options and deliver it through the existing pipeline."""
    with Operation("youtube", "download") as operation:
        try:
            with TemporaryDirectory(prefix="social-video-downloader-") as temporary_directory:
                try:
                    downloaded = await _run_workspace_thread(
                        download_service.download,
                        url,
                        Path(temporary_directory),
                        options,
                    )
                    if not downloaded.file_path.is_file():
                        raise MediaProcessingError("The downloader returned a missing output file.")

                    operation.phase = "prepare"
                    if options.mode is DownloadMode.AUDIO_ONLY:
                        audio = await _run_workspace_thread(
                            prepare_telegram_audio,
                            downloaded.file_path,
                            downloaded.metadata.duration_seconds,
                        )
                        audio_parameters = (
                            {"duration": audio.duration} if audio.duration is not None else {}
                        )
                        operation.phase = "upload"
                        await message.answer_audio(
                            FSInputFile(audio.file_path),
                            caption=downloaded.metadata.title[:1024],
                            **audio_parameters,
                        )
                        return

                    telegram_video = await _run_workspace_thread(
                        prepare_telegram_video,
                        downloaded.file_path,
                    )
                    upload_parameters: dict[str, int] = {}

                    try:
                        probe_data = await _run_workspace_thread(
                            inspect_telegram_video, telegram_video
                        )
                        upload_parameters = telegram_video_upload_parameters(probe_data)
                    except Exception as error:
                        # Preserve the existing best-effort inspection behavior.
                        report_failure("youtube", "prepare", error)

                    operation.phase = "upload"
                    sent_message = await message.answer_video(
                        FSInputFile(telegram_video),
                        caption=downloaded.metadata.title[:1024],
                        supports_streaming=True,
                        **upload_parameters,
                    )

                    if sent_message.video is None:
                        operation.fail(category="unconfirmed_upload")
                    operation.phase = "cleanup"
                except BaseException as error:
                    operation.fail(error)
                    raise
                finally:
                    operation.phase = "cleanup"

        except TelegramEntityTooLarge as error:
            operation.fail(error)
            await message.answer(
                tr("The file is too large to send through Telegram. Try a smaller video.")
            )
        except TelegramAPIError as error:
            operation.fail(error)
            await message.answer(tr("Couldn't send the file to Telegram. Try again later."))
        except DownloaderError as error:
            operation.fail(error)
            await _notify_download_error(message, error)
        except Exception as error:
            operation.fail(error)
            await message.answer(tr("Something went wrong. Try again later."))


async def _send_mode_choices(message: Message, url: str, plan: ChoicePlan) -> None:
    await _publish_choices(message, url, plan, PendingInteractionStep.MODE)


async def _send_quality_choices(message: Message, url: str, plan: ChoicePlan) -> None:
    await _publish_choices(message, url, plan, PendingInteractionStep.QUALITY)


async def _publish_choices(
    message: Message, url: str, plan: ChoicePlan, step: PendingInteractionStep
) -> None:
    interaction = pending_interaction_store.create(
        owner_user_id=message.from_user.id,
        chat_id=message.chat.id,
        url=url,
        plan=plan,
        active_step=step,
        locale=get_i18n().current_locale,
    )
    # Never put a token in Telegram before its confirmed message is bound. If
    # sendMessage applied but its response is lost/cancelled, no buttons exist.
    try:
        card = await message.answer(
            tr("YouTube link recognized. If no buttons appear, send the link again.")
        )
    except TelegramAPIError as error:
        pending_interaction_store.remove(interaction.interaction_id)
        report_failure("youtube", "notification", error)
        return
    except BaseException:
        pending_interaction_store.remove(interaction.interaction_id)
        raise

    binding = pending_interaction_store.set_message_id(
        interaction.interaction_id,
        owner_user_id=message.from_user.id,
        chat_id=message.chat.id,
        message_id=card.message_id,
    )
    if binding.status is not PendingInteractionStatus.FOUND:
        # Expiry/removal while sendMessage was pending must not publish a keyboard.
        pending_interaction_store.remove(interaction.interaction_id)
        return
    if step is PendingInteractionStep.MODE:
        text = tr("Choose a format:")
        keyboard = _mode_keyboard(interaction.interaction_id, plan.mode_choices)
    else:
        text = tr("Choose the quality:")
        keyboard = _quality_keyboard(interaction.interaction_id, plan.quality_choices)
    try:
        await card.edit_text(text, reply_markup=keyboard)
    except TelegramAPIError as error:
        # Keep the binding: the edit may have succeeded despite a lost response.
        # Never resend automatically; the initial receipt explains recovery.
        report_failure("youtube", "notification", error)


async def _handle_mode_callback(
    callback: CallbackQuery,
    interaction: PendingInteraction,
    mode_index: int,
) -> None:
    if mode_index < 0 or mode_index >= len(interaction.plan.mode_choices):
        await callback.answer(tr(_INVALID_CALLBACK_MESSAGE))
        return

    mode_choice = interaction.plan.mode_choices[mode_index]
    if mode_choice.final_options is not None:
        await _consume_and_download(callback, interaction, mode_choice.final_options)
        return

    if not mode_choice.quality_choices:
        await callback.answer(tr(_INVALID_CALLBACK_MESSAGE))
        return

    transition = pending_interaction_store.transition_to_quality(
        interaction.interaction_id,
        owner_user_id=callback.from_user.id,
        chat_id=interaction.chat_id,
        mode_index=mode_index,
        message_id=getattr(callback.message, "message_id", None),
    )
    if transition.status is not PendingInteractionStatus.FOUND or transition.interaction is None:
        await callback.answer(_callback_status_message(transition.status))
        return

    with get_i18n().use_locale(transition.interaction.locale):
        try:
            await callback.answer()
        except TelegramAPIError as error:
            report_failure("youtube", "notification", error)
        if callback.message is not None:
            try:
                await callback.message.edit_text(
                    tr("Choose the quality:"),
                    reply_markup=_quality_keyboard(
                        interaction.interaction_id,
                        transition.interaction.plan.mode_choices[mode_index].quality_choices,
                    ),
                )
            except TelegramAPIError as error:
                # Keep the state: the edit may have reached Telegram despite a lost response.
                # An old mode button can safely retry this same nonterminal transition.
                report_failure("youtube", "notification", error)


async def _handle_quality_callback(
    callback: CallbackQuery,
    interaction: PendingInteraction,
    quality_index: int,
) -> None:
    quality_choices = _active_quality_choices(interaction)
    if quality_index < 0 or quality_index >= len(quality_choices):
        await callback.answer(tr(_INVALID_CALLBACK_MESSAGE))
        return

    await _consume_and_download(
        callback,
        interaction,
        quality_choices[quality_index].final_options,
    )


async def _consume_and_download(
    callback: CallbackQuery,
    interaction: PendingInteraction,
    options: DownloadOptions,
) -> None:
    consume = pending_interaction_store.consume_terminal(
        interaction.interaction_id,
        owner_user_id=callback.from_user.id,
        chat_id=interaction.chat_id,
        message_id=getattr(callback.message, "message_id", None),
    )
    if consume.status is not PendingInteractionStatus.FOUND:
        await callback.answer(_callback_status_message(consume.status))
        return

    with get_i18n().use_locale(interaction.locale):
        pending_interaction_store.remove(interaction.interaction_id)
        try:
            await callback.answer(tr("Starting download…"))
        except TelegramAPIError as error:
            report_failure("youtube", "notification", error)
        if callback.message is not None:
            try:
                await callback.message.edit_text(
                    tr("Download request accepted. Results appear in separate messages."),
                    reply_markup=None,
                )
            except TelegramAPIError as error:
                report_failure("youtube", "notification", error)
            await _download_and_deliver_media(callback.message, interaction.url, options)


def _mode_keyboard(
    interaction_id: str,
    mode_choices: tuple[ModeChoice, ...],
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr(_MODE_LABELS[choice.kind]),
                    callback_data=build_mode_callback_data(interaction_id, index),
                )
            ]
            for index, choice in enumerate(mode_choices)
        ]
    )


def _quality_keyboard(
    interaction_id: str,
    quality_choices: tuple[QualityChoice, ...],
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr(_QUALITY_LABELS[choice.tier]),
                    callback_data=build_quality_callback_data(interaction_id, index),
                )
            ]
            for index, choice in enumerate(quality_choices)
        ]
    )


def _active_quality_choices(interaction: PendingInteraction) -> tuple[QualityChoice, ...]:
    if interaction.selected_mode_index is None:
        return interaction.plan.quality_choices
    if interaction.selected_mode_index >= len(interaction.plan.mode_choices):
        return ()
    return interaction.plan.mode_choices[interaction.selected_mode_index].quality_choices


def _callback_chat_id(callback: CallbackQuery) -> int | None:
    message = callback.message
    chat = getattr(message, "chat", None)
    chat_id = getattr(chat, "id", None)
    return chat_id if isinstance(chat_id, int) else None


def _callback_status_message(status: PendingInteractionStatus) -> str:
    if status is PendingInteractionStatus.CONSUMED:
        return tr("This request is already being processed.")
    return tr(_STALE_CALLBACK_MESSAGE)


def create_router() -> Router:
    """Fresh registration state for each dispatcher; callback behavior is unchanged."""
    router = Router(name="telegram-handlers")
    router.message.register(handle_start, CommandStart())
    router.message.register(handle_text, F.text)
    router.callback_query.register(handle_instagram_callback, F.data.startswith("ig:"))
    router.callback_query.register(handle_choice_callback, F.data)
    return router
