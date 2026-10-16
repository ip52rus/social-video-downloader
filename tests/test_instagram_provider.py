"""Offline boundary and integration tests for the experimental Instagram provider."""

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yt_dlp
from yt_dlp.extractor.instagram import InstagramIE

from social_video_downloader.domain.errors import (
    DownloadFailedError,
    InvalidMediaURLError,
    MediaProcessingError,
    MetadataExtractionError,
    UnsupportedDownloadModeError,
    UnsupportedPlatformError,
    UnsupportedQualityError,
)
from social_video_downloader.domain.models import DownloadMode, DownloadOptions, Platform
from social_video_downloader.providers.base import MediaProvider
from social_video_downloader.providers.instagram import InstagramProvider
from social_video_downloader.services.choice_model import ChoicePlanState
from social_video_downloader.services.download import DownloadService

URL = "https://www.instagram.com/reel/Fixture_01/"
POST_URL = "https://www.instagram.com/p/Fixture_01/"
# Mirrors installed InstagramBaseIE._extract_product_media: direct video_versions
# may have dimensions and a locator but no vcodec/acodec/ext before processing.
INFO = {
    "id": "fixture-id",
    "title": "Fixture Reel",
    "formats": [
        {
            "format_id": "direct",
            "url": "https://media.invalid/fixture.mp4?expires=fixture",
            "width": 360,
            "height": 640,
            "vcodec": None,
            "acodec": None,
        }
    ],
}


class FakeYDL:
    def __init__(self, factory, options):
        self.factory = factory
        self.params = options

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def extract_info(self, url, **kwargs):
        self.factory.extractions.append((url, kwargs))
        if self.factory.extract_error:
            raise self.factory.extract_error
        return deepcopy(self.factory.info)

    def process_ie_result(self, info, *, download):
        assert download is True
        self.factory.processed.append(deepcopy(info))
        path = Path(self.params["outtmpl"])
        if self.factory.output == "symlink":
            path.symlink_to(self.factory.outside)
        elif self.factory.output != "missing":
            path.write_bytes(b"" if self.factory.output == "empty" else b"fixture")
        if self.factory.output == "extra":
            path.with_name("extra.mp4").write_bytes(b"extra")
        if self.factory.output == "partial":
            path.with_suffix(".mp4.part").write_bytes(b"partial")
        if self.factory.process_error:
            raise self.factory.process_error
        return info


class Factory:
    def __init__(self, info: Any = INFO):
        self.info = deepcopy(info)
        self.options = []
        self.extractions = []
        self.processed = []
        self.extract_error = None
        self.process_error = None
        self.output = "normal"
        self.outside = None

    def __call__(self, options):
        self.options.append(options)
        return FakeYDL(self, options)


@pytest.fixture(params=[URL, POST_URL], ids=["reel", "post"])
def publication_url(request):
    return request.param


@pytest.mark.parametrize("path", ["reel", "p"])
@pytest.mark.parametrize(
    "url",
    [
        URL,
        "instagram.com/reel/Fixture_01",
        "http://m.instagram.com/reel/Fixture_01/",
        URL + "?utm_source=fixture#fragment",
        "https://www.instagram.com:443/reel/Fixture_01/",
    ],
)
def test_video_urls_share_one_canonical_inspection(url, path):
    canonical = URL.replace("/reel/", f"/{path}/")
    url = url.replace("/reel/", f"/{path}/")
    factory = Factory()
    provider: MediaProvider = InstagramProvider(factory)
    assert provider.platform is Platform.INSTAGRAM
    assert provider.can_handle(url)
    assert provider.get_supported_modes(url) == (DownloadMode.VIDEO_WITH_AUDIO,)
    assert provider.get_available_qualities(canonical, DownloadMode.VIDEO_WITH_AUDIO) == ()
    metadata = provider.extract_metadata(canonical)
    assert metadata.source_url == canonical
    assert metadata.title == "Fixture Reel"
    assert metadata.duration_seconds is None
    assert metadata.uploader is None
    assert factory.extractions == [
        (
            canonical,
            {
                "download": False,
                "process": False,
                "ie_key": "Instagram",
            },
        )
    ]
    assert factory.processed == []


