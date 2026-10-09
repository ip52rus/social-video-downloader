# Roadmap

## Phase 0 - Foundation
GitHub repository, documentation, security baseline, Git workflow, test strategy, and AI-agent rules.
Gate: governance files exist, contain no secrets or personal data, and the repository history is reviewable.

## Phase 1 - Downloader Core
Transport-independent URL validation, provider detection, provider interface, download result model, temporary workspace, safe filenames, errors, logging, and tests.
Gate: core behavior is independently testable without Telegram.

## Phase 2 - YouTube Provider — validation gate passed
Move the validated prototype into the provider architecture and validate Shorts, representative formats/media cases, and failure behavior.
Gate: a representative integration matrix passes, including relevant success and failure scenarios.

### Verified progress
- The YouTube provider is implemented in the provider architecture.
- Real regular-video downloads succeeded in VIDEO_WITH_AUDIO, VIDEO_ONLY, and AUDIO_ONLY modes.
- The live format-matrix test passed on 2026-10-09 for public video https://www.youtube.com/watch?v=dQw4w9WgXcQ: combined MP4 with video and audio streams, selected-quality video-only output, and audio-only outputs in two distinct containers. ffprobe verified stream composition and reported codecs plus video dimensions/audio sample rate. Command: `YOUTUBE_LIVE_TEST_URL='https://www.youtube.com/watch?v=dQw4w9WgXcQ' uv run pytest tests/integration/test_youtube_live_matrix.py -q -s`; result: `1 passed in 140.06s`.
- Shorts were tested in all three download modes for Lmv2jfPNvzE. ffprobe confirmed AV1 video (720×1280) and Opus audio (48 kHz, stereo) for the combined output, video-only output without audio, and audio-only output without video.
- Additional successful Shorts smoke tests were recorded for VF_MOfnz7OY (formats 398+251) and osrN3A_Rdiw (formats 616+251 via HLS, merged output, exit code 0).
- Deno 2.9.7 was detected during the recorded Shorts checks.
- PR #10 fixed a reproduced duplicate audio format ID issue by trying the normalized suffixed ID before the raw ID. A live check of selector 251-0/251 downloaded audio; ffprobe confirmed Opus, 48 kHz, stereo.
- Deterministic tests cover metadata extraction errors, download failures, post-processing failures, missing final output, workspace cleanup, and five representative format-layout cases.
- GitHub Actions on merge commit `f27051fded257b5f39056c45333b4fa8c50075a3` passed 131 tests and Ruff lint/format checks. The opt-in live test was added in PR #13 and passed CI as a skip when no URL was configured; a separate local real-platform run is recorded above.

### Gate result and limits
The Phase 2 acceptance gate is satisfied by the combination of the live output-mode/container matrix, previously recorded Shorts and regular-video smoke tests, and deterministic provider error-boundary/format-layout tests. This is targeted acceptance evidence, not proof of broad YouTube reliability: live matrix coverage is one regular-video URL, and platform restrictions, transient failures, and untested media variants remain possible. Re-run the live matrix when making material provider/yt-dlp changes and investigate real user-facing failures as they arise.

## Phase 3 - Telegram MVP — next
Implement URL -> download -> result without advertising or monetization.
Gate: complete core user flow works in a test bot, including relevant user-facing error cases.

## Phase 4 - Access Control
Require membership in the project's Telegram community and test member, non-member, leave, and rejoin scenarios.

## Phase 5 - Instagram Provider
Technical spike, reliability assessment, implementation, and acceptance tests.

## Phase 6 - TikTok Provider
Technical spike, reliability assessment, implementation, and acceptance tests.

## Phase 7 - Production Reliability
Introduce queue, workers, rate limits, storage, retries, monitoring, and cleanup only when justified by workload.

## Phase 8 - Advertising Gateway
Add a separate replaceable monetization layer that can be enabled or disabled without provider changes.

## Phase 9 - Production Hardening
Security, abuse prevention, observability, deployment automation, backup and recovery procedures.
