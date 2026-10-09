"""Network-free tests for the real YouTube provider implementation."""

from pathlib import Path
from typing import Any

import pytest

from social_video_downloader.domain.errors import (
    DownloadFailedError,
    MediaProcessingError,
    MetadataExtractionError,
    UnsupportedDownloadModeError,
    UnsupportedQualityError,
)
from social_video_downloader.domain.models import (
    DownloadMode,
    DownloadOptions,
    Platform,
)
from social_video_downloader.providers.youtube import YouTubeProvider

VIDEO_INFO: dict[str, Any] = {
    "id": "abc123",
    "title": "Test: video/short",
    "duration": 123,
    "uploader": "Test Channel",
    "formats": [
        {
            "format_id": "18",
            "ext": "mp4",
            "height": 360,
            "vcodec": "avc1",
            "acodec": "mp4a",
            "tbr": 500,
        },
        {
            "format_id": "137",
            "ext": "mp4",
            "height": 1080,
            "vcodec": "avc1",
            "acodec": "none",
            "tbr": 4000,
        },
        {
            "format_id": "136",
            "ext": "mp4",
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

    assert [quality.id for quality in qualities] == ["height-1080", "height-720"]
    assert [quality.height for quality in qualities] == [1080, 720]
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
        ("720×1280 (max)", 1280),
        ("1080p (max)", 1080),
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


def test_default_download_uses_best_available_quality(
    provider: YouTubeProvider,
    factory: FakeYoutubeDLFactory,
    tmp_path: Path,
) -> None:
    downloaded = provider.download("https://youtu.be/abc123", tmp_path)

    client = factory.instances[-1]
    expected_selector = (
        "bv[vcodec^=avc1][ext=mp4]+ba[acodec^=mp4a]/b[vcodec^=avc1][acodec^=mp4a][ext=mp4]/bv*+ba/b"
    )
    assert client.params["format"] == expected_selector
    assert client.format_selector == expected_selector
    assert client.params["merge_output_format"] == "mp4"
    assert downloaded.file_path.is_file()
    assert downloaded.file_path.suffix == ".mp4"
    assert downloaded.file_path.read_bytes() == b"fake media"
    assert downloaded.metadata.title == "Test: video/short"


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
            quality_id="height-720",
        ),
    )

    expected_selector = (
        "bv[height<=720][vcodec^=avc1][ext=mp4]+ba[acodec^=mp4a]/"
        "b[height<=720][vcodec^=avc1][acodec^=mp4a][ext=mp4]/"
        "bv*[height<=720]+ba/b[height<=720]"
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
            quality_id="height-720",
        ),
    )

    client = factory.instances[-1]
    assert client.params["format"] == "bv[height<=720]"
    assert client.format_selector == "bv[height<=720]"
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
        provider.download("https://youtu.be/abc123", tmp_path)

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert list(tmp_path.iterdir()) == []


def test_post_processing_failure_maps_to_media_processing_error(tmp_path: Path) -> None:
    class PostProcessingError(Exception):
        pass

    factory = FakeYoutubeDLFactory(process_error=PostProcessingError("simulated ffmpeg failure"))
    provider = YouTubeProvider(ydl_factory=factory)

    with pytest.raises(MediaProcessingError) as exc_info:
        provider.download("https://youtu.be/abc123", tmp_path)

    assert isinstance(exc_info.value.__cause__, PostProcessingError)
    assert list(tmp_path.iterdir()) == []


def test_missing_final_media_file_maps_to_media_processing_error(tmp_path: Path) -> None:
    provider = YouTubeProvider(ydl_factory=FakeYoutubeDLFactory(write_output=False))

    with pytest.raises(MediaProcessingError, match="exactly one final media file"):
        provider.download("https://youtu.be/abc123", tmp_path)

    # The temporary workspace is removed even when no final media file is produced.
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "format_spec",
    [
        "bv*+ba/b",
        "bv[height<=720]",
        (
            "bv[vcodec^=avc1][ext=mp4]+ba[acodec^=mp4a]/"
            "b[vcodec^=avc1][acodec^=mp4a][ext=mp4]/"
            "bv*+ba/b"
        ),
        (
            "bv[height<=720][vcodec^=avc1][ext=mp4]+ba[acodec^=mp4a]/"
            "b[height<=720][vcodec^=avc1][acodec^=mp4a][ext=mp4]/"
            "bv*[height<=720]+ba/b[height<=720]"
        ),
        "140-0/140",
        "251-0/251",
    ],
)
def test_format_selectors_compile_with_installed_yt_dlp(
    format_spec: str,
) -> None:
    import yt_dlp

    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
        selector = ydl.build_format_selector(format_spec)

    assert callable(selector)