@pytest.mark.parametrize(
    "url",
    [
        "https://www.instagram.com/p/",
        POST_URL + "extra/",
        "https://www.instagram.com/p/%2e%2e/",
        "https://www.instagram.com/p/fixture%2Fextra/",
        "https://www.instagram.com/p/fixture.jpg/",
        "https://www.instagram.com/p/fixture/embed/",
        "https://evil.instagram.com/p/fixture/",
        "https://instagram.com.evil.invalid/p/fixture/",
        "https://fixture:fixture@instagram.com/p/fixture/",
        "https://@instagram.com/p/fixture/",
        "https://www.instagram.com:8080/p/fixture/",
        "https://www.instagram.com:bad/p/fixture/",
        "https://www.instagram.com/stories/fixture/1/",
        "https://www.instagram.com/fixture/",
        "https://www.instagram.com/reels/",
        "https://www.instagram.com/reels/Fixture_01/",
        URL + "extra/",
        "https://www.instagram.com/reel/",
        "https://www.instagram.com/reel/%2e%2e/",
        "https://www.instagram.com/reel/fixture%2Fextra/",
        "https://evil.instagram.com/reel/fixture/",
        "https://instagram.com.evil.invalid/reel/fixture/",
        "https://evil.invalid/reel/fixture/",
        "https://instagram.com@evil.invalid/reel/fixture/",
        "https://user@instagram.com/reel/fixture/",
        "https://www.instagram.com:8080/reel/fixture/",
        "file:///reel/fixture/",
        "https://[invalid",
        "",
        "https://www.instagram.com:bad/reel/fixture/",
    ],
)
def test_unsupported_urls_never_extract_or_download(url, tmp_path):
    factory = Factory()
    provider = InstagramProvider(factory)
    assert not provider.can_handle(url)
    with pytest.raises(InvalidMediaURLError):
        provider.download(url, tmp_path)
    assert factory.options == []
    assert list(tmp_path.iterdir()) == []


def playlist_entries():
    raise AssertionError("A playlist must never be enumerated")
    yield


@pytest.mark.parametrize(
    "raw",
    [
        None,
        [],
        {},
        {**INFO, "_type": "playlist", "entries": []},
        {**INFO, "entries": None},
        {**INFO, "_type": "multi_video"},
        {"_type": "url", "url": URL},
        {**INFO, "_type": "url_transparent"},
        {**INFO, "_type": "unexpected"},
        {**INFO, "is_private": True},
        *(
            {**INFO, "availability": value}
            for value in ["private", "needs_auth", "subscriber_only"]
        ),
        {**INFO, "has_drm": True},
        {**INFO, "formats": []},
        {**INFO, "formats": None},
    ],
)
def test_non_single_video_results_never_start_media_acquisition(raw, tmp_path, publication_url):
    factory = Factory(raw)
    with pytest.raises(MetadataExtractionError):
        InstagramProvider(factory).download(publication_url, tmp_path)
    assert len(factory.extractions) == 1
    assert factory.processed == []
    assert list(tmp_path.iterdir()) == []


def test_even_single_entry_playlist_is_rejected_without_iteration(tmp_path, publication_url):
    factory = Factory()
    factory.info = {**INFO, "_type": "playlist", "entries": playlist_entries()}

    # Return directly: deepcopy cannot copy a lazy generator.
    def extract(self, url, **kwargs):
        return self.factory.info

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(FakeYDL, "extract_info", extract)
        with pytest.raises(MetadataExtractionError):
            InstagramProvider(factory).download(publication_url, tmp_path)
    assert factory.processed == []
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "changes",
    [
        {"url": None},
        {"url": "file:///fixture.mp4"},
        {"url": "https://[bad"},
        {"url": "https://media.invalid/image.jpg"},
        {"vcodec": "none"},
        {"acodec": "none"},
        {"acodec": " NONE "},
        {"vcodec": " NONE "},
        {"vcodec": True},
        {"vcodec": float("nan")},
        {"vcodec": "", "width": None},
        {"protocol": "m3u8_native"},
        {"protocol": "http_dash_segments"},
        {"ext": "jpg"},
        {"has_drm": True},
    ],
)
def test_unusable_media_formats_are_rejected(changes, tmp_path):
    raw = {**INFO, "formats": [{**INFO["formats"][0], **changes}]}
    factory = Factory(raw)
    with pytest.raises(MetadataExtractionError):
        InstagramProvider(factory).download(URL, tmp_path)
    assert factory.processed == []


