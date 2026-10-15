"""Network-free tests for the real YouTube provider implementation."""

from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from social_video_downloader.domain.errors import (
    DownloadFailedError,
    InvalidMediaURLError,
    MediaProcessingError,
    MetadataExtractionError,
    UnsupportedDownloadModeError,
    UnsupportedPlatformError,
    UnsupportedQualityError,
)
from social_video_downloader.domain.models import (
    DownloadMode,
    DownloadOptions,
    Platform,
)
from social_video_downloader.providers.youtube import YouTubeProvider
from social_video_downloader.services.choice_model import ChoicePlanState, UserChoiceKind
from social_video_downloader.services.download import DownloadService
from social_video_downloader.services.quality_tiers import (
    QualityTier,
    ResolutionConfidence,
    build_quality_tier_plan,
    classify_quality,
)

VIDEO_INFO: dict[str, Any] = {
    "id": "abc123",
    "title": "Test: video/short",
    "duration": 123,
    "uploader": "Test Channel",
    "formats": [
        {
            "format_id": "18",
            "ext": "mp4",
            "width": 640,
            "height": 360,
            "vcodec": "avc1",
            "acodec": "mp4a",
            "tbr": 500,
        },
        {
            "format_id": "137",
            "ext": "mp4",
            "width": 1920,
            "height": 1080,
            "vcodec": "avc1",
            "acodec": "none",
            "tbr": 4000,
        },
        {
            "format_id": "136",
            "ext": "mp4",
            "width": 1280,
            "height": 720,
            "vcodec": "avc1",
            "acodec": "none",
            "tbr": 2500,
        },
        {
            "format_id": "140",
            "ext": "m4a",
            "vcodec": "none",
            "acodec": "mp4a.40.2",
            "abr": 128,
            "tbr": 128,
        },
        {
            "format_id": "251",
            "ext": "webm",
            "vcodec": "none",
            "acodec": "opus",
            "abr": 160,
            "tbr": 160,
        },
    ],
}


def evaluate_video_selector(formats, quality, mode=DownloadMode.VIDEO_WITH_AUDIO):
    """Evaluate the real installed yt-dlp selector without fetching media."""
    import yt_dlp

    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
        info = {
            "formats": [dict(item, url="https://media.invalid/fixture") for item in formats],
        }
        ydl.sort_formats(info)
        select = ydl.build_format_selector(YouTubeProvider._format_selector(mode, quality))
        return list(select({**info, "incomplete_formats": False, "has_merged_format": False}))


def test_medium_portrait_selection_cannot_download_landscape_1080() -> None:
    formats = [
        {
            "format_id": "portrait",
            "width": 720,
            "height": 1280,
            "vcodec": "avc1",
            "acodec": "none",
            "ext": "mp4",
        },
        {
            "format_id": "landscape",
            "width": 1920,
            "height": 1080,
            "vcodec": "avc1",
            "acodec": "none",
            "ext": "mp4",
        },
        {"format_id": "audio", "vcodec": "none", "acodec": "mp4a", "ext": "m4a"},
    ]
    qualities = YouTubeProvider._qualities_from_info(
        {"formats": formats}, DownloadMode.VIDEO_WITH_AUDIO
    )
    medium = next(
        choice.quality
        for choice in build_quality_tier_plan(qualities).choices
        if choice.tier is QualityTier.MEDIUM
    )

    selected = evaluate_video_selector(formats, medium)

    assert len(selected) == 1
    video, audio = selected[0]["requested_formats"]
    assert video["format_id"] == "portrait"
    assert min(video["width"], video["height"]) == 720
    assert audio["format_id"] == "audio"


class FakeYoutubeDL:
    """Minimal yt-dlp substitute that never accesses the network."""

    def __init__(
        self,
        params: dict[str, Any],
        info: dict[str, Any],
        download_extension: str = "mp4",
        extract_error: Exception | None = None,
        process_error: Exception | None = None,
        write_output: bool = True,
    ) -> None:
        self.params = params
        self.format_selector = params.get("format")
        self.info = info
        self.download_extension = download_extension
        self.extract_error = extract_error
        self.process_error = process_error
        self.write_output = write_output
        self.extract_calls: list[tuple[str, bool, bool]] = []
        self.processed = False

    def __enter__(self) -> "FakeYoutubeDL":
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def build_format_selector(self, format_spec: str) -> str:
        return format_spec

    def extract_info(
        self,
        url: str,
        download: bool = True,
        ie_key: str | None = None,
        extra_info: Any = None,
        process: bool = True,
        force_generic_extractor: bool = False,
    ) -> dict[str, Any]:
        self.extract_calls.append((url, download, process))
        if self.extract_error is not None:
            raise self.extract_error
        return self.info.copy()

    def process_ie_result(
        self,
        ie_result: dict[str, Any],
        download: bool = True,
        extra_info: Any = None,
    ) -> dict[str, str]:
        self.processed = True
        assert download is True

        output_template = str(self.params["outtmpl"])
        output_name = (
            output_template.replace("%(id)s", str(self.info["id"]))
            .replace("%(format_id)s", "fake")
            .replace("%(ext)s", self.download_extension)
        )
        output_path = Path(output_name)
        if self.process_error is not None:
            raise self.process_error
        if self.write_output:
            output_path.write_bytes(b"fake media")
        return {"filepath": str(output_path)}


