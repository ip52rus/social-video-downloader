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

The aiogram router owns commands and text intake, user-facing validation responses, and result delivery. It does not contain provider-specific download logic. Membership/access control is deferred to a future monetization or business-model layer and is not part of the current implementation. The /start response describes current platform support. Text messages are validated against supported platform domains. By default, YouTube URLs are passed to the application service; Instagram and TikTok URLs receive an explicit not-connected response. Merged PR #56 adds an explicit Instagram opt-in delegating `/reel/` to the established Reel flow and `/p/` to positively inspected single-video or complete video-carousel flows. Both share one admission slot. PR #56 was separately deployed with bot-only startup/polling verification; real `/p/` Telegram delivery and albums remain unverified. The subsequent share-link correction is offline-only pending its own review and deployment.

The implemented option UX is capability-driven. Telegram shows only meaningful choices for
the current platform/content and keeps a consistent visual language without forcing every
provider into the same option tree. YouTube exposes Video/Audio and video-quality
choices; Instagram and TikTok should normally use direct video
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

### Historical Reel-only opt-in MVP design

The original Reel-only stage reused `InstagramProvider`, `DownloadedMedia` and the
existing optional-audio helper/sendVideo path. A dispatcher-owned Reel handler is
enabled only by `INSTAGRAM_TELEGRAM_ENABLED=true` (default false). It validates raw
reference intent before canonicalization and rejects `/p/`; no carousel integration
or default registry change is included. Reel share queries (including `psln`, `utm_*`
and other irrelevant keys) and harmless fragments are stripped. Known selectors
`img_index`, `media_id`, `item_id`, `carousel_index`, `index` and `slide` remain blocked
case-insensitively in query keys and selector-shaped fragments. Only the provider's
validated HTTPS/www canonical Reel URL reaches acquisition. Carousel query policy is
unchanged. A single active operation owns its worker and
temporary files until the worker really exits, including after cancellation. Scoped
yt-dlp invocation controls bound received media bytes; cooperative deadline checks and
socket timeouts are not a hard thread-termination guarantee. Preparation uses the
existing runner injection with subprocess timeouts and a POSIX per-file write backstop.
Compose passes `INSTAGRAM_TELEGRAM_ENABLED` only to bot with an absent-value default
of false. Its existing `APP_ENV=development` and Local Bot API endpoint are unchanged;
the Settings guard against enabled+production remains. After PR #54, the separately
authorized bot-only deployment and one canonical-Reel smoke succeeded; the user confirmed
delivery, playback, orientation and sound. The original share URL was blocked by `psln`
before acquisition. PR #55 subsequently merged at
`0a87beeaa8acb302b74e980946778608856b13f6` and was separately deployed; the user
confirmed full-share-link delivery, playback, orientation and sound. Size/time were
not recorded. No new deployment occurs in PR #56. One Reel does not establish `/p/`
or album delivery or general production reliability.

### Optional-audio preparation design