@pytest.mark.parametrize(
    "duration,expected",
    [
        (None, None),
        (0, None),
        (-1, None),
        (False, None),
        (True, None),
        (float("nan"), None),
        (float("inf"), None),
        (10**400, None),
        ("12", None),
        (12.5, 12.5),
    ],
)
def test_optional_metadata_is_safe(duration, expected, publication_url):
    factory = Factory({**INFO, "title": "  ", "duration": duration, "uploader": 42})
    result = InstagramProvider(factory).extract_metadata(publication_url)
    assert result.title == ("Instagram Reel" if publication_url == URL else "Instagram Video")
    assert result.duration_seconds == expected
    assert result.uploader is None


@pytest.mark.parametrize("mode", [DownloadMode.AUDIO_ONLY, DownloadMode.VIDEO_ONLY])
def test_unsupported_modes_fail_before_network_or_files(mode, tmp_path, publication_url):
    factory = Factory()
    provider = InstagramProvider(factory)
    with pytest.raises(UnsupportedDownloadModeError):
        provider.download(publication_url, tmp_path, DownloadOptions(mode=mode))
    with pytest.raises(UnsupportedDownloadModeError):
        provider.get_available_qualities(publication_url, mode)
    assert factory.options == []
    assert not list(tmp_path.iterdir())


def test_quality_id_and_invalid_options_fail_before_acquisition(tmp_path, publication_url):
    factory = Factory()
    provider = InstagramProvider(factory)
    with pytest.raises(UnsupportedQualityError):
        provider.download(publication_url, tmp_path, DownloadOptions(quality_id="arbitrary"))
    with pytest.raises(TypeError):
        provider.download(publication_url, tmp_path, {})
    assert factory.options == []


def test_service_direct_plan_reuses_snapshot_and_delivers_exactly_one_file(
    tmp_path, publication_url
):
    factory = Factory()
    factory.info["title"] = "../../outside"
    provider = InstagramProvider(factory)
    service = DownloadService(providers=[provider])
    plan = service.create_choice_plan(publication_url + "?tracking=fixture")
    assert plan.state is ChoicePlanState.DIRECT_DOWNLOAD
    assert plan.automatic_options == DownloadOptions()
    assert not plan.quality_choices
    assert len(factory.extractions) == 1
    result = service.download(publication_url, tmp_path, plan.automatic_options)
    assert len(factory.extractions) == 1
    assert len(factory.processed) == 1
    assert list(tmp_path.iterdir()) == [result.file_path]
    assert result.file_path.read_bytes() == b"fixture"
    assert result.metadata.platform is Platform.INSTAGRAM
    assert result.file_path.parent == tmp_path
    prefix = "Instagram Reel " if publication_url == URL else "Instagram Video "
    assert result.file_path.name.startswith(prefix)
    assert result.file_path.suffix == ".mp4"
    assert provider._inspection_cache == {}
    # A second request receives a fresh snapshot and never overwrites a prior file.
    other = service.download(publication_url, tmp_path)
    assert len(factory.extractions) == 2
    assert other.file_path != result.file_path
    assert len(list(tmp_path.iterdir())) == 2
    for options in factory.options:
        assert options["noplaylist"] is True
        assert (
            options["retries"] == options["fragment_retries"] == options["extractor_retries"] == 0
        )
        assert options["cachedir"] is False
        assert not any("cookie" in key or key in {"username", "password"} for key in options)


def test_provider_remains_disabled_by_default(publication_url):
    with pytest.raises(UnsupportedPlatformError):
        DownloadService().create_choice_plan(publication_url)