class FakeYoutubeDLFactory:
    """Factory that records every client created by the provider."""

    def __init__(
        self,
        info: dict[str, Any] | None = None,
        download_extension: str = "mp4",
        extract_error: Exception | None = None,
        process_error: Exception | None = None,
        write_output: bool = True,
    ) -> None:
        self.info = info if info is not None else VIDEO_INFO
        self.download_extension = download_extension
        self.extract_error = extract_error
        self.process_error = process_error
        self.write_output = write_output
        self.instances: list[FakeYoutubeDL] = []

    def __call__(self, params: dict[str, Any]) -> FakeYoutubeDL:
        client = FakeYoutubeDL(
            params,
            self.info,
            download_extension=self.download_extension,
            extract_error=self.extract_error,
            process_error=self.process_error,
            write_output=self.write_output,
        )
        self.instances.append(client)
        return client


@pytest.fixture
def factory() -> FakeYoutubeDLFactory:
    return FakeYoutubeDLFactory()


@pytest.fixture
def provider(factory: FakeYoutubeDLFactory) -> YouTubeProvider:
    return YouTubeProvider(ydl_factory=factory)


def test_provider_identifies_youtube_urls(provider: YouTubeProvider) -> None:
    assert provider.platform is Platform.YOUTUBE
    assert provider.can_handle("https://www.youtube.com/watch?v=abc123")
    assert provider.can_handle("https://youtu.be/abc123")
    assert not provider.can_handle("https://www.instagram.com/p/abc123/")
    assert not provider.can_handle("https://example.org/video")


def test_extract_metadata_without_downloading(
    provider: YouTubeProvider,
    factory: FakeYoutubeDLFactory,
) -> None:
    metadata = provider.extract_metadata("https://youtu.be/abc123")

    assert metadata.title == "Test: video/short"
    assert metadata.source_url == "https://youtu.be/abc123"
    assert metadata.platform is Platform.YOUTUBE
    assert metadata.duration_seconds == 123
    assert metadata.uploader == "Test Channel"

    client = factory.instances[-1]
    assert client.extract_calls == [("https://youtu.be/abc123", False, False)]
    assert not client.processed


def test_lists_supported_modes(provider: YouTubeProvider) -> None:
    assert provider.get_supported_modes("https://youtu.be/abc123") == (
        DownloadMode.VIDEO_WITH_AUDIO,
        DownloadMode.VIDEO_ONLY,
        DownloadMode.AUDIO_ONLY,
    )


@pytest.mark.parametrize(
    ("formats", "expected_modes"),
    [
        pytest.param(
            [
                {"format_id": "18", "height": 360, "vcodec": "avc1", "acodec": "mp4a"},
            ],
            (DownloadMode.VIDEO_WITH_AUDIO,),
            id="progressive-video-with-audio",
        ),
        pytest.param(
            [
                {"format_id": "137", "height": 1080, "vcodec": "avc1", "acodec": "none"},
                {"format_id": "248", "height": 1080, "vcodec": "vp9", "acodec": "none"},
                {"format_id": "399", "height": 1080, "vcodec": "av01", "acodec": "none"},
                {"format_id": "140", "vcodec": "none", "acodec": "mp4a.40.2"},
                {"format_id": "251", "vcodec": "none", "acodec": "opus"},
            ],
            (
                DownloadMode.VIDEO_WITH_AUDIO,
                DownloadMode.VIDEO_ONLY,
                DownloadMode.AUDIO_ONLY,
            ),
            id="adaptive-avc-vp9-av1-and-aac-opus",
        ),
        pytest.param(
            [{"format_id": "137", "height": 1080, "vcodec": "avc1", "acodec": "none"}],
            (DownloadMode.VIDEO_ONLY,),
            id="video-only-source",
        ),
        pytest.param(
            [{"format_id": "251", "vcodec": "none", "acodec": "opus"}],
            (DownloadMode.AUDIO_ONLY,),
            id="audio-only-source",
        ),
        pytest.param(
            [{"format_id": "unknown", "vcodec": "none", "acodec": "none"}],
            (),
            id="no-usable-audio-or-video",
        ),
    ],
)
def test_supported_modes_for_representative_format_layouts(
    formats: list[dict[str, Any]],
    expected_modes: tuple[DownloadMode, ...],
) -> None:
    assert YouTubeProvider._supported_modes_from_info({"formats": formats}) == expected_modes


def test_lists_video_qualities_from_available_formats(
    provider: YouTubeProvider,
) -> None:
    qualities = provider.get_available_qualities(
        "https://youtu.be/abc123",
        DownloadMode.VIDEO_ONLY,
    )

    assert [quality.id for quality in qualities] == ["video-1920x1080", "video-1280x720"]
    assert [quality.height for quality in qualities] == [1080, 720]
    assert [quality.width for quality in qualities] == [1920, 1280]
    assert all(quality.mode is DownloadMode.VIDEO_ONLY for quality in qualities)


