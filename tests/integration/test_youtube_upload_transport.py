"""P9-R3a: real SDK multipart on numeric loopback; no external platforms or poller."""

import asyncio
import socket
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import pytest
import pytest_asyncio
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.methods import EditMessageText, SendAudio, SendMessage, SendVideo
from aiogram.types import FSInputFile
from aiohttp import web

from social_video_downloader import handlers
from social_video_downloader.bot import create_dispatcher
from social_video_downloader.config import Settings
from social_video_downloader.download_protection import DownloadAdmission
from social_video_downloader.infrastructure.telegram_audio import PreparedAudio
from social_video_downloader.infrastructure.telegram_upload import OwnedUploadFile
from social_video_downloader.telegram_interactions import InMemoryPendingInteractionStore
from tests.test_handlers import FakeDownloadService, terminal_video_mode_plan
from tests.test_telegram_localization import callback_update, message_update

# Synthetic fixture identity only; never use environment credentials.
TOKEN = "123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi"
URL = "https://www.youtube.com/watch?v=Synthetic01"
PAYLOAD = b"synthetic upload bytes\n" * 16384


class TransportSession(AiohttpSession):
    """Observe actual SDK outcomes; all serialization/I/O stays in super()."""

    def __init__(self, state, base):
        super().__init__(api=TelegramAPIServer.from_base(base), timeout=3)
        self.state = state
        self.calls = []
        self.messages = []
        self.errors = []

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        original_api = self.api
        if isinstance(method, (SendVideo, SendAudio)):
            assert isinstance(
                method.audio if isinstance(method, SendAudio) else method.video, FSInputFile
            )
            if self.state.case == "connect":
                self.api = TelegramAPIServer.from_base(self.state.refused_base)
            if self.state.case == "timeout":
                timeout = 1
        try:
            result = await super().make_request(bot, method, timeout)
        except BaseException as error:
            self.errors.append((type(method), type(error)))
            raise
        finally:
            self.api = original_api
        if isinstance(method, (SendMessage, EditMessageText)):
            self.messages.append(result)
        return result


