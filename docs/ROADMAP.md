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
- Complete: validated settings, application logging, and minimal aiogram polling entry point.
- Complete: /start and text-based URL intake with deterministic handler tests.
- In implementation: provider-selection service, YouTube download orchestration, safe domain-error messages, Telegram file delivery, and temporary workspace cleanup. The current PR must pass CI before these are considered verified.
- Remaining gate: manually run a public YouTube URL through a real Telegram test bot, confirm the uploaded file is playable, and record relevant failure behavior and setup instructions.
- Instagram and TikTok are recognized but do not have download providers yet.

Gate: complete core user flow works in a test bot, including relevant user-facing error cases. Deterministic tests alone do not satisfy the live Telegram end-to-end gate.

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