def test_quality_labels_distinguish_portrait_and_landscape() -> None:
    info = {
        "formats": [
            {
                "format_id": "portrait-1280",
                "width": 720,
                "height": 1280,
                "vcodec": "avc1",
                "acodec": "none",
            },
            {
                "format_id": "landscape-1080",
                "width": 1920,
                "height": 1080,
                "vcodec": "avc1",
                "acodec": "none",
            },
        ]
    }

    qualities = YouTubeProvider._qualities_from_info(
        info,
        DownloadMode.VIDEO_ONLY,
    )

    assert [(item.label, item.height) for item in qualities] == [
        ("720×1280", 1280),
        ("1920×1080", 1080),
    ]
    assert [(item.width, item.height) for item in qualities] == [
        (720, 1280),
        (1920, 1080),
    ]


def test_lists_audio_qualities_from_available_formats(
    provider: YouTubeProvider,
) -> None:
    qualities = provider.get_available_qualities(
        "https://youtu.be/abc123",
        DownloadMode.AUDIO_ONLY,
    )

    assert [quality.id for quality in qualities] == ["audio:251", "audio:140"]
    assert [quality.bitrate_kbps for quality in qualities] == [160, 128]


def test_download_reuses_info_from_quality_discovery(
    factory: FakeYoutubeDLFactory,
    tmp_path: Path,
) -> None:
    provider = YouTubeProvider(ydl_factory=factory)
    url = "https://youtu.be/abc123"

    qualities = provider.get_available_qualities(url, DownloadMode.VIDEO_ONLY)
    selected_quality = next(item for item in qualities if item.height == 720)

    downloaded = provider.download(
        url,
        tmp_path,
        DownloadOptions(
            mode=DownloadMode.VIDEO_ONLY,
            quality_id=selected_quality.id,
        ),
    )

    assert downloaded.file_path.is_file()
    assert len(factory.instances) == 2
    assert len(factory.instances[0].extract_calls) == 1
    assert factory.instances[1].extract_calls == []
    assert factory.instances[1].processed


@pytest.mark.parametrize("mode", [DownloadMode.VIDEO_WITH_AUDIO, DownloadMode.VIDEO_ONLY])
def test_default_video_download_requires_concrete_quality(
    provider: YouTubeProvider,
    factory: FakeYoutubeDLFactory,
    tmp_path: Path,
    mode: DownloadMode,
) -> None:
    with pytest.raises(UnsupportedQualityError):
        provider.download("https://youtu.be/abc123", tmp_path, DownloadOptions(mode=mode))

    assert not factory.instances[-1].processed
    assert list(tmp_path.iterdir()) == []


def test_video_with_audio_download_prefers_compatible_codecs_for_selected_quality(
    provider: YouTubeProvider,
    factory: FakeYoutubeDLFactory,
    tmp_path: Path,
) -> None:
    downloaded = provider.download(
        "https://youtu.be/abc123",
        tmp_path,
        DownloadOptions(
            mode=DownloadMode.VIDEO_WITH_AUDIO,
            quality_id="video-1280x720",
        ),
    )

    expected_selector = (
        "bv[width=1280][height=720][vcodec^=avc1][ext=mp4]+ba[acodec^=mp4a]/"
        "b[width=1280][height=720][vcodec^=avc1][acodec^=mp4a][ext=mp4]/"
        "bv*[width=1280][height=720]+ba/b[width=1280][height=720]"
    )
    client = factory.instances[-1]
    assert client.params["format"] == expected_selector
    assert client.format_selector == expected_selector
    assert client.params["merge_output_format"] == "mp4"
    assert downloaded.file_path.is_file()


def test_video_only_download_uses_selected_quality(
    provider: YouTubeProvider,
    factory: FakeYoutubeDLFactory,
    tmp_path: Path,
) -> None:
    downloaded = provider.download(
        "https://youtu.be/abc123",
        tmp_path,
        DownloadOptions(
            mode=DownloadMode.VIDEO_ONLY,
            quality_id="video-1280x720",
        ),
    )

    client = factory.instances[-1]
    assert client.params["format"] == "bv[width=1280][height=720]"
    assert client.format_selector == "bv[width=1280][height=720]"
    assert client.params["retries"] == 10
    assert client.params["fragment_retries"] == 10
    assert "merge_output_format" not in client.params
    assert downloaded.file_path.is_file()


@pytest.mark.parametrize(
    ("quality_id", "expected_selector", "extension"),
    [
        ("audio:140", "140-0/140", "m4a"),
        ("audio:251", "251-0/251", "webm"),
    ],
)
def test_audio_only_download_uses_selected_format(
    factory: FakeYoutubeDLFactory,
    tmp_path: Path,
    quality_id: str,
    expected_selector: str,
    extension: str,
) -> None:
    factory.download_extension = extension
    provider = YouTubeProvider(ydl_factory=factory)

    downloaded = provider.download(
        "https://youtu.be/abc123",
        tmp_path,
        DownloadOptions(
            mode=DownloadMode.AUDIO_ONLY,
            quality_id=quality_id,
        ),
    )

    client = factory.instances[-1]
    assert client.params["format"] == expected_selector
    assert client.format_selector == expected_selector
    assert "merge_output_format" not in client.params
    assert downloaded.file_path.suffix == f".{extension}"
    assert downloaded.file_path.is_file()


