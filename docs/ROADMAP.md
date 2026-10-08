# Roadmap

## Phase 0 - Foundation
GitHub repository, documentation, security baseline, Git workflow, test strategy, and AI-agent rules.
Gate: governance files exist, contain no secrets or personal data, and the repository history is reviewable.

## Phase 1 - Downloader Core
Transport-independent URL validation, provider detection, provider interface, download result model, temporary workspace, safe filenames, errors, logging, and tests.
Gate: core behavior is independently testable without Telegram.

## Phase 2 - YouTube Provider
Move the validated prototype into the provider architecture and test Shorts, separate streams, formats, and failure cases.
Gate: representative integration matrix passes.

## Phase 3 - Telegram MVP
Implement URL -> download -> result without advertising or monetization.
Gate: complete core user flow works in a test bot.

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