def test_cache_expiry_and_bound(monkeypatch, tmp_path, publication_url):
    import social_video_downloader.providers.instagram as module

    clock = [10.0]
    monkeypatch.setattr(module, "monotonic", lambda: clock[0])
    factory = Factory()
    provider = InstagramProvider(factory)
    provider.extract_metadata(publication_url)
    clock[0] += provider._INSPECTION_CACHE_TTL_SECONDS
    provider.download(publication_url, tmp_path)
    assert len(factory.extractions) == 2
    for i in range(provider._INSPECTION_CACHE_MAX_ENTRIES + 1):
        provider.extract_metadata(publication_url.replace("Fixture_01", f"Fixture{i}"))
    assert len(provider._inspection_cache) == provider._INSPECTION_CACHE_MAX_ENTRIES
    assert publication_url.replace("Fixture_01", "Fixture0") not in provider._inspection_cache


@pytest.mark.parametrize("failure", ["missing", "empty", "extra", "partial", "symlink"])
def test_invalid_output_is_rejected_and_workspace_cleaned(failure, tmp_path, publication_url):
    output = tmp_path / "output"
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"outside")
    factory = Factory()
    factory.output = failure
    factory.outside = outside
    with pytest.raises(MediaProcessingError):
        InstagramProvider(factory).download(publication_url, output)
    assert list(output.iterdir()) == []
    assert outside.read_bytes() == b"outside"


def test_extractor_and_download_failures_are_safe_and_not_retried(
    tmp_path, capsys, publication_url
):
    factory = Factory()
    factory.extract_error = RuntimeError("private URL fixture")
    provider = InstagramProvider(factory)
    with pytest.raises(MetadataExtractionError, match="Unable to inspect") as exc:
        provider.download(publication_url, tmp_path)
    assert "private URL" not in str(exc.value)
    assert len(factory.extractions) == 1
    assert not factory.processed
    factory.extract_error = None
    factory.process_error = RuntimeError("private URL fixture")
    with pytest.raises(DownloadFailedError, match="download failed"):
        provider.download(publication_url, tmp_path)
    assert len(factory.processed) == 1
    assert list(tmp_path.iterdir()) == []
    logger = factory.options[-1]["logger"]
    for method in [logger.debug, logger.warning, logger.error]:
        method("private URL fixture")
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


def test_real_ytdlp_processing_selects_only_valid_direct_formats(tmp_path):
    calls = []
    unsafe = [
        {"format_id": "silent", "vcodec": "avc1", "acodec": "none", "ext": "mp4"},
        {"format_id": "audio", "vcodec": "none", "acodec": "mp4a", "ext": "mp4"},
        {"format_id": "image", "vcodec": "none", "acodec": "none", "ext": "jpg"},
    ]
    info = {
        **INFO,
        "formats": [
            *INFO["formats"],
            {**INFO["formats"][0], "format_id": "direct-high", "width": 720, "height": 1280},
            *[
                {**item, "url": "https://media.invalid/unsafe", "height": 2160, "width": 3840}
                for item in unsafe
            ],
        ],
    }

    class LocalYDL(yt_dlp.YoutubeDL):
        def extract_info(self, url, **kwargs):
            calls.append((url, kwargs))
            return deepcopy(info)

        def process_info(self, selected):
            calls.append(selected["format_id"])
            Path(self.prepare_filename(selected)).write_bytes(b"synthetic video fixture")

        def urlopen(self, request):
            raise AssertionError("Offline test attempted network access")

    provider = InstagramProvider(LocalYDL)
    service = DownloadService([provider])
    plan = service.create_choice_plan(URL)
    result = service.download(URL, tmp_path, plan.automatic_options)
    assert calls == [
        (URL, {"download": False, "process": False, "ie_key": "Instagram"}),
        "direct-high",
    ]
    assert result.file_path.read_bytes() == b"synthetic video fixture"


