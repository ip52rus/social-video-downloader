"""Network-forbidden carousel transport; synthetic collection and sender boundaries."""

import asyncio
import sys
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from aiogram.methods import SendMediaGroup, SendVideo
from aiogram.types import Chat, FSInputFile, InputMediaVideo, Message, Video

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
from social_video_downloader.infrastructure import telegram_carousel as transport
from social_video_downloader.infrastructure import telegram_carousel_preparation as preparation

URL = "https://www.instagram.com/p/Synthetic_01/"


def collection(tmp_path, count, photos=()):
    items = []
    videos = []
    for position in range(1, count + len(photos) + 1):
        photo = position in photos
        item = CarouselItem(
            position,
            f"synthetic-{position}",
            CarouselItemKind.PHOTO if photo else CarouselItemKind.VIDEO,
            ("photo_marker",) if photo else ("video_versions",),
            0 if photo else 1,
        )
        items.append(item)
        if not photo:
            path = tmp_path / f"source-{position}.mp4"
            path.write_bytes(bytes([position]) * 20)
            videos.append(
                DownloadedCarouselVideo(
                    position,
                    item.item_id,
                    DownloadedMedia(path, MediaMetadata("Synthetic", URL, Platform.INSTAGRAM)),
                )
            )
    plan = CarouselSelectionPlan(
        URL,
        len(items),
        tuple(items),
        tuple(x for x in items if x.kind is CarouselItemKind.VIDEO),
        CarouselScope.PUBLICATION,
        CarouselPlanState.READY,
        parent_identity=CarouselParentIdentity("1386527023699267419445", "Synthetic_01"),
    )
    result = DownloadedCarousel(
        URL, tuple(videos), sum(v.media.file_path.stat().st_size for v in videos)
    )
    return result, plan


def response(message_id, album=None, chat_id=1):
    return Message(
        message_id=message_id,
        date=datetime.now(UTC),
        chat=Chat(id=chat_id, type="private"),
        media_group_id=album,
        video=Video(
            file_id="synthetic", file_unique_id="synthetic", width=64, height=96, duration=1
        ),
    )


class Sender:
    def __init__(self, error_at=None, malformed=None):
        self.calls = []
        self.error_at = error_at
        self.malformed = malformed
        self.active = False
        self.seen_paths = []

    async def _send(self, kind, kwargs):
        assert not self.active
        self.active = True
        try:
            if kind == "video":
                SendVideo(**kwargs)
                media = [kwargs["video"]]
            else:
                SendMediaGroup(**kwargs)
                assert all(isinstance(x, InputMediaVideo) for x in kwargs["media"])
                media = [x.media for x in kwargs["media"]]
            assert all(isinstance(x, FSInputFile) and Path(x.path).is_file() for x in media)
            self.seen_paths.extend(Path(x.path) for x in media)
            self.calls.append((kind, kwargs))
            await asyncio.sleep(0)
            if self.error_at == len(self.calls):
                raise TimeoutError("private Telegram diagnostic")
            result = [
                response(
                    (len(self.calls) - 1) * 10 + i + 1,
                    str(len(self.calls)) if kind == "album" else None,
                )
                for i in range(len(media))
            ]
            if self.malformed:
                return self.malformed(result)
            return result if kind == "album" else result[0]
        finally:
            self.active = False

    async def send_video(self, **kwargs):
        return await self._send("video", kwargs)

    async def send_media_group(self, **kwargs):
        return await self._send("album", kwargs)


