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

Instagram and TikTok URLs remain recognition-only in the bot. An experimental Instagram Reel provider exists for explicit injection; default registration and Telegram integration remain pending.

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

On 2026-10-16 the user authorized implementation after the previously conducted Gates
1–3C, limited to anonymous public individual Reels. The cached Gate 3C report confirms
metadata extraction/classification of one five-item `/p/` playlist only; the carousel is
out of scope and that report does not prove media acquisition or Telegram delivery.
Full Gates 1–3B reports were not available in the handoff used for this PR. The GO is an
explicit development scope decision, not a broad reliability verdict.

Merged PR #44 implements the `MediaProvider` contract, direct MP4 Reel acquisition, rejection
boundaries, explicit `DownloadService` injection and deterministic validation. It leaves
the default registry and Telegram activation unchanged. Real Instagram downloads and
Telegram end-to-end checks remain outstanding for this implementation.

The first real provider smoke failed before acquisition and reported incomplete codec/
dimension metadata. Offline reproduction confirmed an overly strict direct-MP4 admission
rule, now corrected and verified locally; success on the real Reel is still unverified.

Next: separately authorize a bounded real provider smoke with the correction. Successful
acquisition must precede a focused PR for default registration, Telegram direct-download
routing/messages and scoped external/client acceptance.
No running-stack rebuild/restart is authorized by this stage.
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