def test_expired_snapshot_that_becomes_playlist_never_downloads(
    monkeypatch, tmp_path, publication_url
):
    import social_video_downloader.providers.instagram as module

    clock = [0.0]
    monkeypatch.setattr(module, "monotonic", lambda: clock[0])
    factory = Factory()
    service = DownloadService([InstagramProvider(factory)])
    plan = service.create_choice_plan(publication_url)
    clock[0] = InstagramProvider._INSPECTION_CACHE_TTL_SECONDS
    factory.info = {"_type": "playlist", "entries": [INFO]}
    with pytest.raises(MetadataExtractionError):
        service.download(publication_url, tmp_path, plan.automatic_options)
    assert len(factory.extractions) == 2
    assert not factory.processed
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("reason", ["HTTP Error 429", "Login required", "HTTP Error 403"])
def test_upstream_rejection_never_triggers_authentication_or_retry(reason, tmp_path):
    factory = Factory()
    factory.extract_error = yt_dlp.utils.DownloadError(reason)
    provider = InstagramProvider(factory)
    with pytest.raises(MetadataExtractionError) as exc:
        provider.download(URL, tmp_path)
    assert reason not in str(exc.value)
    assert len(factory.extractions) == 1
    assert not factory.processed
    assert not list(tmp_path.iterdir())


def _direct_format(identifier, **changes):
    return {
        **INFO["formats"][0],
        "format_id": identifier,
        "ext": "mp4",
        **changes,
    }


def _offline_processor(info, processed):
    class OfflineYDL(yt_dlp.YoutubeDL):
        def extract_info(self, url, **kwargs):
            assert kwargs == {"download": False, "process": False, "ie_key": "Instagram"}
            return deepcopy(info)

        def process_info(self, selected):
            processed.append((selected["format_id"], selected["protocol"]))
            Path(self.prepare_filename(selected)).write_bytes(b"offline fixture")

        def urlopen(self, request):
            raise AssertionError("Format selection must not access the network")

    return OfflineYDL


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"url": "https://media.invalid/master.m3u8"}, id="implicit-hls"),
        pytest.param(
            {"url": "https://media.invalid/master.m3u8", "protocol": "https"},
            id="hls-with-http-label",
        ),
        pytest.param(
            {"url": "https://media.invalid/master.M3U8?signature=fixture"},
            id="uppercase-hls",
        ),
        pytest.param({"url": "https://media.invalid/manifest.mpd"}, id="implicit-dash"),
        pytest.param({"url": "https://media.invalid/manifest.f4m"}, id="implicit-f4m"),
        pytest.param({"protocol": "m3u8_native"}, id="explicit-hls"),
        pytest.param({"protocol": "http_dash_segments"}, id="explicit-dash"),
        pytest.param({"fragments": [{"url": "https://media.invalid/part.mp4"}]}, id="fragments"),
        pytest.param({"fragments": []}, id="empty-fragment-list"),
        pytest.param({"manifest_url": "https://media.invalid/manifest.mpd"}, id="manifest"),
        pytest.param({"manifest_stream_number": 0}, id="dash-representation"),
    ],
)
@pytest.mark.parametrize("with_direct_fallback", [False, True])
def test_real_processing_rejects_manifest_formats_before_acquisition(
    changes, with_direct_fallback, tmp_path, publication_url
):
    processed = []
    unsafe = _direct_format("manifest", width=1080, height=1920, **changes)
    formats = [unsafe]
    if with_direct_fallback:
        formats.insert(0, _direct_format("direct"))
    provider = InstagramProvider(_offline_processor({**INFO, "formats": formats}, processed))
    if with_direct_fallback:
        provider.download(publication_url, tmp_path)
        assert processed == [("direct", "https")]
    else:
        with pytest.raises(MetadataExtractionError):
            provider.download(publication_url, tmp_path)
        assert processed == []
        assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "formats, expected",
    [
        pytest.param(
            [
                _direct_format("compatible", vcodec="avc1.64001f", acodec="mp4a.40.2"),
                _direct_format("vp9", vcodec="vp09.00.31.08", acodec="mp4a.40.2"),
            ],
            "compatible",
            id="equal-resolution-h264-over-vp9",
        ),
        pytest.param(
            [
                _direct_format("compatible", vcodec="h264", acodec="aac"),
                _direct_format("unknown-audio", vcodec="avc1.640028", width=1080, height=1920),
            ],
            "compatible",
            id="compatible-over-higher-unknown-audio",
        ),
        pytest.param(
            [
                _direct_format("unknown", width=720, height=1280),
                _direct_format(
                    "vp9", vcodec="vp09.00.40.08", acodec="mp4a.40.2", width=1080, height=1920
                ),
            ],
            "unknown",
            id="incomplete-before-known-incompatible",
        ),
        pytest.param(
            [
                _direct_format("unknown-audio", vcodec="avc1.64001f"),
                _direct_format("vp9", vcodec="vp09.00.31.08", acodec="mp4a.40.2"),
            ],
            "unknown-audio",
            id="incomplete-audio-fallback",
        ),
        pytest.param(
            [
                _direct_format("unknown-audio", vcodec="avc1.64001f"),
                _direct_format("vp9", vcodec="vp09.00.40.08", width=1080, height=1920),
            ],
            "unknown-audio",
            id="known-incompatible-video-with-unknown-audio-is-last",
        ),
        pytest.param(
            [
                _direct_format("unknown"),
                _direct_format("opus", acodec="opus", width=1080, height=1920),
            ],
            "unknown",
            id="known-incompatible-audio-with-unknown-video-is-last",
        ),
        pytest.param(
            [_direct_format("low"), _direct_format("high", width=720, height=1280)],
            "high",
            id="quality-within-incomplete-class",
        ),
        pytest.param(
            [
                _direct_format("low", vcodec="h264", acodec="aac"),
                _direct_format("high", vcodec="h264", acodec="aac", width=720, height=1280),
            ],
            "high",
            id="quality-within-compatible-class",
        ),
        pytest.param(
            [
                _direct_format("low", vcodec="vp09.00.31.08", acodec="mp4a.40.2"),
                _direct_format(
                    "high", vcodec="vp09.00.40.08", acodec="mp4a.40.2", width=1080, height=1920
                ),
            ],
            "high",
            id="other-codec-fallback",
        ),
        pytest.param(
            [
                _direct_format(
                    "signed",
                    vcodec="avc3.64001f",
                    acodec="mp4a.40.5",
                    url="https://media.invalid/resource?signature=fixture",
                )
            ],
            "signed",
            id="signed-direct-url-without-extension",
        ),
    ],
)
@pytest.mark.parametrize("reverse", [False, True])
def test_real_processing_prefers_compatibility_before_quality(
    formats, expected, reverse, tmp_path, publication_url
):
    processed = []
    raw = {**INFO, "formats": list(reversed(formats)) if reverse else formats}
    provider = InstagramProvider(_offline_processor(raw, processed))
    result = provider.download(publication_url, tmp_path)
    assert processed == [(expected, "https")]
    assert result.file_path.read_bytes() == b"offline fixture"


