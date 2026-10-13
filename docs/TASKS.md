# Task Decomposition

## Foundation
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

## Downloader Core
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

## YouTube — Phase 2 acceptance gate passed
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

## Telegram MVP — in progress
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
- [ ] Test additional Telegram clients, including iPhone, and record the exact clients tested.
- [ ] Test upload failures and recovery; record relevant Telegram errors and user-facing behavior.
- [ ] Rehearse restart and recovery behavior for the bot and Local Bot API Server.
- [ ] Rehearse cloud-to-local migration and local-to-cloud rollback with a separate test bot; do not treat `close` as an official local-to-cloud rollback procedure.
- [x] Verify Dockerized YouTube extraction runtime: the bot image includes Deno 2.9.7,
  yt-dlp detects `deno-2.9.7`, controlled metadata/simulation succeeds, and the project
  metadata path succeeds inside the image and Compose bot runtime.
- [ ] Increase test-file sizes cautiously and document actual limits; do not claim support up to 2 GB based on the current 414.7 MB test.
- [ ] Document the full test-bot setup and end-to-end procedure.

The automated checks for provider selection and the mocked Telegram download/delivery flow passed in [GitHub Actions run 37974061474](https://github.com/ip52rus/social-video-downloader/actions/runs/37974061474). PR #27 media-preparation validation adds deterministic coverage for verified stream-copy remux and remux-failure fallback plus real local FFmpeg evidence using synthetic media: compatible MP4 passthrough, H.264/AAC MKV-to-MP4 stream-copy remux without `libx264`, and incompatible-source transcode fallback all passed. The remux check confirmed encoded H.264 and AAC packet payload hashes and decoded video hashes matched; exact decoded AAC checksum differed because of container/timestamp/priming interpretation. Containerized YouTube runtime validation confirmed the bot image exposes pinned Deno 2.9.7 to yt-dlp, raw yt-dlp uses `[jsc:deno]`, controlled metadata/simulation succeeds, and the project metadata path succeeds in the image and Compose bot runtime. A live Local Bot API Server test adds real-delivery evidence: a short video and an MP4 file of approximately 414.7 MB were delivered, and the large file was confirmed playable. This does not close all Phase 3 criteria: additional client checks, upload failure/recovery behavior, restart/recovery validation, cloud/local rollback rehearsal, justified larger-file tests, and a reproducible end-to-end procedure remain outstanding. Instagram and TikTok links are recognized but their download providers are not implemented.

## Access control — separate Phase 4
- [ ] Define required Telegram community.
- [ ] Implement membership check.
- [ ] Test member, non-member, leave, and rejoin behavior.
- [ ] Fail closed on membership-check errors where appropriate.
