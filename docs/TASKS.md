# Task Decomposition

## Phase 0 - Foundation — done
- [x] Create GitHub repository.
- [x] Establish README.
- [x] Establish AGENTS.md.
- [x] Establish Git ignore and environment example.
- [x] Document product definition.
- [x] Document architecture.
- [x] Document roadmap.
- [x] Document security, development, and testing policies.
- [x] Add CI.
- [x] Add dependency management.

## Phase 1 - Downloader Core — done
- [x] Define domain models.
- [x] Define provider interface.
- [x] Define platform-independent download modes and quality options.
- [x] Extend provider contract for mode and quality discovery.
- [x] Implement URL normalization.
- [x] Implement platform detection.
- [x] Implement safe filename generation.
- [x] Implement temporary workspace lifecycle.
- [x] Define error taxonomy.
- [x] Add unit tests for models, errors, provider contract, URL handling, filenames, and workspace lifecycle.
- [x] Add integration harness.

## Phase 2 - YouTube Provider — done
- [x] Move the YouTube provider implementation into the provider architecture.
- [x] Smoke-test metadata extraction and downloads with public videos.
- [x] Validate Shorts with real downloads in all three modes.
- [x] Validate a representative live output-mode/container matrix on a regular public video.
- [x] Validate deterministic provider error boundaries and representative format layouts.