def test_rejects_unknown_quality(
    provider: YouTubeProvider,
    tmp_path: Path,
) -> None:
    with pytest.raises(UnsupportedQualityError):
        provider.download(
            "https://youtu.be/abc123",
            tmp_path,
            DownloadOptions(quality_id="not-available"),
        )


def test_rejects_unsupported_mode(
    tmp_path: Path,
) -> None:
    video_only_info = {
        **VIDEO_INFO,
        "formats": [
            {
                "format_id": "137",
                "ext": "mp4",
                "height": 1080,
                "vcodec": "avc1",
                "acodec": "none",
            }
        ],
    }
    provider = YouTubeProvider(ydl_factory=FakeYoutubeDLFactory(video_only_info))

    with pytest.raises(UnsupportedDownloadModeError):
        provider.download(
            "https://youtu.be/abc123",
            tmp_path,
            DownloadOptions(mode=DownloadMode.AUDIO_ONLY),
        )


def test_rejects_playlist_metadata() -> None:
    playlist_info = {"_type": "playlist", "entries": [], "title": "Playlist"}
    provider = YouTubeProvider(ydl_factory=FakeYoutubeDLFactory(playlist_info))

    with pytest.raises(MetadataExtractionError):
        provider.extract_metadata("https://youtu.be/abc123")


def test_metadata_extractor_failure_maps_to_domain_error() -> None:
    factory = FakeYoutubeDLFactory(extract_error=RuntimeError("simulated extractor failure"))
    provider = YouTubeProvider(ydl_factory=factory)

    with pytest.raises(MetadataExtractionError) as exc_info:
        provider.extract_metadata("https://youtu.be/abc123")

    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_download_failure_maps_to_download_failed_error(tmp_path: Path) -> None:
    factory = FakeYoutubeDLFactory(process_error=RuntimeError("simulated download failure"))
    provider = YouTubeProvider(ydl_factory=factory)

    with pytest.raises(DownloadFailedError) as exc_info:
        provider.download(
            "https://youtu.be/abc123", tmp_path, DownloadOptions(quality_id="video-1280x720")
        )

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert list(tmp_path.iterdir()) == []


def test_post_processing_failure_maps_to_media_processing_error(tmp_path: Path) -> None:
    class PostProcessingError(Exception):
        pass

    factory = FakeYoutubeDLFactory(process_error=PostProcessingError("simulated ffmpeg failure"))
    provider = YouTubeProvider(ydl_factory=factory)

    with pytest.raises(MediaProcessingError) as exc_info:
        provider.download(
            "https://youtu.be/abc123", tmp_path, DownloadOptions(quality_id="video-1280x720")
        )

    assert isinstance(exc_info.value.__cause__, PostProcessingError)
    assert list(tmp_path.iterdir()) == []


def test_missing_final_media_file_maps_to_media_processing_error(tmp_path: Path) -> None:
    provider = YouTubeProvider(ydl_factory=FakeYoutubeDLFactory(write_output=False))

    with pytest.raises(MediaProcessingError, match="exactly one final media file"):
        provider.download(
            "https://youtu.be/abc123", tmp_path, DownloadOptions(quality_id="video-1280x720")
        )

    # The temporary workspace is removed even when no final media file is produced.
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "format_spec",
    [
        "bv[width=1280][height=720]",
        (
            "bv[width=1280][height=720][vcodec^=avc1][ext=mp4]+ba[acodec^=mp4a]/"
            "b[width=1280][height=720][vcodec^=avc1][acodec^=mp4a][ext=mp4]/"
            "bv*[width=1280][height=720]+ba/b[width=1280][height=720]"
        ),
        "140-0/140",
        "251-0/251",
        "ba[ext=m4a][acodec~='^(mp4a|aac)']/ba",
    ],
)
def test_format_selectors_compile_with_installed_yt_dlp(
    format_spec: str,
) -> None:
    import yt_dlp

    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
        selector = ydl.build_format_selector(format_spec)

    assert callable(selector)


@pytest.mark.parametrize(
    ("formats", "expected"),
    [
        (VIDEO_INFO["formats"], "140"),
        (
            VIDEO_INFO["formats"]
            + [
                {
                    "format_id": "better-aac",
                    "ext": "m4a",
                    "vcodec": "none",
                    "acodec": "mp4a.40.2",
                    "abr": 192,
                },
            ],
            "better-aac",
        ),
        ([f for f in VIDEO_INFO["formats"] if f["ext"] != "m4a"], "251"),
        (
            [f for f in VIDEO_INFO["formats"] if f["ext"] != "m4a"]
            + [
                {
                    "format_id": "mislabelled",
                    "ext": "m4a",
                    "vcodec": "none",
                    "acodec": "opus",
                    "abr": 32,
                },
            ],
            "251",
        ),
    ],
)
def test_automatic_audio_prefers_best_native_aac_with_best_audio_fallback(formats, expected):
    import yt_dlp

    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
        info = {"formats": [dict(item, url="https://media.invalid/audio") for item in formats]}
        ydl.sort_formats(info)
        select = ydl.build_format_selector(
            YouTubeProvider._format_selector(DownloadMode.AUDIO_ONLY, None)
        )
        selected = list(select({**info, "incomplete_formats": False, "has_merged_format": False}))

    assert [item["format_id"] for item in selected] == [expected]


