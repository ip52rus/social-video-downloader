# Architecture

## Target logical architecture
Telegram -> Telegram handlers -> application/download service -> provider interface -> provider implementation -> media engine -> temporary storage.

## Runtime and deployment

Current runtime path:

Telegram user -> bot container/process -> aiogram -> application `DownloadService` -> `YouTubeProvider` -> yt-dlp with yt-dlp-ejs and pinned Deno runtime for YouTube JavaScript challenge solving -> FFmpeg / ffprobe -> Telegram Bot API endpoint.

By default, the bot uses Telegram's cloud Bot API endpoint. Setting `TELEGRAM_API_BASE_URL` switches the client to the configured cloud-compatible or local endpoint. When this variable is present, the bot constructs aiogram's local API server configuration with `TelegramAPIServer.from_base(..., is_local=True)` and uses the configured request timeout.

In the current Docker Compose local mode:

bot -> private Compose network -> `telegram-bot-api:8081` -> Telegram infrastructure.

The `telegram-bot-api` service stores its working state and data in a named volume. The Compose setup uses the service DNS name `telegram-bot-api` and the internal base URL `http://telegram-bot-api:8081`; the Local Bot API endpoint is not published externally by default and should remain private unless an explicit secured deployment requires otherwise.

## Configuration and startup
Environment-based settings are validated before starting the application. The Telegram token is required, excluded from the settings representation, and must never be written to logs. The package entry point is python -m social_video_downloader; it configures standard-library logging, creates an aiogram bot and dispatcher, registers the Telegram router, and starts polling. Bot session cleanup runs when polling stops.

## Telegram layer
The aiogram router owns commands and text intake, user-facing validation responses, and result delivery. It does not contain provider-specific download logic. Membership/access control is deferred to a future monetization or business-model layer and is not part of the current implementation. The /start response describes current platform support. Text messages are validated against supported platform domains. YouTube URLs are passed to the application service; Instagram and TikTok URLs are recognized but receive an explicit message that downloading is not yet available.

Future option UX is capability-driven. Telegram should show only meaningful choices for
the current platform/content and keep a consistent visual language without forcing every
provider into the same option tree. YouTube is expected to expose Video/Audio and
video-quality choices in Phase 4; Instagram and TikTok should normally use direct video
download unless future provider evidence proves useful selectable variants.

The synchronous download and media-preparation operations run in worker threads so yt-dlp and FFmpeg do not block the aiogram event loop. Before delivery, the Telegram layer probes media with ffprobe and prepares the downloaded media through this pipeline:

1. MP4 files already containing H.264 video and AAC audio pass through unchanged, without an FFmpeg re-encode.
2. Non-MP4 files with compatible H.264/AAC streams attempt an FFmpeg stream-copy remux to MP4. The remuxed output is re-probed, and the bot uses it only when the resulting container and codecs verify as Telegram-compatible.
3. Files with incompatible codecs, failed remuxes, or remuxed output that does not verify fall back to the existing FFmpeg transcode path, producing H.264/AAC MP4 and verifying the result.
4. Telegram upload parameters, including duration and dimensions, continue to be derived with ffprobe from the prepared file.

The remux path is an optimization for compatible streams when only the container needs conversion; it is not a claim that all media can be remuxed. The transcode path remains the compatibility fallback. No scaling filter is applied, and FFmpeg autorotation is retained. The bot sends the prepared file as a Telegram video with streaming support. A per-request temporary directory holds the media while Telegram uploads it, and is removed after delivery or failure. Telegram upload errors and expected downloader errors are mapped to safe user-facing messages; detailed source exceptions are not sent to the user.

## Application layer
DownloadService normalizes the URL, detects its platform, selects a registered MediaProvider, and returns the provider's transport-neutral DownloadedMedia result. The default registry contains the YouTube provider. A recognized platform without a registered provider raises a domain-level UnsupportedPlatformError. The service does not depend on Telegram.

Future product analytics should be owned by the Telegram/application flow, not by
providers. Conceptually:

Telegram/application flow -> analytics events -> analytics storage.

Analytics events should support product, UX, content-characteristic, and technical
statistics while avoiding source URLs, video titles, channel/author names, Telegram
usernames, message text, and unnecessary personal data. The event model must distinguish
`option unavailable` from `option available but not selected`. Initial storage may later
be SQLite if a separate implementation design confirms it is sufficient, but no database,
event table, external analytics SaaS, queue, or other analytics infrastructure exists in
the current architecture.

## Provider layer
Each provider owns URL recognition, metadata retrieval, media acquisition, and provider-specific quirks.

The YouTube provider delegates extraction to yt-dlp. For YouTube JavaScript challenge
solving, yt-dlp uses yt-dlp-ejs and the pinned Deno runtime provided by the bot Docker
image. This runtime support is separate from provider logic, FFmpeg media processing,
and Telegram Bot API transport.

Providers report which output modes are supported: video with audio, video only, and audio only. They also expose selectable quality options when the platform allows them to be enumerated. Quality identifiers are provider-specific and opaque to the application and Telegram layers; each option also has a user-facing label.

Provider capabilities are technical inputs, not a command to expose every possible mode
to users. The Telegram/application layer decides which supported capabilities are
meaningful product choices for the current provider/content. For example, YouTube
video-only remains a provider capability but is not planned as a normal user-facing
option in Phase 4.

A missing quality selection means automatic selection of the best available quality. If a provider cannot enumerate quality options, it may return an empty list, but it must still use the best available quality for an automatic download. Providers reject unsupported output modes and invalid quality identifiers through domain errors.

## Media engine
Responsible for download and media assembly. The first implementation uses yt-dlp and FFmpeg where appropriate.

## Evolution
The initial implementation may run in one process. Queues, workers, persistent storage, and distributed deployment are introduced only when measured requirements justify them.
