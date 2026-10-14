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

Phase 4 should use the existing provider contract as the minimum capability model rather
than introduce a second independent capability system. Providers expose technical
capabilities for a specific URL through `get_supported_modes(url)` and
`get_available_qualities(url, mode)`, using the existing `DownloadMode` and
`QualityOption` types. The Telegram/application layer applies product policy on top of
those technical capabilities and decides which choices are useful enough to show. The
primary design reference is [Phase 4 Capability Model](PHASE4_CAPABILITY_MODEL.md).

For YouTube, the provider may technically report `VIDEO_WITH_AUDIO`, `VIDEO_ONLY`,
`AUDIO_ONLY`, and multiple quality options. The normal user-facing policy is `Видео` and
`Аудио`; `VIDEO_ONLY` is hidden from the ordinary flow; quality selection is offered only
for `Видео`. For future Instagram and TikTok providers, do not hard-code capabilities
before the provider spike. If a provider/content combination only has normal video and no
meaningful quality alternatives, Telegram should start the download directly without
audio or quality screens.

The Telegram interaction flow uses a small in-memory pending-interaction store and
callback-data helpers for mode and quality buttons. Callback data contains only a
versioned action, a short opaque interaction ID, and a choice index; it does not contain
source URLs, titles, authors, or provider format details. Pending interactions are owned
by user and chat, expire lazily after a short TTL, and are consumed atomically before a
terminal download starts so double-clicks cannot launch duplicate downloads. Bot restart
makes pending buttons stale; persistent recovery and multi-instance coordination are
deferred to production reliability work.

After successful atomic terminal consumption, callback acknowledgement and keyboard
cleanup are best-effort Telegram operations: expected `TelegramAPIError` failures are
logged by operation and exception class without preventing the one selected download.
The stored URL and `DownloadOptions` remain authoritative; neither policy nor media
upload is retried. Cancellation and unrelated programming errors still propagate.
For nonterminal mode-to-quality transitions, acknowledgement failure does not prevent
the keyboard edit. An edit failure retains the unconsumed quality state because Telegram
may have applied the edit before losing the response; an old mode button can retry the
same transition. Domain download-error notifications are also best-effort, preserving
the original domain error category when the notification fails.

The synchronous download and media-preparation operations run in worker threads so yt-dlp and FFmpeg do not block the aiogram event loop. Before delivery, the Telegram layer probes media with ffprobe and prepares the downloaded media through this pipeline:

1. MP4 files already containing H.264 video and AAC audio pass through unchanged, without an FFmpeg re-encode.
2. Non-MP4 files with compatible H.264/AAC streams attempt an FFmpeg stream-copy remux to MP4. The remuxed output is re-probed, and the bot uses it only when the resulting container and codecs verify as Telegram-compatible.
3. Files with incompatible codecs, failed remuxes, or remuxed output that does not verify fall back to the existing FFmpeg transcode path, producing H.264/AAC MP4 and verifying the result.
4. Telegram upload parameters, including duration and dimensions, continue to be derived with ffprobe from the prepared file.

The remux path is an optimization for compatible streams when only the container needs conversion; it is not a claim that all media can be remuxed. The transcode path remains the compatibility fallback. No scaling filter is applied, and FFmpeg autorotation is retained. The bot sends the prepared file as a Telegram video with streaming support. A per-request temporary directory holds the media while Telegram uploads it, and is removed after delivery or failure. Telegram upload errors and expected downloader errors are mapped to safe user-facing messages; detailed source exceptions are not sent to the user.

### Audio compatibility

Normal Telegram audio delivery requires verified AAC in M4A because the previous
automatic `ba` selection could deliver WebM and leave duration unspecified. Source
selection remains in the YouTube provider; a small `telegram_audio` helper alongside
the video helper prepares transport-compatible audio without changing provider
contracts or the video pipeline.

- Automatic AUDIO_ONLY selection uses `ba[ext=m4a][acodec~='^(mp4a|aac)']/ba`: yt-dlp
  ranks the matching native AAC/M4A formats rather than using a fixed format ID. Best
  audio remains the fallback. Explicit provider quality IDs retain their semantics;
  video selectors are unchanged. The provider may return a source WebM on fallback,
  but the Telegram handler never sends it without audio preparation.
- One input ffprobe checks the actual container, codec and streams. A native M4A with
  one AAC audio stream and no video is reused unchanged, with no FFmpeg invocation.
