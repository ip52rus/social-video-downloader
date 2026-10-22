"""Explicit, inactive-by-default Telegram transport for acquired Instagram videos."""

import asyncio
import json
import math
import os
import signal
import sys
from collections.abc import Awaitable
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from pathlib import Path
from time import monotonic
from typing import Protocol
from urllib.parse import urlsplit

from aiogram.types import FSInputFile, InputMediaVideo, Message

from social_video_downloader.domain.carousel import (
    CarouselItemKind,
    CarouselPlanState,
    CarouselSelectionPlan,
    DownloadedCarousel,
    selection_matches_scope,
)
from social_video_downloader.domain.errors import DownloadCleanupError, MediaProcessingError
from social_video_downloader.domain.models import Platform
from social_video_downloader.infrastructure.instagram_metadata import parent_identity_matches
from social_video_downloader.infrastructure.workspace import quarantinable_workspace


@dataclass(frozen=True, slots=True)
class CarouselDeliveryLimits:
    """Per-operation bounds, not global quotas or measured production capacity."""

    max_videos: int = 25
    max_upload_file_bytes: int = 50_000_000
    max_upload_total_bytes: int = 200 * 1024**2
    max_workspace_bytes: int = 1024**3
    max_workspace_entries: int = 2048
    max_prepare_seconds: float = 180
    max_send_seconds: float = 120

    def __post_init__(self):
        for name in (
            "max_videos",
            "max_upload_file_bytes",
            "max_upload_total_bytes",
            "max_workspace_bytes",
            "max_workspace_entries",
        ):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError("Carousel delivery byte/count limits must be positive integers.")
        for value in (self.max_prepare_seconds, self.max_send_seconds):
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError("Carousel delivery deadlines must be finite and positive.")


@dataclass(frozen=True, slots=True)
class CarouselDeliveryProgress:
    total_videos: int
    confirmed_positions: tuple[int, ...] = ()
    uncertain_positions: tuple[int, ...] = ()
    confirmed_batches: int = 0

    @property
    def complete(self) -> bool:
        return (
            self.total_videos > 0
            and len(self.confirmed_positions) == self.total_videos
            and not self.uncertain_positions
        )


class CarouselDeliveryError(MediaProcessingError):
    """Safe caller-facing progress; never contains Telegram/upstream error text."""

    def __init__(self, stage: str, progress: CarouselDeliveryProgress):
        super().__init__(f"Carousel delivery stopped during {stage}; inspect safe progress.")
        self.stage = stage
        self.progress = progress


class CarouselDeliveryCancelled(asyncio.CancelledError):
    def __init__(self, progress: CarouselDeliveryProgress):
        super().__init__("Carousel delivery cancelled; inspect safe progress.")
        self.progress = progress


class CarouselSender(Protocol):
    async def send_video(self, **kwargs) -> Message: ...
    async def send_media_group(self, **kwargs) -> list[Message]: ...


@dataclass(frozen=True, slots=True)
class _PreparedVideo:
    position: int
    path: Path = field(repr=False)
    parameters: dict[str, int]
    fingerprint: tuple[int, ...]


def _fingerprint(path: Path) -> tuple[int, ...]:
    stat = path.lstat()
    if path.is_symlink() or not path.is_file() or stat.st_size <= 0:
        raise MediaProcessingError("Prepared carousel file is invalid.")
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def _validate_collection(collection, plan, limits):
    if (
        not isinstance(collection, DownloadedCarousel)
        or not isinstance(plan, CarouselSelectionPlan)
        or plan.state is not CarouselPlanState.READY
        or not selection_matches_scope(plan)
        or plan.issue is not None
        or not parent_identity_matches(plan.parent_identity, plan.publication_url)
        or not isinstance(plan.selected_videos, tuple)
        or not isinstance(plan.items, tuple)
        or not plan.selected_videos
        or collection.publication_url != plan.publication_url
        or urlsplit(collection.publication_url).query
        or urlsplit(collection.publication_url).fragment
        or type(plan.total_entries) is not int
        or plan.total_entries != len(plan.items)
        or [x.position for x in plan.items] != list(range(1, plan.total_entries + 1))
        or any(
            not isinstance(x.kind, CarouselItemKind)
            or x.kind is CarouselItemKind.UNKNOWN
            or type(x.position) is not int
            for x in plan.items
        )
        or any(
            type(x.admissible_format_count) is not int or x.admissible_format_count <= 0
            for x in plan.selected_videos
        )
        or not isinstance(collection.videos, tuple)
        or not 1 <= len(collection.videos) <= limits.max_videos
        or [(x.position, x.item_id) for x in collection.videos]
        != [(x.position, x.item_id) for x in plan.selected_videos]
        or any(type(x.position) is not int or x.position <= 0 for x in collection.videos)
        or len({x.item_id for x in plan.items}) != len(plan.items)
        or any(not isinstance(x.item_id, str) or not x.item_id for x in plan.items)
        or any(
            x.media.metadata.platform is not Platform.INSTAGRAM
            or x.media.metadata.source_url != collection.publication_url
            for x in collection.videos
        )
        or type(collection.total_bytes) is not int
        or collection.total_bytes <= 0
    ):
        raise MediaProcessingError("Carousel collection does not match the complete selection.")