def install_preparation(monkeypatch, fail_at=None, alter=None):
    calls = []

    async def fake(acquired, workspace, private, limits):
        prepared = []
        for item in acquired.videos:
            calls.append(item.position)
            p = private / f"prepared-{item.position}.mp4"
            p.write_bytes(b"prepared")
            if item.position == fail_at:
                raise RuntimeError("private preparation detail")
            prepared.append(
                transport._PreparedVideo(
                    item.position,
                    p,
                    {"width": 64, "height": 96, "duration": 1},
                    transport._fingerprint(p),
                )
            )
        if alter:
            alter(prepared)
        return tuple(prepared)

    monkeypatch.setattr(transport, "_prepare", fake)
    return calls


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import socket

    def forbidden(*a, **k):
        raise AssertionError("No network is allowed")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "count,expected",
    [
        (1, [1]),
        (2, [2]),
        (3, [3]),
        (9, [9]),
        (10, [10]),
        (11, [10, 1]),
        (12, [10, 2]),
        (20, [10, 10]),
        (21, [10, 10, 1]),
        (25, [10, 10, 5]),
    ],
)
async def test_batching_barrier_order_media_and_cleanup(tmp_path, monkeypatch, count, expected):
    acquired, plan = collection(tmp_path, count)
    originals = {x.media.file_path: x.media.file_path.read_bytes() for x in acquired.videos}
    preparations = install_preparation(monkeypatch)
    sender = Sender()
    original_send = sender._send

    async def barrier(kind, kwargs):
        assert preparations == list(range(1, count + 1))
        return await original_send(kind, kwargs)

    monkeypatch.setattr(sender, "_send", barrier)
    result = await transport.TelegramCarouselDelivery(sender).deliver(
        acquired, plan=plan, workspace=tmp_path, chat_id=1
    )
    assert result.complete and result.confirmed_positions == tuple(range(1, count + 1))
    sizes = [1 if kind == "video" else len(kw["media"]) for kind, kw in sender.calls]
    assert sizes == expected
    positions = []
    for kind, kwargs in sender.calls:
        assert "caption" not in kwargs
        objects = [kwargs] if kind == "video" else kwargs["media"]
        for obj in objects:

            def get(name, obj=obj):
                return obj.get(name) if isinstance(obj, dict) else getattr(obj, name)

            assert (get("width"), get("height"), get("duration")) == (64, 96, 1)
            assert get("supports_streaming") is True
            file = get("video") if kind == "video" else get("media")
            positions.append(int(file.filename.removeprefix("video-").removesuffix(".mp4")))
    assert positions == list(range(1, count + 1))
    assert all(not p.exists() for p in sender.seen_paths)
    assert {p: p.read_bytes() for p in tmp_path.iterdir()} == originals


@pytest.mark.asyncio
async def test_photo_gaps_do_not_change_video_order(tmp_path, monkeypatch):
    acquired, plan = collection(tmp_path, 3, photos=(2, 4))
    install_preparation(monkeypatch)
    result = await transport.TelegramCarouselDelivery(Sender()).deliver(
        acquired, plan=plan, workspace=tmp_path, chat_id=1
    )
    assert result.confirmed_positions == (1, 3, 5)