@pytest.fixture
def extract_product_media():
    class NoNetworkYDL(yt_dlp.YoutubeDL):
        def urlopen(self, request):
            raise AssertionError("Synthetic extractor schema test must not access the network")

    with NoNetworkYDL({"quiet": True, "no_warnings": True, "cachedir": False}) as ydl:
        # Call the installed extractor's local schema mapping, never extract_info().
        extractor = InstagramIE(ydl)

        def extract(product):
            raw = extractor._extract_product_media(product)
            # Normal YoutubeDL.extract_info adds these envelope fields before returning.
            ydl.add_default_extra_info(raw, extractor, URL)
            return raw

        yield extract


DASH_FIXTURE = """<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" mediaPresentationDuration="PT1S">
<Period><AdaptationSet mimeType="video/mp4" codecs="avc1.640028">
<Representation id="dash-video" bandwidth="2000000" width="1080" height="1920">
<BaseURL>https://media.invalid/dash.mp4</BaseURL>
<SegmentTemplate timescale="1" duration="1" startNumber="1"
media="part-$Number$.m4s" initialization="init.mp4"/>
</Representation></AdaptationSet></Period></MPD>"""


@pytest.mark.parametrize(
    "dimensions", [{}, {"width": 360, "height": 640}, {"width": 360}, {"height": 640}]
)
@pytest.mark.parametrize("with_dash", [False, True])
def test_actual_extractor_progressive_schema_reaches_one_acquisition(
    extract_product_media, dimensions, with_dash, tmp_path
):
    product = {
        "pk": 1,
        "video_versions": [{"id": "direct", "url": "https://media.invalid/reel.mp4", **dimensions}],
    }
    if with_dash:
        product["video_dash_manifest"] = DASH_FIXTURE
    raw = extract_product_media(product)
    direct = raw["formats"][0]
    assert direct.get("vcodec") is direct.get("acodec") is direct.get("ext") is None
    assert direct.get("width") == dimensions.get("width")
    assert direct.get("height") == dimensions.get("height")
    if with_dash:
        assert any(f.get("protocol") == "http_dash_segments" for f in raw["formats"])
    processed = []
    provider = InstagramProvider(_offline_processor(raw, processed))
    service = DownloadService([provider])
    plan = service.create_choice_plan(URL)
    assert plan.state is ChoicePlanState.DIRECT_DOWNLOAD
    assert provider._compatibility_rank(direct) == 1
    result = service.download(URL, tmp_path, plan.automatic_options)
    assert processed == [("direct", "https")]
    assert result.metadata.duration_seconds is None
    assert result.file_path.read_bytes() == b"offline fixture"
    # Admission did not fabricate codec or geometry evidence in the original mapping.
    assert direct.get("vcodec") is direct.get("acodec") is None
    assert direct.get("width") == dimensions.get("width")
    assert direct.get("height") == dimensions.get("height")


