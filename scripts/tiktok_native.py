"""Compatibility CLI for the shared native engine; no Telegram startup."""

import sys

from social_video_downloader.infrastructure import tiktok_native as engine

if __name__ == "__main__":
    raise SystemExit(engine.main())
else:
    # Preserve existing offline fault injection/imports without a second engine.
    sys.modules[__name__] = engine