@pytest.mark.asyncio
@pytest.mark.parametrize("position", [1, 2, 3])
async def test_any_preparation_failure_prevents_all_sends(tmp_path, monkeypatch, position):
    acquired, plan = collection(tmp_path, 3)
    install_preparation(monkeypatch, fail_at=position)
    sender = Sender()
    with pytest.raises(transport.CarouselDeliveryError) as error:
        await transport.TelegramCarouselDelivery(sender).deliver(
            acquired, plan=plan, workspace=tmp_path, chat_id=1
        )
    assert error.value.stage == "preparation" and not error.value.progress.complete
    assert error.value.progress.confirmed_positions == () and sender.calls == []
    assert len(list(tmp_path.iterdir())) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change", ["missing", "duplicate", "reordered", "id", "scope", "blocked", "query", "photo"]
)
async def test_invalid_collection_or_reference_never_starts_preparation(
    tmp_path, monkeypatch, change
):
    acquired, plan = collection(tmp_path, 3)
    if change == "missing":
        acquired = replace(acquired, videos=acquired.videos[:-1])
    if change == "duplicate":
        acquired = replace(acquired, videos=(acquired.videos[0],) * 3)
    if change == "reordered":
        acquired = replace(acquired, videos=tuple(reversed(acquired.videos)))
    if change == "id":
        acquired = replace(
            acquired, videos=(replace(acquired.videos[0], item_id="changed"), *acquired.videos[1:])
        )
    if change == "scope":
        plan = replace(plan, scope=CarouselScope.ITEM_REFERENCE)
    if change == "blocked":
        plan = replace(plan, state=CarouselPlanState.BLOCKED)
    if change == "query":
        acquired = replace(acquired, publication_url=URL + "?img_index=1")
        plan = replace(plan, publication_url=acquired.publication_url)
    if change == "photo":
        plan = replace(
            plan, items=(replace(plan.items[0], kind=CarouselItemKind.PHOTO), *plan.items[1:])
        )

    unexpected_preparations = []

    async def forbidden(*a):
        unexpected_preparations.append(True)
        raise AssertionError("Preparation must not start")

    monkeypatch.setattr(transport, "_prepare", forbidden)
    sender = Sender()
    with pytest.raises(transport.CarouselDeliveryError):
        await transport.TelegramCarouselDelivery(sender).deliver(
            acquired, plan=plan, workspace=tmp_path, chat_id=1
        )
    assert not sender.calls
    assert unexpected_preparations == []


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_at", [1, 2, 3])
async def test_send_error_reports_confirmed_and_uncertain_progress_without_retry(
    tmp_path, monkeypatch, failure_at
):
    acquired, plan = collection(tmp_path, 21)
    install_preparation(monkeypatch)
    sender = Sender(error_at=failure_at)
    with pytest.raises(transport.CarouselDeliveryError) as error:
        await transport.TelegramCarouselDelivery(sender).deliver(
            acquired, plan=plan, workspace=tmp_path, chat_id=1
        )
    progress = error.value.progress
    assert progress.confirmed_positions == tuple(range(1, 10 * (failure_at - 1) + 1))
    assert progress.uncertain_positions == tuple(
        range(10 * (failure_at - 1) + 1, min(10 * failure_at, 21) + 1)
    )
    assert not progress.complete and len(sender.calls) == failure_at
    assert "private Telegram diagnostic" not in str(error.value)
    assert all(not p.exists() for p in sender.seen_paths)
    assert len(list(tmp_path.iterdir())) == 21


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response_kind",
    ["missing", "extra", "duplicate", "no_video", "wrong_chat", "bad_group", "none"],
)
async def test_ambiguous_responses_stop_later_batches(tmp_path, monkeypatch, response_kind):
    acquired, plan = collection(tmp_path, 21)
    install_preparation(monkeypatch)

    def malformed(messages):
        if response_kind == "missing":
            return messages[:-1]
        if response_kind == "extra":
            return [*messages, response(99, "1")]
        if response_kind == "duplicate":
            return [messages[0]] * len(messages)
        if response_kind == "no_video":
            return [m.model_copy(update={"video": None}) for m in messages]
        if response_kind == "wrong_chat":
            return [response(i + 1, "1", chat_id=2) for i in range(10)]
        if response_kind == "bad_group":
            return [response(i + 1, str(i)) for i in range(10)]
        return None

    sender = Sender(malformed=malformed)
    with pytest.raises(transport.CarouselDeliveryError) as error:
        await transport.TelegramCarouselDelivery(sender).deliver(
            acquired, plan=plan, workspace=tmp_path, chat_id=1
        )
    assert error.value.progress.confirmed_positions == ()
    assert error.value.progress.uncertain_positions == tuple(range(1, 11))
    assert len(sender.calls) == 1


@pytest.mark.asyncio
async def test_send_timeout_is_ambiguous_and_not_retried(tmp_path, monkeypatch):
    acquired, plan = collection(tmp_path, 11)
    install_preparation(monkeypatch)

    class HungSender(Sender):
        async def send_media_group(self, **kwargs):
            self.calls.append(("album", kwargs))
            await asyncio.Future()

    sender = HungSender()
    with pytest.raises(transport.CarouselDeliveryError) as error:
        await transport.TelegramCarouselDelivery(
            sender, transport.CarouselDeliveryLimits(max_send_seconds=0.01)
        ).deliver(acquired, plan=plan, workspace=tmp_path, chat_id=1)
    assert error.value.progress.uncertain_positions == tuple(range(1, 11))
    assert len(sender.calls) == 1 and len(list(tmp_path.iterdir())) == 11


