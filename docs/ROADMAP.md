# Roadmap

## Phase 0 - Foundation
GitHub repository, documentation, security baseline, Git workflow, test strategy, and AI-agent rules.
Gate: governance files exist, contain no secrets or personal data, and the repository history is reviewable.

## Phase 1 - Downloader Core
Transport-independent URL validation, provider detection, provider interface, download result model, temporary workspace, safe filenames, errors, logging, and tests.
Gate: core behavior is independently testable without Telegram.

## Phase 2 - YouTube Provider
Move the validated prototype into the provider architecture and test Shorts, separate streams, formats, and failure cases.
Gate: representative integration matrix passes, including relevant success and failure scenarios.

### Verified progress
- The YouTube provider is implemented in the provider architecture.
- Real downloads have succeeded for `VIDEO_WITH_AUDIO`, `VIDEO_ONLY`, and `AUDIO_ONLY` using one public YouTube video.
- `VIDEO_ONLY` and `AUDIO_ONLY` outputs were checked with `ffprobe` for their expected stream types.
- The automated suite passed with 120 tests, and Ruff lint and format checks passed at the last recorded verification.
- These results are initial smoke-test evidence, not completion of the representative provider test matrix.

### Remaining Phase 2 checks
- Validate YouTube Shorts.
- Validate a representative range of available formats and relevant media characteristics.
- Validate provider failure scenarios and distinguish application defects from transient external-platform or network failures.
- Re-run the required automated tests and quality checks after any related implementation changes.

Phase 2 remains in progress until its acceptance gate is satisfied. Do not mark the phase complete or move past its gate based only on the initial smoke tests.

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
