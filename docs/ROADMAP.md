# Roadmap

## Phase 0 - Foundation — done
GitHub repository, documentation, security baseline, Git workflow, test strategy, and AI-agent rules.
Gate: governance files exist, contain no secrets or personal data, and the repository history is reviewable.

## Phase 1 - Downloader Core — done
Transport-independent URL validation, provider detection, provider interface, download result model, temporary workspace, safe filenames, errors, logging, and tests.
Gate: core behavior is independently testable without Telegram.

## Phase 2 - YouTube Provider — done
The YouTube provider is implemented in the provider architecture. Real regular-video downloads succeeded in all three output modes, a live matrix passed for combined MP4, selected-quality video-only, and two audio containers, and Shorts smoke tests plus deterministic error-boundary/format-layout tests are recorded.
Evidence and limits are documented in TASKS.md and TESTING.md. Live matrix coverage is one regular public URL, not proof of broad reliability.

## Phase 3 - Telegram Functional MVP — done
The functional Telegram MVP is complete for the supported YouTube flow. It includes:

- Telegram bot entry point and aiogram polling setup;
- `/start`;
- text URL intake and supported-platform recognition;
- YouTube detection and download orchestration;
- transport-independent `DownloadService`;
- Telegram video delivery;
- Local Bot API integration;
- Telegram-compatible media preparation;
- H.264/AAC preference;
- compatible MP4 passthrough;
- verified stream-copy remux for compatible non-MP4 H.264/AAC input;
- transcode fallback for incompatible or failed remux output;
- rotation-aware width, height, and duration upload parameters;
- real Telegram delivery evidence through the Local Bot API Server;
- Dockerized yt-dlp with pinned Deno runtime for YouTube JavaScript challenge solving;
- containerized metadata/simulation evidence for the Deno-enabled runtime.

Gate: a core user can submit a supported YouTube URL and receive downloaded media in Telegram through the implemented flow.

This phase closure does not mean production readiness. It does not close restart/recovery, upload/network failure recovery, cloud/local operational rehearsal, larger-file limit work, repeatable E2E/deployment procedure, monitoring, resource limits, or broader reliability checks. Those are tracked in Phase 9, Production Reliability.

Instagram and TikTok remain recognition-only by default. Instagram has a separate explicit Telegram opt-in with narrow owner-confirmed Reel, single-post and three-video-album evidence; see Phase 5 below. The default downloader registry remains YouTube-only.

## Phase 4 - Download UX and YouTube Options
Expose useful provider/content capabilities through a polished Telegram interaction flow.
The primary capability design is [Phase 4 Capability Model](PHASE4_CAPABILITY_MODEL.md).

Core UX rule: minimum steps + provider-specific capabilities + consistent visual language.
The bot must not force identical options on every provider or add an extra click when
there is no meaningful choice.

