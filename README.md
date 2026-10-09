# Social Video Downloader

Free Telegram bot-service for downloading media from popular social platforms.

## Project status

The downloader core and YouTube provider are implemented, and the YouTube validation gate has passed with documented limits. Phase 3 (Telegram MVP) is in progress: validated configuration, application logging, and a minimal aiogram polling entry point are in place. User-facing handlers, download orchestration, and result delivery are not yet implemented.

The project is not production-ready. Telegram community-membership access control is a separate planned Phase 4. See [the roadmap](docs/ROADMAP.md), [task checklist](docs/TASKS.md), and [testing strategy](docs/TESTING.md).

## Local startup

Use Python 3.13 and uv. Install the project dependencies with uv sync, set TELEGRAM_BOT_TOKEN in your environment, then run:

    uv run python -m social_video_downloader

Optional settings are APP_ENV (development, test, or production) and LOG_LEVEL (DEBUG, INFO, WARNING, ERROR, or CRITICAL). The current entry point starts polling but does not yet respond to user messages. Never commit the real token or put it in logs.
