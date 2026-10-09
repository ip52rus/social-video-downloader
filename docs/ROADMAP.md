# Roadmap

## Phase 0 - Foundation
GitHub repository, documentation, security baseline, Git workflow, test strategy, and AI-agent rules.
Gate: governance files exist, contain no secrets or personal data, and the repository history is reviewable.

## Phase 1 - Downloader Core
Transport-independent URL validation, provider detection, provider interface, download result model, temporary workspace, safe filenames, errors, logging, and tests.
Gate: core behavior is independently testable without Telegram.

## Phase 2 - YouTube Provider
Move the validated prototype into the provider architecture and validate Shorts, representative formats/media cases, and failure behavior.
Gate: a representative integration matrix passes, including relevant success and failure scenarios.

### Verified progress
- The YouTube provider is implemented in the provider architecture.
- Real downloads have succeeded for VIDEO_WITH_AUDIO, VIDEO_ONLY, and AUDIO_ONLY using a public YouTube video; ffprobe confirmed the expected stream composition for VIDEO_ONLY and AUDIO_ONLY.
- Shorts were tested in all three download modes for Lmv2jfPNvzE. ffprobe confirmed AV1 video (720×1280) and Opus audio (48 kHz, stereo) for the combined output, video-only output without audio, and audio-only output without video.
- Additional successful Shorts smoke tests were recorded for VF_MOfnz7OY (formats 398+251) and osrN3A_Rdiw (formats 616+251 via HLS, merged output, exit code 0).
- Deno 2.9.7 was detected during the recorded Shorts checks.
- PR #10 fixed a reproduced duplicate audio format ID issue by trying the normalized suffixed ID before the raw ID. A live check of selector 251-0/251 downloaded audio that ffprobe identified as Opus, 48 kHz, stereo.
- The latest recorded automated suite passed with 122 tests. Ruff lint and format checks passed for the changed YouTube provider and its tests.
- GitHub Actions quality passed on PR #10 head commit 5b49c9455a71ec7d562c46db00e12a1172769dd8. A separate CI result for the merge commit was not confirmed.

### Remaining Phase 2 checks
- Validate a representative matrix of available formats and media characteristics beyond the targeted smoke tests already recorded.
- Validate provider failure scenarios and relevant error boundaries, distinguishing application defects from external-platform and transient network failures. Deterministic tests for extractor, download, post-processing, and missing-output failures are being added; their CI result remains pending.
- Re-run the relevant automated tests and quality checks after further provider changes.

Shorts smoke testing is recorded as complete, but Phase 2 remains in progress until the broader format matrix and failure scenarios satisfy the acceptance gate. Do not infer broad provider reliability from a small number of successful URLs.

## Phase 3 - Telegram MVP
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
