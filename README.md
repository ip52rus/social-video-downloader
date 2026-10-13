# Social Video Downloader

Free Telegram bot-service for downloading media from popular social platforms.

## Project status

The downloader core and YouTube provider are implemented, and the YouTube validation gate has passed within the documented test scope. Phase 3 (Telegram Functional MVP) is complete: the bot accepts supported YouTube URLs, downloads YouTube media, prepares Telegram-compatible video when necessary, and sends it as a video message. Automated tests cover deterministic download orchestration, media preparation, error handling, and cleanup. A real Telegram flow through the Local Bot API Server has been verified with a short video and an MP4 file of approximately 414.7 MB; the large file arrived in Telegram and was confirmed to open and play. Telegram documents a Local Bot API Server upload ceiling of 2000 MB, but this project does not claim validated 2 GB support. The current evidence is limited to the tested scenario, not all file sizes, codecs, clients, or deployment conditions. See [the changelog](CHANGELOG.md) and [testing strategy](docs/TESTING.md) for the recorded evidence and its limits. Instagram and TikTok URLs are recognized, but download providers for those platforms are not implemented.

The project is not production-ready. Next work focuses on Telegram download UX/options and additional platform providers. Access restrictions and monetization are intentionally deferred until the downloader product has broader useful functionality. See [the roadmap](docs/ROADMAP.md), [task checklist](docs/TASKS.md), and [testing strategy](docs/TESTING.md).

## Local startup

Use Python 3.13 and uv. Install dependencies with uv sync, set TELEGRAM_BOT_TOKEN in your environment, then run:

    uv run python -m social_video_downloader

The bot responds to /start. Send a public YouTube video URL to start a download; the bot prepares a Telegram-friendly H.264/AAC MP4 when needed and sends it as a video if download and upload succeed. Instagram and TikTok are currently recognition-only. Optional settings are APP_ENV (development, test, or production), LOG_LEVEL (DEBUG, INFO, WARNING, ERROR, or CRITICAL), TELEGRAM_API_BASE_URL, and TELEGRAM_API_TIMEOUT_SECONDS. Never commit the real token or put it in logs.

## Telegram Bot API endpoint

By default, the bot uses Telegram's cloud Bot API. To point it at a separately running Local Bot API Server, set `TELEGRAM_API_BASE_URL` to its private base URL, for example `http://127.0.0.1:8081`. When this setting is present, the client enables aiogram's local-server mode. Leave it unset to use the cloud API.

Local API requests use a configurable timeout of 1800 seconds by default. Set `TELEGRAM_API_TIMEOUT_SECONDS` to an integer from 1 to 86400 if your deployment needs a different request timeout. This setting is applied only when a custom/local API endpoint is configured; the cloud Bot API retains aiogram's default session behavior.

The repository includes a Docker Compose configuration for the bot and Local Bot API Server. The bot image includes pinned Deno for yt-dlp YouTube JavaScript challenge support. See [the setup and rollout notes](docs/LOCAL_BOT_API.md) before using Compose. The Compose configuration requires `TELEGRAM_BOT_TOKEN`, `TELEGRAM_API_ID`, and `TELEGRAM_API_HASH` in the local environment or `.env` file. Never commit `.env`. Do not expose an unauthenticated Bot API endpoint to the public internet.

## Verification status

The current evidence covers automated tests, a limited live YouTube provider matrix, containerized metadata/simulation validation for the bot image, and real Telegram delivery through the Local Bot API Server. These are separate verification categories and do not establish full production readiness. Still outstanding are additional Telegram client checks, failure and recovery scenarios, restart and rollback rehearsal, and justified larger-file testing. A successful upload of a 414.7 MB file does not establish support for files up to 2 GB.
