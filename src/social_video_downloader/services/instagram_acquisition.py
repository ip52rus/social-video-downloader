"""Bounded, cancellable carousel acquisition, separate from single-file downloads."""

import asyncio
import json
import math
import os
import signal
import sys
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from time import monotonic
from uuid import uuid4

from social_video_downloader.domain.carousel import (
    CarouselItem,
    CarouselItemKind,
    CarouselPlanState,
    CarouselScope,
    CarouselSelectionPlan,
    DownloadedCarousel,
    DownloadedCarouselVideo,
)
from social_video_downloader.domain.errors import DownloadFailedError, DownloadTimeoutError
from social_video_downloader.domain.models import DownloadedMedia, MediaMetadata, Platform
from social_video_downloader.infrastructure.workspace import temporary_workspace
from social_video_downloader.providers.instagram import InstagramProvider


@dataclass(frozen=True, slots=True)
class CarouselAcquisitionLimits:
    """Conservative adjustable guardrails, not measured production capacity."""

    max_videos: int = 25
    max_file_bytes: int = 100 * 1024**2
    max_total_bytes: int = 500 * 1024**2
    max_temp_bytes: int = 512 * 1024**2
    max_seconds: float = 600

    def __post_init__(self):
        for name in ("max_videos", "max_file_bytes", "max_total_bytes", "max_temp_bytes"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError("Carousel byte/count limits must be positive integers.")
        if (
            isinstance(self.max_seconds, bool)
            or not isinstance(self.max_seconds, (int, float))
            or not math.isfinite(self.max_seconds)
            or self.max_seconds <= 0
        ):
            raise ValueError("Carousel deadline must be finite and positive.")


def validate_plan(plan: CarouselSelectionPlan, limits: CarouselAcquisitionLimits) -> None:
    """Reject forged/partial selections and reference intent before launching acquisition."""
    if (
        plan.state is not CarouselPlanState.READY
        or plan.scope is not CarouselScope.PUBLICATION
        or plan.issue is not None
        or InstagramProvider._media_url(plan.publication_url) != plan.publication_url
        or "/p/" not in plan.publication_url
        or type(plan.total_entries) is not int
        or plan.total_entries != len(plan.items)
        or [x.position for x in plan.items] != list(range(1, len(plan.items) + 1))
        or any(not x.item_id or x.kind is CarouselItemKind.UNKNOWN for x in plan.items)
        or len({x.item_id for x in plan.items}) != len(plan.items)
        or plan.selected_videos != tuple(x for x in plan.items if x.kind is CarouselItemKind.VIDEO)
        or not plan.selected_videos
        or any(x.admissible_format_count <= 0 for x in plan.selected_videos)
    ):
        raise DownloadFailedError("Carousel requires a complete READY publication plan.")
    if len(plan.selected_videos) > limits.max_videos:
        raise DownloadFailedError("Carousel video count exceeds the operation limit.")


def plan_payload(plan: CarouselSelectionPlan) -> dict:
    # Local pipe only; never logged or written as a persistent snapshot.
    return {
        "publication_url": plan.publication_url,
        "total_entries": plan.total_entries,
        "items": [asdict(item) for item in plan.items],
    }


def plan_from_payload(data: dict) -> CarouselSelectionPlan:
    items = tuple(
        CarouselItem(
            x["position"],
            x["item_id"],
            CarouselItemKind(x["kind"]),
            tuple(x["evidence"]),
            x["admissible_format_count"],
        )
        for x in data["items"]
    )
    return CarouselSelectionPlan(
        data["publication_url"],
        data["total_entries"],
        items,
        tuple(x for x in items if x.kind is CarouselItemKind.VIDEO),
        CarouselScope.PUBLICATION,
        CarouselPlanState.READY,
    )


async def _kill(process: asyncio.subprocess.Process) -> None:
    # The process group includes ffprobe, so cleanup never races a surviving writer.
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)
    await process.wait()


