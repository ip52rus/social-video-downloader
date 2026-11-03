# Technology Baseline
## Current deployed runtime — 2026-11-03 (from saved P9-R4)

**Deployed, not pre-launch.** The Telegram bot [@GetThatVideo_bot](https://t.me/GetThatVideo_bot) is running on HOSTKEY VPS under Docker Compose with an internal Local Telegram Bot API Server. The last saved P9-R4 technical postflight was **PASS on 2026-10-31 at 08:23:43 UTC**, source `1df3fc129c6880555bc021cbbade74c6ce1fe14a` (merged [PR #89](https://github.com/ip52rus/social-video-downloader/pull/89), [post-merge CI SUCCESS](https://github.com/ip52rus/social-video-downloader/actions/runs/41067317374)), image `sha256:f93a3f497ad23761397f557bb849b73eff85e8c57665c9efad8b40d244aedde3` (linux/amd64). Previous image and rollback tag are retained. One poller, bot/API RUNNING, restart 0/OOM false were recorded; MacBook bot/API containers remain stopped. **This is a dated checkpoint, not a fresh 2026-11-03 server-health check.**

Runtime verified on the deployed Linux image: Python 3.13.18, yt-dlp 2026.10.26, yt-dlp-ejs 0.8.0, Deno 2.9.7, aiogram 3.31.0, aiohttp 3.14.4, FFmpeg/ffprobe 7.1.5. Docker Compose runs the bot and internal Local Telegram Bot API on HOSTKEY; the MacBook containers are stopped. The following 2026-10-29 section is retained as a historical architecture checkpoint.


## Deployment checkpoint — 2026-10-29

The same Python/Compose architecture is deployed on HOSTKEY VPS with one bot poller
and an internal Local Bot API; MacBook containers are retained stopped for rollback.
The dated [operations record](LOCAL_BOT_API.md#hostkey-vps-checkpoint-2026-10-28)
is the deployment authority, not the older local-setup terminology below. No fresh
D1 runtime observation. Ordinary TikTok uses the native protected transport, not
yt-dlp; Instagram and YouTube retain their provider engines. Gettext/Babel with
aiogram I18n supplies package-local EN/RU/ES catalogs. POSIX workers and bounded IPC
provide metadata/acquisition isolation; no browser/Go service or queue is deployed.
FFmpeg conversion fallback described below applies to the compatible existing
YouTube pipeline, not a new transcode policy for Instagram or TikTok.


## Runtime

- Python 3.13.
- uv manages the project environment, dependencies, and lockfile.
- The project uses a src/ layout.

## Application

- aiogram 3.x is the Telegram framework.
- yt-dlp is the initial media acquisition engine.
- The project uses `yt-dlp[default]` with yt-dlp-ejs support. Deno is the JavaScript
  runtime used by yt-dlp for YouTube challenge solving.
- ffprobe is used to inspect media streams, container, duration, dimensions, and upload
  parameters.
- FFmpeg is required where downloaded video and audio streams must be assembled, where
  compatible H.264/AAC streams need stream-copy remuxing to MP4, or where incompatible
  media must be transcoded to a Telegram-compatible H.264/AAC MP4.
- FFmpeg stream-copy remux is used as an optimization when the streams are already
  compatible and only container conversion is needed.
- FFmpeg H.264/AAC transcoding remains the compatibility fallback when streams are
  incompatible or a remux fails or does not verify.

## Local runtime and deployment

- Docker is used to build a bot image with Python dependencies, FFmpeg/ffprobe, and
  pinned Deno 2.9.7.
- Docker Compose is used for the local bot + Local Telegram Bot API Server setup.
- Telegram Local Bot API Server can be used as an optional Bot API endpoint for larger
  upload workflows.
- The bot image intentionally installs Deno only as the supported JavaScript runtime for
  yt-dlp YouTube challenge solving. Node, Bun, and QuickJS are not intentionally
  installed.

## Development quality

- pytest for tests.
- pytest-asyncio for asynchronous tests.
- Ruff for linting and formatting.
- GitHub Actions for CI.

## Dependency policy

Dependencies are declared in pyproject.toml and resolved into uv.lock.
Application dependencies are kept separate from development-only dependencies.
Version ranges are bounded to prevent accidental major-version migrations.

## Architecture policy

The Telegram framework is an adapter, not the downloader core.
Provider-specific behavior must remain behind provider interfaces.
Infrastructure such as Redis, queues, object storage, or distributed workers is not part of the initial baseline; it requires a measured requirement and an explicit architectural change.
