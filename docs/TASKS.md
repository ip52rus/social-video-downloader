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
- [ ] Design the complete Telegram interaction flow for download options.
- [ ] Define the inline keyboard and state model.
- [ ] Expose video-with-audio, video-only, and audio-only choices.
- [ ] Expose provider quality selection where available.
- [ ] Preserve automatic/best-option selection.
- [ ] Design loading, progress, and status behavior where justified.
- [ ] Define cancellation and retry behavior if appropriate.
- [ ] Review and standardize user-facing messages.
- [ ] Define consistent error messages.
- [ ] Keep the YouTube options UX minimal and fast.

The current provider architecture already exposes modes and quality options. Phase 4 should connect these capabilities to Telegram UX before redesigning provider internals.

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