Functional scope ACCEPTED on 2026-10-15 against main
`ced1200bf2a81a1bb63c200e6441e8458d0af0df`, using the existing Compose bot and Local Bot
API. Real Telegram validation confirmed the playlist-context watch URL, Video/Audio
choices, landscape Medium 936x720, portrait Medium 720x1280 and High 1080x1920, playable
image/sound, M4A playback/duration, callback protection and distinct-URL isolation.
Earlier Local Bot API validation also delivered a file above 50 MB. Evidence and its
limits are recorded in [TESTING.md](TESTING.md#phase-4-functional-acceptance-2026-10-15).

The application choice model, inline interaction state, safe quality mapping and media
delivery are accepted within that tested functional scope. This is not exhaustive format
coverage, acceptance of all original backlog items, or production readiness.

Remaining work retains the existing phase definitions:

- unchecked analytics design/implementation/validation items remain in Phase 4 TASKS.md;
  no analytics implementation or storage choice is implied by functional acceptance;
- copy, obsolete choice prompts, loading/progress and interaction polish remain Phase 8;
- HTTP 403 recovery, metadata/event-loop responsiveness, network/restart recovery and
  monitoring remain Phase 9, which is open;
- later usage evidence may justify simplifying options; no product policy changes here.

Target YouTube UX:

- first choice: `🎬 Видео` or `🎵 Аудио`;
- after Video: `Низкое`, `Среднее`, `Высокое`;
- Audio starts without additional quality selection unless later evidence justifies it;
- video-without-audio is not exposed as a normal user option.

Target Instagram UX:

- normally download video directly;
- no audio-only option by default;
- no quality-selection step unless a future provider proves useful selectable variants.

Target TikTok UX:

- direct video download by default;
- no unnecessary audio or quality screen.

For future platforms, UX derives from provider/content capabilities rather than a fixed
global options flow. Do not hard-code Instagram, TikTok, or other future-provider
capabilities before the provider spike proves what each platform/content type can
actually offer.

YouTube quality semantics:

- Low means lower bandwidth/resolution;
- Medium means approximately 720p class;
- High means approximately 1080p class or best reasonable Telegram-oriented quality;
- High must not mean unlimited 4K/8K automatically;
- final resolution selection should gracefully use the nearest useful available format.

Analytics should improve UX and technical decisions without collecting users' viewing
history. Track product and technical statistics, not source URLs, video titles,
channel/author names, Telegram usernames, message text, or unnecessary personal data.
Use pseudonymous or anonymous user identity sufficient for aggregate usage statistics.
Analytics must distinguish `option unavailable` from `option available but not selected`.
It should also distinguish technically available options hidden by product policy from
options shown to the user.

The current provider architecture already exposes modes and quality options. This phase
should connect those capabilities to Telegram UX, add only the capability modeling needed
for product choices, and avoid redesigning provider internals or creating a second
capability source of truth without evidence.

## Phase 5 - Instagram Provider — in progress

On 2026-10-16 the user initially authorized implementation after the previously conducted Gates
1–3C, limited to anonymous public individual Reels. The cached Gate 3C report confirms
metadata extraction/classification of one five-item `/p/` playlist only; the carousel is
out of scope and that report does not prove media acquisition or Telegram delivery.
Full Gates 1–3B reports were not available in the handoff used for this PR. The GO is an
explicit development scope decision, not a broad reliability verdict.

Merged PR #44 implements the `MediaProvider` contract, direct MP4 Reel acquisition, rejection
boundaries, explicit `DownloadService` injection and deterministic validation. It leaves
the default registry and Telegram activation unchanged.

The first real provider smoke failed before acquisition on incomplete metadata. After
PR #45, a separately authorized repeat passed for one public Reel on 2026-10-16:
13 formats, 3 admitted, one extraction and acquisition; MP4 H.264/AAC, 720x1280,
11.282041 seconds, 1,317,210 bytes, preparation passthrough and ffprobe/full decode PASS.
No Telegram upload was performed; this is not broad reliability evidence.

The user subsequently approved a broader Phase 5 scope: public Reels, ordinary public
single-video posts, and video-only selection from carousels. Photos are NEVER downloaded
or delivered. Single-video `/p/` results reuse the provider with offline validation.
The first carousel stage now provides guarded metadata inspection and immutable whole-
publication selection plans only. UNKNOWN, unavailable/unsupported videos and unreliable
identities block selection; only confirmed PHOTO entries can be excluded. Item-reference
URLs remain blocked. Bounded ordered acquisition is implemented separately with deterministic
validation and one bounded real three-video smoke; larger collections and Telegram
integration remain unverified.
Eventual video delivery uses ordered Telegram groups, splitting more than 10 videos;
a single remainder uses one video message. Never silently omit a selected video.

At that provider-only stage, real single-video `/p/` and Telegram delivery required
separate gates. Subsequent routing and narrow live acceptance are recorded below;
the default downloader registry remains YouTube-only.
PR #47 inspection and PR #48 PHOTO correction were independently reviewed and merged.
The final authorized metadata gate passed on one real 20-entry mixed publication:
17 VIDEO, 3 PHOTO (8/9/18), zero UNKNOWN, READY with ordered unique IDs and three direct
MP4 candidates per VIDEO. One extraction/three observed HTTP requests, zero acquisition.
The mixed-classification gate is closed for that case only.
PR #49 bounded acquisition was independently reviewed and merged. The user subsequently
approved silent video across Reels, single posts and carousel VIDEO entries. Admission,
compatibility ranking and actual carousel stream validation now allow optional audio;
no synthetic audio or conversion is added. Direct MP4/protocol/manifest/DRM guards and
resource limits remain. PR #50 was independently reviewed and merged. A separately
authorized production smoke then passed on one three-video carousel: 3/3 silent
H.264 MP4 files, 720x960, 1,961,198 bytes total, exact order, ffprobe PASS, no conversion
or Telegram calls. Only that small real-acquisition gate is closed.
PR #51 merged explicit optional-audio preparation and atomic derivative ownership;
existing callers keep the audio-required default. A separate reusable carousel
transport now has offline coverage for preparation-before-upload, ordered batches,
bounded resources and safe partial progress. No handlers/default routing were enabled.
PR #52 transport was independently reviewed and merged. A narrow Reel-only Telegram
integration is now implemented offline behind `INSTAGRAM_TELEGRAM_ENABLED=false`;
PRs #53/#54 are merged. The separately authorized bot-only deployment and one canonical
Reel delivery smoke passed; the user confirmed playback, orientation and sound.
The initial shared URL failed on the irrelevant `psln` query key. PR #55 subsequently
merged at `0a87beeaa8acb302b74e980946778608856b13f6` and was separately deployed.
The user confirmed full-share-link delivery, playback, orientation and sound;
size/time were not recorded. This is narrow Reel evidence, not `/p/`/album reliability.
That earlier fix stripped ordinary queries/harmless fragments, retained known item-selector
rejection and left carousel policy unchanged. No restart, environment change or live request is
part of that share-link implementation. Compose defaults false; APP_ENV=development
and the production guard remain unchanged. Larger-carousel acquisition and broad
reliability remain unverified; later narrow `/p/`/album acceptance is recorded below. Item-specific semantics remain
blocked pending separate validation; the installed extractor ignores `img_index`.
No running-stack rebuild/restart is authorized by this stage.
Merged PR #56 (`feat/instagram-post-carousel-telegram`) connects
public `/p/` URLs to positively inspected post/provider single-video download or existing
carousel inspection/acquisition and Telegram album transport, without changing the
YouTube flow or the production-only Settings guard. The route shares the current
Reel admission slot. Initial bounded carousel scope is at most 10 videos, 25 MiB
per source/upload file and 100 MiB total; oversize/unknown selections are blocked,
not truncated. The share-link follow-up aligns `/p/` query/fragment admission with Reels:
strip non-selector share data and block known encoded/case-varied item selectors before
extraction. Malformed references and the 32-field bound remain. PR #56 passed independent
review, merged at `20d14441a2b7ea906ed2a0abc83679d25d9f2d32` and was separately
deployed only to bot, with source/polling verification and unchanged Local Bot API.
The external three-video acquisition gate is not
proof of Telegram album playback. Before review corrections, GitHub Actions lint, formatting and offline/FFmpeg integration tests passed
(1277 passed, one optional external YouTube test skipped) before any real
album smoke. PR #57 subsequently passed independent review, merged at
`13da14d6f1ea9378d776543c94b22b7b716630d3`, passed post-merge CI #39151964361
and was separately deployed only to bot.
On 2026-10-18 the owner confirmed one full-link single-video `/p/` delivery with normal
playback and one previously rejected full-link three-video carousel arriving as one
ordered, playable, silent album. Single-post processing was subjectively sufficiently
fast; exact time was not measured. Only these two real user acceptance cases are closed.
Other publication shapes, mixed-media delivery, clients/devices, larger/multi-batch
albums, file-size boundaries, recovery, load and production capacity remain open.
See [the evidence and limits](TESTING.md#instagram-live-acceptance-2026-10-18).
Review corrections remove the UNSUPPORTED_CONTENT-to-single fallback: only explicit
available VIDEO evidence and coherent identity seed the single-file snapshot, and no
second extraction can override a block. Initial inspection uses the existing guard/event
and a shared operation deadline; slot/workspace ownership survives cancellation until
worker completion. Those corrections passed independent review before merge; the
share-link follow-up also passed review before the narrow live acceptance above.
The source-shape follow-up rejects present malformed carousel fields before
mapping and requires complete source-to-playlist count/identity/order preservation.
It added no downloader or metadata model; another independent review was required after
offline verification. That PR review/merge/deployment subsequently completed as recorded
above. The user's two initial post-deployment refusals
do not identify the exact URL parameters because the links were not supplied.
See [the scope and acceptance record](PHASE5_INSTAGRAM_REELS.md).

The general gated sequence remains:

Order:

1. technical spike;
2. real-world reliability assessment;
3. explicit Go/No-Go;
4. provider implementation only if viable;
5. deterministic and external validation;
6. integration into the common Telegram UX.

Where Instagram exposes meaningful format or quality choices, map them into the shared download-options model.

## Phase 6 - TikTok Provider
The previous yt-dlp harness remains in unmerged Draft PR #59 and is discontinued:
the final series stopped on unrecognized metadata HTML before any media GET.
Phase 6C prepares a separate native public-video CLI from main, using tt-dlp's
embed-state approach under MIT attribution. Offline synthetic HTTP/local-media
checks establish implementation boundaries only. The next gate is one separately
authorized A/B run proving complete MP4, actual streams, decode and existing media
preparation; metadata alone is not GO. No Telegram integration before that gate.
See [Phase 6C](PHASE6C_TIKTOK_NATIVE.md). No live request is part of preparation.

Use the same gated process as Instagram:

1. technical spike;
2. real-world reliability assessment;
3. explicit Go/No-Go;
4. provider implementation only if viable;
5. deterministic and external validation;
6. Telegram UX integration.

## Phase 7 - Additional Social Platforms
Evaluate other popular services one by one. Do not promise universal platform support.

Candidates should be selected later based on:

- user demand;
- technical feasibility;
- legal and platform restrictions;
- extraction reliability;
- maintenance burden.

Each platform requires its own technical spike and Go/No-Go gate before implementation. Do not hard-code a long unsupported platform list into product claims.

## Phase 8 - Unified Product UX
Polish the complete downloader experience after multiple providers exist.

Include:

- consistent Telegram UI;
- inline keyboards;
- provider-independent mode and quality presentation;
- all bot messages, including removing or updating obsolete video/audio choice prompts
  after selection when their inline buttons disappear;
- loading and waiting messages;
- success messages;
- unsupported-content messages;
- retry and error states;
- provider-specific exceptions only where necessary;
- consistent naming and button copy;
- final interaction-flow review.

Goal: the bot should feel like one coherent service rather than several provider integrations.

## Phase 9 - Production Reliability
Complete the operational and reliability work that is intentionally not part of the functional MVP gate.

Status: OPEN. Phase 4 functional acceptance does not satisfy this reliability gate.

Include:

- bot restart and recovery;
- Local Bot API restart and recovery;
- temporary network/API failure behavior;
- intermittent YouTube HTTP 403 diagnosis and a narrowly bounded recovery strategy,
  with explicit limits and no duplicate downloads/uploads;
- upload failures;
- repeatable deployment and E2E procedure;
- resource observations;
- disk and temporary-file cleanup behavior;
- concurrency and load assessment;
- remove synchronous metadata extraction/planning from the async event loop and verify
  that slow inspection does not block other Telegram callbacks;
- rate limits when justified;
- queues and workers only if measured workload requires them;
- monitoring and observability;
- deployment automation where justified;
- backup and recovery procedures where relevant;
- large-file behavior and actual limits;
- strategy for files exceeding Telegram Bot API delivery limits.

For media above Telegram delivery limits, the current design direction is a possible external temporary object-storage/download-link fallback. Do not implement or commit to S3, R2, or any storage provider until this phase has a demonstrated requirement and design decision. Do not claim support for files above 2 GB.

## Phase 10 - Monetization and Access Control
Access restrictions and monetization are deferred until the project has a useful, working multi-platform downloader product worth monetizing.

Investigate and design:

- Telegram community membership gate;
- advertising gateway;
- optional paid/free models if desired later;
- other monetization mechanisms;
- access restrictions required by the chosen model.

Current product decision: membership is not required during core product development. Advertising must remain modular and must not be coupled into provider implementations.