### Recorded verification evidence
- Live matrix run on 2026-10-09 for https://www.youtube.com/watch?v=dQw4w9WgXcQ: 1 passed in 140.06s.
- The live test downloaded combined video/audio MP4, selected-quality video-only, and audio-only outputs in two distinct containers. ffprobe verified stream composition, codecs, dimensions, sample rate, and expected containers.
- Shorts were tested in all three modes; additional successful Shorts smoke tests were recorded for VF_MOfnz7OY and osrN3A_Rdiw.
- The duplicate audio format ID issue was reproduced and fixed. Deterministic tests cover provider errors, cleanup, and representative format layouts.
- GitHub Actions run [37966225469](https://github.com/ip52rus/social-video-downloader/actions/runs/37966225469) passed 131 tests and Ruff lint/format checks on merge commit f27051fded257b5f39056c45333b4fa8c50075a3.

The Phase 2 gate is satisfied by the combined live matrix and deterministic failure-boundary coverage. Scope limitation: the live matrix was run against one regular public video, not every YouTube format or platform condition.

## Phase 3 - Telegram Functional MVP — done
- [x] Add validated environment-based application settings and deterministic tests.
- [x] Configure standard-library application logging and add an aiogram bot/dispatcher polling entry point.
- [x] Test logging configuration and bot/dispatcher construction without Telegram API calls.
- [x] Implement /start and text-based URL intake with supported-platform recognition and safe user-facing validation responses.
- [x] Add deterministic handler tests for /start, valid YouTube/Instagram/TikTok URLs, invalid links, and unsupported domains.
- [x] Connect URL normalization and provider selection through the transport-independent DownloadService.
- [x] Add deterministic tests for YouTube handler orchestration, safe domain-error responses, file delivery calls, and temporary workspace cleanup; CI passed.
- [x] Add deterministic media-compatibility tests for H.264/AAC MP4 passthrough,
  compatible non-MP4 stream-copy remux, remux-failure fallback, incompatible-codec
  transcoding, output verification, and processing failures.
- [x] Deliver prepared MP4 output through Telegram video messages with streaming support instead of generic documents.
- [x] Validate real local stream-copy remux with synthetic H.264/AAC MKV input and
  confirm the prepared MP4 preserves encoded video/audio packet payloads, preserves
  decoded video content, avoids `libx264`, and verifies as H.264/AAC MP4.
- [x] Validate real local incompatible-source fallback transcode with synthetic MPEG-4
  video input and confirm the prepared output verifies as H.264/AAC MP4.
- [x] Verify live delivery through the Local Bot API Server with a short video.
- [x] Verify live delivery through the Local Bot API Server with an MP4 file of approximately 414.7 MB; confirm the large file arrives and plays. The tested file was H.264/AAC, 1920x1080, and approximately 1649 seconds long.
- [x] Verify Dockerized YouTube extraction runtime: the bot image includes Deno 2.9.7,
  yt-dlp detects `deno-2.9.7`, controlled metadata/simulation succeeds, and the project
  metadata path succeeds inside the image and Compose bot runtime.

The Phase 3 functional gate is satisfied: a core user can submit a supported YouTube URL and receive downloaded media in Telegram through the implemented flow.

The automated checks for provider selection and the mocked Telegram download/delivery flow passed in [GitHub Actions run 37974061474](https://github.com/ip52rus/social-video-downloader/actions/runs/37974061474). PR #27 media-preparation validation adds deterministic coverage for verified stream-copy remux and remux-failure fallback plus real local FFmpeg evidence using synthetic media: compatible MP4 passthrough, H.264/AAC MKV-to-MP4 stream-copy remux without `libx264`, and incompatible-source transcode fallback all passed. The remux check confirmed encoded H.264 and AAC packet payload hashes and decoded video hashes matched; exact decoded AAC checksum differed because of container/timestamp/priming interpretation. Containerized YouTube runtime validation confirmed the bot image exposes pinned Deno 2.9.7 to yt-dlp, raw yt-dlp uses `[jsc:deno]`, controlled metadata/simulation succeeds, and the project metadata path succeeds in the image and Compose bot runtime. A live Local Bot API Server test adds real-delivery evidence: a short video and an MP4 file of approximately 414.7 MB were delivered, and the large file was confirmed playable.

This closure does not mean production readiness. Additional client checks, upload failure/recovery behavior, restart/recovery validation, cloud/local rollback rehearsal, justified larger-file tests, monitoring/resource limits, and a reproducible end-to-end procedure were not verified here; they are tracked under Phase 9, Production Reliability. Instagram and TikTok links are recognized but their download providers are not implemented.

## Phase 4 - Download UX and YouTube Options
- [ ] Review and accept [the Phase 4 capability model](PHASE4_CAPABILITY_MODEL.md) before implementation.
- [x] Define how Telegram UX interprets existing provider/content capabilities without creating a second independent capability system at the application choice-model level.
- [x] Reuse existing `DownloadMode`, `QualityOption`, `get_supported_modes()`, and `get_available_qualities()` as the provider capability source of truth for the Low/Medium/High foundation.
- [x] Define the product/UX policy foundation that maps video `QualityOption` values to Low/Medium/High tier choices without Telegram transport coupling.
- [x] Implement immutable application choice-plan models and `DownloadService.create_choice_plan(url)` without Telegram transport coupling.
- [x] Design the Telegram interaction and state flow.
- [x] Implement the pending-interaction store and callback-data helpers without Telegram UX wiring.
- [x] Implement the documented Low, Medium, and High quality-tier mapping semantics for YouTube foundation code. Telegram UI integration remains open.
- [x] Wire Telegram URL intake and callbacks to `ChoicePlan` for direct download, mode
  choice, quality choice, and blocked states.
- [x] Prevent expected Telegram acknowledgement/keyboard failures from losing an
  atomically accepted terminal download; preserve exact stored options and single consume.
- [x] Keep mode-to-quality transitions recoverable after Telegram API failures and
  handle secondary domain-error notification failures without an unhandled traceback.
- [ ] Revalidate this callback-resilience fix in a real Telegram client after deployment;
  deterministic fault tests do not establish live network-failure recovery.
- [ ] Design a privacy-conscious analytics event model.
- [ ] Implement an application-level analytics abstraction and storage only after the analytics design is accepted.
- [x] Implement YouTube Video/Audio UX with `🎬 Видео` and `🎵 Аудио`.
- [x] Implement YouTube video quality choice with `Низкое`, `Среднее`, and `Высокое`.
- [x] Prefer native AAC/M4A for automatic YouTube audio and guarantee verified M4A/AAC
  before Telegram delivery through passthrough, stream-copy remux, or required transcode.
- [x] Supply reliable positive audio duration to Telegram, reusing preparation probes
  when source metadata is missing/invalid and omitting unknown duration safely.
- [ ] Revalidate M4A audio delivery/playback and displayed duration in a real Telegram
  client after deployment; current verification is deterministic/local synthetic only.
- [ ] Keep YouTube audio direct unless later evidence justifies audio quality selection.
- [ ] Do not expose video-without-audio as a normal user option.
- [ ] Preserve provider-specific automatic selection where safe; YouTube video must
  retain an exact, fully dimensioned quality ID even when the quality screen is skipped.
- [ ] Design loading, progress, and status behavior where justified.
- [ ] Define cancellation and retry behavior if appropriate.
- [ ] Review and standardize user-facing messages.
- [ ] Define consistent error messages.
- [ ] Keep the YouTube options UX minimal and fast.
- [ ] Validate UX and analytics.
- [ ] Use collected evidence later to simplify choices if users overwhelmingly prefer one option.

The current provider architecture already exposes modes and quality options. Phase 4
should connect these capabilities to Telegram UX before redesigning provider internals.
The capability-driven UX rule is: minimum steps + provider-specific capabilities +
consistent visual language. Do not force identical options on every provider, and never
add an extra click when there is no meaningful choice. Do not hard-code Instagram,
TikTok, or future-platform capabilities before their provider spikes prove what the
platform/content can actually offer.

Low/Medium/High foundation implemented in application services:

- `QualityOption.width` is available and validated like `height`.
- The YouTube provider preserves extracted video width and height in `QualityOption`
  values without changing yt-dlp selectors, codec/container preference, or download
  behavior.
- `build_quality_tier_plan()` maps video qualities to Low 480, Medium 720, and High 1080
  targets using `min(width, height)` when both dimensions exist, a documented
  one-dimension fallback when only one dimension exists, and no tier mapping for
  unclassifiable options.
- Duplicate tier mappings collapse to one underlying provider quality, preserving the
  semantically closest tier and exposing when only one distinct quality remains so a
  future UI can skip the quality screen.
- Verification: deterministic unit tests cover model validation, landscape/portrait/square
  1080-class classification, exact and missing targets, all-below/all-above cases,
  one-dimension fallback, unclassifiable options, duplicate collapse, one-choice plans,
  and input-order determinism.

Application choice-model design added to `docs/PHASE4_CAPABILITY_MODEL.md`:

- Proposed immutable `ChoicePlan`, `ModeChoice`, and `QualityChoice` concepts that map
  provider capabilities to product policy and final `DownloadOptions`; hidden modes use a
  simple mode/reason field rather than a separate capability model.
- Recommended `DownloadService.create_choice_plan(url)` as the minimal service boundary so
  normalization and provider selection are not duplicated in Telegram handlers or a second
  planning service.
- Documented YouTube Video/Audio behavior, quality-screen skipping rules, direct
  one-choice provider flow, no-choice/error distinction, and analytics boundaries.

Application choice-model foundation implemented in application services:

- `ChoicePlanState`, `UserChoiceKind`, `ChoicePlan`, `ModeChoice`, and `QualityChoice`
  model direct download, mode selection, quality selection, and blocked states.
- `DownloadService.create_choice_plan(url)` reuses existing URL normalization and provider
  selection before reading provider capabilities.
- Terminal and automatic paths carry concrete `DownloadOptions`; skipped one-quality
  video paths preserve the exact provider `quality_id`.
- Unsafe unclassifiable video-quality mappings remain distinct from legitimate
  single-path provider automatic behavior.
- Verification: deterministic unit tests cover direct automatic video, Video/Audio mode
  selection, hidden `VIDEO_ONLY`, concrete audio options, three/two/one quality-tier
  outcomes, unsafe unclassifiable quality blocking, no useful modes, deterministic mode
  ordering, and actionable terminal options.

Telegram interaction state-flow design added to `docs/PHASE4_CAPABILITY_MODEL.md`:

- Use a small dedicated in-memory pending-interaction store for callback flows instead of
  aiogram FSM, Redis, or a database at this stage.
- Callback data contains only a version, opaque interaction ID, action type, and choice
  index; URLs, titles, authors, and provider format details stay out of callback data.
- Pending state is owned by user and chat, stores the existing `ChoicePlan` plus the URL
  needed for download, expires lazily after a short TTL, and is atomically consumed before
  terminal downloads to avoid double-click duplicates.
- Documented direct download, mode choice, quality choice, blocked, stale, expired,
  wrong-owner, consumed, restart, and download-error behavior.

Telegram pending-interaction foundation implemented in `social_video_downloader.telegram_interactions`:

- Added immutable pending-interaction state with user/chat ownership, optional message
  validation, source URL stored only in memory, immutable `ChoicePlan`, 15-minute TTL,
  active step, selected mode index, and consumed state.
- Added a lock-protected in-memory store for create, lookup, mode-to-quality transition,
  atomic terminal consume, lazy expiry, and explicit removal.
- Added opaque interaction ID generation and callback serialization/parsing for
  `dl:v1:<interaction_id>:m:<mode_index>` and
  `dl:v1:<interaction_id>:q:<quality_index>`.
- Verification: deterministic unit tests cover creation, ID shape and uniqueness,
  callback parsing and rejection, callback payload size and URL exclusion, ownership,
  expiry boundary, lazy removal, selected mode persistence, unknown and consumed states,
  and single-process double-consume protection.

Telegram choice wiring implemented in `social_video_downloader.handlers`:

- YouTube URL intake now calls `DownloadService.create_choice_plan(url)` before deciding
  direct download, mode choice, quality choice, or blocked handling.
- Direct-download plans reuse the existing media download/preparation/probing/delivery
  path with `plan.automatic_options` and create no pending interaction.
- Mode and quality choice plans create in-memory pending interactions and render inline
  keyboards from application-provided choices only.
- Callback handling parses compact callback payloads, validates ownership/staleness,
  resolves selections against the stored `ChoicePlan`, atomically consumes terminal
  interactions, and passes exact stored `DownloadOptions` to the shared delivery path.
- Verification: deterministic handler tests cover direct, mode, quality, blocked,
  terminal mode choices, mode-to-quality transition, exact quality resolution, invalid
  indexes, malformed/unknown/expired/wrong-owner/wrong-chat/consumed callbacks,
  double-click protection, and callback policy-boundary behavior.

Focused callback resilience implemented on 2026-10-15:

- Expected Telegram API/network failures during terminal acknowledgement or keyboard
  cleanup no longer prevent the accepted download. Atomic consume still admits only
  one execution, using the original URL/options, with no media-upload retry.
- Nonterminal transition failures retain unconsumed state; an old mode button can retry
  the same quality keyboard. No replacement interaction or persistence was added.
- Failed domain-error notifications log the original error category and Telegram
  exception class without logging exception contents, source URLs, or user identifiers.
- Deterministic handler/store verification: 94 passed, including fault injection,
  concurrent duplicate callbacks, exact options, single media upload, and propagation
  of cancellation/programming errors. Full quality-check results are in TESTING.md.
- This is a bounded reliability fix, not Phase 4 completion or production-readiness
  evidence. The running Compose stack has not been rebuilt with this change.

Focused M4A audio/duration implementation (2026-10-15):

- Automatic audio selection prefers the best ranked native AAC/M4A with best-audio
  fallback; explicit quality IDs, video selectors and product choices are unchanged.
- Telegram audio preparation verifies actual streams/container, reuses native M4A,
  stream-copies AAC where possible, and encodes incompatible audio only when required.
- Duration uses reliable existing metadata or the same probes needed for compatibility;
  invalid/unknown values are omitted. No duration-only conversion/probe was added.
- `uv run pytest`: 357 passed, 1 skipped (opt-in YouTube live matrix). This includes four
  real local synthetic-media tests with FFmpeg, unchanged video tests, and callback
  resilience regressions. Quality checks and performance-gate evidence are in TESTING.md.
- No live YouTube/Telegram request, Compose rebuild/restart, new dependency, or
  production-performance benchmark was performed. Phase 4 remains open.

Focused YouTube playlist-context correction (2026-10-15):

- [x] Treat individual watch URLs with a valid single video ID and playlist context as
  single-video requests inside the YouTube provider, before extraction/cache/download.
- [x] Preserve unrelated query parameters, keep `noplaylist=True` and `process=False`,
  and reject malformed/ambiguous context URLs and playlist-only requests before extraction.
- [x] Add deterministic regressions for the false-BLOCKED redirect, shared inspection
  identity, canonical download targets, unchanged audio/video choices and quality tiers.
- [ ] Revalidate a playlist-context watch URL in the real Telegram client after deployment.

No quality policy, HTTP 403 handling, retries, media preparation, callback behavior,
dependencies, or runtime configuration changes are included. The existing Compose
stack is not rebuilt/restarted; Phase 4 and production reliability remain open.
Verification evidence is recorded in TESTING.md.

Full deterministic/local verification: 417 passed, 1 skipped (external matrix disabled);
Ruff lint/format, Compose configuration validation, and diff whitespace checks passed.

Focused YouTube quality-selection safety (2026-10-15):

- [x] Reproduce both confirmed defects in failing deterministic regressions before the
  fix: portrait 720-class selected landscape 1080-class; empty YouTube video qualities
  became unrestricted automatic video.
- [x] Identify distinct video dimension pairs and constrain every actual yt-dlp video
  selector branch to the exact chosen width and height, preserving codec/audio fallback.
- [x] Filter YouTube application choices to complete dimensions at or below 1080-class;
  preserve the exact safe ID for single-choice paths, audio-only availability, and
  `BLOCKED` when no safe useful path remains.
- [x] Retain `SINGLE_DIMENSION` classification as lower-confidence information while
  excluding incomplete dimensions from actionable YouTube video. No missing dimensions
  are invented and no automatic video fallback is allowed.
- [ ] Revalidate selected video quality, audio fallback, and normal M4A/callback behavior
  in the real Telegram client after an approved deployment.

QualityOption/DownloadOptions contracts are unchanged; provider IDs are opaque and now
encode dimension pairs instead of height alone. Existing playlist-context handling,
audio preparation, callbacks, retries, dependencies, and Compose are unchanged. Verification
evidence and metadata-only guarantee limits are recorded in TESTING.md. Phase 4 and
production reliability remain open.

Verification for quality-selection safety: 469 passed, 1 skipped (external matrix
disabled); Ruff lint/format, quiet Compose validation, and diff checks passed. Existing
M4A, video preparation, playlist-context and callback-resilience tests remain passing.

Analytics requirements for this phase:

- [ ] Track product statistics: total downloads, unique/returning users, downloads per user, platform usage, video vs audio, quality selected, and option availability vs option selected.
- [ ] Track content characteristics where technically available: short-form vs regular/long-form, duration buckets, source resolution, result resolution, and file-size buckets.
- [ ] Track technical statistics: success/failure, error category, passthrough/remux/transcode, download time, preparation time, Telegram upload time, total processing time, and useful source/result codec/container data.
- [ ] Track UX statistics: video selected, audio selected, quality selected, retries, and cancellations where implemented.
- [ ] Distinguish `option unavailable`, `option available but hidden by product policy`, and `option available but not selected`.
- [ ] Avoid storing source URLs, video titles, channel/author names, Telegram usernames, message text, or unnecessary personal data.
- [ ] Use pseudonymous or anonymous user identity sufficient for aggregate usage statistics.
- [ ] Keep product analytics in the Telegram/application flow and out of provider implementations.
- [ ] Do not introduce SQLite tables, external analytics SaaS, ClickHouse, Kafka, Redis, or other analytics infrastructure without a separate design stage.

## Phase 5 - Instagram Provider
- [ ] Run a technical spike.
- [ ] Assess real-world reliability and extraction stability.
- [ ] Make an explicit Go/No-Go decision before implementation.
- [ ] Implement the provider only if the spike is viable.
- [ ] Add deterministic validation.
- [ ] Add external validation within a documented scope.
- [ ] Map meaningful Instagram format or quality choices into the shared download-options model where available.
- [ ] Integrate the provider into the common Telegram UX.

## Phase 6 - TikTok Provider
- [ ] Run a technical spike.
- [ ] Assess real-world reliability and extraction stability.
- [ ] Make an explicit Go/No-Go decision before implementation.
- [ ] Implement the provider only if the spike is viable.
- [ ] Add deterministic validation.
- [ ] Add external validation within a documented scope.
- [ ] Map meaningful TikTok format or quality choices into the shared download-options model where available.
- [ ] Integrate the provider into the common Telegram UX.

## Phase 7 - Additional Social Platforms
- [ ] Select candidate platforms based on user demand, feasibility, legal/platform restrictions, extraction reliability, and maintenance burden.
- [ ] Run a technical spike for each candidate platform.
- [ ] Make an explicit Go/No-Go decision for each candidate before implementation.
- [ ] Implement only viable providers.
- [ ] Validate each provider with deterministic and scoped external checks.
- [ ] Integrate viable providers into the common Telegram UX.

Do not promise universal platform support or hard-code a long unsupported platform list into product claims.

## Phase 8 - Unified Product UX
- [ ] Review the complete multi-provider Telegram UI.
- [ ] Standardize inline keyboards.
- [ ] Present modes and quality options consistently across providers.
- [ ] Review all bot messages.
- [ ] Standardize loading and waiting messages.
- [ ] Standardize success messages.
- [ ] Standardize unsupported-content messages.
- [ ] Standardize retry and error states.
- [ ] Keep provider-specific exceptions only where necessary.
- [ ] Finalize consistent naming and button copy.
- [ ] Perform a final interaction-flow review.

## Phase 9 - Production Reliability
- [ ] Test additional Telegram clients, including iPhone, and record the exact clients tested.
- [ ] Test upload failures and recovery; record relevant Telegram errors and user-facing behavior.
- [ ] Rehearse restart and recovery behavior for the bot and Local Bot API Server.
- [ ] Rehearse cloud-to-local migration and local-to-cloud rollback with a separate test bot; do not treat `close` as an official local-to-cloud rollback procedure.
- [ ] Document the full test-bot setup and repeatable end-to-end procedure.
- [ ] Increase test-file sizes cautiously and document actual limits; do not claim support up to 2 GB based on the current 414.7 MB test.
- [ ] Observe resource usage and document operational limits.
- [ ] Verify disk and temporary-file cleanup behavior under failures.
- [ ] Assess concurrency and load.
- [ ] Add rate limits only when justified.
- [ ] Introduce queues or workers only if measured workload requires them.
- [ ] Add monitoring and observability when deployment needs are clear.
- [ ] Add deployment automation where justified.
- [ ] Define backup and recovery procedures where relevant.
- [ ] Define the strategy for files exceeding Telegram Bot API delivery limits.

For media above Telegram delivery limits, keep only a future design direction for now: possible external temporary object storage with download-link fallback. Do not implement S3, R2, or any storage provider during documentation planning, and do not claim support for files above 2 GB.

## Phase 10 - Monetization and Access Control
- [ ] Investigate Telegram community membership gating as a future access option.
- [ ] Design advertising gateway options.
- [ ] Evaluate optional paid/free models if desired later.
- [ ] Evaluate other monetization mechanisms.
- [ ] Define access restrictions required by the chosen model.
- [ ] Keep advertising modular and decoupled from provider implementations.
- [ ] Implement access gating only after a product decision and only after the downloader product is useful enough to monetize.

Membership is not required during core product development.