Optional-audio preparation design: extend the existing video helper with the explicit
keyword-only `allow_silent=False` flag. Existing callers continue requiring audio;
only opt-in callers may prepare video-only files. Use actual ffprobe container/stream
facts for passthrough and output validation, conditionally map existing audio, and
reuse the current stream-copy/transcode settings. No provider or transport routing
change, new pipeline, or synthetic audio is required.

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
Real Telegram client M4A playback/duration and the recorded video/callback flows are
functionally ACCEPTED as of 2026-10-15; see
[the evidence and limits](TESTING.md#phase-4-functional-acceptance-2026-10-15).
This changes validation status only. Live fault recovery, broader format/client coverage,
and Phase 9 production reliability remain open; obsolete choice-prompt cleanup is Phase 8.

### Offline carousel delivery design

Offline carousel delivery design: a separate Telegram infrastructure component consumes
`DownloadedCarousel` plus the original READY selection plan and an approved request
workspace. The plan supplies expected identities/positions absent from the acquired
result; comparison checks completeness without extraction or reselection. Preparation
runs in a killable POSIX process with private same-filesystem hard-link aliases, existing
optional-audio preparation and bounded FFmpeg output. Only a fully validated prepared
collection crosses the upload barrier. Injected Telegram sends are sequential and
nontransactional; uncertain responses stop subsequent batches without retries. No live
routing/handler or downloader contract changes are required.

## Application layer

DownloadService normalizes the URL, detects its platform, selects a registered MediaProvider, and returns the provider's transport-neutral DownloadedMedia result. The default registry contains the YouTube provider. The experimental `InstagramProvider` can be explicitly injected for development/testing; default registration and Telegram activation are deferred to a separate integration stage. A recognized platform without a registered provider raises a domain-level UnsupportedPlatformError. The service does not depend on Telegram.

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

Individual YouTube `/watch` URLs with playlist context are canonicalized inside the
provider before inspection, cache lookup, and download. For a single valid 11-character
`v` plus `list`, the provider removes `list` and normalizes the video parameter while
preserving unrelated query parameters. This avoids yt-dlp's unprocessed `_type=url`
redirect being mistaken for missing capabilities with `process=False`. Context URLs
with missing, malformed, or duplicate video IDs and playlist-only URLs are rejected
before extraction. Global URL normalization, `noplaylist=True`, `process=False`,
quality selection, and provider/application responsibilities remain unchanged; no
generic redirect resolver or playlist processing is introduced.

Providers report which output modes are supported: video with audio, video only, and audio only. They also expose selectable quality options when the platform allows them to be enumerated. Quality identifiers are provider-specific and opaque to the application and Telegram layers; each option also has a user-facing label. Video quality options may include both `width` and `height` so application policy can classify resolution consistently across landscape, portrait, and square videos.

Provider capabilities are technical inputs, not a command to expose every possible mode
to users. The Telegram/application layer decides which supported capabilities are
meaningful product choices for the current provider/content. For example, YouTube
video-only remains a provider capability but is not planned as a normal user-facing
option in Phase 4.

This distinction keeps providers focused on factual extraction capability. Product/UX
policy belongs above the provider layer and may vary by platform, content type, and
evidence from real usage.

YouTube video requires a concrete provider quality ID: an empty/unclassifiable quality
list must not become automatic/best. The application admits only fully dimensioned
YouTube options with `min(width, height) <= 1080`; otherwise it retains an independent
audio-only route or blocks video. `classify_quality` still records partial dimensions
as `SINGLE_DIMENSION`, but those options are not actionable YouTube video choices.
Future non-YouTube providers retain their own automatic behavior when qualities are absent.

Reason for the provider correction: the former `height-H` identity merged distinct
widths, and height ceilings could admit a higher short-side class than the chosen tier.
Video IDs now identify dimension pairs (`video-WxH`), with partial dimensions represented
explicitly. All video selector alternatives require the selected exact width and height,
including codec/container fallbacks; partial or absent dimensions and missing video
quality IDs fail safely. Codec ranking and audio pairing remain yt-dlp responsibilities,
with the existing H.264/MP4/AAC preferences. No provider contract or download engine is
added, and the provider does not recompute product tiers or enforce their policy ceiling.
Video-with-audio quality discovery requires either a combined stream at that size or
a separate audio stream that can be paired with it; video-only facts remain independent.
Guarantees depend on correct source metadata; they do not prove the actual encoded
dimensions, file size, or upstream format availability without media validation.

### Experimental Instagram Reel provider

Reason for this addition: the user authorized a narrow Phase 5 implementation after
Gates 1–3C, while retaining the one-file `DownloadedMedia` contract. No new capability
model, downloader engine, transport pipeline or infrastructure is needed.

`InstagramProvider` implements `MediaProvider` for anonymous individual `/reel/<id>/`
and `/p/<id>/` URLs on the explicit Instagram host allowlist. It canonicalizes to
HTTPS/www without tracking parameters, preserves the path kind in cache identity, and
pins extraction to the Instagram extractor. URL acceptance alone does not establish
content type: only a top-level single-video result with admissible formats is accepted.
Stories, profiles, photos, collections, redirect results, private/auth-gated results and
unsupported formats fail before media acquisition. Any result containing `entries`,
including a one-entry playlist, is rejected without recursively processing or downloading
its entries. `noplaylist=True` does not replace this validation or select a carousel item.

The provider admits only direct HTTP(S) MP4 candidates without explicit video
absence or a DRM marker. Explicitly audio-free (`acodec="none"`) video is now eligible
under the approved silent-Instagram product policy; missing audio metadata stays unknown.
Instagram `video_versions` may omit dimensions and codecs;
these fields remain unknown and are not prerequisites for direct-MP4 admission.
Before acquisition, yt-dlp's `determine_protocol` checks the effective protocol,
including URL-derived detection when protocol metadata is
missing. Manifest URLs (including a misleading HTTP/MP4 label), fragment data and DASH
representation markers are rejected. Signed direct MP4 locators need not end in `.mp4`
when the extractor supplies that extension. DASH/HLS assembly and separate audio-only/
video-only user routes remain outside this scope. The legacy `VIDEO_WITH_AUDIO` enum names
Instagram's normal video route, not a requirement that every Instagram file contain audio.
Missing dimensions/codecs are not proof of actual streams. Carousel acquisition probes
actual MP4 video and optional audio; normal single-video acquisition retains its existing
output-file checks. Telegram preparation requires audio by default; explicit
`allow_silent=True` permits video-only preparation. Instagram routing remains disabled
until a separate transport integration. No synthetic
audio or conversion merely because audio is absent is introduced.

The yt-dlp selector yields exactly one admitted format. It first prefers metadata-confirmed
H.264/AAC, then incomplete codec metadata with no already-known incompatible codec, then
other admitted MP4 codecs. Silent H.264 or unknown-video candidates enter the compatible/
incomplete group rather than being treated as an incompatible audio codec. Within each
group, candidates without explicit silence (including UNKNOWN audio) precede explicit
`acodec="none"`, then yt-dlp's native quality ordering is retained. This does not label
UNKNOWN as confirmed audio. Compatibility still wins across groups: silent H.264 may
beat VP9/AAC, preserving the video-codec compatibility priority. A higher-resolution
VP9 or unknown-audio option cannot displace an available confirmed H.264/AAC option. Selection does not retry another format after acquisition
failure; actual file compatibility still requires the existing media preparation checks.

A small bounded, 180-second inspection cache shares one validated snapshot between mode
inspection, quality inspection and download. Download consumes the snapshot; expiry
requires fresh inspection. The provider exposes only normal video and no quality menu,
so explicit injection into `DownloadService` produces `DIRECT_DOWNLOAD` using the
existing choice model. Unknown quality IDs and other modes fail before extraction.

Metadata extraction uses `download=False, process=False`; only the validated single-video
snapshot is passed to yt-dlp processing. Acquisition uses a fixed filename in the existing
request workspace, checks for exactly one nonempty regular file (rejecting symlinks and
extra outputs), and publishes a generated safe filename without trusting source titles
or IDs as filesystem paths. The workspace is removed on success or failure. Duration is
optional; real upload parameters remain the responsibility of the existing ffprobe path.
Posts without a title use the neutral `Instagram Video` fallback; Reel fallback titles
and filenames retain their existing label. Both use generated filenames, not source titles.
No cookies, credentials, persistent extractor cache or application retry loop is configured;
yt-dlp extraction/download/fragment retries are zero and socket timeout is 20 seconds.
This is not a whole-request deadline or a guarantee of one HTTP request: extractor internals
may make multiple requests. Raw yt-dlp log messages are suppressed to avoid exposing
source URLs or account data; domain errors retain safe public messages.

The default provider registry, Telegram handlers and running deployment remain YouTube-only.
After PR #45 corrected incomplete-metadata admission, one public Reel passed a real
provider/service smoke on 2026-10-16: one extraction/acquisition, H.264/AAC MP4,
720x1280, 11.282041 seconds and 1,317,210 bytes. Existing preparation used passthrough;
ffprobe and full FFmpeg decoding passed. There was no Telegram upload. This evidence
predates the `/p/` extension; real single-video `/p/` acquisition and all Instagram
Telegram end-to-end delivery remain unverified.

The approved carousel scope is VIDEO ONLY: never acquire or deliver photos. Eventual
video delivery preserves original order, splits more than 10 videos into sequential
Telegram groups and sends a single remainder as one video. A selected video must never
be silently omitted. Bounded carousel acquisition is a separate explicit operation;
an explicit offline-tested media-group component is described below. Live routing
remains disabled and the single-file contract stays intact.
See [the accepted plan and evidence boundary](PHASE5_INSTAGRAM_REELS.md).

### Carousel inspection design decision

Carousel planning needs source type evidence that yt-dlp discards. A per-instance
Instagram extractor subclass preserves only immutable type/identity evidence, with
guards on source shape, entry count and ID mapping. It is registered only for the
explicit carousel inspection call; no global patch or second extraction is used.
The provider returns a bounded cached inspection; a separate application service
builds an immutable ordered selection plan. Neither result contains transport objects
or signed media locators. READY describes metadata selection only; it does not execute acquisition.
Single-file provider/download contracts, registry and Telegram routing stay unchanged.

`InstagramProvider.inspect_carousel` accepts canonical publication identities only.
`InstagramCarouselService.create_selection_plan` validates URL intent first: known
item-reference candidates (including `img_index`) are BLOCKED before extraction/cache
lookup. The follow-up share-link correction reuses the Reel guard: non-selector query
keys, bare share flags and harmless fragments share the provider's canonical cache key.
Malformed references and more than 32 query fields remain blocked. No index semantics
are guessed; raw tracking data never reaches the provider.

VIDEO requires positive video evidence; malformed/conflicting type markers give UNKNOWN.
PHOTO requires `is_video=False`, `GraphImage`, or strictly integer `media_type=1`,
corroborating `image_versions2.candidates` and no video evidence or malformed/conflicting
type fields. Numeric `media_type` alone, empty formats and thumbnails cannot establish
PHOTO. A successful numeric contribution is recorded as `media_type_photo` in evidence.
The added combination follows one real 20-entry publication's source metadata diagnosis;
its corrected selection behavior subsequently passed the separately authorized live gate
for that one publication (see the Phase 5 evidence record).
Missing/duplicate/unverifiable IDs, mapping shape/order changes, unavailable content,
UNKNOWN or a VIDEO without admitted direct MP4 formats block the entire selection.
Only positively classified PHOTO entries may be excluded. No count-based truncation occurs.
Plans preserve all valid source positions/IDs, contain tuples/frozen values and no media
URLs. Unsupported reference plans have unknown entry count and no extraction. Facts use
a separate bounded 180-second cache, retaining no raw payloads or signed locators.
Expiry re-inspects; identities are coherent within a snapshot, not guaranteed across time.
The existing MP4 admission filter is reused. Metadata-only planning does not select/acquire a format;
codec preference for single-file acquisition is unchanged. Acquisition verifies actual streams.

## Media engine
Responsible for download and media assembly. The first implementation uses yt-dlp and FFmpeg where appropriate.

## Evolution
The initial implementation may run in one process. Queues, workers, persistent storage, and distributed deployment are introduced only when measured requirements justify them.

### Ordered carousel acquisition design decision

A separate explicit async acquisition service retains the single-file contracts.
A short-lived child process is necessary to enforce a whole-operation deadline and
cancellation even during blocking yt-dlp extraction/network reads. This is not a queue
or persistent worker. Current source and dependencies are reused; no Telegram transport
runs in the child. Fresh carousel metadata must match every planned identity, position
and classification before processing any selected video. A bounded response reader
limits actual media bytes before writes; ffprobe will verify actual video/audio.
All staged files belong to one isolated workspace; failure/cancellation removes the
workspace before returning. Successful output ownership transfers to the caller only
when the complete ordered collection is returned. No media transformation is included.


`InstagramCarouselAcquisition.acquire(plan, output_dir)` returns a frozen
`DownloadedCarousel` with an ordered tuple of `DownloadedCarouselVideo` (original position,
stable item ID, existing `DownloadedMedia`), aggregate count/bytes and canonical publication
identity. Signed locators and extractor account/title data never enter the collection.
Only complete READY whole-publication plans are accepted; item-reference URLs, forged
partial selections and count-limit overflow fail before launching the child.

The child always performs exactly one fresh metadata extraction, ignoring the facts cache
for media locators. The existing instance-local adapter rechecks source/mapped identity.
All original positions, IDs, types and the selected video set must still match, and every
selected child must remain admissible before the first download. A changed publication
requires a new plan; no silent reselection. Only these children enter yt-dlp processing,
sequentially, using the existing direct MP4 selector and H.264/AAC priority. No parent
playlist processing, photos, retries, separate streams, remux or transcoding is allowed.

Adjustable `CarouselAcquisitionLimits` defaults: 25 selected videos, 100 MiB/file,
500 MiB total received media bytes, 512 MiB temporary logical media-file bytes and 600 s
for the operation. These are conservative implementation guardrails, not measured capacity
or the old 25 MiB live-smoke ceiling. Insufficient free disk rejects acquisition.
The response reader caps each read before a write and counts actual bytes independent of
Content-Length; yt-dlp max_filesize and POSIX RLIMIT_FSIZE provide additional safeguards.
At an exhausted unknown-length stream budget the operation fails closed, even if EOF might
follow exactly at that boundary. Logical media limits exclude filesystem bookkeeping and
metadata/process memory; no physical disk quota or aggregate multi-operation capacity is claimed.

The POSIX-only short-lived child has a separate process group. The parent terminates and
reaps it (including ffprobe) on timeout/cancellation before workspace cleanup; repeated
cancellation still waits for cleanup and propagates cancellation. ffprobe reuses the
existing reader, scans packets with network protocols disabled, and requires actual MP4,
recognized video codecs and positive video dimensions. Audio is optional, but every
present audio stream must have a recognized nonempty codec. Probe errors, audio-only
files, wrong containers and unknown/invalid stream codecs fail;
this does not promise full decoding, Telegram codec compatibility or playback.

Files are staged under a private temporary workspace inside the caller's output directory.
After all files validate, exclusive generated-name hard links publish the collection without
copies or overwrites. No result is returned until all publication steps succeed. Failures
and cancellation remove staged and already published owned names; unrelated files remain.
Success removes staging names and transfers ownership of returned files to the caller,
which must delete them when finished. This is caller-result atomicity, not a filesystem-wide
transaction or crash/power-loss recovery. Hard-link support on the output filesystem is
required. Default registry, YouTube, normal single-file paths and Telegram handlers are unchanged.


### Silent Instagram policy and transport boundary

The user explicitly approved silent MP4 videos for Reels, single-video `/p/` posts and
carousel VIDEO entries after one separate anonymous metadata diagnostic of a three-video
publication. All three source items had boolean `has_audio=False`; upstream mapping
preserved three structural direct HTTPS MP4 candidates per item with `acodec="none"`.
Those nine direct candidates failed only the former audio-absence predicate; 23 further
manifest-derived formats failed audio and fragment-marker checks (32 formats total).
No candidate loss in mapping was observed. One extraction/three metadata HTTP requests,
zero acquisition: these facts do not establish actual stream contents or playback.

Only the Instagram audio-absence policy is changed. Locator, explicit video absence,
manifest/fragment/protocol/DRM checks, collection identities, deadlines, byte limits and
publication cleanup remain in force. A separately authorized three-video live acquisition
passed at main `055fced0bdf337a5b04132600cc803321db59c80`: three ordered silent H.264
MP4 files, 720x960, 1,961,198 bytes total, ffprobe PASS; no conversion or Telegram calls.
This closes only that bounded three-video acquisition gate, not larger-carousel reliability.

`prepare_telegram_video(path, runner=None, *, allow_silent=False)` preserves the
audio-required default used by existing YouTube handlers. Opt-in permits H.264 silent
MP4 passthrough without changing bytes or orientation metadata, compatible stream-copy
remux and video-only H.264 conversion when necessary. AAC audio is retained/produced
when audio exists; silent sources have no audio mapping and never gain a track.
Actual container, valid stream codecs and positive video dimensions are probed locally;
output checks require MP4/H.264 and preserve source audio presence. Failed derivatives
are removed; existing destination files are not overwritten. Preparation uses a private
staging directory beside the destination so FFmpeg's `-y` only touches owned files.
After validation, exclusive same-filesystem `os.link` publication retains the existing
derivative name and atomically fails on any destination collision. Hard-link support is
required; failure is safe, with no overwrite/copy fallback. Only staging paths are cleaned;
the destination is never unlinked by preparation. A successful link transfers the final
file to the caller, whose request workspace owns its lifetime. Upload metadata remains
video-derived. Callers own successful derivatives inside their request workspace.
PR #51, including the P2 ownership correction, was independently reviewed and merged.
Future Instagram callers must explicitly opt in; existing handlers/routing are unchanged.
The separate carousel transport below opts in without activating live delivery.
Local generated fixtures verify preparation, not real Telegram delivery or playback.


### Explicit offline carousel Telegram transport

`TelegramCarouselDelivery(sender, limits=None).deliver(collection, *, plan, workspace,
chat_id)` consumes acquired videos and the original READY whole-publication plan. It
compares all selected positions/IDs and requires complete, unique ordered inputs; PHOTO
entries are never given to preparation. No extractor, acquisition or sender is constructed.
The injected sender implements the installed aiogram `send_video`/`send_media_group` API.

The preparation barrier validates regular nonempty source files inside the caller-owned
approved local workspace (no symlink traversal or duplicate file identities). A private
workspace contains hard-link aliases; originals are never transformed or deleted. One
short-lived POSIX process runs existing `prepare_telegram_video(..., allow_silent=True)`
and real local ffprobe. All outputs require MP4/H.264, optional AAC and positive video
dimensions. Video-derived upload parameters and actual `InputMediaVideo`/`FSInputFile`
objects for the whole collection exist before the first send. H.264 MP4 passthrough
preserves bytes; incompatible containers/codecs use the existing helper and settings.

Configurable per-operation defaults: 25 videos, 50,000,000 bytes per upload file,
200 MiB aggregate upload, 1 GiB logical workspace bytes, 2048 workspace entries,
180 seconds preparation and 120 seconds per Telegram send. The workspace count includes
all caller originals, unrelated regular files, aliases, derivatives and FFmpeg staging;
hard links count once per inode. Sequential FFmpeg output inherits a POSIX per-file limit
bounded by the remaining upload/workspace budgets; cap exhaustion fails, never silently
returns a shortened movie. An independent async deadline kills/reaps the preparation
process group before cleanup, including on repeated cancellation. This requires local
same-filesystem hard links and exclusive caller ownership for the operation's lifetime.
These are adjustable initial limits, not product-wide acquisition limits, physical disk
quotas, global memory/concurrency enforcement or validated production capacity.

Batch sizes follow ordered slices of 10: singleton uses sendVideo, 2–10 use sendMediaGroup;
11 -> 10+1, 12 -> 10+2, 20 -> 10+10, 21 -> 10+10+1, 25 -> 10+10+5. Streaming support and
probed dimensions/duration are supplied; captions are omitted. Calls are strictly awaited.
Responses require the expected number of video Messages, unique message IDs, matching
numeric chat targets and coherent distinct album IDs. Any send error, timeout or malformed
response stops subsequent batches without retry. Confirmed positions remain confirmed;
the current batch is uncertain. `CarouselDeliveryError.progress` and cancellation progress
expose positions/counts only; final user communication/recovery belongs to the caller.
Telegram batches are not transactional: earlier confirmed sends are not rolled back, and
callers must not blindly replay the collection after an ambiguous result.

Private aliases, derivatives and staging are removed after success/failure/cancellation;
caller originals and unrelated existing files remain. The caller eventually removes its
acquired outputs. Live handlers/YouTube/default registration remain unchanged. Only the
prior real three-video acquisition is verified externally; real album upload/playback,
larger carousels and broad Instagram reliability remain NOT VERIFIED.

## Opt-in /p/ Telegram integration (PR #56)

Post-share correction design: reuse the Reel query/fragment intent rule through a
small transport-independent helper in the existing domain URL module. Validate the
host/path with InstagramProvider first, reject known item selectors before stripping
the raw reference, and pass only the provider's canonical URL to inspection. Unknown
non-selector tracking keys, bare share flags and ordinary anchors must not block a
whole publication. Keep the 32-field bound and malformed-reference rejection; no
metadata, selection, acquisition or transport contract changes are needed.
The shared helper decodes selector names, including repeated escaping, and matches
case-insensitively. Malformed percent escapes and empty query names fail closed in
both paths; correctly escaped literal percent signs remain ordinary share data.

Source-shape correction design: validate the presence and complete list structure of
`carousel_media` in the instance-local extractor adapter before yt-dlp can filter it.
An absent field permits ordinary single-video inspection; a present malformed value
or inconsistent mapped collection must produce the existing INVALID_METADATA result,
never permission for a single-video path. Reuse the existing guarded playlist/count
representation and source-to-mapped identity checks, without a new metadata model or
handler-side reconstruction. A present null, non-list, invalid member or nested
collection is rejected before calling the upstream mapper. Valid collections must
map to a playlist of equal length, with matching item identities and order; otherwise
the adapter returns an incomplete guarded playlist consumed as INVALID_METADATA.
Known original list counts remain available even on rejection. Empty collections
remain blocked as NO_VIDEOS. Single-post cache, format and cancellation rules stay unchanged.

Immutable-source correction: keeping the original list by reference is insufficient
if an upstream mapper mutates it in place. Before mapping, retain only a tuple of
existing frozen ItemEvidence values (ordered source/mapped IDs, kind, signals and
availability), the original count and parent availability. Compare mapped entries
against those initial facts, never against the possibly mutated source list. This
adds no parallel classifier or raw-payload copy; mapper fault injection is offline
contract testing, not observed mutation by unmodified yt-dlp or a live exploit.

Review correction design: a generic BLOCKED issue cannot prove a single video.
Reuse the instance-local adapter's ItemEvidence and existing MediaMetadata as the
positive single-post result of a narrow provider/service inspection operation.
Only a verified public VIDEO with stable source/mapped identity and direct formats
may seed the existing single-file inspection cache. Acquisition consumes that same
snapshot; blocked metadata never triggers a second interpretation. No domain model,
downloader or transport layer is added. The initial inspection shares the existing
cooperative guard/event and a deadline starting before extraction; asynchronous
carousel stages consume the remaining budget while retaining their cleanup semantics.

Merged PR #56 (`feat/instagram-post-carousel-telegram`) adds a separate
Telegram `InstagramPostHandler` behind the existing `InstagramReelHandler`
and unchanged opt-in flag, sharing one `_active` admission slot per dispatcher.
The main transport-independent carousel contracts remain unchanged.
`InstagramCarouselService.inspect_publication` checks raw `/p/` query intent before
calling `InstagramProvider.inspect_post` through the existing guarded adapter.
An existing `MediaMetadata` result positively identifies a single video: source
ItemEvidence must be VIDEO, available and identity-consistent, with admissible
formats and no parent access/DRM conflict. Missing evidence fails closed. The same
provider's bounded inspection cache supplies the single-file worker; no second
extraction can reinterpret a blocked source. Every BLOCKED plan fails closed.
READY carousel plans pass to `InstagramCarouselAcquisition`
and then `TelegramCarouselDelivery`, with caller-owned temporary workspace
cleanup, sender obtained from the current Telegram Message, and safe partial
delivery feedback (no retry).

The experimental route deliberately narrows the reusable components' defaults:
10 selected videos, 25 MiB source and upload file, 100 MiB total acquisition
and upload, 130 MiB acquisition temporary budget and 400 MiB logical delivery
workspace budget. This is per operation, not a physical disk quota or measured
concurrent system capacity. Photos are excluded only when positively classified;
unknown items and over-budget publications fail instead of being shortened.
One cooperative guard/event starts before initial metadata extraction. The existing
300-second carousel operation window now covers inspection, acquisition, preparation
and delivery; acquisition receives only the remaining time. Single-post work retains
its 180-second cap from the same start, with up to 120 seconds for sending inside the
original 300-second window. Preparation/send stage caps are also retained. Timeout or
cancellation prevents subsequent metadata opens and later media stages, but cannot
force-stop an already blocked native/network call. The executor slot/workspace stays
owned until the worker exits; existing subprocess stages retain kill/reap cleanup.
If the common deadline interrupts an upload, the transport's confirmed/uncertain
progress survives; no retry or false pre-delivery-failure claim is introduced.
Before these review corrections, GitHub Actions with FFmpeg/ffprobe passed 1277 offline tests (one external
YouTube test opt-in skipped), plus Ruff lint/format. The real Telegram album
and broader client playback gates are pending. Final independent review passed at
`219e1bfcc134e80be24bb8565f6dfc18dae77c21`; merge commit
`20d14441a2b7ea906ed2a0abc83679d25d9f2d32` was separately deployed by replacing
only bot. All 88 checked image paths matched main, polling started, and Local Bot API
was unchanged. This is technical deployment evidence, not live `/p/`/album acceptance.
The current share-link correction makes no additional deployment or environment change.