@pytest.mark.parametrize(
    "product_changes, locator",
    [
        ({"video_codec": "none"}, "https://media.invalid/reel.mp4"),
        ({"has_audio": False}, "https://media.invalid/reel.mp4"),
        ({}, "https://media.invalid/master.m3u8"),
        ({}, "https://media.invalid/manifest.mpd"),
        ({}, "https://media.invalid/resource?signature=fixture"),
        ({}, "https://media.invalid/image.jpg"),
    ],
)
def test_incomplete_extractor_schema_keeps_unsupported_candidates_blocked(
    extract_product_media, product_changes, locator, tmp_path
):
    raw = extract_product_media(
        {
            "pk": 1,
            "video_versions": [{"id": "unsupported", "url": locator}],
            **product_changes,
        }
    )
    processed = []
    provider = InstagramProvider(_offline_processor(raw, processed))
    with pytest.raises(MetadataExtractionError):
        provider.download(URL, tmp_path)
    assert processed == []
    assert not list(tmp_path.iterdir())


def test_incomplete_signed_mp4_with_declared_extension_is_admissible(
    extract_product_media, tmp_path
):
    raw = extract_product_media(
        {
            "pk": 1,
            "video_versions": [
                {"id": "signed", "url": "https://media.invalid/resource?signature=fixture"}
            ],
        }
    )
    # The provider interface also accepts a supplied container hint, without inventing codecs.
    raw["formats"][0]["ext"] = "mp4"
    processed = []
    provider = InstagramProvider(_offline_processor(raw, processed))
    provider.download(URL, tmp_path)
    assert processed == [("signed", "https")]
    assert provider._compatibility_rank(raw["formats"][0]) == 1


PRODUCT_VIDEO = {
    "pk": 1,
    "video_versions": [{"id": "direct", "url": "https://media.invalid/video.mp4"}],
}
PRODUCT_PHOTO = {
    "pk": 2,
    "image_versions2": {
        "candidates": [{"url": "https://media.invalid/photo.jpg", "width": 640, "height": 640}]
    },
}


