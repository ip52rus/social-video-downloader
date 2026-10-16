"""Network-forbidden carousel acquisition through real yt-dlp and local ffprobe."""

import asyncio
import io
import json
import shutil
import subprocess
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest
import yt_dlp
from yt_dlp.networking import Response

from social_video_downloader.domain.carousel import (
    CarouselItemKind,
    CarouselPlanState,
    CarouselScope,
)
from social_video_downloader.domain.errors import DownloadFailedError, DownloadTimeoutError
from social_video_downloader.infrastructure.instagram_acquisition import (
    _MediaBudget,
    acquire_in_workspace,
)
from social_video_downloader.infrastructure.instagram_metadata import CarouselInstagramIE
from social_video_downloader.infrastructure.workspace import temporary_workspace
from social_video_downloader.providers.instagram import InstagramProvider
from social_video_downloader.services.instagram_acquisition import (
    CarouselAcquisitionLimits,
    InstagramCarouselAcquisition,
    plan_from_payload,
    plan_payload,
)
from social_video_downloader.services.instagram_carousel import InstagramCarouselService

URL = "https://www.instagram.com/p/Fixture_Carousel/"
VIDEO = {"media_type": 2, "video_versions": [{"url": "https://media.invalid/video.mp4"}]}
PHOTO = {
    "media_type": 1,
    "image_versions2": {"candidates": [{"url": "https://media.invalid/photo.jpg"}]},
}


def product(count, photos=()):
    return {
        "pk": 100,
        "carousel_media": [
            {**deepcopy(PHOTO if i in photos else VIDEO), "pk": 1000 + i}
            for i in range(1, count + 1)
        ],
    }


class Runtime:
    def __init__(self, data, media):
        self.data = deepcopy(data)
        self.media = media
        self.extractions = 0
        self.processed = []
        self.selected_formats = []
        self.requests = 0
        self.mutate = lambda raw: raw
        self.fail_at = None
        self.output = "normal"
        self.headers = None
        self.provider = InstagramProvider(self.factory)

    def factory(self, options):
        owner = self

        class LocalYDL(yt_dlp.YoutubeDL):
            def __init__(self):
                super().__init__(options, auto_init=False)

            def extract_info(self, url, **kwargs):
                assert url == URL
                assert kwargs == {"download": False, "process": False, "ie_key": "Instagram"}
                owner.extractions += 1
                raw = CarouselInstagramIE(self)._extract_product(deepcopy(owner.data))
                return owner.mutate(raw)

            def process_ie_result(self, result, download=True, **kwargs):
                assert result.get("_type", "video") == "video"
                assert "entries" not in result
                return super().process_ie_result(result, download=download, **kwargs)

            def process_info(self, info):
                owner.processed.append(info["id"])
                owner.selected_formats.append(info["format_id"])
                assert self.params["retries"] == self.params["fragment_retries"] == 0
                assert self.params["continuedl"] is False
                if len(owner.processed) == owner.fail_at:
                    raise RuntimeError("synthetic failure")
                if owner.output == "normal":
                    return super().process_info(info)
                target = Path(self.prepare_filename(info))
                if owner.output == "symlink":
                    target.symlink_to(owner.media)
                elif owner.output not in {"missing", "directory"}:
                    target.write_bytes(b"" if owner.output == "empty" else owner.media.read_bytes())
                if owner.output == "directory":
                    target.mkdir()
                if owner.output == "extra":
                    target.with_name("unexpected.mp4").write_bytes(b"extra")

            def urlopen(self, request):
                assert request.url.startswith("https://media.invalid/")
                assert ".jpg" not in request.url
                owner.requests += 1
                body = owner.media.read_bytes()
                headers = (
                    owner.headers
                    if owner.headers is not None
                    else {"Content-Length": str(len(body))}
                )
                return Response(io.BytesIO(body), request.url, headers)

        return LocalYDL()

    def plan(self):
        return InstagramCarouselService(self.provider).create_selection_plan(URL)


