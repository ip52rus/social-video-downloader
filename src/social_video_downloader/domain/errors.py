"""Domain exceptions for the downloader core."""


class DownloaderError(Exception):
    """Base class for expected downloader errors."""


class InvalidMediaURLError(DownloaderError):
    """Raised when a submitted media URL is invalid."""


class UnsupportedPlatformError(DownloaderError):
    """Raised when no provider supports the submitted URL."""


class MetadataExtractionError(DownloaderError):
    """Raised when media metadata cannot be extracted."""


class DownloadFailedError(DownloaderError):
    """Raised when downloading media fails."""


class DownloadTimeoutError(DownloadFailedError):
    """Raised when downloading exceeds the allowed time."""


class MediaProcessingError(DownloadFailedError):
    """Raised when downloaded media cannot be assembled or processed."""


class UnsupportedDownloadModeError(DownloaderError):
    """Raised when a provider cannot produce the requested output mode."""


class UnsupportedQualityError(DownloaderError):
    """Raised when a requested quality option is unavailable."""