async def _reap(process):
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)
    await process.wait()


async def _finish_cleanup(operation: Awaitable):
    task = asyncio.create_task(operation)
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    task.result()
    if cancelled:
        raise asyncio.CancelledError


async def _prepare(collection, workspace, private, limits):
    """Only paths and technical metadata cross the local child pipe; no credentials."""
    payload = json.dumps(
        {
            "workspace": str(workspace),
            "private": str(private),
            "inputs": [str(x.media.file_path) for x in collection.videos],
            "total_bytes": collection.total_bytes,
            "limits": asdict(limits),
        }
    ).encode()
    creation = asyncio.create_task(
        asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "social_video_downloader.infrastructure.telegram_carousel_preparation",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )
    )
    process = None
    try:
        async with asyncio.timeout(limits.max_prepare_seconds):
            process = await asyncio.shield(creation)
            stdout, _ = await process.communicate(payload)
        if process.returncode != 0:
            raise MediaProcessingError("Carousel preparation failed within its limits.")
        raw = json.loads(stdout)
        if not isinstance(raw, list) or len(raw) != len(collection.videos):
            raise MediaProcessingError("Carousel preparation returned an incomplete manifest.")
        prepared = []
        total = 0
        for original, item in zip(collection.videos, raw, strict=True):
            name = item["name"]
            if not isinstance(name, str) or Path(name).name != name or name in {".", ".."}:
                raise MediaProcessingError("Carousel preparation returned an invalid path.")
            path = private / name
            fingerprint = _fingerprint(path)
            if fingerprint != tuple(item["fingerprint"]):
                raise MediaProcessingError("Prepared carousel output changed.")
            parameters = item["parameters"]
            if (
                not isinstance(parameters, dict)
                or not {"width", "height"} <= parameters.keys()
                or not parameters.keys() <= {"width", "height", "duration"}
                or any(type(x) is not int or x <= 0 for x in parameters.values())
                or fingerprint[2] > limits.max_upload_file_bytes
            ):
                raise MediaProcessingError("Prepared carousel output is not deliverable.")
            total += fingerprint[2]
            prepared.append(_PreparedVideo(original.position, path, parameters, fingerprint))
        if total > limits.max_upload_total_bytes:
            raise MediaProcessingError("Prepared carousel upload total exceeds its limit.")
        return tuple(prepared)
    except BaseException:

        async def stop():
            child = process if process is not None else await creation
            await _reap(child)

        try:
            await _finish_cleanup(stop())
        except Exception:
            raise DownloadCleanupError("Carousel preparation cleanup is unconfirmed.") from None
        raise


def _check_response(response, batch, chat_id, seen_ids, seen_groups):
    messages = [response] if len(batch) == 1 else response
    if not isinstance(messages, list) or len(messages) != len(batch):
        raise ValueError("Incomplete Telegram response")
    groups = set()
    for message in messages:
        if (
            not isinstance(message, Message)
            or message.video is None
            or message.message_id <= 0
            or message.message_id in seen_ids
            or (type(chat_id) is int and message.chat.id != chat_id)
        ):
            raise ValueError("Unexpected Telegram response")
        seen_ids.add(message.message_id)
        groups.add(message.media_group_id)
    if (
        len(batch) > 1 and (len(groups) != 1 or not next(iter(groups)) or groups & seen_groups)
    ) or (len(batch) == 1 and groups != {None}):
        raise ValueError("Unexpected Telegram media group response")
    if len(batch) > 1:
        seen_groups.update(groups)