def test_automatic_audio_download_installs_native_preference(tmp_path):
    factory = FakeYoutubeDLFactory(download_extension="m4a")
    provider = YouTubeProvider(ydl_factory=factory)

    provider.download(
        "https://youtu.be/abc123", tmp_path, DownloadOptions(mode=DownloadMode.AUDIO_ONLY)
    )

    assert factory.instances[-1].params["format"] == "ba[ext=m4a][acodec~='^(mp4a|aac)']/ba"
    assert "merge_output_format" not in factory.instances[-1].params


SINGLE_WATCH_URL = "https://www.youtube.com/watch?v=abcDEF123_-"
CONTEXT_WATCH_URL = f"{SINGLE_WATCH_URL}&list=PLexample"


class PlaylistContextYoutubeDL(FakeYoutubeDL):
    """Model yt-dlp's unprocessed redirect without resolving it or using a network."""

    def extract_info(self, url: str, download: bool = True, **kwargs: Any) -> dict[str, Any]:
        info = super().extract_info(url, download=download, **kwargs)
        assert self.params["noplaylist"] is True
        assert download is False
        assert kwargs["process"] is False
        if "list" in parse_qs(urlsplit(url).query):
            return {"_type": "url", "url": SINGLE_WATCH_URL, "ie_key": "Youtube"}
        return info


class PlaylistContextFactory(FakeYoutubeDLFactory):
    def __call__(self, params: dict[str, Any]) -> PlaylistContextYoutubeDL:
        client = PlaylistContextYoutubeDL(params, self.info)
        self.instances.append(client)
        return client


@pytest.mark.parametrize(
    "url",
    [
        SINGLE_WATCH_URL,
        f"{SINGLE_WATCH_URL}&t=10&si=share%2Bvalue",
        "https://m.youtube.com/watch?v=abcDEF123_-",
        "http://youtube.com/watch?v=abcDEF123_-",
        "https://youtu.be/abcDEF123_-?si=share",
        "https://www.youtube.com/shorts/abcDEF123_-",
    ],
)
def test_single_video_targets_are_preserved(url: str, factory: FakeYoutubeDLFactory) -> None:
    metadata = YouTubeProvider(ydl_factory=factory).extract_metadata(url)

    assert metadata.source_url == url
    assert factory.instances[0].extract_calls == [(url, False, False)]
    assert not factory.instances[0].processed


@pytest.mark.parametrize(
    ("url", "target"),
    [
        (CONTEXT_WATCH_URL, SINGLE_WATCH_URL),
        ("https://www.youtube.com/watch?list=PLexample&v=abcDEF123_-", SINGLE_WATCH_URL),
        (f"{SINGLE_WATCH_URL}&list=", SINGLE_WATCH_URL),
        (f"{CONTEXT_WATCH_URL}&list=PLother", SINGLE_WATCH_URL),
        (f"{SINGLE_WATCH_URL}&%6cist=PLexample", SINGLE_WATCH_URL),
        ("https://www.youtube.com/watch?v=abcDEF123%5F-&list=PLexample", SINGLE_WATCH_URL),
        ("https://www.youtube.com/watch?%76=abcDEF123_-&list=PLexample", SINGLE_WATCH_URL),
        (
            f"{CONTEXT_WATCH_URL}&index=2&start_radio=1&t=10&si=share%2Bvalue",
            f"{SINGLE_WATCH_URL}&index=2&start_radio=1&t=10&si=share%2Bvalue",
        ),
        (
            "https://m.youtube.com/watch?v=abcDEF123_-&list=PLexample",
            "https://m.youtube.com/watch?v=abcDEF123_-",
        ),
    ],
)
def test_watch_playlist_context_is_removed_before_extraction(url: str, target: str) -> None:
    from yt_dlp.extractor.youtube import YoutubeIE, YoutubeTabIE

    factory = PlaylistContextFactory()
    metadata = YouTubeProvider(ydl_factory=factory).extract_metadata(url)

    assert metadata.source_url == target
    assert factory.instances[0].extract_calls == [(target, False, False)]
    assert not factory.instances[0].processed
    assert YoutubeIE.suitable(target)
    assert not YoutubeTabIE.suitable(target)


def test_unprocessed_playlist_context_redirect_reproduces_false_blocked() -> None:
    raw = PlaylistContextYoutubeDL(YouTubeProvider._base_options(), VIDEO_INFO)
    redirect = raw.extract_info(CONTEXT_WATCH_URL, download=False, process=False)
    assert redirect["_type"] == "url"
    provider = YouTubeProvider(ydl_factory=FakeYoutubeDLFactory(info=redirect))

    plan = DownloadService([provider]).create_choice_plan(SINGLE_WATCH_URL)

    assert plan.state is ChoicePlanState.BLOCKED
    assert plan.blocked_reason == "no_useful_modes"
    assert not raw.processed


