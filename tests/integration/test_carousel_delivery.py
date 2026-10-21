"""Actual isolated local preparation plus mocked Telegram sends; no live platforms."""

import shutil
import subprocess
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from aiogram.types import Chat, Message, Video

from social_video_downloader.domain.carousel import (
    CarouselItem,
    CarouselItemKind,
    CarouselParentIdentity,
    CarouselPlanState,
    CarouselScope,
    CarouselSelectionPlan,
    DownloadedCarousel,
    DownloadedCarouselVideo,
)
from social_video_downloader.domain.models import DownloadedMedia, MediaMetadata, Platform
from social_video_downloader.infrastructure.telegram_carousel import (
    CarouselDeliveryError,
    CarouselDeliveryLimits,
    TelegramCarouselDelivery,
)
from social_video_downloader.infrastructure.telegram_media import (
    inspect_telegram_video,
    prepare_telegram_video,
    telegram_video_upload_parameters,
)

pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="Real local media fixtures require FFmpeg/ffprobe",
)
URL = "https://www.instagram.com/p/Synthetic_01/"


@pytest.fixture(scope="module")
def media(tmp_path_factory):
    root = tmp_path_factory.mktemp("carousel-local-media")
    result = {}
    for name, extension, video, audio in [
        ("silent", "mp4", "libx264", False),
        ("audio", "mp4", "libx264", True),
        ("remux", "mkv", "libx264", False),
        ("transcode", "mkv", "mpeg4", False),
    ]:
        path = root / f"{name}.{extension}"
        cmd = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=64x96:r=10"]
        if audio:
            cmd += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000"]
        cmd += ["-t", "0.6", "-c:v", video, "-pix_fmt", "yuv420p"]
        if audio:
            cmd += ["-c:a", "aac"]
        subprocess.run([*cmd, str(path)], check=True, capture_output=True, timeout=15)
        result[name] = path
    return result


def acquired(tmp_path, media, kinds):
    items = []
    videos = []
    for index, kind in enumerate(kinds, 1):
        source = tmp_path / f"source-{index}{media[kind].suffix}"
        shutil.copyfile(media[kind], source)
        item = CarouselItem(
            index, f"synthetic-{index}", CarouselItemKind.VIDEO, ("video_versions",), 1
        )
        items.append(item)
        videos.append(
            DownloadedCarouselVideo(
                index,
                item.item_id,
                DownloadedMedia(source, MediaMetadata("Synthetic", URL, Platform.INSTAGRAM)),
            )
        )
    plan = CarouselSelectionPlan(
        URL,
        len(items),
        tuple(items),
        tuple(items),
        CarouselScope.PUBLICATION,
        CarouselPlanState.READY,
        parent_identity=CarouselParentIdentity("1386527023699267419445", "Synthetic_01"),
    )
    return DownloadedCarousel(
        URL, tuple(videos), sum(x.media.file_path.stat().st_size for x in videos)
    ), plan


class LocalSender:
    def __init__(self):
        self.calls = []
        self.paths = []
        self.contents = []

    async def send(self, kwargs, group):
        files = [m.media for m in kwargs["media"]] if group else [kwargs["video"]]
        parameters = (
            [
                {"width": m.width, "height": m.height, "duration": m.duration}
                for m in kwargs["media"]
            ]
            if group
            else [{k: kwargs[k] for k in ("width", "height", "duration")}]
        )
        self.calls.append(kwargs)
        messages = []
        for i, (file, provided) in enumerate(zip(files, parameters, strict=True), 1):
            path = Path(file.path)
            self.paths.append(path)
            self.contents.append(path.read_bytes())
            probe = inspect_telegram_video(path)
            assert telegram_video_upload_parameters(probe) == provided
            assert "mp4" in probe["format"]["format_name"].split(",")
            assert [s["codec_name"] for s in probe["streams"] if s["codec_type"] == "video"] == [
                "h264"
            ]
            messages.append(
                Message(
                    message_id=i,
                    date=datetime.now(UTC),
                    chat=Chat(id=1, type="private"),
                    media_group_id="synthetic-group" if group else None,
                    video=Video(
                        file_id="synthetic",
                        file_unique_id="synthetic",
                        width=64,
                        height=96,
                        duration=1,
                    ),
                )
            )
        return messages if group else messages[0]

    async def send_media_group(self, **kwargs):
        return await self.send(kwargs, True)

    async def send_video(self, **kwargs):
        return await self.send(kwargs, False)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kinds", [("silent",), ("audio",), ("silent", "audio"), ("remux", "transcode", "silent")]
)
async def test_real_local_preparation_barrier_and_owned_cleanup(tmp_path, media, kinds):
    result, plan = acquired(tmp_path, media, kinds)
    originals = {x.media.file_path: x.media.file_path.read_bytes() for x in result.videos}
    # A caller-owned collision name must not be overwritten or deleted by preparation.
    existing = tmp_path / "source-1.telegram-compatible.mp4"
    existing.write_bytes(b"unrelated")
    sender = LocalSender()
    progress = await TelegramCarouselDelivery(sender).deliver(
        result, plan=plan, workspace=tmp_path, chat_id=1
    )
    assert progress.complete and progress.confirmed_positions == tuple(range(1, len(kinds) + 1))
    for source, kind, body in zip(result.videos, kinds, sender.contents, strict=True):
        assert source.media.file_path.read_bytes() == originals[source.media.file_path]
        if kind in ("silent", "audio"):
            assert body == originals[source.media.file_path]
    assert all(not p.exists() for p in sender.paths)
    assert set(tmp_path.iterdir()) == set(originals) | {existing}
    assert existing.read_bytes() == b"unrelated"