class TelegramCarouselDelivery:
    """Reusable transport; callers explicitly supply a sender, plan and owned workspace."""

    def __init__(self, sender: CarouselSender, limits: CarouselDeliveryLimits | None = None):
        self.sender = sender
        self.limits = limits or CarouselDeliveryLimits()

    async def deliver(
        self,
        collection: DownloadedCarousel,
        *,
        plan: CarouselSelectionPlan,
        workspace: Path,
        chat_id: int | str,
    ) -> CarouselDeliveryProgress:
        total = (
            len(collection.videos)
            if isinstance(collection, DownloadedCarousel) and isinstance(collection.videos, tuple)
            else 0
        )
        progress = CarouselDeliveryProgress(total)
        stage = "preparation"
        pending = ()
        started = monotonic()
        try:
            _validate_collection(collection, plan, self.limits)
            if not (
                (type(chat_id) is int and chat_id != 0)
                or (isinstance(chat_id, str) and chat_id.strip())
            ):
                raise MediaProcessingError("Carousel delivery requires a valid chat target.")
            if os.name != "posix":
                raise MediaProcessingError("Bounded carousel preparation requires POSIX.")
            workspace = Path(workspace)
            if workspace.is_symlink() or not workspace.is_dir():
                raise MediaProcessingError("Carousel requires an approved regular workspace.")
            workspace = workspace.resolve(strict=True)
            with quarantinable_workspace(base_dir=workspace) as private:
                prepared = await _prepare(collection, workspace, private, self.limits)
                if [x.position for x in prepared] != [x.position for x in collection.videos]:
                    raise MediaProcessingError("Prepared carousel order changed.")
                if (
                    len({x.path for x in prepared}) != len(prepared)
                    or any(_fingerprint(x.path) != x.fingerprint for x in prepared)
                    or any(x.fingerprint[2] > self.limits.max_upload_file_bytes for x in prepared)
                    or sum(x.fingerprint[2] for x in prepared) > self.limits.max_upload_total_bytes
                ):
                    raise MediaProcessingError("Prepared carousel barrier validation failed.")
                seen_ids = set()
                seen_groups = set()
                media = tuple(
                    InputMediaVideo(
                        media=FSInputFile(x.path, filename=f"video-{x.position}.mp4"),
                        **x.parameters,
                        supports_streaming=True,
                    )
                    for x in prepared
                )
                if monotonic() - started >= self.limits.max_prepare_seconds:
                    raise MediaProcessingError(
                        "Carousel preparation barrier exceeded its deadline."
                    )
                # This is the barrier: every file is ready before the first send.
                for start in range(0, len(prepared), 10):
                    batch = prepared[start : start + 10]
                    stage = "validation"
                    for item in batch:
                        if _fingerprint(item.path) != item.fingerprint:
                            raise MediaProcessingError(
                                "Prepared carousel file changed before upload."
                            )
                    stage = "delivery"
                    pending = tuple(x.position for x in batch)
                    async with asyncio.timeout(self.limits.max_send_seconds):
                        if len(batch) == 1:
                            item = batch[0]
                            response = await self.sender.send_video(
                                chat_id=chat_id,
                                video=media[start].media,
                                **item.parameters,
                                supports_streaming=True,
                                request_timeout=math.ceil(self.limits.max_send_seconds),
                            )
                        else:
                            response = await self.sender.send_media_group(
                                chat_id=chat_id,
                                media=list(media[start : start + 10]),
                                request_timeout=math.ceil(self.limits.max_send_seconds),
                            )
                    _check_response(response, batch, chat_id, seen_ids, seen_groups)
                    progress = CarouselDeliveryProgress(
                        total,
                        (*progress.confirmed_positions, *pending),
                        (),
                        progress.confirmed_batches + 1,
                    )
                    pending = ()
                return progress
        except DownloadCleanupError:
            raise
        except asyncio.CancelledError:
            raise CarouselDeliveryCancelled(
                CarouselDeliveryProgress(
                    total,
                    progress.confirmed_positions,
                    pending,
                    progress.confirmed_batches,
                )
            ) from None
        except Exception:
            raise CarouselDeliveryError(
                stage,
                CarouselDeliveryProgress(
                    total,
                    progress.confirmed_positions,
                    pending,
                    progress.confirmed_batches,
                ),
            ) from None
