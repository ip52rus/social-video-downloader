"""Application logging configuration."""

import logging

from social_video_downloader.config import Settings


def configure_logging(settings: Settings) -> None:
    """Configure standard-library logging using validated application settings."""
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
