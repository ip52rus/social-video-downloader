# Social Video Downloader

Free Telegram-first downloader for supported public YouTube, Instagram and ordinary TikTok media.

## Project status — deployed on HOSTKEY VPS

**Deployed, not pre-launch.** The Telegram bot [@GetThatVideo_bot](https://t.me/GetThatVideo_bot) is running on HOSTKEY VPS under Docker Compose with an internal Local Telegram Bot API Server. The last saved P9-R4 technical postflight was **PASS on 2026-10-31 at 08:23:43 UTC**, source `1df3fc129c6880555bc021cbbade74c6ce1fe14a` (merged [PR #89](https://github.com/ip52rus/social-video-downloader/pull/89), [post-merge CI SUCCESS](https://github.com/ip52rus/social-video-downloader/actions/runs/41067317374)), image `sha256:f93a3f497ad23761397f557bb849b73eff85e8c57665c9efad8b40d244aedde3` (linux/amd64). Previous image and rollback tag are retained. One poller, bot/API RUNNING, restart 0/OOM false were recorded; MacBook bot/API containers remain stopped. **This is a dated checkpoint, not a fresh 2026-11-03 server-health check.**

**Limits:** Phase 8 MVP accepted with documented limitations; Phase 9C locally accepted (owner 5/5); Phase 9 reliability remains OPEN. P9-R2 LIVE concurrency responsiveness is INCONCLUSIVE. P9-R4 did not perform Telegram LIVE downloads/uploads. The YouTube metadata/snapshot production root cause remains UNKNOWN. P9-R5f proved a conflict in the *private offline diagnostic guard*, not a production fix. P9-R5g offline hardening was authorized, but no result is recorded at this checkpoint. No claim of broad platform reliability or near-2 GB support.

**Deployed runtime:** yt-dlp `2026.10.26`, Python `3.13.18`, Deno `2.9.7`, yt-dlp-ejs `0.8.0`, aiogram `3.31.0`, FFmpeg/ffprobe `7.1.5`. Instagram and TikTok routes are enabled on the VPS; the source defaults are opt-in. VPS working capacity is one request, diagnostics are off. `APP_ENV=development` is an intentional application setting required by the existing Instagram guard, **not** a claim that the VPS is a development server.

See [P9-R4 deployment record](docs/LOCAL_BOT_API.md#p9-r4-deployment-checkpoint--2026-10-31), [current evidence](docs/TESTING.md#current-deployment-and-investigation-checkpoint--2026-11-03), [scope](docs/PROJECT.md), [roadmap](docs/ROADMAP.md) and [tasks](docs/TASKS.md). The [2026-10-29 handoff](docs/CHAT_HANDOFF_2026-10-29.md) is a historical checkpoint. TikTok Short Drama is [deferred research](docs/research/TIKTOK_SHORT_DRAMA.md), not a supported route.

### Earlier functional evidence (historical)

The downloader core and YouTube provider are implemented, and the YouTube validation gate has passed within the documented test scope. Phase 3 (Telegram Functional MVP) is complete: the bot accepts supported YouTube URLs, downloads YouTube media, prepares Telegram-compatible video when necessary, and sends it as a video message. Automated tests cover deterministic download orchestration, media preparation, error handling, and cleanup. A real Telegram flow through the Local Bot API Server has been verified with a short video and an MP4 file of approximately 414.7 MB; the large file arrived in Telegram and was confirmed to open and play. Telegram documents a Local Bot API Server upload ceiling of 2000 MB, but this project does not claim validated 2 GB support. The current evidence is limited to the tested scenario, not all file sizes, codecs, clients, or deployment conditions. See [the changelog](CHANGELOG.md) and [testing strategy](docs/TESTING.md) for the recorded evidence and its limits. By default in source configuration, Instagram and TikTok URLs remain recognition-only; both routes are enabled on the HOSTKEY VPS per the dated P9-R4 checkpoint. Instagram remains opt-in: real Reel delivery and, on 2026-10-18 after PR #57, one full-link single-video `/p/` and one ordered three-video silent Telegram album were owner-confirmed with normal playback. This limited acceptance does not establish broad reliability; the downloader registry remains YouTube-only by default. See [Phase 5 scope](docs/PHASE5_INSTAGRAM_REELS.md).

Phase 4 functional scope is **ACCEPTED (2026-10-15)**: playlist-context watch links,
Video/Audio choices, recorded landscape/portrait quality selections, M4A playback and
duration, callback protection and distinct-URL isolation were validated in a real
Telegram client. See [the evidence and limits](docs/TESTING.md#phase-4-functional-acceptance-2026-10-15).

Functional MVP acceptance is not general production reliability. Phase 8 MVP is
accepted; any broader polish is deferred backlog. Phase 9B fixed initial metadata/
planning event-loop blocking within its tested contract; actual LIVE concurrency
responsiveness remains INCONCLUSIVE. Intermittent YouTube HTTP 403, network/restart
recovery, load and monitoring remain open in Phase 9. Analytics and additional platform providers are
not implied by functional acceptance. Access restrictions and monetization remain
deferred. See [the roadmap](docs/ROADMAP.md) and [task checklist](docs/TASKS.md).

## Local startup

Do not start this command with the production token while HOSTKEY polls. Use a
separately authorized test bot for development; the retained MacBook stack is rollback,
not a second active deployment.

Use Python 3.13 and uv. Install dependencies with uv sync, set TELEGRAM_BOT_TOKEN in your environment, then run:

    uv run python -m social_video_downloader

The bot responds to /start. Send a public YouTube video URL, choose Video or Audio when
offered, and select an available video quality if needed. Video uses Telegram-compatible
MP4 preparation; audio is delivered as verified M4A/AAC with reliable duration when
available. Instagram and TikTok are recognition-only by default. A disabled-by-default Instagram Reel and public /p/ post/carousel opt-in
is documented in [Phase 5](docs/PHASE5_INSTAGRAM_REELS.md). With merged PR #56, `/p/`
requires positive public-video evidence or a complete READY carousel plan; blocked or
ambiguous metadata never triggers a single-video fallback. PR #57's merged and deployed
share-link fix accepts irrelevant query keys/bare flags and harmless anchors while
blocking known item selectors. On 2026-10-18 the owner confirmed one full-link single
post and one ordered three-video silent album with normal Telegram playback. This is
[narrow user acceptance](docs/TESTING.md#instagram-live-acceptance-2026-10-18), not broad
publication, device, file-size or production-capacity validation.

TikTok public-video delivery is an explicit opt-in: set
`TIKTOK_TELEGRAM_ENABLED=true` to admit any Telegram user, including with
`APP_ENV=production`. No test-user allowlist is required. Default capacity is two
TikTok operations per bot process and one per user; set
`TIKTOK_MAX_CONCURRENT_OPERATIONS` to an integer 1–8 to adjust the process limit.
Saturated requests receive a busy response without queuing. Full public video URLs
and HTTPS share links on exact `vm.tiktok.com` / `vt.tiktok.com` hosts are supported.
Short references must contain one alphanumeric path token without query or fragment;
redirects resolve only inside the admitted supervised operation. Separate streams and
retries remain unsupported. This is not a production-readiness or deployment approval.
Phase 6H passed one full-link live case; Phase 6I passed one owner-authorized `vm`
short-link delivery/playback case. `vt` remains offline-only; broader mobile-link
coverage, high-load reliability and general TikTok availability are unverified. See
[Phase 6I limits and next gate](docs/PHASE6I_TIKTOK_SHORT_LINKS.md).

Optional settings are
APP_ENV (development, test, or production), LOG_LEVEL (DEBUG, INFO, WARNING, ERROR, or
CRITICAL), TELEGRAM_API_BASE_URL, and TELEGRAM_API_TIMEOUT_SECONDS. Never commit the real
token or put it in logs.

## Telegram Bot API endpoint

By default, the bot uses Telegram's cloud Bot API. To point it at a separately running Local Bot API Server, set `TELEGRAM_API_BASE_URL` to its private base URL, for example `http://127.0.0.1:8081`. When this setting is present, the client enables aiogram's local-server mode. Leave it unset to use the cloud API.

Local API requests use a configurable timeout of 1800 seconds by default. Set `TELEGRAM_API_TIMEOUT_SECONDS` to an integer from 1 to 86400 if your deployment needs a different request timeout. This setting is applied only when a custom/local API endpoint is configured; the cloud Bot API retains aiogram's default session behavior.

The repository includes a Docker Compose configuration for the bot and Local Bot API Server. The bot image includes pinned Deno for yt-dlp YouTube JavaScript challenge support. See [the setup and rollout notes](docs/LOCAL_BOT_API.md) before using Compose. The Compose configuration requires `TELEGRAM_BOT_TOKEN`, `TELEGRAM_API_ID`, and `TELEGRAM_API_HASH` in the local environment or `.env` file. Never commit `.env`. Do not expose an unauthenticated Bot API endpoint to the public internet.

## Verification status

The current evidence covers automated tests, a limited live YouTube provider matrix, containerized metadata/simulation validation for the bot image, and real Telegram delivery through the Local Bot API Server. These are separate verification categories. VPS deployment is confirmed technically at the dated P9-R4 checkpoint, while broader Phase 9 reliability acceptance remains open. Still outstanding are additional Telegram client checks, failure and recovery scenarios, restart and rollback rehearsal, and justified larger-file testing. A successful upload of a 414.7 MB file does not establish support for files up to 2 GB.
