"""Domain exceptions for the downloader core."""


class DownloaderError(Exception):
    """Base class for expected downloader errors."""


class InvalidMediaURLError(DownloaderError):
    """Raised when a submitted media URL is invalid."""


class UnsupportedPlatformError(DownloaderError):
    """Raised when no provider supports the submitted URL."""


class MetadataExtractionError(DownloaderError):
    """Raised when media metadata cannot be extracted."""


class MetadataBusyError(DownloaderError):
    """YouTube metadata admission is occupied or quarantined."""


class DownloadFailedError(DownloaderError):
    """Raised when downloading media fails."""


class DownloadTimeoutError(DownloadFailedError):
    """Raised when downloading exceeds the allowed time."""


class DownloadCleanupError(DownloadFailedError):
    """Owned native resources could not be safely released; quarantine workspace."""


class MetadataTimeoutError(MetadataExtractionError, TimeoutError):
    """The bounded YouTube metadata deadline expired."""


class MetadataCleanupError(MetadataExtractionError, DownloadCleanupError):
    """YouTube metadata ownership is unconfirmed; keep admission quarantined."""


class MediaProcessingError(DownloadFailedError):
    """Raised when downloaded media cannot be assembled or processed."""


class UnsupportedDownloadModeError(DownloaderError):
    """Raised when a provider cannot produce the requested output mode."""


class UnsupportedQualityError(DownloaderError):
    """Raised when a requested quality option is unavailable."""
