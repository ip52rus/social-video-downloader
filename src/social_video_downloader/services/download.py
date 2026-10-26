"""Application service for selecting providers and downloading media."""

from collections.abc import Iterable
from pathlib import Path

from social_video_downloader.domain.errors import UnsupportedPlatformError
from social_video_downloader.domain.models import DownloadedMedia, DownloadOptions
from social_video_downloader.domain.urls import detect_platform, normalize_media_url
from social_video_downloader.providers.base import MediaProvider
from social_video_downloader.providers.youtube import YouTubeProvider
from social_video_downloader.services.choice_model import ChoicePlan, build_choice_plan
from social_video_downloader.services.youtube_metadata import YouTubeMetadata

_YOUTUBE_METADATA = YouTubeMetadata()


class DownloadService:
    """Route validated media URLs to the provider that can download them."""

    def __init__(self, providers: Iterable[MediaProvider] | None = None) -> None:
        selected_providers = providers if providers is not None else (YouTubeProvider(),)
        self._providers = {provider.platform: provider for provider in selected_providers}
        self._youtube_metadata = _YOUTUBE_METADATA

    async def create_choice_plan_async(self, url: str) -> ChoicePlan:
        """Bound Telegram YouTube inspection without changing the synchronous core API."""
        normalized_url, provider = self._provider_for_url(url)
        if not isinstance(provider, YouTubeProvider):
            raise UnsupportedPlatformError("Async metadata is available only for YouTube.")
        return await self._youtube_metadata.plan(provider, normalized_url)

    def _provider_for_url(self, url: str) -> tuple[str, MediaProvider]:
        """Normalize a URL and return the configured provider for its platform."""
        normalized_url = normalize_media_url(url)
        platform = detect_platform(normalized_url)
        provider = self._providers.get(platform)

        if provider is None:
            raise UnsupportedPlatformError(
                f"No download provider is configured for platform '{platform.value}'."
            )

        return normalized_url, provider

    def create_choice_plan(self, url: str) -> ChoicePlan:
        """Build an actionable application-level choice plan for a media URL."""
        normalized_url, provider = self._provider_for_url(url)
        return build_choice_plan(provider, normalized_url)

    async def download_bounded(self, url, output_dir, options, limits):
        """Run the existing YouTube engine under an explicit owned write boundary."""
        from social_video_downloader.infrastructure.youtube_bounded import acquire

        normalized, provider = self._provider_for_url(url)
        if not isinstance(provider, YouTubeProvider):
            raise UnsupportedPlatformError("Bounded acquisition is a YouTube path.")
        return await acquire(provider, normalized, output_dir, options, limits)

    def download(
        self,
        url: str,
        output_dir: Path,
        options: DownloadOptions | None = None,
    ) -> DownloadedMedia:
        """Normalize a URL, select its provider, and download the requested media."""
        normalized_url, provider = self._provider_for_url(url)
        return provider.download(normalized_url, output_dir, options)
