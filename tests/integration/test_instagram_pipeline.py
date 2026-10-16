"""Real yt-dlp processing and local FFmpeg, with synthetic acquisition only."""

import shutil
import subprocess
from copy import deepcopy

import pytest
import yt_dlp

from social_video_downloader.domain.errors import MediaProcessingError
from social_video_downloader.infrastructure.telegram_media import (
    inspect_telegram_video,
    prepare_telegram_video,
    telegram_video_upload_parameters,
)
from social_video_downloader.infrastructure.workspace import temporary_workspace
from social_video_downloader.providers.instagram import InstagramProvider
from social_video_downloader.services.choice_model import ChoicePlanState
from social_video_downloader.services.download import DownloadService

pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="Local synthetic Reel tests require ffmpeg and ffprobe.",
)


@pytest.mark.parametrize("media_kind", ["audio-video", "silent", "invalid"])
def test_reel_result_uses_existing_transport_validation_and_cleanup(tmp_path, media_kind):
    fixture = tmp_path / "synthetic.mp4"
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=blue:s=64x96:r=10",
    ]
    if media_kind == "audio-video":
        command += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000"]
    command += ["-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if media_kind == "audio-video":
        command += ["-c:a", "aac"]
    subprocess.run([*command, str(fixture)], check=True, capture_output=True)
    if media_kind == "invalid":
        fixture.write_bytes(b"not a media container")
    original = fixture.read_bytes()
    extractions = []
    processing = []
    raw = {
        "id": "synthetic",
        "title": "Synthetic Reel",
        "formats": [
            {
                "format_id": "direct",
                "url": "https://media.invalid/synthetic.mp4",
            }
        ],
    }

    class LocalYDL(yt_dlp.YoutubeDL):
        def extract_info(self, url, **kwargs):
            extractions.append((url, kwargs))
            return deepcopy(raw)

        def process_info(self, info):
            processing.append(info["format_id"])
            shutil.copyfile(fixture, self.prepare_filename(info))

        def urlopen(self, request):
            raise AssertionError("Synthetic integration must not access the network")

    service = DownloadService([InstagramProvider(LocalYDL)])
    url = "https://www.instagram.com/reel/Synthetic_01/"
    plan = service.create_choice_plan(url)
    assert plan.state is ChoicePlanState.DIRECT_DOWNLOAD
    with temporary_workspace(base_dir=tmp_path) as workspace:
        workspace_path = workspace
        result = service.download(url, workspace, plan.automatic_options)
        assert result.metadata.duration_seconds is None
        assert len(extractions) == 1
        assert processing == ["direct"]
        if media_kind == "audio-video":
            calls = []

            def runner(command, **kwargs):
                calls.append(command)
                return subprocess.run(command, **kwargs)

            prepared = prepare_telegram_video(result.file_path, runner=runner)
            assert prepared == result.file_path
            assert prepared.read_bytes() == original
            assert [call[0] for call in calls] == ["ffprobe"]
            parameters = telegram_video_upload_parameters(inspect_telegram_video(prepared))
            assert parameters == {"width": 64, "height": 96, "duration": 1}
        elif media_kind == "silent":
            with pytest.raises(MediaProcessingError, match="both video and audio"):
                prepare_telegram_video(result.file_path)
        else:
            with pytest.raises(MediaProcessingError):
                prepare_telegram_video(result.file_path)
    assert not workspace_path.exists()
    assert fixture.read_bytes() == original
    assert list(tmp_path.iterdir()) == [fixture]