@pytest_asyncio.fixture
async def wire(monkeypatch, tmp_path):
    baseline_tasks = set(asyncio.all_tasks())
    state = SimpleNamespace(
        case="success",
        close_unknown=False,
        media_requests=0,
        bodies=[],
        fields=[],
        active_readers=set(),
        handles=[],
        native_handles=[],
        mode="video",
        closing_started=asyncio.Event(),
        uploads=[],
        cleanup_open_counts=[],
        cleanup_snapshots=[],
        managers=[],
        outcomes=[],
        read_calls=0,
        reader_blocked=asyncio.Event(),
        first_bytes=asyncio.Event(),
        release=asyncio.Event(),
        blocked_network=[],
        texts=[],
    )
    sequence = [1000]

    async def endpoint(request):
        method = request.match_info["method"]
        if method in {"sendVideo", "sendAudio"}:
            state.media_requests += 1
            assert request.content_type == "multipart/form-data"
            parts = await request.multipart()
            total, fields = bytearray(), {}
            while (part := await parts.next()) is not None:
                if part.filename:
                    assert part.filename == (
                        "example.m4a" if method == "sendAudio" else "example.mp4"
                    )
                    while chunk := await part.read_chunk(8192):
                        total.extend(chunk)
                        state.first_bytes.set()
                        if state.case == "partial":
                            state.bodies.append(bytes(total))
                            request.transport.abort()
                            return web.Response()
                else:
                    fields[part.name] = await part.text()
            state.bodies.append(bytes(total))
            state.fields.append(fields)
            assert bytes(total) == PAYLOAD
            assert fields["audio" if method == "sendAudio" else "video"].startswith("attach://")
            if state.case == "lost":
                request.transport.abort()
                return web.Response()
            if state.case == "timeout":
                await state.release.wait()
            if state.case in {"400", "429", "500"}:
                code = int(state.case)
                body = {"ok": False, "error_code": code, "description": "Synthetic refusal"}
                if code == 429:
                    body["parameters"] = {"retry_after": 1}
                return web.json_response(body, status=code)
            payload = {
                "message_id": 2000,
                "date": 0,
                "chat": {"id": 7, "type": "private"},
                "video": {
                    "file_id": "fixture",
                    "file_unique_id": "fixture",
                    "width": 64,
                    "height": 96,
                    "duration": 1,
                },
            }
            if method == "sendAudio":
                payload.pop("video")
                payload["audio"] = {
                    "file_id": "fixture",
                    "file_unique_id": "fixture",
                    "duration": 1,
                }
        else:
            data = await request.post()
            if method == "answerCallbackQuery":
                return web.json_response({"ok": True, "result": True})
            assert method in {"sendMessage", "editMessageText"}
            state.texts.append(data.get("text", ""))
            if state.case == "edit" and data.get("text") == "✅ File sent.":
                return web.json_response(
                    {
                        "ok": False,
                        "error_code": 500,
                        "description": "Synthetic terminal edit failure",
                    },
                    status=500,
                )
            sequence[0] += 1
            payload = {
                "message_id": int(data.get("message_id", sequence[0])),
                "date": 0,
                "chat": {"id": int(data["chat_id"]), "type": "private"},
                "text": data.get("text", ""),
            }
            if data.get("reply_markup"):
                import json

                payload["reply_markup"] = json.loads(data["reply_markup"])
        return web.json_response({"ok": True, "result": payload})

    application = web.Application()
    application.router.add_post("/bot{token}/{method}", endpoint)
    runner = web.AppRunner(application, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    refused = socket.socket()
    refused.bind(("127.0.0.1", 0))  # Bound but not listening: deterministic connect refusal.
    refused_port = refused.getsockname()[1]
    allowed_ports = {port, refused_port}
    connect, connect_ex, resolve = (
        socket.socket.connect,
        socket.socket.connect_ex,
        socket.getaddrinfo,
    )

    def check(address):
        if (
            not isinstance(address, tuple)
            or address[0] != "127.0.0.1"
            or address[1] not in allowed_ports
        ):
            state.blocked_network.append(True)
            raise AssertionError("External network is forbidden in this fixture")

    def guarded_connect(sock, address):
        check(address)
        return connect(sock, address)

    def guarded_connect_ex(sock, address):
        check(address)
        return connect_ex(sock, address)

    def guarded_resolve(host, service, *args, **kwargs):
        check((host, int(service)))
        return resolve(host, service, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_resolve)
    state.refused_base = f"http://127.0.0.1:{refused_port}"
    session = TransportSession(state, f"http://127.0.0.1:{port}")
    bot = Bot(TOKEN, session=session)
    now = [0.0]
    gate = DownloadAdmission(max_active=1, clock=lambda: now[0], free_bytes=lambda: 100 * 1024**3)
    service = FakeDownloadService(plan=terminal_video_mode_plan())
    original_download = service.download

    def download(*args, **kwargs):
        result = original_download(*args, **kwargs)
        result.file_path.write_bytes(PAYLOAD)
        return result

    monkeypatch.setattr(service, "download", download)
    monkeypatch.setattr(handlers, "download_service", service)
    monkeypatch.setattr(handlers, "pending_interaction_store", InMemoryPendingInteractionStore())
    monkeypatch.setattr(handlers, "prepare_telegram_video", lambda path, **kw: path)
    monkeypatch.setattr(
        handlers, "prepare_telegram_audio", lambda path, duration, **kw: PreparedAudio(path, None)
    )
    monkeypatch.setattr(handlers, "inspect_telegram_video", lambda path, **kw: {})
    monkeypatch.setattr(handlers, "telegram_video_upload_parameters", lambda probe: {})
    real_delivery = handlers._download_and_deliver_media

    async def delivery(*args, **kwargs):
        try:
            result = await real_delivery(*args, **kwargs)
        except asyncio.CancelledError:
            state.outcomes.append("cancelled")
            raise
        state.outcomes.append(result.state.value)
        return result

    monkeypatch.setattr(handlers, "_download_and_deliver_media", delivery)
    import aiofiles.threadpool
    import aiogram.types.input_file as input_file

    native_open = aiofiles.threadpool.sync_open

    def observe_native_open(*args, **kwargs):
        handle = native_open(*args, **kwargs)
        state.native_handles.append(handle)
        return handle

    monkeypatch.setattr(aiofiles.threadpool, "sync_open", observe_native_open)
    original_open = input_file.aiofiles.open
    finish = OwnedUploadFile._finish

    async def observed_finish(upload):
        state.uploads.append(upload)
        state.closing_started.set()
        if state.case == "reader_unknown" or state.close_unknown:
            raise OSError("Synthetic private close failure")
        return await finish(upload)

    monkeypatch.setattr(OwnedUploadFile, "_finish", observed_finish)

    class TrackedOpen:
        def __init__(self, path, *args, **kwargs):
            self.path = Path(path)
            self.context = original_open(path, *args, **kwargs)

        async def __aenter__(self):
            self.file = await self.context.__aenter__()
            state.handles.append(self.file)
            state.active_readers.add(self.path)
            owner = self

            class Reader:
                async def read(self, size):
                    data = await owner.file.read(size)
                    state.read_calls += 1
                    if state.case == "cancel" and state.read_calls == 2:
                        state.reader_blocked.set()
                        await state.release.wait()
                    return data

            return Reader()

        async def __aexit__(self, *args):
            try:
                return await self.context.__aexit__(*args)
            finally:
                state.active_readers.discard(self.path)

    # Only cancellation tests install a barrier around real aiofiles I/O.
    # Partial-upload tests keep the original aiofiles.open itself unchanged.
    state.install_read_barrier = lambda: monkeypatch.setattr(
        input_file.aiofiles, "open", TrackedOpen
    )

    class OwnedDirectory(TemporaryDirectory):
        def __init__(self, **kwargs):
            super().__init__(dir=tmp_path, **kwargs)
            state.managers.append(self)

        def __exit__(self, *args):
            state.cleanup_snapshots.append(set(state.active_readers))
            state.cleanup_open_counts.append(sum(not h.closed for h in state.native_handles))
            if state.case == "cleanup_unknown":
                self._finalizer.detach()
                raise OSError("Synthetic cleanup failure")
            return super().__exit__(*args)

    monkeypatch.setattr(handlers, "TemporaryDirectory", OwnedDirectory)
    dp = create_dispatcher(Settings("synthetic"), download_admission=gate)
    state.bot, state.dp, state.session = bot, dp, session
    state.gate, state.now, state.service = gate, now, service
    try:
        yield state
    finally:
        state.release.set()
        await session.close()
        await runner.cleanup()
        refused.close()
        for upload in state.uploads:
            await finish(upload)
        for manager in state.managers:
            manager.cleanup()
        assert not state.active_readers
        assert all(handle.closed for handle in state.handles)
        assert all(handle.closed for handle in state.native_handles)
        assert not list(tmp_path.iterdir())
        assert not state.blocked_network
        assert not [
            task
            for task in asyncio.all_tasks() - baseline_tasks
            if task is not asyncio.current_task() and not task.done()
        ]


async def prepare(state):
    await state.dp.feed_update(state.bot, message_update(URL, "en"))
    card = state.session.messages[-1]
    data = card.reply_markup.inline_keyboard[1 if state.mode == "audio" else 0][0].callback_data
    return callback_update(card, data, "en")


async def assert_replay_and_recovery(state, update):
    attempts = sum(isinstance(m, (SendVideo, SendAudio)) for m in state.session.calls)
    downloads = len(state.service.calls)
    await state.dp.feed_update(state.bot, update)
    assert sum(isinstance(m, (SendVideo, SendAudio)) for m in state.session.calls) == attempts == 1
    assert len(state.service.calls) == downloads == 1
    assert not state.gate._leases
    assert not state.active_readers
    assert all(handle.closed for handle in state.handles)
    assert all(count == 0 for count in state.cleanup_open_counts), (
        "workspace cleanup started with native upload file handles still open",
        state.cleanup_open_counts,
    )
    assert all(not snapshot for snapshot in state.cleanup_snapshots)
    assert all(not call[1].exists() for call in state.service.calls)
    # A new independent request, not a retry of the consumed operation.
    state.case = "success"
    state.now[0] = 3
    next_update = await prepare(state)
    await state.dp.feed_update(state.bot, next_update)
    assert len(state.service.calls) == 2
    assert sum(isinstance(m, (SendVideo, SendAudio)) for m in state.session.calls) == 2
    assert state.outcomes[-1] == "delivered"
    assert not state.gate._leases
    assert all(
        TOKEN not in text and "Synthetic" not in text and "127.0.0.1" not in text
        for text in state.texts
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case,expected,error",
    [
        ("success", "delivered", None),
        ("connect", "uncertain", TelegramNetworkError),
        ("partial", "uncertain", TelegramNetworkError),
        ("lost", "uncertain", TelegramNetworkError),
        ("timeout", "uncertain", TelegramNetworkError),
        ("500", "uncertain", TelegramServerError),
        ("400", "failed", TelegramBadRequest),
        ("429", "failed", TelegramRetryAfter),
        ("edit", "delivered", None),
    ],
)
@pytest.mark.parametrize("mode", ["video", "audio"])
async def test_upload_transport_outcome_and_recovery(wire, case, expected, error, mode):
    wire.mode = mode
    update = await prepare(wire)
    wire.case = case
    await wire.dp.feed_update(wire.bot, update)
    assert wire.outcomes == [expected]
    if error:
        assert (SendAudio if mode == "audio" else SendVideo, error) in wire.session.errors
    if case == "edit":
        assert (EditMessageText, TelegramServerError) in wire.session.errors
    if case == "connect":
        assert wire.media_requests == 0
    elif case == "partial":
        assert 0 < len(wire.bodies[0]) < len(PAYLOAD)
    else:
        assert wire.bodies == [PAYLOAD]
    if expected == "uncertain":
        assert "The file may have arrived" in wire.texts[-1]
    elif expected == "failed":
        assert "Couldn't send the file" in wire.texts[-1]
    elif case != "edit":
        assert wire.texts[-1] == "✅ File sent."
    wire.release.set()
    await assert_replay_and_recovery(wire, update)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["video", "audio"])