@pytest.mark.asyncio
@pytest.mark.parametrize("during_send", [False, True])
async def test_cancellation_reports_progress_and_cleans_private_files(
    tmp_path, monkeypatch, during_send
):
    acquired, plan = collection(tmp_path, 11)
    entered = asyncio.Event()
    install_preparation(monkeypatch)
    if not during_send:

        async def hang(c, w, p, limits):
            (p / "partial").write_bytes(b"partial")
            entered.set()
            await asyncio.Future()

        monkeypatch.setattr(transport, "_prepare", hang)

    class HungSender(Sender):
        async def send_media_group(self, **kwargs):
            self.calls.append(("album", kwargs))
            entered.set()
            await asyncio.Future()

    sender = HungSender()
    task = asyncio.create_task(
        transport.TelegramCarouselDelivery(sender).deliver(
            acquired, plan=plan, workspace=tmp_path, chat_id=1
        )
    )
    await asyncio.wait_for(entered.wait(), 2)
    task.cancel()
    with pytest.raises(transport.CarouselDeliveryCancelled) as error:
        await task
    assert error.value.progress.uncertain_positions == (tuple(range(1, 11)) if during_send else ())
    assert len(sender.calls) == int(during_send)
    assert len(list(tmp_path.iterdir())) == 11


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["missing_later", "duplicate_path", "oversized"])
async def test_complete_barrier_rechecks_all_outputs_before_first_send(
    tmp_path, monkeypatch, mutation
):
    acquired, plan = collection(tmp_path, 11)

    def alter(prepared):
        if mutation == "missing_later":
            prepared[-1].path.unlink()
        if mutation == "duplicate_path":
            prepared[-1] = replace(
                prepared[-1], path=prepared[0].path, fingerprint=prepared[0].fingerprint
            )
        if mutation == "oversized":
            prepared[-1].path.write_bytes(b"too large" * 10)

    install_preparation(monkeypatch, alter=alter)
    sender = Sender()
    with pytest.raises(transport.CarouselDeliveryError):
        await transport.TelegramCarouselDelivery(sender).deliver(
            acquired, plan=plan, workspace=tmp_path, chat_id=1
        )
    assert not sender.calls


def payload(acquired, tmp_path, limits=None):
    private = tmp_path / "private"
    private.mkdir()
    return {
        "workspace": str(tmp_path),
        "private": str(private),
        "inputs": [str(x.media.file_path) for x in acquired.videos],
        "total_bytes": acquired.total_bytes,
        "limits": asdict(limits or transport.CarouselDeliveryLimits()),
    }


@pytest.mark.parametrize(
    "invalid",
    ["missing", "empty", "symlink", "outside", "duplicate", "total", "workspace_bytes", "entries"],
)
def test_preparation_input_and_workspace_limits(tmp_path, invalid):
    acquired, _ = collection(tmp_path, 2)
    data = payload(acquired, tmp_path)
    first = acquired.videos[0].media.file_path
    if invalid == "missing":
        first.unlink()
    if invalid == "empty":
        first.write_bytes(b"")
    if invalid == "symlink":
        first.unlink()
        first.symlink_to(acquired.videos[1].media.file_path)
    if invalid == "outside":
        data["inputs"][0] = str(tmp_path.parent / "outside.mp4")
    if invalid == "duplicate":
        data["inputs"][1] = data["inputs"][0]
    if invalid == "total":
        data["total_bytes"] += 1
    if invalid == "workspace_bytes":
        data["limits"]["max_workspace_bytes"] = 1
    if invalid == "entries":
        data["limits"]["max_workspace_entries"] = 1

    def forbidden(*a, **k):
        raise AssertionError("Preparation should not start")

    with pytest.raises((ValueError, OSError, transport.MediaProcessingError)):
        preparation.prepare_collection(data, prepare=forbidden)


