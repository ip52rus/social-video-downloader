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

This closure does not mean production readiness. Additional client checks, upload failure/recovery behavior, restart/recovery validation, cloud/local rollback rehearsal, justified larger-file tests, monitoring/resource limits, and a reproducible end-to-end procedure were not verified here; they are tracked under Phase 9, Production Reliability. Instagram and TikTok links remain recognition-only in the bot. The experimental Instagram Reel provider added in Phase 5 is available only through explicit injection.

## Phase 4 - Download UX and YouTube Options

Functional acceptance recorded on 2026-10-15 for main
`ced1200bf2a81a1bb63c200e6441e8458d0af0df`. Real Telegram evidence covers playlist-context
watch links, Video/Audio choices, landscape Medium 936x720, portrait Medium 720x1280,
portrait High 1080x1920, image/sound, M4A playback/duration, callback protection and
distinct-URL isolation. Prior Local Bot API delivery above 50 MB remains valid scoped
evidence, not a new large-file test on this revision. See
[TESTING.md](TESTING.md#phase-4-functional-acceptance-2026-10-15) for evidence categories
and unverified cases. Functional acceptance does not close analytics, all UX polish, or
Phase 9 production reliability; unchecked tasks remain open.

- [x] Accept the implemented functional scope of [the Phase 4 capability model](PHASE4_CAPABILITY_MODEL.md); this records current acceptance, not a claim about a historical pre-implementation review.
- [x] Define how Telegram UX interprets existing provider/content capabilities without creating a second independent capability system at the application choice-model level.
- [x] Reuse existing `DownloadMode`, `QualityOption`, `get_supported_modes()`, and `get_available_qualities()` as the provider capability source of truth for the Low/Medium/High foundation.
- [x] Define the product/UX policy foundation that maps video `QualityOption` values to Low/Medium/High tier choices without Telegram transport coupling.
- [x] Implement immutable application choice-plan models and `DownloadService.create_choice_plan(url)` without Telegram transport coupling.
- [x] Design the Telegram interaction and state flow.
- [x] Implement the pending-interaction store and callback-data helpers without Telegram UX wiring.
- [x] Implement the documented Low, Medium, and High quality-tier mapping semantics and Telegram UI integration; live coverage is limited to the recorded cases.
- [x] Wire Telegram URL intake and callbacks to `ChoicePlan` for direct download, mode
  choice, quality choice, and blocked states.
- [x] Prevent expected Telegram acknowledgement/keyboard failures from losing an
  atomically accepted terminal download; preserve exact stored options and single consume.
- [x] Keep mode-to-quality transitions recoverable after Telegram API failures and
  handle secondary domain-error notification failures without an unhandled traceback.
- [x] Revalidate callback protection and distinct-URL isolation in a real Telegram client;
  forced acknowledgement/cleanup failures remain deterministic-test evidence only.
- [ ] Design a privacy-conscious analytics event model.
- [ ] Implement an application-level analytics abstraction and storage only after the analytics design is accepted.
- [x] Implement YouTube Video/Audio UX with `🎬 Видео` and `🎵 Аудио`.
- [x] Implement YouTube video quality choice with `Низкое`, `Среднее`, and `Высокое`.
- [x] Prefer native AAC/M4A for automatic YouTube audio and guarantee verified M4A/AAC
  before Telegram delivery through passthrough, stream-copy remux, or required transcode.
- [x] Supply reliable positive audio duration to Telegram, reusing preparation probes
  when source metadata is missing/invalid and omitting unknown duration safely.
- [x] Revalidate M4A audio delivery/playback and correct nonzero displayed duration in a
  real Telegram client within the accepted scope.
- [x] Keep YouTube audio direct unless later evidence justifies audio quality selection.
- [x] Do not expose video-without-audio as a normal user option.
- [x] Preserve provider-specific automatic selection where safe; YouTube video must
  retain an exact, fully dimensioned quality ID even when the quality screen is skipped.
- [ ] Design loading, progress, and status behavior where justified.
- [ ] Define cancellation and retry behavior if appropriate.
- [ ] Review and standardize user-facing messages.
- [ ] Define consistent error messages.
- [ ] Keep the YouTube options UX minimal and fast.
- [x] Accept the recorded functional Telegram UX results.
- [ ] Validate remaining UX polish and analytics; these are not implied by functional acceptance.
- [ ] Use collected evidence later to simplify choices if users overwhelmingly prefer one option.

The implemented provider/application flow connects existing modes and quality options to
Telegram UX without a parallel capability system.
The capability-driven UX rule is: minimum steps + provider-specific capabilities +
consistent visual language. Do not force identical options on every provider, and never
add an extra click when there is no meaningful choice. Do not hard-code Instagram,
TikTok, or future-platform capabilities before their provider spikes prove what the
platform/content can actually offer.

Low/Medium/High foundation implemented in application services:

- `QualityOption.width` is available and validated like `height`.
- The YouTube provider preserves extracted video width and height in `QualityOption`;
  the later quality-safety correction below enforces exact dimension selectors.
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
- At implementation time this was deterministic-only evidence without a stack rebuild.
  Subsequent deployment and functional client acceptance are recorded in TESTING.md;
  this does not establish live fault recovery or production readiness.

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
- That implementation stage performed no live YouTube/Telegram request, Compose
  rebuild/restart, new dependency, or production benchmark. Subsequent functional client
  acceptance is recorded in TESTING.md; broader reliability remains open.

Focused YouTube playlist-context correction (2026-10-15):

- [x] Treat individual watch URLs with a valid single video ID and playlist context as
  single-video requests inside the YouTube provider, before extraction/cache/download.
- [x] Preserve unrelated query parameters, keep `noplaylist=True` and `process=False`,
  and reject malformed/ambiguous context URLs and playlist-only requests before extraction.
- [x] Add deterministic regressions for the false-BLOCKED redirect, shared inspection
  identity, canonical download targets, unchanged audio/video choices and quality tiers.
- [x] Revalidate a playlist-context watch URL in the real Telegram client after deployment;
  choices and a selected video succeeded, separately from an observed HTTP 403 attempt.

That implementation stage changed no quality policy, HTTP 403 handling, retries, media
preparation, callbacks, dependencies, or runtime configuration and did not rebuild the
stack. Subsequent functional deployment/client evidence is recorded in TESTING.md;
remaining UX/analytics and production reliability are not closed.

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
- [x] Revalidate the recorded selected video qualities and normal M4A/callback behavior
  in the real Telegram client after approved deployment.

Rare missing/partial-dimension audio-fallback or BLOCKED cases remain NOT VERIFIED live;
deterministic tests cover them. Extend live coverage only when justified as Phase 9 work.

QualityOption/DownloadOptions contracts are unchanged; provider IDs are opaque and now
encode dimension pairs instead of height alone. Existing playlist-context handling,
audio preparation, callbacks, retries, dependencies, and Compose are unchanged. Verification
evidence and metadata-only guarantee limits are recorded in TESTING.md. Functional scope
is accepted; remaining UX/analytics and production reliability remain open.

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

## Phase 5 - Instagram Provider — in progress

- [x] Record explicit user GO for narrow anonymous public Reel implementation (2026-10-16).
- [x] Define and agree PR 1 scope and acceptance criteria; retain the one-file provider contract.
- [x] Implement `InstagramProvider` for individual `/reel/<id>/` URLs and direct MP4 formats.
- [x] Reject collections, redirects, unsupported URLs/formats and auth-gated metadata before acquisition.
- [x] Use shared inspection data, safe temporary storage, domain errors and existing choice model.
- [x] Validate explicit `DownloadService` injection and `DIRECT_DOWNLOAD` without audio/quality menus.
- [x] Add offline provider tests and synthetic yt-dlp/ffprobe integration; record results in TESTING.md.
- [x] Address PR #44 P1/P2: reject implicit manifests/fragments before acquisition and prefer compatible codecs using real yt-dlp selection regression tests.
- [x] Independently review and merge PR #44 after the user's separate decision.
- [x] Reproduce and correct overly strict rejection of incomplete direct-MP4 metadata offline; preserve manifest rejection and compatibility priority.
- [ ] Integrate default provider registration and Telegram direct-download routing/messages in a separate integration PR.
- [x] Validate one real anonymous Reel through corrected provider/service after PR #45: 2026-10-16, one extraction/acquisition, preparation passthrough, ffprobe/full decode PASS; no Telegram upload.
- [x] Record expanded Phase 5 scope: Reels, public single-video posts and video-only carousel selection; photos are never downloaded/delivered.
- [x] Extend the existing provider to single-video `/p/` posts with deterministic classification, acquisition and preparation tests; retain one-file contract and all format restrictions.
- [ ] Validate real anonymous single-video `/p/` acquisition after separate authorization; offline tests do not close this gate.
- [x] Inspect one real five-video carousel metadata-only: two URL variants, five stable ordered IDs, three direct MP4 candidates per item; installed yt-dlp ignores `img_index`; zero acquisition.
- [x] Implement guarded instance-local source type preservation, immutable carousel inspection/selection plans and deterministic tests; keep single-file contracts unchanged.
- [x] Independently review and merge carousel inspection/planning PR #47.
- [x] Record one real 20-entry metadata case: 17 VIDEO and three UNKNOWN at 8/9/18, original IDs/order preserved, BLOCKED / unknown_item; source diagnosis supports corroborated PHOTO candidates, zero acquisition.
- [x] Correct corroborated integer media_type=1 PHOTO classification with deterministic tests; preserve conflict guards and report numeric evidence.
- [x] Independently review and merge the focused PHOTO classification fix (PR #48).
- [x] Validate corrected mixed-carousel selection live on one publication: 20 items, 17 VIDEO, PHOTO at 8/9/18, zero UNKNOWN, READY; unique IDs/order PASS, three direct MP4 candidates per VIDEO, one extraction/three metadata HTTP requests, zero acquisition.
- [ ] Validate reliable item-reference semantics separately; keep `img_index` and ambiguous references blocked meanwhile.
- [x] Implement bounded ordered multi-video acquisition with fresh plan revalidation, actual stream checks, resource budgets and all-or-nothing cleanup; deterministic tests only. Photos are NEVER acquired.
- [x] Independently review and merge bounded acquisition (PR #49).
- [x] Validate one separately authorized bounded three-video silent carousel acquisition: 3/3 files, original order, MP4/H.264 720x960, 1,961,198 bytes total, ffprobe PASS; no conversion or Telegram calls. Larger collections remain unverified.
- [x] Implement explicit optional-audio Telegram preparation with default audio-required behavior: silent passthrough/remux/transcode, output validation, cleanup and upload metadata verified on local generated media; no artificial audio. Future Instagram callers must opt in.
- [x] Implement reusable offline Telegram carousel transport: prepare all videos first; 2–10 per group, more than 10 split sequentially, a single remainder sent individually; no routing activation.
- [ ] Validate real Telegram delivery/playback after separately authorized deployment changes.
- [ ] Assess broader extraction stability and recovery; production reliability remains open.

Evidence limitation: previous Gates 1–3C are reported in the handoff and the user authorized
GO; full Gates 1–3B evidence was unavailable here. Gate 3C demonstrates metadata for one
five-element `/p/` playlist, which remains excluded from single-file download.
Those early gates acquired no carousel media; the later three-video smoke is recorded below.
PR 1 tests do not substitute for real Instagram or Telegram validation. Meaningful
Instagram quality choices, DASH/HLS assembly, live Telegram routing, Stories, private
content and authentication remain outside the implemented scope. Single-video `/p/`
support is implemented offline; carousel inspection is implemented separately, while
bounded acquisition has deterministic coverage and one real three-video PASS; larger
collections and Telegram delivery remain unfinished.
The first real provider smoke failed during inspection (13 formats, none admitted),
with zero acquisition attempts. The incomplete-metadata rejection is reproduced and
fixed in PR #45. Its repeat real smoke passed: 13 formats, 3 admitted, 10 rejected for
manifest/fragment markers; MP4 H.264/AAC, 720x1280, 11.282041 seconds, 1,317,210 bytes.
The initial run's other ten rejection reasons were unverified; the later run's diagnosis
does not retroactively establish them. No real single-video `/p/` acquisition or Instagram
Telegram delivery is claimed. The newer carousel metadata-only experiment is recorded
separately in TESTING.md. The later 20-entry source diagnostic justifies the PHOTO
adjustment for that observed shape. The final corrected live mixed-selection gate passed
for the same publication; the separate three-video acquisition smoke below does not
verify acquisition of that 17-video selection.
See [the accepted scope](PHASE5_INSTAGRAM_REELS.md) for the evidence boundary.

### Ordered carousel acquisition verification

- 74 new deterministic acquisition cases passed; full suite 944 passed, 1 skipped.
- Actual installed yt-dlp HTTP processing and local synthetic MP4/ffprobe exercised;
  no live Instagram/Telegram calls. Ruff lint/format, diff and documentation checks PASS.
- Explicit operation defaults: 25 videos, 100 MiB/file, 500 MiB total received media,
  512 MiB temporary logical media bytes and 600 seconds; adjustable per service.
- Successful generated files belong to the caller. Failure/cancellation removes all
  owned files, without overwriting/deleting unrelated files. No crash recovery claim.
- PR #49 was independently reviewed and merged; the subsequent three-video live smoke
  passed. Larger collections and Telegram integration/validation remain open.


### Silent Instagram video acquisition

- [x] Record approved optional-audio policy for Reels, single-video posts and carousel VIDEO entries; keep normal route/enum and all direct-video safety guards.
- [x] Record one real metadata-only diagnostic: 3 VIDEO, has_audio=False, 3 direct MP4 candidates each; 32 mapped formats, zero acquisition. That diagnostic did not validate actual streams.
- [x] Admit silent direct MP4, retain compatibility-first ranking and prefer non-silent/unknown audio within comparable groups; no fabricated audio/codec claims.
- [x] Validate actual silent MP4 video through carousel ffprobe; reject audio-only, corrupt/wrong-container files and invalid present stream codecs; preserve budgets/cleanup.
- [x] Independently review and merge silent-video support (PR #50).

One real silent three-video acquisition passed at main `055fced0bdf337a5b04132600cc803321db59c80`: files 613050/738479/609669 bytes, each 5.041667 seconds,
720x960 H.264 MP4 without audio; 6.90 seconds acquisition, exact original order.
Limits 3 videos, 30 MiB/file, 75 MiB received, 90 MiB temporary media, 180 seconds held.
All outputs/runtime were deleted. Larger carousels, broad availability and Telegram
playback remain NOT VERIFIED. Instagram is disabled by default.

Verification: focused Instagram suite 563 passed; full suite 1032 passed, 1 skipped.
Ruff lint/format, diff, documentation consistency and security/scope checks PASS.
These checks used local synthetic media only; no external platform or Telegram calls.

### Optional-audio Telegram preparation

The helper has keyword-only `allow_silent=False`; default callers still require audio.
Local generated fixtures verify silent passthrough, stream-copy remux, H.264 conversion,
optional audio preservation, output/container/stream checks, rotation/upload metadata and
partial-file cleanup. No synthetic audio, routing changes or external calls in this stage.

- [x] Independently review and merge optional-audio preparation and P2 collision fix (PR #51).

Live Telegram delivery/playback and routing of ordered groups remain the open tasks above.
Verification: focused suite 98 passed; full suite 1112 passed, 1 skipped; net +80 cases.
Real local FFmpeg/ffprobe fixtures passed, including silent remux/transcode and rotation.
Ruff lint/format, diff, documentation and security/scope checks PASS; no live requests.

PR #51 P2 correction: replace non-atomic output ownership with private same-filesystem
staging and atomic no-overwrite hard-link publication. Cleanup never unlinks the shared
destination. Late/concurrent collisions, failed publication and interruption have
specific deterministic regression coverage; API, routing and optional-audio policy stay
unchanged. Correction verification: focused 108 passed; full 1122 passed, 1 skipped;
net +10 cases, real local FFmpeg/ffprobe still passing. Ruff lint/format, diff and
security/scope checks PASS; no live requests. Details are recorded in TESTING.md.

### Offline carousel Telegram transport

- [x] Implement explicit reusable transport consuming acquired collection plus expected plan/workspace; no downloader or handler changes.
- [x] Prepare/probe every selected video with optional audio before any send; preserve sources and bound generated output/time/workspace use.
- [x] Implement deterministic sequential batching and safe confirmed/uncertain partial progress without send retries.
- [x] Add network-forbidden transport and actual local preparation/resource/cleanup regression coverage.
- [x] Independently review and merge the inactive transport (PR #52; user-confirmed review PASS).
- [ ] Validate real Telegram albums/playback under separate authorization; existing real evidence is acquisition of three videos only.

Offline transport verification: 80 new passing cases (66 transport/process, 14 real local
preparation); full suite 1202 passed, 1 skipped. Ruff lint/format, diff, documentation and
security/scope checks PASS. Current handlers, acquisition, models, dependencies and Compose
are unchanged. No live external-platform or Telegram calls.

### Reel-only Telegram MVP (offline)

- [x] Connect public Reels to the existing provider, optional-audio preparation and sendVideo behind an explicit disabled-by-default flag.
- [x] Historical Reel-only stage: reject item selectors and `/p/`; strip ordinary Reel share queries and harmless fragments. Merged PR #56 adds guarded `/p/` routing separately below.
- [x] Add scoped media-byte/preparation limits and one active Reel per handler instance; keep admission/workspace until a cancelled worker actually exits.
- [x] Verify the narrow integration offline, including local silent/audio passthrough and video-only conversion.
- [x] Independently review and merge the Reel MVP (PR #53).
- [x] Validate one real canonical Reel upload; user confirmed client playback, orientation and sound. Exact file size/time were not recorded; broader reliability remains open.
- [x] Independently review PR #56 at `219e1bfcc134e80be24bb8565f6dfc18dae77c21` (PASS), merge at `20d14441a2b7ea906ed2a0abc83679d25d9f2d32`, and separately deploy only bot. Full offline suite/CI: 1397 passed, 1 skipped. Image source identity and polling passed; Local Bot API was unchanged. This closes technical integration/deployment only, not real `/p/` delivery or album playback.
- [ ] Confirm real Telegram album send for the previously tested three-silent-video publication, including order, playback, cleanup and no synthetic sound, only after separate deployment/smoke approval.
- [ ] Reassess initial 10-video / 25 MiB-per-file / 100 MiB-total limits and source-query policy using test evidence before expansion.
- Review correction P1: use source-confirmed single-video metadata and the same cached
  snapshot; BLOCKED never permits fallback. Domain/download contracts and media policy stay unchanged.
- Review correction P2: initial inspection shares cancellation/deadline with later stages;
  keep admission/workspace until worker exit, and preserve uncertain-send progress on timeout.
- Review correction P3: current architecture describes `/reel/` and `/p/`; Reel-only
  statements are historical. Live `/p/`/album gates remain OPEN; PR #56 re-review completed above.
- Prior correction verification: net +43 deterministic cases; full suite 1320 passed,
  1 skipped (external YouTube opt-in); focused post/Reel/preparation tests 204 passed,
  extended Instagram/local-media tests 777 passed, YouTube/handler/config regressions 242 passed.
  Ruff lint/format and diff checks PASS. Tests forbid socket connections and include
  real local FFmpeg/ffprobe; no new external-platform or Telegram evidence.
- Source-shape follow-up: validate present carousel fields before mapping and require
  complete count/identity/order preservation afterward. Malformed collections must not
  become single videos; empty lists remain NO_VIDEOS. Offline verification PASS:
  net +42 cases, focused source-shape 40 passed (29 failed before the fix), combined
  carousel/post/Reel 303 passed, extended Instagram/local-media 819 passed,
  YouTube/handlers/config 242 passed, full pytest 1362 passed and 1 external opt-in skipped.
  Ruff lint/format, diff, documentation and security/scope checks PASS. At this historical
  stage, repeat review/merge/deployment remained open; their completion is recorded above.
  Live `/p/`/album gates remain OPEN.
- Immutable-source follow-up: freeze the original count and ordered ItemEvidence
  before mapping, then compare every mapped identity, kind, evidence signal and
  availability flag with those initial facts. Do not derive expectations from a
  source list that upstream may have mutated. Eleven synthetic mutation scenarios
  cover inspection and handler refusal without acquisition, media sends or repeat
  extraction. These are mapper fault-injection cases, not observed upstream mutation
  or a live exploit. PR #56 subsequently passed repeat review; live `/p/`/album gates remain OPEN.
  Verification: net +35 cases; new subset 35 passed (33 failed/2 passed before the fix),
  extended Instagram/local FFmpeg/ffprobe 854 passed, YouTube/handlers/config 242 passed,
  full pytest 1397 passed and 1 external opt-in skipped. Ruff lint/format, diff and
  security/scope checks PASS. No new external-platform requests or delivery evidence.

### Post share-link correction — offline follow-up

- The user reported two reference-policy refusals after PR #56 deployment; actual
  URLs were not supplied. Synthetic tests reproduce unknown-query, bare-flag and
  ordinary-fragment rejection without claiming the users' exact parameters.
- Reuse one transport-independent Reel/post reference guard. Strip non-selector share
  data before provider inspection; retain known selectors, encoded/case variants,
  malformed-reference rejection and the 32-field bound. Metadata snapshot, selection,
  acquisition, delivery, product limits and the running environment remain unchanged.
- Offline verification PASS: net +73 deterministic cases; full pytest 1470 passed,
  1 skipped (external YouTube opt-in); extended Instagram/local-media 927 passed;
  YouTube/handlers/URL/bot/config 267 passed. Ruff lint/format, diff, documentation and
  security/scope checks PASS. The 132-case control set changed from 69 failed/63 passed
  before the fix to 132 passed; later encoding/malformed-reference cases also pass.
- Review, merge and separate deployment of this correction remain OPEN. Corrected
  live `/p/`/album delivery and client playback remain NOT VERIFIED.

The user chose one controlled smoke with the existing main bot and accepted a short
planned bot-only restart after PR review/merge. General production rollout is not approved.
Cooperative network deadlines do not force-stop a thread or bound DNS; no restart-proof
deduplication, global quotas or production capacity is claimed.

- [x] Prepare disabled-by-default bot-only Compose flag forwarding; preserve APP_ENV=development, Local Bot API and the Settings production-mode guard.
  Verification: Compose absent/true resolution and unchanged remaining config PASS; offline pytest 1234 passed, 1 skipped; Ruff/diff/security PASS.
- [x] Review/merge the configuration PR (#54) before changing the protected server environment.
- [x] Deploy only bot with --no-deps after confirming no active download; verify polling, retained YouTube code and unchanged Local Bot API. Live YouTube was not retested.
- [x] Execute one approved canonical Reel smoke and verify client playback; temporary files cleaned, 25 MiB limit retained.
- [x] Correct share-link admission offline: accept/strip `psln` and irrelevant query keys/anchors, retain known item selectors and strict URL validation. Canonical URL reaches provider; one synthetic send; no deployment changes.
- [x] Merge PR #55 at `0a87beeaa8acb302b74e980946778608856b13f6` and separately deploy the share-link fix. The user confirmed full Reel share-link delivery, playback, orientation and sound with `utm_source`/`psln`. Size/time were not recorded; this does not validate `/p/`, albums or general reliability.
- [ ] Restore false and recreate only bot if rollback is needed.

The deployment/smoke above was separately authorized after configuration preparation.
The share-link implementation was offline; its deployment/smoke followed separately.
The current PR #56 corrections perform no environment change, restart, polling or live call.
See DEVELOPMENT.md for the controlled procedure.

Share-link correction verification: net +34 cases; Reel handler 66 passed; combined
handler/config/bot suite 176 passed; full pytest 1268 passed, 1 skipped with network
connections forbidden. Ruff lint/format, diff, documentation and scope/security PASS.
Existing YouTube and local FFmpeg/ffprobe regressions passed; no live calls or deployment.

Reel MVP verification: 32 new cases; focused 142 passed; full 1234 passed, 1 skipped.
Ruff lint/format, diff, documentation and security/scope review PASS; no live requests.

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
- [ ] Review all bot messages, including removing or updating obsolete video/audio choice
  prompts after selection; disappearing buttons must not leave an irrelevant instruction.
- [ ] Standardize loading and waiting messages.
- [ ] Standardize success messages.
- [ ] Standardize unsupported-content messages.
- [ ] Standardize retry and error states.
- [ ] Keep provider-specific exceptions only where necessary.
- [ ] Finalize consistent naming and button copy.
- [ ] Perform a final interaction-flow review.

## Phase 9 - Production Reliability

Status: OPEN; not closed by Phase 4 functional acceptance.

- [ ] Diagnose intermittent YouTube HTTP 403 and define/test a narrowly bounded recovery
  strategy with explicit attempt limits and no duplicate media delivery.
- [ ] Remove synchronous metadata extraction/planning from the async event loop; verify
  callback responsiveness while metadata inspection is slow or fails.
- [ ] Test additional Telegram clients, including iPhone, and record the exact clients tested.
- [ ] Test temporary network/API and upload failures and recovery; record relevant
  Telegram errors and user-facing behavior without assuming live fault recovery from unit tests.
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