@pytest.mark.parametrize("repeat", [False, True])
async def test_cancelled_real_upload_closes_reader_before_workspace_cleanup(wire, mode, repeat):
    wire.mode = mode
    update = await prepare(wire)
    wire.case = "cancel"
    wire.install_read_barrier()
    task = asyncio.create_task(wire.dp.feed_update(wire.bot, update))
    try:
        await asyncio.wait_for(wire.reader_blocked.wait(), 3)
        await asyncio.wait_for(wire.first_bytes.wait(), 3)
        task.cancel()
        await asyncio.wait_for(wire.closing_started.wait(), 3)
        assert not task.done()
        assert wire.gate._leases[7].working
        assert wire.service.calls[0][1].exists()
        assert wire.cleanup_snapshots == []
        # /cancel is not permission to free an executing request.
        await wire.dp.feed_update(wire.bot, message_update("/cancel", "en"))
        assert wire.gate._leases[7].working
        if repeat:
            task.cancel()
        wire.release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
    finally:
        wire.release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert wire.outcomes == ["cancelled"]
    assert "Delivery isn't confirmed" in wire.texts[-1]
    await assert_replay_and_recovery(wire, update)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["video", "audio"])
@pytest.mark.parametrize("failure", ["reader_unknown", "cleanup_unknown", "reader_unknown_network"])
async def test_unknown_cleanup_retains_workspace_and_admission(wire, mode, failure):
    wire.mode = mode
    update = await prepare(wire)
    wire.case = "partial" if failure == "reader_unknown_network" else failure
    wire.close_unknown = failure == "reader_unknown_network"
    await wire.dp.feed_update(wire.bot, update)
    # A confirmed receipt remains delivered even if cleanup is unknown.
    if failure == "reader_unknown_network":
        assert wire.outcomes == ["uncertain"]
        assert "The file may have arrived" in wire.texts[-1]
    else:
        assert wire.outcomes == ["delivered"]
        assert "error occurred while finishing" in wire.texts[-1]
    assert len(wire.service.calls) == wire.media_requests == 1
    assert wire.service.calls[0][1].exists()
    lease = wire.gate._leases[7]
    assert lease.quarantined and lease.working and lease.contexts == 0
    await wire.dp.feed_update(wire.bot, update)
    await wire.dp.feed_update(wire.bot, message_update("/cancel", "en"))
    wire.now[0] = 3
    await wire.dp.feed_update(wire.bot, message_update(URL, "en"))
    await wire.dp.feed_update(wire.bot, message_update(URL, "en", user=8))
    assert wire.gate._leases[7] is lease
    assert len(wire.service.calls) == wire.media_requests == 1
    assert "Synthetic private" not in " ".join(wire.texts)
