import pytest

from social_video_downloader.domain.errors import (
    DownloaderError,
    DownloadFailedError,
    DownloadTimeoutError,
    InvalidMediaURLError,
    MediaProcessingError,
    MetadataExtractionError,
    UnsupportedDownloadModeError,
    UnsupportedPlatformError,
    UnsupportedQualityError,
)


@pytest.mark.parametrize(
    "error_type",
    [
        InvalidMediaURLError,
        UnsupportedPlatformError,
        MetadataExtractionError,
        DownloadFailedError,
        DownloadTimeoutError,
        MediaProcessingError,
        UnsupportedDownloadModeError,
        UnsupportedQualityError,
    ],
)
def test_all_domain_errors_inherit_from_downloader_error(error_type):
    assert issubclass(error_type, DownloaderError)


def test_download_timeout_is_a_download_failure():
    assert issubclass(DownloadTimeoutError, DownloadFailedError)


def test_media_processing_error_is_a_download_failure():
    assert issubclass(MediaProcessingError, DownloadFailedError)


def test_domain_error_preserves_message():
    message = "The media URL is invalid."

    error = InvalidMediaURLError(message)

    assert str(error) == message


def test_download_error_can_be_caught_by_base_class():
    with pytest.raises(DownloaderError):
        raise DownloadTimeoutError("Download timed out.")
