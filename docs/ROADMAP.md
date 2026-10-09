# Roadmap

## Phase 0 - Foundation
GitHub repository, documentation, security baseline, Git workflow, test strategy, and AI-agent rules.
Gate: governance files exist, contain no secrets or personal data, and the repository history is reviewable.

## Phase 1 - Downloader Core
Transport-independent URL validation, provider detection, provider interface, download result model, temporary workspace, safe filenames, errors, logging, and tests.
Gate: core behavior is independently testable without Telegram.

## Phase 2 - YouTube Provider — validation gate passed
The YouTube provider is implemented in the provider architecture. Real regular-video downloads succeeded in all three output modes, a live matrix passed for combined MP4, selected-quality video-only, and two audio containers, and Shorts smoke tests plus deterministic error-boundary/format-layout tests are recorded.
Evidence and limits are documented in TASKS.md and TESTING.md. Live matrix coverage is one regular public URL, not proof of broad reliability.

## Phase 3 - Telegram MVP — in progress
Implement URL -> download -> result without advertising or monetization.
- Complete: validated environment-based settings and deterministic tests.
- Complete: standard-library logging configuration and minimal aiogram bot/dispatcher polling entry point.
- Next: /start and URL intake, then download orchestration, error mapping, and result delivery.
Gate: complete core user flow works in a test bot, including relevant user-facing error cases. Handler tests alone do not satisfy the live Telegram end-to-end gate.

## Phase 4 - Access Control
Require membership in the project's Telegram community and test member, non-member, leave, and rejoin scenarios. Membership is an ongoing condition of access, not a requirement to actively post or participate.

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
