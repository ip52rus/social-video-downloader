"""Actual installed yt-dlp selection/HTTP/file/merge parity using local fixtures."""

import io
import json
import subprocess
from copy import deepcopy
from time import monotonic

import pytest
import yt_dlp
from yt_dlp.networking import Response

from social_video_downloader.domain.errors import UnsupportedQualityError
from social_video_downloader.domain.models import DownloadMode, DownloadOptions
from social_video_downloader.providers.youtube import YouTubeProvider
from social_video_downloader.services.download import DownloadService
from tests.test_youtube_metadata import owner as owner
from tests.youtube_metadata_fixtures import fixture_info, info


@pytest.fixture(scope="module")
def assets(tmp_path_factory):
    directory = tmp_path_factory.mktemp("youtube-local-media")
    result = {}
    for name, video, audio, ext in [
        ("combined", "libx264", "aac", "mp4"),
        ("video", "libx264", None, "mp4"),
        ("audio", None, "aac", "m4a"),
        ("vp9", "libvpx-vp9", None, "webm"),
        ("opus", None, "libopus", "webm"),
    ]:
        path = directory / (name + "." + ext)
        command = ["ffmpeg", "-v", "error", "-nostdin", "-y"]
        if video:
            command += ["-f", "lavfi", "-i", "color=c=black:s=32x32:r=10"]
        if audio:
            command += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000"]
        command += ["-t", "0.25", "-threads", "1"]
        if video:
            command += ["-c:v", video, "-pix_fmt", "yuv420p"]
        if audio:
            command += ["-c:a", audio]
        command += [str(path)]
        subprocess.run(
            command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20
        )
        result[name] = path.read_bytes()
    return result


class LocalYDL(yt_dlp.YoutubeDL):
    def __init__(self, options, source, assets, trace, allow_extract):
        super().__init__(options)
        self.source, self.trace, self.allow_extract = source, trace, allow_extract
        self.payloads = {}
        for descriptor in source["formats"]:
            video, audio = descriptor["vcodec"] != "none", descriptor["acodec"] != "none"
            name = (
                "combined"
                if video and audio
                else ("vp9" if descriptor["vcodec"].startswith("vp9") else "video")
                if video
                else ("opus" if descriptor["acodec"] == "opus" else "audio")
            )
            data = assets[name]
            self.payloads[descriptor["url"]] = data
            fragments = descriptor.get("fragments", [])
            for i, fragment in enumerate(fragments):
                self.payloads[fragment["url"]] = data[
                    len(data) * i // len(fragments) : len(data) * (i + 1) // len(fragments)
                ]

    def extract_info(self, url, *, download, process):
        self.trace["extract"] += 1
        assert self.allow_extract and download is False and process is False
        return deepcopy(self.source)

    def urlopen(self, request):
        assert request.url in self.payloads
        self.trace["requests"].append((request.url, dict(request.headers)))
        data = self.payloads[request.url]
        return Response(
            io.BytesIO(data), request.url, {"Content-Length": str(len(data))}, status=200
        )

    def process_ie_result(self, result, download=True, **kwargs):
        self.trace["process"] += 1
        result = super().process_ie_result(result, download=download, **kwargs)
        self.trace["selector"] = self.params["format"]
        self.trace["formats"] = [
            tuple(
                item.get(k)
                for k in ("format_id", "width", "height", "vcodec", "acodec", "ext", "protocol")
            )
            for item in (result.get("requested_formats") or [result])
        ]
        return result


def new_trace():
    return dict(extract=0, process=0, requests=[])


def probe(path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,codec_name,width,height,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        timeout=10,
    )
    return json.loads(result.stdout)["streams"]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", range(13))
async def test_real_ytdlp_original_and_subprocess_snapshot_download_parity(
    owner, assets, tmp_path, case
):
    supervisor, state = owner
    video_id = f"fixture{case:04d}"
    url = "https://www.youtube.com/watch?v=" + video_id
    if case == 12:
        url += "&list=synthetic-list&index=2"
    raw = fixture_info(video_id)
    old_trace, new_download_trace = new_trace(), new_trace()
    original = YouTubeProvider(lambda opts: LocalYDL(opts, raw, assets, old_trace, True))
    restored = YouTubeProvider(lambda opts: LocalYDL(opts, raw, assets, new_download_trace, False))
    old_service, new_service = DownloadService([original]), DownloadService([restored])
    new_service._youtube_metadata = supervisor
    old_plan = old_service.create_choice_plan(url)
    new_plan = await new_service.create_choice_plan_async(url)
    assert old_plan == new_plan
    canonical = original._normalize_youtube_url(url)
    original_stamp, original_info = original._planning_snapshot(canonical)
    restored_stamp, restored_info = restored._planning_snapshot(canonical)
    assert original_info == restored_info
    options = []
    for mode in original.get_supported_modes(url):
        if mode is DownloadMode.AUDIO_ONLY:
            options.append(DownloadOptions(mode))
        options.extend(
            DownloadOptions(mode, q.id) for q in original.get_available_qualities(url, mode)
        )
    for index, option in enumerate(options):
        if index:
            original._store_info(canonical, deepcopy(original_info), original_stamp)
            restored._store_info(canonical, deepcopy(restored_info), restored_stamp)
        old_trace.update(new_trace())
        new_download_trace.update(new_trace())
        before = old_service.download(url, tmp_path / f"before-{index}", option)
        after = new_service.download(url, tmp_path / f"after-{index}", option)
        assert old_trace == new_download_trace
        assert new_download_trace["extract"] == 0 and new_download_trace["process"] == 1
        assert probe(before.file_path) == probe(after.file_path)
        assert restored._cached_info(canonical) is None
        if option.quality_id and option.quality_id.startswith("video-"):
            dimensions = tuple(map(int, option.quality_id[6:].split("x")))
            videos = [f for f in new_download_trace["formats"] if f[3] != "none"]
            assert len(videos) == 1 and videos[0][1:3] == dimensions
    assert len(state.processes) == 1


@pytest.mark.asyncio
async def test_expired_snapshot_fresh_extraction_preserves_exact_quality_rejection(
    owner, assets, tmp_path
):
    supervisor, _ = owner
    raw = fixture_info("fixture0000")
    trace = new_trace()
    provider = YouTubeProvider(lambda opts: LocalYDL(opts, raw, assets, trace, True))
    await supervisor.plan(provider, "https://youtu.be/fixture0002")
    provider._inspection_cache["https://youtu.be/fixture0002"] = (
        monotonic() - 181,
        info("fixture0002"),
    )
    with pytest.raises(UnsupportedQualityError):
        provider.download(
            "https://youtu.be/fixture0002",
            tmp_path,
            DownloadOptions(DownloadMode.VIDEO_WITH_AUDIO, "video-1920x1080"),
        )
    assert trace["extract"] == 1 and trace["process"] == 0 and not trace["requests"]