@pytest.mark.parametrize("context_first", [True, False])
def test_equivalent_watch_urls_share_choice_plan_and_inspection_cache(context_first: bool) -> None:
    factory = PlaylistContextFactory()
    provider = YouTubeProvider(ydl_factory=factory)
    service = DownloadService([provider])
    first, second = (
        (CONTEXT_WATCH_URL, SINGLE_WATCH_URL)
        if context_first
        else (SINGLE_WATCH_URL, CONTEXT_WATCH_URL)
    )

    plan = service.create_choice_plan(first)
    assert service.create_choice_plan(second) == plan
    assert provider.extract_metadata(second).source_url == SINGLE_WATCH_URL
    assert plan.state is ChoicePlanState.CHOOSE_MODE
    assert plan.blocked_reason is None
    assert plan.technical_modes == (
        DownloadMode.VIDEO_WITH_AUDIO,
        DownloadMode.VIDEO_ONLY,
        DownloadMode.AUDIO_ONLY,
    )
    video, audio = plan.mode_choices
    assert video.kind is UserChoiceKind.VIDEO
    assert audio.kind is UserChoiceKind.AUDIO
    assert audio.final_options == DownloadOptions(mode=DownloadMode.AUDIO_ONLY)
    assert [(choice.tier, choice.quality.id) for choice in video.quality_choices] == [
        (QualityTier.LOW, "video-640x360"),
        (QualityTier.MEDIUM, "video-1280x720"),
        (QualityTier.HIGH, "video-1920x1080"),
    ]
    assert len(factory.instances) == 1
    assert factory.instances[0].extract_calls == [(SINGLE_WATCH_URL, False, False)]
    assert not factory.instances[0].processed


@pytest.mark.parametrize("cached_url", [None, SINGLE_WATCH_URL, CONTEXT_WATCH_URL])
@pytest.mark.parametrize("download_url", [SINGLE_WATCH_URL, CONTEXT_WATCH_URL])
def test_playlist_context_download_uses_canonical_target_and_cached_info(
    cached_url: str | None, download_url: str, tmp_path: Path
) -> None:
    factory = PlaylistContextFactory()
    provider = YouTubeProvider(ydl_factory=factory)
    if cached_url is not None:
        provider.get_supported_modes(cached_url)

    downloaded = provider.download(
        download_url, tmp_path, DownloadOptions(quality_id="video-1280x720")
    )

    assert downloaded.metadata.source_url == SINGLE_WATCH_URL
    assert downloaded.file_path.is_file()
    assert [call for client in factory.instances for call in client.extract_calls] == [
        (SINGLE_WATCH_URL, False, False)
    ]
    assert sum(client.processed for client in factory.instances) == 1
    assert factory.instances[-1].processed


@pytest.mark.parametrize(
    ("url", "error"),
    [
        ("https://www.youtube.com/playlist?list=PLexample", MetadataExtractionError),
        ("https://www.youtube.com/playlist/?list=PLexample", MetadataExtractionError),
        ("https://www.youtube.com/playlist", MetadataExtractionError),
        ("https://www.youtube.com/playlist?v=abcDEF123_-&list=PLexample", MetadataExtractionError),
        ("https://www.youtube.com/watch?list=PLexample", InvalidMediaURLError),
        ("https://www.youtube.com/watch?v=&list=PLexample", InvalidMediaURLError),
        ("https://www.youtube.com/watch?v=short&list=PLexample", InvalidMediaURLError),
        (f"{SINGLE_WATCH_URL}x&list=PLexample", InvalidMediaURLError),
        (f"{CONTEXT_WATCH_URL}&v=otherID1234", InvalidMediaURLError),
        (f"{CONTEXT_WATCH_URL}&v=", InvalidMediaURLError),
        (f"{CONTEXT_WATCH_URL}&v=abcDEF123_-", InvalidMediaURLError),
        (f"{CONTEXT_WATCH_URL}&%76=otherID1234", InvalidMediaURLError),
        ("https://www.youtube.com/watch?v=abcDEF123%2F&list=PLexample", InvalidMediaURLError),
        ("https://www.youtube.com/watch?v=abcDEF123%20&list=PLexample", InvalidMediaURLError),
        ("https://www.youtube.com/watch?v=abcDEF123%00&list=PLexample", InvalidMediaURLError),
        (
            "https://user:password@youtube.com/watch?v=abcDEF123_-&list=PLexample",
            InvalidMediaURLError,
        ),
        ("ftp://youtube.com/watch?v=abcDEF123_-&list=PLexample", InvalidMediaURLError),
        (
            "https://youtube.com.example.org/watch?v=abcDEF123_-&list=PLexample",
            UnsupportedPlatformError,
        ),
    ],
)
@pytest.mark.parametrize("operation", ["inspect", "download"])
def test_invalid_playlist_context_is_rejected_before_extraction(
    url: str, error: type[Exception], operation: str, tmp_path: Path
) -> None:
    factory = PlaylistContextFactory()
    provider = YouTubeProvider(ydl_factory=factory)

    with pytest.raises(error):
        if operation == "download":
            provider.download(url, tmp_path)
        else:
            provider.extract_metadata(url)

    assert factory.instances == []
    assert list(tmp_path.iterdir()) == []


