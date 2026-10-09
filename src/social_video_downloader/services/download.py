"""Application service for selecting providers and downloading media."""

from collections.abc import Iterable
from pathlib import Path

from social_video_downloader.domain.errors import UnsupportedPlatformError
from social_video_downloader.domain.models import DownloadedMedia, DownloadOptions
from social_video_downloader.domain.urls import detect_platform, normalize_media_url
from social_video_downloader.providers.base import MediaProvider
from social_video_downloader.providers.youtube import YouTubeProvider


class DownloadService:
    """Route validated media URLs to the provider that can download them."""

    def __init__(self, providers: Iterable[MediaProvider] | None = None) -> None:
        selected_providers = providers if providers is not None else (YouTubeProvider(),)
        self._providers = {provider.platform: provider for provider in selected_providers}

    def download(
        self,
        url: str,
        output_dir: Path,
        options: DownloadOptions | None = None,
    ) -> DownloadedMedia:
        """Normalize a URL, select its provider, and download the requested media."""
        normalized_url = normalize_media_url(url)
        platform = detect_platform(normalized_url)
        provider = self._providers.get(platform)

        if provider is None:
            raise UnsupportedPlatformError(
                f"No download provider is configured for platform '{platform.value}'."
            )

        return provider.download(normalized_url, output_dir, options)