- AAC in another container first attempts `-c:a copy` into M4A. The result is re-probed;
  a failed or unverifiable remux falls back to AAC encoding. Incompatible codecs go
  directly to AAC encoding. Every converted output is checked for M4A/AAC and audio-only
  streams; invalid output causes a safe `MediaProcessingError`, never an extension-only
  or incompatible fallback upload.
- Encoding uses at most 128 kbps (64 kbps for mono), capped at a known source bitrate.
  Unknown source bitrate uses that default; it does not imply restored source quality.
  Transcoding is lossy and adds CPU/latency; native passthrough and stream-copy avoid it.
- Reliable positive finite `MediaMetadata.duration_seconds` takes precedence for
  `answer_audio(duration=...)`. Otherwise duration is read in the existing codec/container
  probes: final output first, then source/container or audio-stream duration. Seconds
  are rounded to a positive Telegram integer; unknown/invalid values are omitted.
  Reliable metadata skips duration fields, and no separate duration-only probe runs.

Preparation runs in the existing worker-thread path. Partial failed conversions are
removed and all source/output files remain inside the per-request temporary workspace.
Passthrough introduces no media copy; remux/transcode create only their necessary output.
This adds no queues, persistence, dependencies, audio-format screen, or upload retries.
Real Telegram client revalidation is outstanding; Phase 4/production reliability remain
open.

## Application layer
DownloadService normalizes the URL, detects its platform, selects a registered MediaProvider, and returns the provider's transport-neutral DownloadedMedia result. The default registry contains the YouTube provider. A recognized platform without a registered provider raises a domain-level UnsupportedPlatformError. The service does not depend on Telegram.

`DownloadService.create_choice_plan(url)` reuses the same normalization and provider
selection path to build an immutable application-level choice plan before any Telegram UI
is rendered. The plan maps provider capabilities into product choices with concrete
`DownloadOptions` for every terminal path. It hides `VIDEO_ONLY` from normal product UX,
uses the Low/Medium/High tier foundation for video quality choices, preserves exact
provider `quality_id` values when a quality screen is skipped, and blocks unsafe
unclassifiable video-quality mappings rather than treating provider automatic/best as
product High.

The choice model uses the existing provider contract and keeps provider `quality_id`
values opaque. It does not call Telegram APIs, duplicate provider extraction logic, or
invent a parallel source of truth for platform capabilities. Future Telegram flow code
should render the plan and pass its stored `DownloadOptions` back to
`DownloadService.download()`.

Future product analytics should be owned by the Telegram/application flow, not by
providers. Conceptually:

Telegram/application flow -> analytics events -> analytics storage.

Analytics events should support product, UX, content-characteristic, and technical
statistics while avoiding source URLs, video titles, channel/author names, Telegram
usernames, message text, and unnecessary personal data. The event model must distinguish
`option unavailable`, `option available but hidden by product policy`, and
`option available but not selected`. Initial storage may later be SQLite if a separate
implementation design confirms it is sufficient, but no database, event table, external
analytics SaaS, queue, or other analytics infrastructure exists in the current
architecture.

## Provider layer
Each provider owns URL recognition, metadata retrieval, media acquisition, and provider-specific quirks.

The YouTube provider delegates extraction to yt-dlp. For YouTube JavaScript challenge
solving, yt-dlp uses yt-dlp-ejs and the pinned Deno runtime provided by the bot Docker
image. This runtime support is separate from provider logic, FFmpeg media processing,
and Telegram Bot API transport.

Providers report which output modes are supported: video with audio, video only, and audio only. They also expose selectable quality options when the platform allows them to be enumerated. Quality identifiers are provider-specific and opaque to the application and Telegram layers; each option also has a user-facing label. Video quality options may include both `width` and `height` so application policy can classify resolution consistently across landscape, portrait, and square videos.

Provider capabilities are technical inputs, not a command to expose every possible mode
to users. The Telegram/application layer decides which supported capabilities are
meaningful product choices for the current provider/content. For example, YouTube
video-only remains a provider capability but is not planned as a normal user-facing
option in Phase 4.

This distinction keeps providers focused on factual extraction capability. Product/UX
policy belongs above the provider layer and may vary by platform, content type, and
evidence from real usage.

A missing quality selection means automatic selection of the best available quality. If a provider cannot enumerate quality options, it may return an empty list, but it must still use the best available quality for an automatic download. Providers reject unsupported output modes and invalid quality identifiers through domain errors.

## Media engine
Responsible for download and media assembly. The first implementation uses yt-dlp and FFmpeg where appropriate.

## Evolution
The initial implementation may run in one process. Queues, workers, persistent storage, and distributed deployment are introduced only when measured requirements justify them.
