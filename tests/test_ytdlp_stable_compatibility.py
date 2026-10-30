"""Offline compatibility boundaries for the approved stable extractor upgrade."""

from time import monotonic

import pytest
from yt_dlp import YoutubeDL
from yt_dlp.extractor.youtube import YoutubeIE

from social_video_downloader.domain.errors import MetadataExtractionError
from social_video_downloader.infrastructure import youtube_snapshot as wire


@pytest.mark.parametrize(
    "html",
    [
        '<script>var ytInitialData = {"contents": {"synthetic": true}};</script>',
        '<script id="yt-initial-data" type="application/json">'
        '{"contents": {"synthetic": true}}</script>',
    ],
    ids=["legacy-assignment", "dedicated-json-script"],
)
def test_actual_extractor_reads_both_initial_data_layouts(html, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Initial-data parsing must not access the network.")

    with YoutubeDL({"quiet": True, "plugin_dirs": []}, auto_init=False) as ydl:
        monkeypatch.setattr(ydl, "urlopen", forbidden)
        assert YoutubeIE(ydl).extract_yt_initial_data("abcdefghijk", html) == {
            "contents": {"synthetic": True}
        }


@pytest.mark.parametrize("boundary", ["request", "response"])
def test_metadata_ipc_refuses_different_extractor_version(boundary):
    req = wire.request("https://www.youtube.com/watch?v=abcdefghijk", "synthetic-version-nonce")
    if boundary == "request":
        req["yt_dlp"] = "different-extractor-version"
        with pytest.raises(MetadataExtractionError):
            wire.validate_request(req)
    else:
        payload = wire.response(req, {"id": "abcdefghijk"}, monotonic())
        payload["yt_dlp"] = "different-extractor-version"
        with pytest.raises(MetadataExtractionError):
            wire.validate_response(payload, req)
