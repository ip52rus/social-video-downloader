# Task Decomposition

## P9-R2 evidence closeout and P9-R3a — 2026-10-30

P9-R1b is **MERGED / OFFLINE VERIFIED**, deployed as source `742bc105`.
P9-R2 experimental series is **CLOSED / INCONCLUSIVE**; LIVE responsiveness
acceptance remains **OPEN / INCONCLUSIVE**. Phase 9 remains **OPEN**.
[Evidence and limits](TESTING.md#p9-r2-live-evidence-closeout--2026-10-30).

P9-R3a includes offline upload-transport tests, fixtures/documentation and the
separately owner-authorized minimal upload ownership fix. Coverage is
**OFFLINE VERIFIED**: 30 focused checks and 606 related regressions passed. The original
partial-upload FAIL is preserved as historical evidence and now passes with the
owned reader guard. SDK/session/multipart, delivery classification and quarantine
policy are unchanged.
[Coverage and limits](TESTING.md#p9-r3a-offline-upload-transport--offline-verified).
Independent review and exact-head CI remain separate gates. No merge, deployment
or LIVE recovery acceptance is implied.

- [x] Close the completed P9-R2 series as INCONCLUSIVE; keep LIVE acceptance open.
- [x] Diagnose the real partial-upload reader/cleanup ordering FAIL and obtain
  separate owner authorization for the minimal production fix.
- [x] Verify Video/Audio A–I transport cases, cancellation/repeated cancellation,
  no-resend, ownership drain, quarantine and next-request admission offline.
- [ ] Complete independent review and exact-head CI of the P9-R3a Draft PR.
- [ ] Any merge, deployment or LIVE recovery acceptance requires separate owner scope.

## P9-R2d deployment checkpoint — 2026-10-30

HOSTKEY bot-only deployment of `742bc105e923500fc0b22844bec2809c0c8fbc45`:
**TECHNICAL PASS**, checked at 07:41 UTC. Old poller exited before the new startup;
API identity/state, environment and resource limits were preserved.
`CONCURRENCY_DIAGNOSTICS=false`; **LIVE concurrency responsiveness: INCONCLUSIVE**.
No media downloads or Telegram LIVE scenarios were performed for deployment.
[Evidence, rollback tag and limits](P9_R2D_DEPLOYMENT.md). Documentation closeout
was merged in PR #87; later separately authorized experiments are recorded above.

## Current checkpoint — 2026-10-29

Baseline f74dc6c / merged PR #83; Phase 8 accepted through PR #82; Phase 9C
**LOCAL ACCEPTED**. HOSTKEY designated sole poller after 2026-10-28 technical cutover;
MacBook bot/API preserved stopped. D1 reads saved evidence, not production.
See [current evidence](TESTING.md#checkpoint-2026-10-29), [operations](LOCAL_BOT_API.md#hostkey-vps-checkpoint-2026-10-28)
and [next main stage](CHAT_HANDOFF_2026-10-29.md#28-next-development-stage).
Historical unchecked tasks remain historical or explicitly deferred; later acceptance
records supersede old merge/deployment gates, without erasing earlier failures.

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

### Item selection — merged, deployed and narrowly LIVE accepted (2026-10-22)

Reason: an explicit img_index is original publication intent, not permission to
choose an arbitrary video subset. Reuse parent/full-manifest inspection, the same
acquisition process and delivery transport with an explicit SINGLE_VIDEO scope.
A small typed Instagram pending store retains server-side validated plans; reserve
the shared Instagram slot before consuming a callback and release it only after
owned work/cleanup. Do not retain that slot while waiting for user choice.
The implementation stage was offline-only; the later separately authorized
deployment and owner LIVE acceptance are recorded below.
Inspection found a cleanup-exception gap in the existing carousel lifecycle:
failed reap could fall through automatic directory deletion and slot release.
The implementation closed it with opt-in quarantine workspaces and an explicit
cleanup error that retains the Instagram slot, without expanding downloader or network behavior.
Verification: 77 targeted tests PASS; full inherited socket/DNS-blocked offline
pytest 1946 passed / 1 opt-in live test skipped (258.35 s). Ruff lint/format,
diff-check, 70 local documentation links and privacy/scope/security review PASS.
PR #70 is merged at `49f333eb3daff1d43fa2471e185e7071e8d179db`;
post-merge CI #39745923630 SUCCESS. These offline results are separate from the
later deployment, owner-confirmed LIVE cases and read-only health evidence in
[Item Selection LIVE acceptance](TESTING.md#instagram-item-selection--live-acceptance-2026-10-22).

- [x] Implement verified PUBLICATION / SINGLE_VIDEO scopes and bounded one-shot callbacks; complete offline checks.
- [x] Merge PR #70 and verify successful post-merge CI on the merge HEAD.
- [x] Deploy to the existing main bot; preserve Local Bot API, volumes, `.env` and the previous image for rollback.
- [x] Record owner LIVE PASS for `img_index=2` → “Только видео №2” on one two-video carousel: selected video delivered, playback/orientation/sound confirmed.
- [x] Record owner LIVE PASS for a new submission of the same reference → “Все видео из карусели”: both videos delivered, playback/orientation/sound confirmed.
- [x] Record read-only post-LIVE health evidence: running containers, one poller, no restart/OOM, orphan media workers, residual media files or observed operation errors; rollback image available.
- [ ] Validate mixed PHOTO source positions with separately authorized LIVE acquisition/delivery; prior mixed metadata and offline checks are not this gate.
- [ ] Assess broader Instagram publication compatibility and extraction stability.
- [ ] Validate failure recovery and rehearse rollback; retained image availability is not a rollback rehearsal.
- [ ] Confirm internal quarantine/`_blocked` state through a separately approved safe method. Current value is UNKNOWN; health verdict remains INCOMPLETE, with no observed blocking symptoms.

This closes only two user scenarios on one publication, not Phase 5 or Phase 9
reliability. No per-test sizes, HTTP counts, exact media formats or timings are claimed.

### Parent identity contract — offline implementation

The existing URL originates from input, and the previous worker comparison did not
detect a parent-only identity change. This focused change adds observed product PK
and shortcode binding to the immutable inspection/plan and private worker pipe,
then rechecks parent plus the entire ordered manifest before any media GET.
Missing/conflicting parent evidence must refuse; URL-derived IDs are not evidence.
Single-item downloading and selection buttons remain out of scope.
Verification: 576 focused regressions PASS; the final parent-specific suite has
67 PASS. Full inherited socket/DNS-blocked offline pytest: 1869 passed, 1 opt-in
live test skipped (227.51 s). Ruff lint/format, diff-check, 44 local documentation
links and security/privacy review PASS. Exact-head Draft PR CI is required before
handoff and recorded in GitHub checks. No live calls or deployment are authorized;
installed response formats are not a universal Instagram compatibility guarantee.

Current narrow live evidence includes
[Item Selection acceptance (2026-10-22)](TESTING.md#instagram-item-selection--live-acceptance-2026-10-22)
and the earlier [Instagram acceptance (2026-10-18)](TESTING.md#instagram-live-acceptance-2026-10-18).
Earlier stage records retain their original verification scope; Phase 5 is not complete.

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
- [x] Integrate Instagram via explicit Telegram opt-in (PRs #53/#56); the default downloader registry remains YouTube-only.
- [x] Validate one real anonymous Reel through corrected provider/service after PR #45: 2026-10-16, one extraction/acquisition, preparation passthrough, ffprobe/full decode PASS; no Telegram upload.
- [x] Record expanded Phase 5 scope: Reels, public single-video posts and video-only carousel selection; photos are never downloaded/delivered.
- [x] Extend the existing provider to single-video `/p/` posts with deterministic classification, acquisition and preparation tests; retain one-file contract and all format restrictions.
- [x] Record one owner-confirmed full-link single-video `/p/` delivery and normal playback after PR #57 (2026-10-18); no separate extraction metrics were recorded.
- [x] Inspect one real five-video carousel metadata-only: two URL variants, five stable ordered IDs, three direct MP4 candidates per item; installed yt-dlp ignores `img_index`; zero acquisition.
- [x] Implement guarded instance-local source type preservation, immutable carousel inspection/selection plans and deterministic tests; keep single-file contracts unchanged.
- [x] Independently review and merge carousel inspection/planning PR #47.
- [x] Record one real 20-entry metadata case: 17 VIDEO and three UNKNOWN at 8/9/18, original IDs/order preserved, BLOCKED / unknown_item; source diagnosis supports corroborated PHOTO candidates, zero acquisition.
- [x] Correct corroborated integer media_type=1 PHOTO classification with deterministic tests; preserve conflict guards and report numeric evidence.
- [x] Independently review and merge the focused PHOTO classification fix (PR #48).
- [x] Validate corrected mixed-carousel selection live on one publication: 20 items, 17 VIDEO, PHOTO at 8/9/18, zero UNKNOWN, READY; unique IDs/order PASS, three direct MP4 candidates per VIDEO, one extraction/three metadata HTTP requests, zero acquisition.
- [x] Support one unambiguous positive canonical `img_index=N` through the verified Item Selection flow (PR #70); other selectors and malformed/ambiguous references remain rejected.
- [x] Implement bounded ordered multi-video acquisition with fresh plan revalidation, actual stream checks, resource budgets and all-or-nothing cleanup; deterministic tests only. Photos are NEVER acquired.
- [x] Independently review and merge bounded acquisition (PR #49).
- [x] Validate one separately authorized bounded three-video silent carousel acquisition: 3/3 files, original order, MP4/H.264 720x960, 1,961,198 bytes total, ffprobe PASS; no conversion or Telegram calls. Larger collections remain unverified.
- [x] Implement explicit optional-audio Telegram preparation with default audio-required behavior: silent passthrough/remux/transcode, output validation, cleanup and upload metadata verified on local generated media; no artificial audio. Future Instagram callers must opt in.
- [x] Implement reusable offline Telegram carousel transport: prepare all videos first; 2–10 per group, more than 10 split sequentially, a single remainder sent individually; no routing activation.
- [x] Validate the narrow real single-post and three-video-album delivery/playback cases after separately authorized PR #57 deployment; see the acceptance record below.
- [ ] Assess broader extraction stability and recovery; production reliability remains open.

Evidence limitation: previous Gates 1–3C are reported in the handoff and the user authorized
GO; full Gates 1–3B evidence was unavailable here. Gate 3C demonstrates metadata for one
five-element `/p/` playlist, which remains excluded from single-file download.
Those early gates acquired no carousel media; the later three-video smoke is recorded below.
PR 1 tests do not substitute for real Instagram or Telegram validation. Meaningful
Instagram quality choices, DASH/HLS assembly, Stories, private content and
authentication remain outside the implemented scope. Single-video `/p/`, carousel
delivery and Item Selection have the narrow later acceptance records linked above;
larger collections and broader compatibility/recovery remain unverified.
The first real provider smoke failed during inspection (13 formats, none admitted),
with zero acquisition attempts. The incomplete-metadata rejection is reproduced and
fixed in PR #45. Its repeat real smoke passed: 13 formats, 3 admitted, 10 rejected for
manifest/fragment markers; MP4 H.264/AAC, 720x1280, 11.282041 seconds, 1,317,210 bytes.
The initial run's other ten rejection reasons were unverified; the later run's diagnosis
does not retroactively establish them. That early provider smoke did not establish
single-video `/p/` acquisition or Instagram Telegram delivery; later acceptance is
recorded separately. The newer carousel metadata-only experiment is recorded
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
- [x] Record one real three-video album with all videos delivered, original order, normal playback and original silence, owner-confirmed after PR #57; larger/multi-batch albums remain unverified.

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
- [x] Confirm one previously rejected full-link carousel delivers all three videos in one ordered, playable album with silence preserved (owner report, 2026-10-18). No link to the earlier measured acquisition fixture is inferred.
- [ ] Verify live `/p/` and album cleanup telemetry separately; the owner acceptance report did not include it.
- [x] Replace historical 25 MiB/file and 100 MiB aggregate Instagram gates in Phase 9C
  with configurable resource/endpoint budgets; ten-video ceiling retained. Further
  count/source-policy expansion and near-2 GB validation are not accepted.
- Review correction P1: use source-confirmed single-video metadata and the same cached
  snapshot; BLOCKED never permits fallback. Domain/download contracts and media policy stay unchanged.
- Review correction P2: initial inspection shares cancellation/deadline with later stages;
  keep admission/workspace until worker exit, and preserve uncertain-send progress on timeout.
- Review correction P3: current architecture describes `/reel/` and `/p/`; Reel-only
  statements are historical. The later narrow live `/p/`/album acceptance is recorded below; PR #56 re-review completed above.
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
  Live `/p/`/album gates were still open at that stage; see the later acceptance below.
- Immutable-source follow-up: freeze the original count and ordered ItemEvidence
  before mapping, then compare every mapped identity, kind, evidence signal and
  availability flag with those initial facts. Do not derive expectations from a
  source list that upstream may have mutated. Eleven synthetic mutation scenarios
  cover inspection and handler refusal without acquisition, media sends or repeat
  extraction. These are mapper fault-injection cases, not observed upstream mutation
  or a live exploit. PR #56 subsequently passed repeat review; the later live acceptance is recorded below.
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
- [x] Independently review and merge PR #57 at `13da14d6f1ea9378d776543c94b22b7b716630d3`; post-merge CI #39151964361 SUCCESS. Separately deploy only bot with rollback retained; no live test was initiated during deployment.

### Owner-confirmed Instagram live acceptance — 2026-10-18

- [x] Single-video `/p/`: full share link accepted without the prior refusal; video delivered and played normally. Processing was subjectively sufficiently fast, not timed.
- [x] Carousel: previously rejected full share link delivered all three videos in one album, original order preserved, normal playback, all silent as in the originals.
- Evidence is the owner's real use of the running bot at `13da14d6...`, not another offline or provider-only experiment. Exact URLs/query combinations, sizes, times, codecs, request counts and cleanup telemetry were not recorded.
- Broader publication types, mixed-media delivery, client/device coverage, larger/multi-batch albums, size boundaries, recovery, concurrency and production capacity remain open. No limits or activation defaults change.
- See [the evidence and limits](TESTING.md#instagram-live-acceptance-2026-10-18). This docs-only stage performs no new platform calls or Docker operations.

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
The PR #56 corrections performed no environment change, restart, polling or live call
during implementation; later deployment and acceptance are recorded separately above.
See DEVELOPMENT.md for the controlled procedure.

Share-link correction verification: net +34 cases; Reel handler 66 passed; combined
handler/config/bot suite 176 passed; full pytest 1268 passed, 1 skipped with network
connections forbidden. Ruff lint/format, diff, documentation and scope/security PASS.
Existing YouTube and local FFmpeg/ffprobe regressions passed; no live calls or deployment.

Reel MVP verification: 32 new cases; focused 142 passed; full 1234 passed, 1 skipped.
Ruff lint/format, diff, documentation and security/scope review PASS; no live requests.

## Phase 6 - TikTok Provider

- [x] Inspect tt-dlp `08a1f42` sources/tests and MIT license; retain attribution.
- [x] Prepare separate native embed resolver/acquisition CLI with explicit source
  identity, constrained video-host/DNS/TLS/redirect policy, operation-local cookies,
  bounded streaming, complete framing and owned worker/workspace cleanup. Keep
  PR #59 and production providers/handlers/DownloadService unchanged.
- [x] Verify offline with synthetic HTTP, local FFmpeg fixtures and socket denial;
  44 focused cases and full suite 1514 passed / 1 external opt-in skipped.
  Ruff lint/format, diff, MIT attribution and security/scope checks pass; exact-head
  CI is checked after publication. See [TESTING](TESTING.md#phase-6c-native-tiktok-offline).
- [x] First separately authorized native A/B run: A refused as `unsupported_photo`
  after one metadata response; no media GET, B not run, cleanup confirmed. This
  is not evidence of a real photo layout because HTML was not retained.
- [x] Fix key-presence photo detection offline: permit null/empty object/array
  placeholders only with independently valid video data; refuse populated image
  data and unknown/conflicting structures. Offline verification: 72 focused cases,
  full suite 1542 passed / 1 skipped, Ruff and scope review pass. See Phase 6C in TESTING.
- [x] Separately authorized A/B retest on `85ab929`: A complete MP4 (1,097,768 bytes),
  one video/audio stream, decode and passthrough PASS; B metadata PASS / media 403.
  Two metadata and two media requests, 5.149 s, exact counters and cleanup PASS.
  Fixed codec labels were not independent codec measurements; 403 cause is unknown.
- [x] Add bounded safe CDN/source/request diagnostics and actual existing-probe
  codec names offline, without changing network or preparation behavior.
  Verification: 85 focused passed, full offline suite 1555 passed / 1 skipped,
  Ruff and differential scope review PASS. See Phase 6C of TESTING.
- [x] One separately authorized B-only diagnostic retest on `f3213d6`: metadata
  PASS, one `urls` candidate / tiktokcdn-eu.com, query present, cookies not sent,
  media HTTP 403 / zero bytes. 1.788 s, exact counters and cleanup PASS. Cause unknown.
- [x] Compare media-source semantics with pinned tt-dlp/Cobalt and installed yt-dlp;
  retain `video.urls` as an uncertain supported source, without network fallback.
- [x] Prepare explicit offline benchmark mode: at most four independent owner-approved
  videos, per-case audio expectation, continuation after case-local errors, shared
  original budgets and cleanup. Ordinary fail-fast remains available. Focused: 103 PASS;
  full offline suite 1573 passed / 1 skipped, Ruff and scope checks PASS. See TESTING.
- [x] Separately authorized four-new-publication reliability benchmark on `511b538`:
  4/4 complete MP4, H.264/AAC, one video/audio stream, decode/preparation passthrough.
  Metadata 4 requests / 1,142,585 bytes; media 4 requests / 14,460,237 bytes;
  4 acquisitions, 19.152 s, exact counters, cleanup PASS. This small sample is not
  general platform reliability; earlier B's repeated 403 remains unexplained.
- [x] Owner authorized an isolated Phase 6D offline implementation on a new stacked
  branch, without modifying PR #60/main or activating Telegram. Extract one shared
  engine, keep CLI/benchmark, add standard-video/silent-capable TikTokProvider and
  dispatcher-local restricted handler. Default-off dev/test flag, deny-empty user
  allowlist, owned file lifetime, bounded upload and cancellation/group cleanup.
- [x] Deterministic Phase 6D validation: 143 focused cases pass with external sockets
  denied, including existing CLI/benchmark and fake Telegram delivery/failures.
  Full offline/quality and exact-head CI evidence: [TESTING](TESTING.md).
  Architecture/security and protected environment reviewed in the same change.
- [x] Separately authorized controlled Telegram attempts on PR #61 started polling
  and processed one owner message each, then stopped on embed metadata HTTP 429;
  one metadata request per attempt, no media GET/acquisition/upload, exact counters
  and process/session/workspace cleanup. No delivery in those embed attempts;
  subsequent public-page Phase 6G delivery passed as recorded below.
- [ ] Complete independent Phase 6D review before broader activation. See
  [Phase 6D](PHASE6D_TIKTOK_TELEGRAM.md); initial offline checks are not live delivery.
- [x] Validate restricted real Telegram delivery through the subsequent public-page
  Phase 6G path below. The old embed failures remain; broader activation, production
  readiness and wider TikTok UX/quality support are not accepted by this one case.
- [x] Phase 6E source comparison: standalone and Telegram have identical shared
  transport/canonicalization; tracking queries are removed. No client-side cause
  of HTTP 429 established. Public-page universal-state schema corroborated by
  installed yt-dlp 2026.08.19 and pinned Cobalt source research (no AGPL code copied).
- [x] Prepare an isolated explicit public-page parser/session prototype, source ID
  before media admission, existing bounded transport and no media GET/fallback or
  handler/CLI change. 45 new focused PASS, full offline suite 1658 passed / 1 skipped;
  Ruff, diff/documentation and scope/security PASS. Evidence: [TESTING](TESTING.md).
- [x] Separately authorized Phase 6E metadata-only experiment on `4265328`: HTTP 200,
  matching source ID, one admitted `playAddr`, 1 request / 405,981 bytes, 2.632 s,
  exact counters and cleanup PASS. No media GET in that gate; see later Phase 6F below.
  See [Phase 6E](PHASE6E_TIKTOK_PUBLIC_PAGE.md).
- [x] Implement and verify Phase 6F offline: explicit one-publication `--public-page`
  acquisition using the same transport, verifier and process supervisor. Preserve
  metadata-only inspection and all embed/provider/Telegram paths. 20 new / 208 focused
  PASS, full offline 1678 passed / 1 skipped, six supplemental fault injections,
  Ruff and scope/security PASS. Exact-head publication CI is required before handoff. See
  [Phase 6F](PHASE6F_TIKTOK_PUBLIC_PAGE_MP4.md).
- [x] Separately authorized Phase 6F MP4 test on `f31fdb5`: complete 571,013-byte MP4,
  matching source ID, one playAddr, H.264/AAC, 576×1024, 12 s per CLI, full decode and
  passthrough PASS. One metadata request / 410,890 bytes, one media request (200),
  one acquisition, 5.506 s, exact counters and cleanup PASS. No Telegram delivery.
- [x] Implement and verify Phase 6G offline: internal public-page export to caller
  workspace, existing provider/handler with silent support, no embed fallback.
  19 new cases / 226 focused PASS, full offline 1696 passed / 1 skipped; Ruff,
  diff-check and scope/security PASS. Exact-head CI is required before handoff. See
  [Phase 6G](PHASE6G_TIKTOK_PUBLIC_PAGE_TELEGRAM.md).
- [x] Owner-authorized Phase 6G LIVE PASS on `5896383`: one queued owner message,
  public-page metadata / matching ID, one media GET (200), complete 571,013-byte
  H.264/AAC MP4, full decode and passthrough. One confirmed sendVideo; owner confirmed
  normal playback, correct orientation and sound. Metadata 1 request / 411,812 bytes,
  media 1 request / 571,013 bytes, one acquisition, 5.432 s handler/delivery, exact
  counters and worker/session/private/caller workspace cleanup PASS. Bot stopped;
  containers remained exited, no retry, fallback, merge or deployment.
- [x] Owner-authorized sequential merge of PRs #60–64 completed at main `fe59c1d`;
  exact final main CI passed (1696 passed / 1 skipped). No deployment followed.
- [x] Phase 6H offline public MVP: remove TikTok test-user/production guards, retain
  the default-off flag, add bounded process capacity (default two, one per user),
  independent ownership/cancellation and fail-closed cleanup. 356 focused PASS, full
  offline 1716 passed / 1 skipped, Ruff/diff/security PASS. Publication requires exact-
  head Draft PR CI before handoff; see [Phase 6H](PHASE6H_TIKTOK_PUBLIC_MVP.md).
- [x] Owner-authorized Phase 6H PUBLIC TIKTOK LIVE PASS on `6665b90`: one second-account
  full-link request without personal allowlist; public-page metadata/source ID, one
  complete 565,847-byte MP4 (HTTP 200), H.264/AAC, full decode/passthrough and one
  confirmed sendVideo. Owner confirmed playback, orientation and sound. Polling/session,
  worker and workspace cleanup PASS; Docker stayed exited, no retry/fallback/deployment.
  The approved queued update was read without acknowledgement/deletion; restart replay
  prevention was not tested. See
  [Phase 6H evidence](PHASE6H_TIKTOK_PUBLIC_MVP.md#owner-confirmed-public-tiktok-live-pass).
- [x] Final PR #65 docs-only preparation: LIVE evidence recorded without private data,
  final diff/security review PASS, full network-blocked pytest 1716 passed / 1 skipped
  (186.73 s), Ruff/diff PASS and 30 local links/anchors PASS. Exact documentation-head
  CI passed on documentation HEAD `a662406` before handoff.
- [x] Owner-authorized PR #65 merge completed at main `fc78686`, post-merge CI SUCCESS.
  No deployment followed. The one full-link case does not prove short-link support,
  all-publication support, scalability, general reliability or production readiness.
- [x] Phase 6I offline short-link support: pure vm/vt admission, resolution inside the
  existing supervised public-page operation after slot reservation, bounded pinned
  redirects, shared metadata budget/cookies, no retry or Embed fallback. 53 targeted
  PASS; full network-blocked 1769 passed / 1 skipped, Ruff/diff/privacy/security/link
  checks PASS. Exact Draft PR HEAD CI is required before handoff; see
  [Phase 6I](PHASE6I_TIKTOK_SHORT_LINKS.md).
- [x] Owner-authorized SHORT-LINK LIVE PASS on `b08f57d`: one new mobile-app `vm`
  share link, HTTP 301 redirect, validated full publication/source ID, public-page
  metadata HTTP 200, one `playAddr`, complete 1,049,546-byte MP4 via HTTP 200.
  H.264/AAC (one video/one audio), 720×720, 14 s, full decode and passthrough PASS;
  one confirmed sendVideo and owner playback/orientation/sound PASS. Metadata
  2 attempts / 415,102 bytes, media 1 attempt, one acquisition, exact counters,
  native 3.409 s. Polling/session, worker/FFmpeg and workspace cleanup PASS;
  containers stayed exited, no retry/fallback/merge/deployment. Old updates were
  preserved unacknowledged by explicit owner approval; restart replay was not tested.
  See [Phase 6I live evidence](PHASE6I_TIKTOK_SHORT_LINKS.md#owner-confirmed-short-link-live-pass).
- [x] Final PR #66 documentation and code/scope review: no new defect found;
  full network-blocked pytest 1769 passed / 1 skipped (219.88 s), Ruff/diff/privacy
  and local links PASS. Only docs changed; exact documentation-head CI is required
  before handoff and recorded in GitHub checks.
- [x] Independently merge PR #66 at main `389258cee9cf966be531ae5d6d60b192a59bcdb2`;
  post-merge [CI #39517532808](https://github.com/ip52rus/social-video-downloader/actions/runs/39517532808)
  SUCCESS. Prepare the new bot image and preserve the old image under the rollback
  tag; see [deployment configuration](DEVELOPMENT.md#deployed-public-tiktok-configuration).
- [x] Complete the separately authorized Cloud-to-Local Bot API transition: cloud
  logout SUCCESS and internal Local API getMe PASS. Start only the updated bot;
  preserve the Local API container and named volume. Public TikTok true/2,
  Instagram enabled, APP_ENV=development, one polling instance; both services RUNNING.
- [x] Stage D PUBLIC DEPLOYMENT ACCEPTED: one TikTok short link, one Instagram Reel
  and one YouTube video delivered through the deployed bot. The owner confirmed
  full playback, orientation and sound for each. Worker/workspace cleanup PASS;
  no restart/OOM/runtime errors observed, rollback image retained. Detailed HTTP,
  byte and latency counters were not measured in this smoke stage; see
  [Stage D evidence](TESTING.md#public-deployment-stage-d-acceptance).
- [x] Persist only TikTok true/2 in the existing local protected, Git-ignored `.env`;
  preserve other values and mode 0600. Compose validation without shell overrides
  confirms future standard recreation retains true/2. No restart, recreation or
  new platform request was performed for this finalization; services remain running.

Live short-link evidence covers `vm`; `vt` remains offline-only. Broader mobile-link
coverage, high-load behavior and general TikTok reliability remain unverified;
historical HTTP 429/403 are not universally resolved. This documentation branch
requires exact-head CI and a separate merge decision; it does not redeploy the bot.

### Targeted TikTok metadata refusal diagnostics (2026-10-25)

- [x] Preserve native refusal detail through one fixed, allowlisted WARNING event
  per failed export; keep the existing domain error and user copy unchanged.
- [x] Record observed failure stage and bounded metadata HTTP status/body counters,
  with missing worker reports/counters explicitly unknown; no extra HTTP requests.
- [x] Verify offline regression: 46 new tests, 379 focused passed, full suite
  2783 passed / 1 skipped; Ruff lint/format, diff, privacy and new-link checks pass.
  Exact-head GitHub CI is a publication gate, reported on the Draft PR.
- [x] Record PR #81 merge at b55a019, post-merge CI #40231655683 SUCCESS and
  separately authorized bot-only deployment. Diagnostics remain enabled.
- [ ] Preserve the unresolved exact codes of the original five historical failures; later
  three-request diagnostics/network-exit observations do not reconstruct those codes.
  Original internal codes remain
  UNKNOWN. Later three missing-state refusals, one metadata-only UNKNOWN result and
  the owner-confirmed network-dependent success are recorded in the
  [chronology](TESTING.md#subsequent-deployment-and-live-observations). No parser or
  universal TikTok availability fix is claimed.

See [diagnostic contract](TIKTOK_METADATA_DIAGNOSTICS.md) and
[offline evidence](TESTING.md#tiktok-metadata-refusal-diagnostics).
This diagnostic change does not itself close acceptance; the separate Phase 8
owner decision is recorded below. Phase 9 reliability remains OPEN.

## Phase 7 - Additional Social Platforms

- [ ] Select candidate platforms based on user demand, feasibility, legal/platform restrictions, extraction reliability, and maintenance burden.
- [ ] Run a technical spike for each candidate platform.
- [ ] Make an explicit Go/No-Go decision for each candidate before implementation.
- [ ] Implement only viable providers.
- [ ] Validate each provider with deterministic and scoped external checks.
- [ ] Integrate viable providers into the common Telegram UX.

Do not promise universal platform support or hard-code a long unsupported platform list into product claims.

## Phase 8 - Unified Product UX

E1a was merged in PR #75; E1b interface localization merged in PR #76.
E2 YouTube choice text/keyboard synchronization merged in PR #77. E3 safe
pre-binding and minimal request cards merged in PR #78. E4 merged in PR #79 at
177f11e and was separately deployed. E5 merged in PR #80 at 082986e and was
separately deployed; post-merge CI #40184267688 SUCCESS. The owner decision on
2026-10-26 is **PHASE 8 MVP — ACCEPTED WITH DOCUMENTED LIMITATIONS**.
See [final acceptance](PHASE8_UX_ACCEPTANCE.md#final-mvp-owner-acceptance--2026-10-26).
Phase 9 remains OPEN; the historical Phase 8 acceptance did not authorize its next work.

- [x] Implement and verify inactive E1a: safe EN/RU/ES resolver, ContextVar middleware, compiled package
  catalogs and backward-compatible presentation locale in pending records. Telegram
  handlers/copy/routing/media were unchanged at E1a verification; see
  [foundation contract](INTERNATIONALIZATION.md) and
  [verification](TESTING.md#phase-8-e1a-internationalization-foundation): 136 new cases,
  full offline 2200 passed / 1 skipped; installed wheel resources and quality gates PASS.
- [x] Merge E1a PR #75; post-merge CI #40078428913 SUCCESS on efb4f324. No E1a deployment.
- [x] Separately authorize E1b automatic interface localization.
- [x] Complete E1b offline acceptance: 68 user-facing entries, EN/RU/ES catalogs,
  sender middleware, validated pinned callbacks and unchanged media/API contracts.
  286 new cases; full offline 2487 passed / 1 skipped; wheel/catalog and quality gates PASS.
  See [contract](INTERNATIONALIZATION.md) and [translation review](TRANSLATIONS.md).
- [x] Merge E1b PR #76 at 08d726d; post-merge CI #40085827763 SUCCESS.
  E1b excluded /language, profile mutation, E2 text synchronization and E3 pre-binding.
- [x] Complete E2 offline acceptance: one translated quality prompt plus keyboard edit
  on the same YouTube message; pinned locale, unchanged callback/selection/media budgets,
  ambiguous-edit recovery and one-shot delivery. Six new cases; focused 540 passed,
  full offline 2493 passed / 1 skipped; quality/privacy checks PASS. See
  [E2 verification](TESTING.md#phase-8-e2-youtube-choice-ux).
- [x] Merge E2 PR #77 at b7462f8 after the separate owner decision;
  post-merge CI #40110968231 SUCCESS. This does not establish LIVE acceptance.
- [x] Record final owner confirmation of Video/Audio and quality selection on the
  deployed MVP; this is later LIVE evidence, not a test performed by E3.
- [x] Complete E3 offline acceptance: fail-closed message binding; noninteractive
  receipt → confirmed binding → prompt/keyboard edit; durable accepted-request
  text on terminal selection and direct download. 58 new offline cases, 583
  UI/packaging subset PASS; extended metadata/cache/parity/cancellation focused
  set: 702 passed; full offline: 2551 passed / 1 skipped. See
  [E3 verification](TESTING.md#phase-8-e3-pre-binding-and-status-cards).
- [x] Merge E3 PR #78 at bbfdf85; post-merge CI #40123097002 SUCCESS.
- [x] Record owner-confirmed E3 LIVE PASS, supplied with E4 authorization. Exact
  case counts, timings and language/client coverage were not supplied. This is
  separate owner evidence and does not close Phase 9 reliability.
- [x] Preserve five newly damaged historical TikTok worktrees in a verified private
  checkpoint; resume E4 by owner authorization, without restoration. Cause and
  historical untracked/ignored loss remain UNKNOWN. Add the permanent worktree
  rule to AGENTS.md and development guidance for all future tasks.
- [x] Complete E4 offline acceptance: one localized /start, typed YouTube terminal
  outcomes, best-effort existing-card edits, serialized UI updates and minimal
  Instagram prompt retirement. See
  [E4 verification](TESTING.md#phase-8-e4-terminal-ux-and-start).
- [x] Merge E4 PR #79 at 177f11e; exact-head CI #40139859877 and post-merge
  CI #40178485535 SUCCESS. A separate authorized bot-only deployment succeeded;
  the later E5 deployment is recorded separately below.
- [x] Record owner E4 LIVE PASS: one short /start, correct available-platform list,
  YouTube video delivery and “✅ Файл отправлен.” without old buttons. Client,
  sample count, EN/ES and other platform coverage were not supplied. See the
  [evidence ledger](PHASE8_UX_ACCEPTANCE.md#owner-live-evidence-ledger).
- [x] Complete E5 offline acceptance: final handler/localization review, available-
  platform error guidance, actionable Instagram stale refusal and restart/new-request
  regression. 79 new cases; focused 693 passed; full offline 2737 passed / 1 skipped. See
  [E5 verification](TESTING.md#phase-8-e5-final-ux-acceptance).
- [x] Record E5 merge PR #80 at 082986e, post-merge CI #40184267688 SUCCESS and
  separately authorized bot-only deployment; offline evidence stays separate.
- [x] Record final owner LIVE PASS for YouTube selection/delivery/terminal card,
  one Instagram Reel and common greeting/unsupported-link UX; RU is LIVE-checked.
- [x] Record owner TikTok PASS after changing VPN exit to the Netherlands, following
  missing-state failures through the reported Kazakhstan exit; retain failures and
  diagnostics. Network-egress dependence is observed, exact cause is not proven.
- [x] Explicitly accept/defer the bounded
  [remaining manual matrix](PHASE8_UX_ACCEPTANCE.md#remaining-manual-acceptance-matrix)
  as MVP limitations at that date: EN/ES LIVE, then-untested VPS TikTok egress, other carousel/client
  combinations, load/recovery and stale post-restart cards. Do not repeat confirmed
  journeys without a concrete regression or relabel untested cases as LIVE PASS.
- [ ] Separately decide whether durable ownership/message binding for visual cleanup
  after restart is required. No persistence, recovery or background cleanup is
  implemented; stale callbacks are safely refused without another download.

The unchecked UX ideas below remain deferred backlog beyond the owner-accepted
MVP. They do not block its scoped acceptance or imply universal client coverage;
provider-specific capabilities are intentionally preserved.

- [x] Review the complete multi-provider Telegram UI offline; see the E5 journey review.
- [ ] Standardize inline keyboards.
- [ ] Present modes and quality options consistently across providers.
- [x] Review all bot messages, including removing or updating obsolete video/audio choice
  prompts after selection; known consumed prompts are retired. Unvalidated restart
  cards remain the documented separate design limit.
- [ ] Standardize loading and waiting messages.
- [ ] Standardize success messages.
- [ ] Standardize unsupported-content messages.
- [ ] Standardize retry and error states.
- [ ] Keep provider-specific exceptions only where necessary.
- [ ] Finalize consistent naming and button copy.
- [x] Perform the E5 interaction-flow review offline; the later owner MVP acceptance
  and its retained manual gaps are recorded above.

## Phase 9 - Production Reliability

Status: OPEN; not closed by Phase 4 functional acceptance.

### Phase 9C — shared limits and download protection

Status: **LOCAL ACCEPTED**. PR #83 is merged; local deployment passed on
2026-10-26 and the owner reported **5/5 LIVE PASS** on 2026-10-28.
General Phase 9 stays **OPEN**.
Later HOSTKEY migration remains a separate technical event.

- [x] Replace Telegram Instagram's historical 25 MiB/file gates with shared validated
  file/request/workspace/free-disk budgets and endpoint-aware upload ceiling; retain
  ten-video count, identity/format guards, deadlines and retry prohibition.
- [x] Count actual streamed bytes without trusting Content-Length; propagate budgets
  through Reel, single-post, carousel acquisition/preparation/delivery.
- [x] Reserve one unfinished request per user across YouTube/Instagram/TikTok before
  metadata, including waiting choices, delivery, worker drain and safe cleanup.
- [x] Separate bounded user/pending leases from actual global workers; waiting
  choices occupy no worker. Busy callbacks preserve the choice without extraction
  or consume; metadata/download/prepare/delivery/cleanup share worker capacity.
- [x] Bound YouTube native writes/reads during acquisition and current FFmpeg outputs
  during merge/preparation, using endpoint-aware defaults independent of 512 MiB.
  Drain owned processes before cleanup; uncertainty preserves the root and quarantine.
- [x] Throttle repeated link-refusal messages after the first localized response.
- [x] Add bounded global admission without a queue, short per-user link cooldown,
  localized refusals and `/cancel` for idle waiting choices only; preserve original
  15-minute expiry, ownership/binding, pinned locale and one-shot consumption.
- [x] Retain shared reservations on cleanup quarantine, including repeated cancellation
  and overlapping publication/callback contexts; no automatic recovery/retry.
- [x] Merge [PR #83](https://github.com/ip52rus/social-video-downloader/pull/83)
  with its review corrections as `f74dc6c933012b809d4e6dc33ed3f3bdadc39d34`;
  implementation exact-head [CI #40327275768](https://github.com/ip52rus/social-video-downloader/actions/runs/40327275768)
  and post-merge CI #40333460016 SUCCESS.
- [x] Complete separately authorized bot-only local deployment on 2026-10-26:
  TECHNICAL PASS; Local Bot API/configuration/volume preserved, rollback image
  prepared but rollback not executed.
- [x] Record owner LIVE acceptance on 2026-10-28: 5/5 PASS for rejection during
  YouTube choice/download, waiting-choice `/cancel`, YouTube delivery/playback
  and delivery/playback of one Instagram video above 25 MiB.
- [x] Record HOSTKEY cutover TECHNICAL PASS 2026-10-28, one VPS poller, local bot/API
  retained stopped; do not label it a second full platform/load/recovery acceptance.

See [design, defaults and limits](PHASE9C_DOWNLOAD_PROTECTION.md) and
[offline verification](TESTING.md#phase-9c-shared-limits-and-admission-offline),
[local deployment](TESTING.md#phase-9c-local-deployment-2026-10-26) and
[owner acceptance](TESTING.md#phase-9c-owner-live-acceptance-2026-10-28).
Historical smaller-file and platform LIVE evidence below is unchanged. Local
acceptance does not establish near-2 GB delivery, arbitrary-downloader/RSS isolation,
load/failure-recovery readiness or universal platform reliability.

- [x] Phase 9A read-only baseline: inspect current main/worktrees and unchanged running
  Docker services, restart/OOM, one-shot CPU/RAM/disk and logging-driver settings.
  Record legacy sensitive log markers without exposing payloads; see
  [baseline and safe events](DEVELOPMENT.md#phase-9a-operational-baseline-and-safe-events).
- [x] Implement minimal fixed-field events for YouTube, Instagram Reel/posts and
  TikTok, monotonic durations, safe typed failures and service/polling lifecycle.
  Remove verbose YouTube probe/path/response/traceback logs and direct yt-dlp stderr;
  suppress unstructured library output at the configured sink. Preserve existing
  user messages, request counts/retries, admission, cancellation, cleanup/quarantine.
- [x] Verify Phase 9A offline privacy, lifecycle, sink-failure and regression checks;
  355 focused PASS, full 1802 passed / 1 skipped (224.16 s), Ruff/diff/privacy and
  47 local links PASS; evidence in [TESTING](TESTING.md#phase-9a-safe-operational-events-offline).
- [x] Complete Phase 9A independent review, exact-head CI and merge (PR #68).
  The safe operational events were subsequently deployed to the existing main bot in a
  separately authorized rollout. Structured events were observed in the 2026-10-22
  [read-only post-LIVE check](TESTING.md#instagram-item-selection--live-acceptance-2026-10-22);
  broader reliability and Phase 9B operational acceptance remain open.
- [x] Phase 9B offline baseline confirmed synchronous YouTube metadata blocks the
  event loop; the subsequent snapshot feasibility gate passed for the investigated
  VOD formats. Neither gate changed production code or deployed a metadata worker.
- [x] Fix the separately reproduced YouTube cancellation/workspace race: retain
  ownership of download, audio/video preparation and video-probe executor work until
  it finishes, including after repeated cancellation. Cleanup follows worker completion;
  cancellation never starts another stage or media send. See
  [offline cancellation verification](TESTING.md#youtube-cancellation-safety-offline).
- [x] Merge cancellation safety as [PR #72](https://github.com/ip52rus/social-video-downloader/pull/72);
  post-merge main `01ffe0e` CI #39845155273 SUCCESS. This is source/CI evidence,
  not deployment evidence by itself; PR #72 is included in the later Phase 9B rollout
  recorded below. That historical legacy-thread limit predates Phase 9C owned acquisition; preparation
  executor work still must drain before cleanup.
- [x] Phase 9B metadata subprocess: implement and locally verify one admitted POSIX
  child, bounded private snapshot IPC, synchronized cache, off-loop planning and
  process-group cleanup/quarantine. See
  [metadata verification](TESTING.md#phase-9b-bounded-youtube-metadata-offline):
  94 new / 377 focused PASS; full offline 2064 passed / 1 skipped, 338.42 s.
- [x] Complete independent read-only review of [PR #73](https://github.com/ip52rus/social-video-downloader/pull/73):
  READY FOR MERGE, no confirmed BLOCKER/HIGH/MEDIUM findings or required corrections;
  code/diff/tests/CI review without new dynamic measurements. Exact source-head CI
  #39857426360 SUCCESS; merged main `04a07ba`, post-merge CI #39928312040 SUCCESS.
- [x] Complete separately authorized bot-only deployment on 2026-10-23: TECHNICAL PASS.
  One replacement, one polling consumer, RUNNING, restart 0 / OOM false; Local Bot API,
  volume and configuration preserved. Rollback prepared, not executed or rehearsed.
- [x] Record one owner-controlled two-account LIVE functional smoke on 2026-10-23:
  PASS for YouTube metadata/format choices and the expected stale-button notification.
  No final download option was selected; no media was intentionally started by these
  user actions. No retry. See [review, deployment and LIVE evidence](TESTING.md#phase-9b-review-deployment-and-live-acceptance-2026-10-23).
- [ ] Establish LIVE concurrency responsiveness: INCONCLUSIVE in that one attempt.
  Callback/metadata overlap was not proven and callback latency was not measured;
  metadata operation duration of 5.174 s is not callback latency. No repeat authorized.
- [ ] Verify general production reliability, load and recovery independently of this
  narrow smoke; Phase 9 remains OPEN. Historical worktree data UNKNOWN and temporary
  storage risk remain accepted/preserved, not resolved; see the acceptance record.

- [ ] Diagnose intermittent YouTube HTTP 403 and define/test a narrowly bounded recovery
  strategy with explicit attempt limits and no duplicate media delivery.
- [x] Verify removal of initial synchronous YouTube metadata/planning from Telegram's
  event loop, including callback/heartbeat measurements during a synthetic two-second
  inspection: fake callback lateness p50 1960.74 ms before / 1.00 ms after in three
  measurements per path. This is offline scheduling evidence, not real Telegram
  availability. Expired-cache extraction inside the existing download thread is retained.
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
- [x] Add justified minimal link cooldown and repeated Busy notice throttling in Phase 9C; further tuning requires evidence.
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

## Deferred research — TikTok Short Drama

- [x] Preserve prior anonymous/API/OSS/browser experiments and negative evidence.
- [x] Complete S1 offline architecture/normalizer assessment: 86 tests, Ruff PASS, HTTP 0.
- [x] Complete S2 offline request comparison: 15 checks, Ruff PASS, HTTP 0;
  next anonymous LIVE NO-GO, mandatory account authorization UNKNOWN.
- [x] Preserve owner desktop Chrome populated playback evidence without sensitive values.
- [ ] Reopen only after main priorities/new proven permitted mechanism and owner decision.
  No active monitoring, new downloader, repeated GET, auth-cookie integration or production
  support is authorized. [Canonical research](research/TIKTOK_SHORT_DRAMA.md).

## D1 documentation checkpoint

- [x] Reconcile code/Git/CI, Phase 8, Phase 9B/9C and dated HOSTKEY cutover evidence.
- [x] Preserve research conclusions in version-controlled text independent of local folders.
- [x] Add agent reading order, scope/security gates and self-contained chat handoff.
- [x] Verify docs-only scope, links, privacy and unchanged main/19 existing registrations.
- [ ] Independent review/owner acceptance of D1 Draft PR; no merge/deployment implied.
  Exact-head CI is reported on the PR; it does not authorize the next stage.

### D1.2 — local closeout and handoff reconciliation

- [x] Recheck exact PR heads/base/CI and existing main/worktree integrity before changes.
- [x] Merge docs-only PR #84 as `a0d57f253c74aaf563efb456abdf4ae9854eee2b` after explicit authorization.
- [x] Merge that main into the existing #85 branch without rebase/force-push; reconcile
  four documents, retain implementation CI #40327275768, single local evidence ledger,
  HOSTKEY context, Short Drama DEFERRED and complete handoff/agent rules.
- [x] Recheck Markdown/anchors/privacy/diff/docs-only scope and unchanged original checkout.
- [ ] Final independent review/owner decision for #85; exact-head CI is required and
  reported on the PR. No #85 merge, deployment, LIVE or Phase 9 work is authorized here.

### P9-R1b — minimal opt-in concurrency instrumentation

- [x] Owner approved only two extraction monotonic timestamps over the existing metadata IPC.
- [x] Preserve default-off behavior, legacy snapshots/cache/TTL, strict wire budgets and guards.
- [x] Add bounded private correlation and parent observation before callback admission,
  including Busy; separate API round trip from client latency and event-loop scheduling.
- [x] Complete focused offline verification and privacy/performance review: instrumentation **OFFLINE VERIFIED**.
- [x] Address PR #86 overlap-gate review: require FAIL for missing extraction boundaries
  or unproved synthetic overlap; retain INCONCLUSIVE for incomplete real observations.
- Exact-head CI is required on the submitted PR HEAD and reported in its checks; no LIVE result is inferred.
- [x] PR #86 merged as `742bc105e923500fc0b22844bec2809c0c8fbc45`;
  post-merge CI #40952269982 SUCCESS, rechecked during P9-R2d documentation closeout.
- [x] Separately authorized P9-R2d HOSTKEY bot-only deployment: TECHNICAL PASS;
  diagnostics remains false. See [deployment evidence](P9_R2D_DEPLOYMENT.md).
- [x] P9-R2d documentation PR #87 merged as `1aa0943`; post-merge CI #41024517298
  SUCCESS, rechecked at P9-R3a preflight.
- [ ] P9-R2 LIVE responsiveness remains INCONCLUSIVE; do not close this gate from synthetic tests.

See [contract and measurement limits](DEVELOPMENT.md#p9-r1b-opt-in-concurrency-diagnostics)
and [offline proof](TESTING.md#p9-r1b-minimal-concurrency-instrumentation--offline).