@pytest.mark.parametrize(
    "kind",
    [
        "silent",
        "audio",
        "wrong_container",
        "wrong_video",
        "wrong_audio",
        "no_video",
        "bad_dimensions",
    ],
)
def test_actual_probe_policy_accepts_only_compatible_video_optional_audio(kind):
    streams = [{"codec_type": "video", "codec_name": "h264", "width": 64, "height": 96}]
    if kind in ("audio", "wrong_audio"):
        streams.append({"codec_type": "audio", "codec_name": "aac" if kind == "audio" else "opus"})
    if kind == "wrong_video":
        streams[0]["codec_name"] = "vp9"
    if kind == "no_video":
        streams = []
    if kind == "bad_dimensions":
        streams[0]["width"] = 0
    data = {
        "format": {
            "format_name": "matroska" if kind == "wrong_container" else "mp4",
            "duration": "1",
        },
        "streams": streams,
    }
    if kind in ("silent", "audio"):
        assert preparation._validate_probe(data) == {"width": 64, "height": 96, "duration": 1}
    else:
        with pytest.raises(transport.MediaProcessingError):
            preparation._validate_probe(data)


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_process_deadline_and_cancellation_reap_writer_before_cleanup(
    tmp_path, monkeypatch, cancel
):
    acquired, plan = collection(tmp_path, 1)
    original = asyncio.create_subprocess_exec
    processes = []
    script = """import json,sys,time
from pathlib import Path
p=json.load(sys.stdin)
Path(p['private'],'partial.mp4').write_bytes(b'partial')
time.sleep(60)
"""

    async def child(*args, **kwargs):
        process = await original(sys.executable, "-c", script, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", child)
    service = transport.TelegramCarouselDelivery(
        Sender(), transport.CarouselDeliveryLimits(max_prepare_seconds=5 if cancel else 0.2)
    )
    task = asyncio.create_task(service.deliver(acquired, plan=plan, workspace=tmp_path, chat_id=1))
    if cancel:
        for _ in range(200):
            if list(tmp_path.glob("*/partial.mp4")):
                break
            await asyncio.sleep(0.01)
        assert list(tmp_path.glob("*/partial.mp4"))
        task.cancel()
    with pytest.raises(
        transport.CarouselDeliveryCancelled if cancel else transport.CarouselDeliveryError
    ):
        await task
    assert processes and all(x.returncode is not None for x in processes)
    assert list(tmp_path.iterdir()) == [acquired.videos[0].media.file_path]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["empty", "photo_only", "malformed_videos", "bool_position"])
async def test_malformed_or_empty_collections_cannot_report_complete(tmp_path, monkeypatch, case):
    acquired, plan = collection(tmp_path, 1)
    if case == "empty":
        acquired = replace(acquired, videos=(), total_bytes=0)
        plan = replace(plan, items=(), selected_videos=(), total_entries=0)
    if case == "photo_only":
        acquired, plan = collection(tmp_path, 0, photos=(1,))
    if case == "malformed_videos":
        acquired = replace(acquired, videos=None)
    if case == "bool_position":
        acquired = replace(acquired, videos=(replace(acquired.videos[0], position=True),))
    calls = install_preparation(monkeypatch)
    sender = Sender()
    with pytest.raises(transport.CarouselDeliveryError) as error:
        await transport.TelegramCarouselDelivery(sender).deliver(
            acquired, plan=plan, workspace=tmp_path, chat_id=1
        )
    assert not error.value.progress.complete and not calls and not sender.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("response_kind", ["none", "list", "group"])
async def test_individual_video_requires_an_individual_message(
    tmp_path, monkeypatch, response_kind
):
    acquired, plan = collection(tmp_path, 1)
    install_preparation(monkeypatch)

    def malformed(messages):
        return {"none": None, "list": messages, "group": response(1, "unexpected")}[response_kind]

    sender = Sender(malformed=malformed)
    with pytest.raises(transport.CarouselDeliveryError) as error:
        await transport.TelegramCarouselDelivery(sender).deliver(
            acquired, plan=plan, workspace=tmp_path, chat_id=1
        )
    assert error.value.progress.uncertain_positions == (1,) and not error.value.progress.complete
    assert len(sender.calls) == 1