def video_format(format_id, width, height, *, vcodec="avc1", acodec="none", ext="mp4"):
    return {
        "format_id": format_id,
        "width": width,
        "height": height,
        "vcodec": vcodec,
        "acodec": acodec,
        "ext": ext,
    }


@pytest.mark.parametrize("mode", [DownloadMode.VIDEO_WITH_AUDIO, DownloadMode.VIDEO_ONLY])
@pytest.mark.parametrize(
    ("width", "height"),
    [(720, 1280), (1280, 720), (1920, 1080), (1080, 1920), (720, 720), (720, 1080)],
)
def test_real_selector_preserves_dimensions_in_mixed_orientation_formats(mode, width, height):
    formats = [
        video_format("chosen", width, height),
        video_format("ultra", 3840, 2160),
        video_format("same-height", width + 1200, height),
        video_format("width-only", width, None),
        video_format("height-only", None, height),
        video_format("unknown", None, None),
        {"format_id": "audio", "vcodec": "none", "acodec": "mp4a", "ext": "m4a"},
    ]
    qualities = YouTubeProvider._qualities_from_info({"formats": formats}, mode)
    quality = next(item for item in qualities if item.width == width and item.height == height)

    selected = evaluate_video_selector(formats, quality, mode)

    assert len(selected) == 1
    if mode is DownloadMode.VIDEO_WITH_AUDIO:
        video, audio = selected[0]["requested_formats"]
        assert audio["acodec"] == "mp4a"
    else:
        video = selected[0]
    assert video["format_id"] == "chosen"
    assert (video["width"], video["height"]) == (width, height)


@pytest.mark.parametrize(
    ("video", "audio_codec", "audio_ext"),
    [
        (video_format("avc", 1280, 720), "mp4a.40.2", "m4a"),
        (video_format("vp9", 1280, 720, vcodec="vp9", ext="webm"), "opus", "webm"),
        (video_format("combined", 1280, 720, acodec="mp4a.40.2"), None, None),
        (
            video_format("combined-vp9", 1280, 720, vcodec="vp9", acodec="opus", ext="webm"),
            None,
            None,
        ),
    ],
)
def test_real_selector_codec_fallbacks_keep_selected_size_and_audio(video, audio_codec, audio_ext):
    formats = [video, video_format("larger-native", 1920, 1080, acodec="mp4a.40.2")]
    if audio_codec is not None:
        formats.append(
            {"format_id": "audio", "vcodec": "none", "acodec": audio_codec, "ext": audio_ext}
        )
    quality = next(
        item
        for item in YouTubeProvider._qualities_from_info(
            {"formats": formats}, DownloadMode.VIDEO_WITH_AUDIO
        )
        if item.width == 1280
    )

    selected = evaluate_video_selector(formats, quality)

    assert len(selected) == 1
    streams = selected[0].get("requested_formats", [selected[0]])
    assert any(item["acodec"] != "none" for item in streams)
    assert [item["format_id"] for item in streams if item["vcodec"] != "none"] == [
        video["format_id"]
    ]


def test_real_selector_prefers_native_mp4_aac_within_selected_dimensions():
    formats = [
        video_format("avc", 1280, 720),
        video_format("vp9", 1280, 720, vcodec="vp9", ext="webm"),
        {"format_id": "aac", "vcodec": "none", "acodec": "mp4a.40.2", "ext": "m4a"},
        {"format_id": "opus", "vcodec": "none", "acodec": "opus", "ext": "webm"},
    ]
    (quality,) = YouTubeProvider._qualities_from_info(
        {"formats": formats}, DownloadMode.VIDEO_WITH_AUDIO
    )

    selected = evaluate_video_selector(formats, quality)

    assert [item["format_id"] for item in selected[0]["requested_formats"]] == ["avc", "aac"]


@pytest.mark.parametrize(("width", "height"), [(720, None), (None, 720), (None, None)])
def test_incomplete_video_dimensions_are_never_actionable(width, height, tmp_path):
    info = {**VIDEO_INFO, "formats": [video_format("partial", width, height, acodec="mp4a")]}
    factory = FakeYoutubeDLFactory(info)
    provider = YouTubeProvider(ydl_factory=factory)
    qualities = provider.get_available_qualities(SINGLE_WATCH_URL, DownloadMode.VIDEO_WITH_AUDIO)
    if width is None and height is None:
        assert qualities == ()
        quality = None
    else:
        (quality,) = qualities
        assert classify_quality(quality).confidence is ResolutionConfidence.SINGLE_DIMENSION

    with pytest.raises(UnsupportedQualityError):
        provider.download(
            SINGLE_WATCH_URL, tmp_path, DownloadOptions(quality_id=quality.id if quality else None)
        )

    assert not any(client.processed for client in factory.instances)
    assert list(tmp_path.iterdir()) == []