@pytest.fixture(scope="module")
def media_files(tmp_path_factory):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("Local synthetic acquisition tests require FFmpeg and ffprobe")
    directory = tmp_path_factory.mktemp("carousel-fixtures")
    result = {}
    for kind in ("video", "silent", "audio"):
        path = directory / f"{kind}.mp4"
        args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        if kind != "audio":
            args += ["-f", "lavfi", "-i", "color=c=blue:s=64x96:r=10"]
        if kind != "silent":
            args += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000"]
        args += ["-t", "0.3"]
        if kind != "audio":
            args += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
        if kind != "silent":
            args += ["-c:a", "aac"]
        subprocess.run([*args, str(path)], check=True, capture_output=True)
        result[kind] = path
    corrupt = directory / "corrupt.mp4"
    corrupt.write_bytes(b"not media")
    result["corrupt"] = corrupt
    return result


def acquire(runtime, plan, tmp_path, limits=None):
    with temporary_workspace(base_dir=tmp_path) as workspace:
        return acquire_in_workspace(
            plan, workspace, limits or CarouselAcquisitionLimits(), runtime.provider
        )


@pytest.mark.parametrize("count", [1, 2, 5, 10, 11, 20, 21])
def test_sequential_complete_acquisition_and_snapshot_refresh(tmp_path, media_files, count):
    runtime = Runtime(product(count), media_files["video"])
    plan = runtime.plan()
    result = acquire(runtime, plan, tmp_path)
    assert len(result["durations"]) == count
    assert all(0 < value < 1 for value in result["durations"])
    assert runtime.processed == [f"video-{i}" for i in range(1, count + 1)]
    assert runtime.extractions == 2  # planning plus exactly one uncached acquisition extraction
    assert runtime.requests == count
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("count,photos", [(3, (2,)), (20, (8, 9, 18))])
def test_mixed_only_videos_in_original_order(tmp_path, media_files, count, photos):
    runtime = Runtime(product(count, photos), media_files["video"])
    plan = runtime.plan()
    assert [x.position for x in plan.items if x.kind is CarouselItemKind.PHOTO] == list(photos)
    acquire(runtime, plan, tmp_path)
    assert runtime.processed == [f"video-{i}" for i in range(1, count + 1) if i not in photos]
    assert runtime.requests == count - len(photos)


@pytest.mark.parametrize(
    "mutation", ["id", "order", "count", "kind", "unknown", "unsupported", "mapped_id"]
)
def test_changed_publication_fails_before_first_acquisition(tmp_path, media_files, mutation):
    runtime = Runtime(product(3), media_files["video"])
    plan = runtime.plan()
    items = runtime.data["carousel_media"]
    if mutation == "id":
        items[1]["pk"] = 9999
    if mutation == "order":
        items.reverse()
    if mutation == "count":
        items.pop()
    if mutation == "kind":
        items[1] = {**deepcopy(PHOTO), "pk": items[1]["pk"]}
    if mutation == "unknown":
        items[1] = {"pk": items[1]["pk"]}
    if mutation == "unsupported":
        items[1]["video_versions"] = [{"width": 720}]
    if mutation == "mapped_id":

        def change(raw):
            raw["entries"][1]["id"] = "different"
            return raw

        runtime.mutate = change
    with pytest.raises(DownloadFailedError):
        acquire(runtime, plan, tmp_path)
    assert runtime.processed == [] and runtime.requests == 0
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "case", ["photo", "empty", "unknown", "unsupported", "reference", "forged", "count"]
)
def test_invalid_plan_never_starts_acquisition(tmp_path, media_files, case):
    runtime = Runtime(product(2), media_files["video"])
    if case == "photo":
        runtime.data = product(2, (1, 2))
    if case == "empty":
        runtime.data = product(0)
    if case == "unknown":
        runtime.data["carousel_media"][0] = {"pk": 1001}
    if case == "unsupported":
        runtime.data["carousel_media"][0]["video_versions"] = [{"width": 720}]
    plan = runtime.plan()
    if case == "reference":
        plan = replace(plan, publication_url=URL + "?img_index=1")
    if case == "forged":
        plan = replace(plan, selected_videos=plan.selected_videos[:1])
    limits = CarouselAcquisitionLimits(max_videos=1 if case == "count" else 25)
    with pytest.raises(DownloadFailedError):
        acquire(runtime, plan, tmp_path, limits)
    assert not runtime.processed and not runtime.requests