class InstagramCarouselAcquisition:
    """One short-lived process per operation; no background service or Telegram calls."""

    def __init__(self, limits: CarouselAcquisitionLimits | None = None):
        self.limits = limits or CarouselAcquisitionLimits()

    async def acquire(self, plan: CarouselSelectionPlan, output_dir: Path) -> DownloadedCarousel:
        validate_plan(plan, self.limits)
        if os.name != "posix":
            raise DownloadFailedError("Bounded carousel acquisition requires a POSIX runtime.")
        started = monotonic()
        output_dir = Path(output_dir)
        if output_dir.is_symlink():
            raise DownloadFailedError("Carousel output directory must not be a symlink.")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_dir = output_dir.resolve(strict=True)
        published = []
        try:
            with temporary_workspace(base_dir=output_dir) as workspace:
                payload = json.dumps(
                    {
                        "plan": plan_payload(plan),
                        "limits": asdict(self.limits),
                        "workspace": str(workspace),
                    }
                ).encode()
                process = None
                creation = asyncio.create_task(
                    asyncio.create_subprocess_exec(
                        sys.executable,
                        "-m",
                        "social_video_downloader.infrastructure.instagram_acquisition",
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                        start_new_session=True,
                    )
                )
                try:
                    async with asyncio.timeout(self.limits.max_seconds - (monotonic() - started)):
                        process = await asyncio.shield(creation)
                        stdout, _ = await process.communicate(payload)
                    if process.returncode != 0:
                        raise DownloadFailedError(
                            "Carousel acquisition failed; no collection returned."
                        )
                    result = json.loads(stdout)
                    durations = result["durations"]
                    files = sorted(workspace.iterdir())
                    expected = [
                        workspace / f"video-{x.position:04d}.mp4" for x in plan.selected_videos
                    ]
                    if (
                        files != expected
                        or len(durations) != len(expected)
                        or any(
                            p.is_symlink() or not p.is_file() or p.stat().st_size <= 0
                            for p in files
                        )
                        or any(p.stat().st_size > self.limits.max_file_bytes for p in files)
                        or sum(p.stat().st_size for p in files)
                        > min(self.limits.max_total_bytes, self.limits.max_temp_bytes)
                    ):
                        raise DownloadFailedError("Carousel outputs failed final validation.")
                    # Exclusive hard links: no overwrite, no extra media-byte copy.
                    # Roll back every owned name if publication is interrupted.
                    prefix = uuid4().hex
                    videos = []
                    for item, source, duration in zip(
                        plan.selected_videos, files, durations, strict=True
                    ):
                        if monotonic() - started >= self.limits.max_seconds:
                            raise TimeoutError
                        destination = output_dir / f"instagram-{prefix}-{item.position:04d}.mp4"
                        os.link(source, destination, follow_symlinks=False)
                        published.append(destination)
                        videos.append(
                            DownloadedCarouselVideo(
                                item.position,
                                item.item_id,
                                DownloadedMedia(
                                    destination,
                                    MediaMetadata(
                                        "Instagram Video",
                                        plan.publication_url,
                                        Platform.INSTAGRAM,
                                        duration_seconds=duration,
                                    ),
                                ),
                            )
                        )
                    await asyncio.sleep(0)
                    if monotonic() - started >= self.limits.max_seconds:
                        raise TimeoutError
                    collection = DownloadedCarousel(
                        plan.publication_url,
                        tuple(videos),
                        sum(p.stat().st_size for p in files),
                    )
                except BaseException:

                    async def reap():
                        child = process if process is not None else await creation
                        await _kill(child)

                    cleanup = asyncio.create_task(reap())
                    cancelled = False
                    while not cleanup.done():
                        try:
                            await asyncio.shield(cleanup)
                        except asyncio.CancelledError:
                            cancelled = True
                    cleanup.result()
                    if cancelled:
                        raise asyncio.CancelledError from None
                    raise
            return collection
        except BaseException as exc:
            for path in published:
                path.unlink(missing_ok=True)
            if isinstance(exc, TimeoutError):
                raise DownloadTimeoutError("Carousel operation exceeded its deadline.") from None
            raise