def test_quality_identities_and_tiers_are_deterministic_with_shared_heights():
    formats = [video_format("portrait", 720, 1080), video_format("landscape", 1920, 1080)]
    qualities = YouTubeProvider._qualities_from_info({"formats": formats}, DownloadMode.VIDEO_ONLY)

    assert len({item.id for item in qualities}) == 2
    assert qualities == YouTubeProvider._qualities_from_info(
        {"formats": list(reversed(formats))}, DownloadMode.VIDEO_ONLY
    )
    assert [
        (choice.tier, choice.quality.id) for choice in build_quality_tier_plan(qualities).choices
    ] == [
        (QualityTier.MEDIUM, "video-720x1080"),
        (QualityTier.HIGH, "video-1920x1080"),
    ]


@pytest.mark.parametrize("changed_dimensions", [(1920, 1080), (None, 720), (3840, 2160)])
def test_changed_selected_dimensions_fail_without_fallback(
    changed_dimensions, tmp_path, monkeypatch
):
    factory = FakeYoutubeDLFactory(
        {**VIDEO_INFO, "formats": [video_format("same-id", 1280, 720, acodec="mp4a")]}
    )
    provider = YouTubeProvider(ydl_factory=factory)
    (quality,) = provider.get_available_qualities(SINGLE_WATCH_URL, DownloadMode.VIDEO_WITH_AUDIO)
    # Expire the existing inspection to exercise revalidation against fresh metadata.
    monkeypatch.setattr(provider, "_INSPECTION_CACHE_TTL_SECONDS", 0)
    factory.info = {
        **VIDEO_INFO,
        "formats": [video_format("same-id", *changed_dimensions, acodec="mp4a")],
    }

    with pytest.raises(UnsupportedQualityError):
        provider.download(SINGLE_WATCH_URL, tmp_path, DownloadOptions(quality_id=quality.id))

    assert not any(client.processed for client in factory.instances)


@pytest.mark.parametrize("mode", [DownloadMode.VIDEO_WITH_AUDIO, DownloadMode.VIDEO_ONLY])
def test_real_selector_missing_selected_size_cannot_fall_back_to_other_quality(mode):
    (quality,) = YouTubeProvider._qualities_from_info(
        {"formats": [video_format("chosen", 720, 1280)]}, DownloadMode.VIDEO_ONLY
    )
    formats = [video_format("different", 1920, 1080, acodec="mp4a")]

    assert evaluate_video_selector(formats, quality, mode) == []


def test_video_with_audio_discovery_excludes_unpairable_video_only_size():
    formats = [
        video_format("silent", 1280, 720),
        video_format("combined", 1920, 1080, acodec="mp4a.40.2"),
    ]
    info = {"formats": formats}

    (quality,) = YouTubeProvider._qualities_from_info(info, DownloadMode.VIDEO_WITH_AUDIO)

    assert quality.id == "video-1920x1080"
    assert evaluate_video_selector(formats, quality)[0]["format_id"] == "combined"
    (video_only,) = YouTubeProvider._qualities_from_info(info, DownloadMode.VIDEO_ONLY)
    assert video_only.id == "video-1280x720"


@pytest.mark.parametrize("with_audio", [True, False])
@pytest.mark.parametrize(
    ("width", "height"), [(720, None), (None, 720), (None, None), (3840, 2160)]
)
def test_provider_metadata_cannot_create_unsafe_video_download_plan(width, height, with_audio):
    formats = [video_format("video", width, height, acodec="mp4a")]
    if with_audio:
        formats.append({"format_id": "audio", "vcodec": "none", "acodec": "mp4a", "ext": "m4a"})
    factory = FakeYoutubeDLFactory({**VIDEO_INFO, "formats": formats})
    provider = YouTubeProvider(ydl_factory=factory)

    plan = DownloadService([provider]).create_choice_plan(SINGLE_WATCH_URL)

    if with_audio:
        assert plan.state is ChoicePlanState.DIRECT_DOWNLOAD
        assert plan.automatic_options == DownloadOptions(mode=DownloadMode.AUDIO_ONLY)
    else:
        assert plan.state is ChoicePlanState.BLOCKED
        assert plan.automatic_options is None
    assert len(factory.instances) == 1
    assert not factory.instances[0].processed


def test_single_safe_video_plan_downloads_exact_quality_from_shared_snapshot(tmp_path):
    formats = [video_format("combined", 720, 1280, acodec="mp4a.40.2")]
    factory = FakeYoutubeDLFactory({**VIDEO_INFO, "formats": formats})
    provider = YouTubeProvider(ydl_factory=factory)
    service = DownloadService([provider])

    plan = service.create_choice_plan(SINGLE_WATCH_URL)

    assert plan.state is ChoicePlanState.DIRECT_DOWNLOAD
    assert plan.automatic_options == DownloadOptions(
        mode=DownloadMode.VIDEO_WITH_AUDIO, quality_id="video-720x1280"
    )
    result = service.download(SINGLE_WATCH_URL, tmp_path, plan.automatic_options)
    assert result.file_path.is_file()
    assert factory.instances[1].processed
    assert factory.instances[1].extract_calls == []
    quality = plan.mode_choices[0].quality_choices[0].quality
    assert factory.instances[1].params["format"] == YouTubeProvider._format_selector(
        DownloadMode.VIDEO_WITH_AUDIO, quality
    )
    assert evaluate_video_selector(formats, quality)[0]["format_id"] == "combined"