@pytest.mark.parametrize(
    "protocol,url,extra",
    [
        (None, "https://media.invalid/file.m3u8", {}),
        ("m3u8_native", "https://media.invalid/file.mp4", {}),
        ("http_dash_segments", "https://media.invalid/file.mp4", {}),
        ("https", "https://media.invalid/file.mp4", {"fragments": []}),
        (
            "https",
            "https://media.invalid/file.mp4",
            {"manifest_url": "https://media.invalid/m.mpd"},
        ),
        ("https", "https://media.invalid/file.mp4", {"acodec": "none"}),
        ("https", "https://media.invalid/file.mp4", {"vcodec": "none"}),
        ("https", "https://media.invalid/file.mp4", {"has_drm": True}),
    ],
)
def test_inadmissible_fresh_child_never_processed(tmp_path, media_files, protocol, url, extra):
    runtime = Runtime(product(2), media_files["video"])
    plan = runtime.plan()

    def mutate(raw):
        raw["entries"][1]["formats"] = [{"url": url, "ext": "mp4", "protocol": protocol, **extra}]
        return raw

    runtime.mutate = mutate
    with pytest.raises(DownloadFailedError):
        acquire(runtime, plan, tmp_path)
    assert runtime.processed == [] and runtime.requests == 0


@pytest.mark.parametrize("output", ["missing", "empty", "extra", "symlink", "directory"])
def test_output_shape_rejected_and_workspace_removed(tmp_path, media_files, output):
    runtime = Runtime(product(2), media_files["video"])
    plan = runtime.plan()
    runtime.output = output
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_text("keep")
    with pytest.raises(DownloadFailedError):
        acquire(runtime, plan, tmp_path)
    assert list(tmp_path.iterdir()) == [unrelated]
    assert unrelated.read_text() == "keep"
    assert media_files["video"].is_file()


@pytest.mark.parametrize("failure_at", [1, 2, 3])
def test_first_middle_last_failure_never_returns_partial_collection(
    tmp_path, media_files, failure_at
):
    runtime = Runtime(product(3), media_files["video"])
    plan = runtime.plan()
    runtime.fail_at = failure_at
    with pytest.raises(RuntimeError):
        acquire(runtime, plan, tmp_path)
    assert len(runtime.processed) == failure_at
    assert runtime.requests == failure_at - 1
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("kind", ["silent", "audio", "corrupt"])
def test_real_probe_rejects_missing_streams_or_corruption(tmp_path, media_files, kind):
    runtime = Runtime(product(1), media_files[kind])
    with pytest.raises(DownloadFailedError):
        acquire(runtime, runtime.plan(), tmp_path)
    assert runtime.requests == 1
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("limit", ["max_file_bytes", "max_total_bytes", "max_temp_bytes"])
@pytest.mark.parametrize("headers", [{}, {"Content-Length": "99999999"}, {"Content-Length": "5"}])
def test_real_http_downloader_budget_independent_of_size_headers(
    tmp_path, media_files, limit, headers
):
    runtime = Runtime(product(2), media_files["video"])
    runtime.headers = headers
    size = runtime.media.stat().st_size
    amount = size // 2 if limit == "max_file_bytes" else size + size // 2
    limits = replace(CarouselAcquisitionLimits(), **{limit: amount})
    with pytest.raises(DownloadFailedError):
        acquire(runtime, runtime.plan(), tmp_path, limits)
    assert runtime.requests <= 2
    assert not list(tmp_path.iterdir())


def test_stream_guard_caps_reads_even_without_content_length():
    limits = CarouselAcquisitionLimits(max_file_bytes=5, max_total_bytes=8, max_temp_bytes=9)
    budget = _MediaBudget(limits)
    raw = io.BytesIO(b"123456789")
    response = budget.wrap(Response(raw, "https://media.invalid/file.mp4", {}))
    assert response.read(10000) == b"12345"
    with pytest.raises(DownloadFailedError):
        response.read(1)
    assert budget.total == 5


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_videos", 0),
        ("max_file_bytes", True),
        ("max_total_bytes", -1),
        ("max_temp_bytes", 1.5),
        ("max_seconds", float("nan")),
        ("max_seconds", float("inf")),
        ("max_seconds", 0),
    ],
)
def test_invalid_limits(field, value):
    with pytest.raises(ValueError):
        CarouselAcquisitionLimits(**{field: value})


