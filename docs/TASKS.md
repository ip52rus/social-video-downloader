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
- Live matrix run on 2026-10-09 for https://www.youtube.com/watch?v=dQw4w9WgXcQ:
  `YOUTUBE_LIVE_TEST_URL='https://www.youtube.com/watch?v=dQw4w9WgXcQ' uv run pytest tests/integration/test_youtube_live_matrix.py -q -s` → `1 passed in 140.06s`.
- The live test downloaded combined video/audio MP4, selected-quality video-only output, and audio-only outputs in two distinct containers. ffprobe checks passed for actual stream composition, codec identification, video dimensions, audio sample rate, and expected audio containers.
- Shorts https://www.youtube.com/shorts/Lmv2jfPNvzE (20 seconds) was tested in all three modes. ffprobe confirmed AV1 video (720×1280), Opus audio (48 kHz, stereo), and the expected stream composition in each mode.
- Additional successful Shorts smoke tests were recorded for VF_MOfnz7OY using formats 398+251, and osrN3A_Rdiw using 616+251 via HLS. The latter was merged to an MP4 output; recorded process exit code was 0.
- Deno 2.9.7 was detected during the recorded Shorts checks.
- The duplicate audio format ID issue was reproduced and fixed in PR #10. Selector 251-0/251 downloaded audio successfully; ffprobe confirmed Opus, 48 kHz, stereo.
- Deterministic tests cover metadata extractor errors, generic download failures, post-processing failures, missing final output, temporary-workspace cleanup, and five format-layout cases.
- GitHub Actions run [37966225469](https://github.com/ip52rus/social-video-downloader/actions/runs/37966225469) passed 131 tests and Ruff lint/format checks on merge commit `f27051fded257b5f39056c45333b4fa8c50075a3`.

The Phase 2 gate is satisfied by the combined live matrix and deterministic failure-boundary coverage. Scope limitation: the live matrix was run against one regular public video, so this is not a claim of broad reliability across every YouTube format, restriction, or transient platform condition.

## Telegram MVP — in progress
- [x] Add validated environment-based application settings for the Telegram bot token, environment name, and log level.
- [x] Add deterministic tests for required configuration, defaults, normalization, invalid values, token redaction in repr, and immutability.
- [ ] Configure application logging from settings.
- [ ] Create the aiogram bot/dispatcher entry point.
- [ ] Implement /start and URL intake.
- [ ] Connect URL validation/provider selection to the download service.
- [ ] Implement progress/state handling and result delivery.
- [ ] Map expected domain errors to safe user-facing messages.
- [ ] Test handler logic with mocked Telegram interactions.
- [ ] Perform a manual test-bot end-to-end flow for a public YouTube URL.
- [ ] Document setup and run instructions.

## Access control — separate Phase 4
- [ ] Define required Telegram community.
- [ ] Implement membership check.
- [ ] Test member, non-member, leave, and rejoin behavior.
- [ ] Fail closed on membership-check errors where appropriate.