@pytest.fixture
def product_runtime():
    """Real extract_info/Instagram classification; replace HTTP answers and acquisition."""

    def build(product):
        calls = {"extractions": [], "processing": 0, "acquisitions": [], "result_type": None}

        class FixtureInstagramIE(InstagramIE):
            @classmethod
            def ie_key(cls):
                return "Instagram"

            @property
            def _can_impersonate(self):
                # Select the JSON fixture branch only; no transport impersonation is configured.
                return True

            def _real_initialize(self):
                pass

            def _download_json(self, url, *args, **kwargs):
                if "/web/get_ruling_for_content/" in url:
                    return {"status": "ok"}
                if url == "https://www.instagram.com/api/graphql":
                    return {
                        "data": {
                            "xig_polaris_media": {"if_not_gated_logged_out": deepcopy(product)}
                        }
                    }
                raise AssertionError("Unexpected synthetic metadata request")

            def _download_webpage_handle(self, *args, **kwargs):
                raise AssertionError("No webpage request is allowed")

        class ProductYDL(yt_dlp.YoutubeDL):
            def __init__(self, options):
                super().__init__(options, auto_init=False)
                self.add_info_extractor(FixtureInstagramIE(self))

            def extract_info(self, url, **kwargs):
                assert kwargs == {"download": False, "process": False, "ie_key": "Instagram"}
                calls["extractions"].append(url)
                raw = super().extract_info(url, **kwargs)
                calls["result_type"] = raw.get("_type", "video")
                calls["entry_count"] = len(raw.get("entries", []))
                return raw

            def process_ie_result(self, raw, *, download):
                assert download is True
                calls["processing"] += 1
                return super().process_ie_result(raw, download=download)

            def process_info(self, info):
                calls["acquisitions"].append(info["format_id"])
                Path(self.prepare_filename(info)).write_bytes(b"synthetic product fixture")

            def urlopen(self, request):
                raise AssertionError("Synthetic product extraction must not access the network")

        return ProductYDL, calls

    return build


@pytest.mark.parametrize(
    "product, result_type, entries",
    [
        pytest.param(PRODUCT_VIDEO, "video", 0, id="single-video"),
        pytest.param(
            {"pk": 3, "carousel_media": [PRODUCT_VIDEO, {**PRODUCT_VIDEO, "pk": 4}]},
            "playlist",
            2,
            id="video-carousel",
        ),
        pytest.param(
            {"pk": 3, "carousel_media": [PRODUCT_PHOTO, PRODUCT_VIDEO]},
            "playlist",
            2,
            id="mixed-carousel",
        ),
        pytest.param(
            {"pk": 3, "carousel_media": [PRODUCT_VIDEO]},
            "playlist",
            1,
            id="one-entry-carousel",
        ),
        pytest.param(
            {"pk": 3, "carousel_media": [PRODUCT_PHOTO, {**PRODUCT_PHOTO, "pk": 4}]},
            "playlist",
            2,
            id="photo-carousel",
        ),
        pytest.param(PRODUCT_PHOTO, None, 0, id="single-photo"),
        pytest.param({"pk": 3, "carousel_media": []}, None, 0, id="empty-publication"),
    ],
)
def test_installed_extractor_classifies_products_before_acquisition(
    product_runtime, product, result_type, entries, publication_url, tmp_path
):
    factory, calls = product_runtime(product)
    service = DownloadService(providers=[InstagramProvider(factory)])
    if result_type == "video":
        plan = service.create_choice_plan(publication_url + "?tracking=fixture")
        assert plan.state is ChoicePlanState.DIRECT_DOWNLOAD
        assert plan.technical_modes == (DownloadMode.VIDEO_WITH_AUDIO,)
        assert plan.automatic_options == DownloadOptions(mode=DownloadMode.VIDEO_WITH_AUDIO)
        assert not plan.quality_choices
        result = service.download(publication_url, tmp_path, plan.automatic_options)
        assert calls["processing"] == 1
        assert calls["acquisitions"] == ["direct"]
        assert result.metadata.source_url == publication_url
        assert result.metadata.title == (
            "Instagram Reel" if publication_url == URL else "Instagram Video"
        )
        assert result.file_path.parent == tmp_path
        assert list(tmp_path.iterdir()) == [result.file_path]
        assert result.file_path.read_bytes() == b"synthetic product fixture"
    else:
        with pytest.raises(MetadataExtractionError):
            service.create_choice_plan(publication_url)
        assert calls["processing"] == 0
        assert calls["acquisitions"] == []
        assert list(tmp_path.iterdir()) == []
    assert calls["extractions"] == [publication_url]
    assert calls["result_type"] == result_type
    if result_type is not None:
        assert calls["entry_count"] == entries


def test_reel_and_post_cache_identities_do_not_collide():
    factory = Factory()
    provider = InstagramProvider(factory)
    provider.extract_metadata(URL)
    provider.extract_metadata(POST_URL)
    assert set(provider._inspection_cache) == {URL, POST_URL}
    assert [url for url, _ in factory.extractions] == [URL, POST_URL]