def test_plan_wire_roundtrip_and_expired_inspection_does_not_reuse_locators(tmp_path, media_files):
    runtime = Runtime(product(1), media_files["video"])
    plan = runtime.plan()
    runtime.provider._carousel_cache[URL] = (0, runtime.provider.inspect_carousel(URL))
    assert plan_from_payload(json.loads(json.dumps(plan_payload(plan)))) == plan
    acquire(runtime, plan, tmp_path)
    assert runtime.extractions == 2


def subprocess_script(media_path, count=2, mode="normal"):
    # Only a test launcher is substituted; child executes the production acquisition
    # body, actual yt-dlp processing and ffprobe against local synthetic responses.
    return f"""
import sys,json,time
from pathlib import Path
sys.path.insert(0,{str(Path(__file__).parent)!r})
from test_instagram_acquisition import Runtime,product
import social_video_downloader.infrastructure.instagram_acquisition as boundary
runtime=Runtime(product({count}),Path({str(media_path)!r}))
if {mode!r} == 'fail': runtime.fail_at = 2
if {mode!r} == 'hang':
    payload=json.load(sys.stdin)
    Path(payload['workspace'],'partial.mp4').write_bytes(b'partial')
    time.sleep(60)
boundary.InstagramProvider=lambda: runtime.provider
boundary.main()
"""


def install_child(monkeypatch, script):
    original = asyncio.create_subprocess_exec
    processes = []

    async def launch(executable, *args, **kwargs):
        assert args == ("-m", "social_video_downloader.infrastructure.instagram_acquisition")
        process = await original(executable, "-c", script, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", launch)
    return processes


@pytest.mark.asyncio
async def test_public_collection_is_immutable_and_caller_owns_outputs(
    tmp_path, media_files, monkeypatch
):
    runtime = Runtime(product(2), media_files["video"])
    processes = install_child(monkeypatch, subprocess_script(runtime.media))
    result = await InstagramCarouselAcquisition().acquire(runtime.plan(), tmp_path)
    assert [x.position for x in result.videos] == [1, 2]
    assert [x.item_id for x in result.videos] == ["1001", "1002"]
    assert result.file_count == 2
    assert result.total_bytes == 2 * runtime.media.stat().st_size
    assert all(x.media.file_path.parent == tmp_path for x in result.videos)
    assert all(x.media.file_path.read_bytes() == runtime.media.read_bytes() for x in result.videos)
    assert len(list(tmp_path.iterdir())) == 2
    with pytest.raises(FrozenInstanceError):
        result.total_bytes = 0
    assert all(p.returncode == 0 for p in processes)


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_deadline_and_cancellation_kill_writer_before_cleanup(
    tmp_path, media_files, monkeypatch, cancel
):
    runtime = Runtime(product(2), media_files["video"])
    processes = install_child(monkeypatch, subprocess_script(runtime.media, mode="hang"))
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_text("keep")
    service = InstagramCarouselAcquisition(
        CarouselAcquisitionLimits(max_seconds=10 if cancel else 0.5)
    )
    task = asyncio.create_task(service.acquire(runtime.plan(), tmp_path))
    if cancel:
        for _ in range(200):
            if list(tmp_path.glob("*/partial.mp4")):
                break
            await asyncio.sleep(0.01)
        assert list(tmp_path.glob("*/partial.mp4"))
        task.cancel()
    with pytest.raises(asyncio.CancelledError if cancel else DownloadTimeoutError):
        await task
    assert processes and all(p.returncode is not None for p in processes)
    assert list(tmp_path.iterdir()) == [unrelated]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["collision", "exception", "cancellation"])
