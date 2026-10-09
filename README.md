# Social Video Downloader

Free Telegram bot-service for downloading media from popular social platforms.

## Project status

The downloader core and YouTube provider are implemented, and the YouTube validation gate has passed with documented limits. Phase 3 (Telegram MVP) is in progress: the bot recognizes supported URLs, can download individual YouTube videos through the existing provider, and attempts to send the resulting file in Telegram. Deterministic tests and CI for this flow are being validated; a real Telegram test-bot end-to-end run remains outstanding. Instagram and TikTok links are recognized but their download providers are not implemented.

The project is not production-ready. Telegram community-membership access control is a separate planned Phase 4. See [the roadmap](docs/ROADMAP.md), [task checklist](docs/TASKS.md), and [testing strategy](docs/TESTING.md).

## Local startup

Use Python 3.13 and uv. Install dependencies with uv sync, set TELEGRAM_BOT_TOKEN in your environment, then run:

    uv run python -m social_video_downloader

The bot responds to /start. Send a public YouTube video URL to start a download; the bot sends the resulting file if both download and Telegram upload succeed. Instagram and TikTok are currently recognition-only. Optional settings are APP_ENV (development, test, or production) and LOG_LEVEL (DEBUG, INFO, WARNING, ERROR, or CRITICAL). Never commit the real token or put it in logs.

## Verification status

Automated tests use mocked providers and Telegram message methods; they do not prove that a live Telegram upload succeeds. Complete the test-bot end-to-end check before treating the Telegram MVP acceptance gate as passed.