@pytest.mark.asyncio
async def test_repeated_cancellation_waits_for_preparation_process_cleanup(tmp_path, monkeypatch):
    acquired, plan = collection(tmp_path, 1)
    original_create = asyncio.create_subprocess_exec
    processes = []
    script = """import json,sys,time
from pathlib import Path
p=json.load(sys.stdin)
Path(p['private'],'partial.mp4').write_bytes(b'partial')
time.sleep(60)
"""

    async def child(*args, **kwargs):
        process = await original_create(sys.executable, "-c", script, **kwargs)
        processes.append(process)
        return process

    original_reap = transport._reap
    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow_reap(process):
        entered.set()
        await release.wait()
        await original_reap(process)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", child)
    monkeypatch.setattr(transport, "_reap", slow_reap)
    task = asyncio.create_task(
        transport.TelegramCarouselDelivery(Sender()).deliver(
            acquired, plan=plan, workspace=tmp_path, chat_id=1
        )
    )
    for _ in range(200):
        if list(tmp_path.glob("*/partial.mp4")):
            break
        await asyncio.sleep(0.01)
    assert list(tmp_path.glob("*/partial.mp4"))
    task.cancel()
    await entered.wait()
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done() and list(tmp_path.glob("*/partial.mp4"))
    release.set()
    with pytest.raises(transport.CarouselDeliveryCancelled):
        await task
    assert all(p.returncode is not None for p in processes)
    assert list(tmp_path.iterdir()) == [acquired.videos[0].media.file_path]


@pytest.mark.asyncio
async def test_all_aiogram_objects_exist_before_first_request(tmp_path, monkeypatch):
    acquired, plan = collection(tmp_path, 21)
    install_preparation(monkeypatch)
    objects = []
    actual = transport.InputMediaVideo

    def build(**kwargs):
        result = actual(**kwargs)
        objects.append(result)
        return result

    monkeypatch.setattr(transport, "InputMediaVideo", build)
    sender = Sender()
    send = sender._send

    async def barrier(kind, kwargs):
        assert len(objects) == 21
        return await send(kind, kwargs)

    monkeypatch.setattr(sender, "_send", barrier)
    result = await transport.TelegramCarouselDelivery(sender).deliver(
        acquired, plan=plan, workspace=tmp_path, chat_id=1
    )
    assert result.complete


@pytest.mark.asyncio
async def test_barrier_deadline_prevents_first_request(tmp_path, monkeypatch):
    acquired, plan = collection(tmp_path, 1)
    install_preparation(monkeypatch)
    prepare = transport._prepare

    async def slow(*args):
        result = await prepare(*args)
        await asyncio.sleep(0.02)
        return result

    monkeypatch.setattr(transport, "_prepare", slow)
    sender = Sender()
    with pytest.raises(transport.CarouselDeliveryError) as error:
        await transport.TelegramCarouselDelivery(
            sender, transport.CarouselDeliveryLimits(max_prepare_seconds=0.01)
        ).deliver(acquired, plan=plan, workspace=tmp_path, chat_id=1)
    assert error.value.stage == "preparation" and not sender.calls


@pytest.mark.asyncio
async def test_reused_album_id_after_success_is_ambiguous(tmp_path, monkeypatch):
    acquired, plan = collection(tmp_path, 21)
    install_preparation(monkeypatch)
    sender = Sender(
        malformed=lambda messages: [
            m.model_copy(update={"media_group_id": "same"}) for m in messages
        ]
    )
    with pytest.raises(transport.CarouselDeliveryError) as error:
        await transport.TelegramCarouselDelivery(sender).deliver(
            acquired, plan=plan, workspace=tmp_path, chat_id=1
        )
    assert error.value.progress.confirmed_positions == tuple(range(1, 11))
    assert error.value.progress.uncertain_positions == tuple(range(11, 21))
    assert len(sender.calls) == 2 and not error.value.progress.complete