async def test_publication_rolls_back_only_owned_names(tmp_path, media_files, monkeypatch, failure):
    runtime = Runtime(product(2), media_files["video"])
    install_child(monkeypatch, subprocess_script(runtime.media))
    import os

    original = os.link
    count = 0
    collision = []

    def link(source, destination, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            if failure == "collision":
                destination.write_bytes(b"unrelated")
                collision.append(destination)
                return original(source, destination, **kwargs)
            if failure == "cancellation":
                raise asyncio.CancelledError
            raise OSError("synthetic publication interruption")
        return original(source, destination, **kwargs)

    monkeypatch.setattr(os, "link", link)
    with pytest.raises(asyncio.CancelledError if failure == "cancellation" else OSError):
        await InstagramCarouselAcquisition().acquire(runtime.plan(), tmp_path)
    assert list(tmp_path.iterdir()) == collision
    if collision:
        assert collision[0].read_bytes() == b"unrelated"


@pytest.mark.asyncio
async def test_blocked_or_item_reference_plan_never_launches_process(
    tmp_path, media_files, monkeypatch
):
    runtime = Runtime(product(1), media_files["video"])

    async def forbidden(*args, **kwargs):
        raise AssertionError("No child may start")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    plan = replace(
        runtime.plan(), scope=CarouselScope.ITEM_REFERENCE, state=CarouselPlanState.BLOCKED
    )
    with pytest.raises(DownloadFailedError):
        await InstagramCarouselAcquisition().acquire(plan, tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("changed", ["availability", "drm", "duplicate_id"])
def test_unavailable_and_unstable_fresh_metadata_never_processes(tmp_path, media_files, changed):
    runtime = Runtime(product(3), media_files["video"])
    plan = runtime.plan()
    item = runtime.data["carousel_media"][1]
    if changed == "availability":
        item["availability"] = "private"
    elif changed == "drm":
        item["has_drm"] = True
    else:
        item["pk"] = 1001
    with pytest.raises(DownloadFailedError):
        acquire(runtime, plan, tmp_path)
    assert not runtime.processed and not runtime.requests


@pytest.mark.parametrize("known", [True, False])
def test_actual_selector_prefers_compatible_and_never_manifest(tmp_path, media_files, known):
    runtime = Runtime(product(1), media_files["video"])
    plan = runtime.plan()

    def formats(raw):
        options = [
            {
                "format_id": "unknown",
                "url": "https://media.invalid/signed?token=fixture",
                "ext": "mp4",
                "height": 1920,
                "width": 1080,
            },
            {
                "format_id": "manifest",
                "url": "https://media.invalid/large.m3u8",
                "ext": "mp4",
                "height": 4000,
                "width": 2000,
            },
            {
                "format_id": "vp9",
                "url": "https://media.invalid/vp9.mp4",
                "ext": "mp4",
                "vcodec": "vp9",
                "acodec": "aac",
                "height": 1920,
                "width": 1080,
            },
        ]
        if known:
            options.append(
                {
                    "format_id": "compatible",
                    "url": "https://media.invalid/compatible.mp4",
                    "ext": "mp4",
                    "vcodec": "h264",
                    "acodec": "aac",
                    "height": 720,
                    "width": 400,
                }
            )
        raw["entries"][0]["formats"] = options
        return raw

    runtime.mutate = formats
    acquire(runtime, plan, tmp_path)
    assert runtime.selected_formats == ["compatible" if known else "unknown"]
    assert runtime.requests == 1


@pytest.mark.asyncio
async def test_public_operation_cleans_all_when_later_child_fails(
    tmp_path, media_files, monkeypatch
):
    runtime = Runtime(product(3), media_files["video"])
    processes = install_child(monkeypatch, subprocess_script(runtime.media, count=3, mode="fail"))
    keep = tmp_path / "keep.mp4"
    keep.write_bytes(b"unrelated")
    with pytest.raises(DownloadFailedError):
        await InstagramCarouselAcquisition().acquire(runtime.plan(), tmp_path)
    assert list(tmp_path.iterdir()) == [keep]
    assert all(p.returncode is not None for p in processes)


@pytest.mark.asyncio
async def test_repeated_cancellation_waits_for_child_cleanup(tmp_path, media_files, monkeypatch):
    import social_video_downloader.services.instagram_acquisition as module

    runtime = Runtime(product(2), media_files["video"])
    processes = install_child(monkeypatch, subprocess_script(runtime.media, mode="hang"))
    original = module._kill
    started = asyncio.Event()
    release = asyncio.Event()

    async def delayed_kill(process):
        started.set()
        await release.wait()
        await original(process)

    monkeypatch.setattr(module, "_kill", delayed_kill)
    task = asyncio.create_task(InstagramCarouselAcquisition().acquire(runtime.plan(), tmp_path))
    for _ in range(200):
        if list(tmp_path.glob("*/partial.mp4")):
            break
        await asyncio.sleep(0.01)
    task.cancel()
    await started.wait()
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert all(p.returncode is not None for p in processes)
    assert list(tmp_path.iterdir()) == []