@pytest.mark.asyncio
@pytest.mark.parametrize("position", [1, 2, 3])
async def test_real_preparation_failure_anywhere_means_zero_sends(tmp_path, media, position):
    result, plan = acquired(tmp_path, media, ("remux", "silent", "transcode"))
    result.videos[position - 1].media.file_path.write_bytes(b"corrupt")
    result = replace(
        result, total_bytes=sum(x.media.file_path.stat().st_size for x in result.videos)
    )
    originals = {x.media.file_path: x.media.file_path.read_bytes() for x in result.videos}
    sender = LocalSender()
    with pytest.raises(CarouselDeliveryError) as error:
        await TelegramCarouselDelivery(sender).deliver(
            result, plan=plan, workspace=tmp_path, chat_id=1
        )
    assert error.value.progress.confirmed_positions == () and not sender.calls
    assert {p: p.read_bytes() for p in tmp_path.iterdir()} == originals


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "budget", ["file", "upload_total", "workspace", "conversion_cap", "video_count"]
)
async def test_real_resource_limits_fail_before_delivery(tmp_path, media, budget):
    kinds = ("remux",) if budget == "conversion_cap" else ("silent", "silent")
    result, plan = acquired(tmp_path, media, kinds)
    limits = CarouselDeliveryLimits()
    if budget == "file":
        limits = replace(limits, max_upload_file_bytes=10)
    if budget == "upload_total":
        limits = replace(limits, max_upload_total_bytes=result.total_bytes - 1)
    if budget == "workspace":
        limits = replace(limits, max_workspace_bytes=result.total_bytes - 1)
    if budget == "conversion_cap":
        limits = replace(limits, max_upload_file_bytes=256)
    if budget == "video_count":
        limits = replace(limits, max_videos=1)
    sender = LocalSender()
    originals = {p: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(CarouselDeliveryError):
        await TelegramCarouselDelivery(sender, limits).deliver(
            result, plan=plan, workspace=tmp_path, chat_id=1
        )
    assert not sender.calls and {p: p.read_bytes() for p in tmp_path.iterdir()} == originals


@pytest.mark.asyncio
@pytest.mark.parametrize("budget", ["upload_total", "workspace"])
async def test_second_conversion_cannot_exhaust_remaining_aggregate_budget(tmp_path, media, budget):
    result, plan = acquired(tmp_path, media, ("remux", "transcode"))
    probe_output = prepare_telegram_video(result.videos[0].media.file_path, allow_silent=True)
    first_output_bytes = probe_output.stat().st_size
    probe_output.unlink()
    limits = CarouselDeliveryLimits()
    if budget == "upload_total":
        limits = replace(limits, max_upload_total_bytes=first_output_bytes + 256)
    else:
        limits = replace(limits, max_workspace_bytes=result.total_bytes + first_output_bytes + 256)
    originals = {p: p.read_bytes() for p in tmp_path.iterdir()}
    sender = LocalSender()
    with pytest.raises(CarouselDeliveryError):
        await TelegramCarouselDelivery(sender, limits).deliver(
            result, plan=plan, workspace=tmp_path, chat_id=1
        )
    assert not sender.calls and {p: p.read_bytes() for p in tmp_path.iterdir()} == originals
