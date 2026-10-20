# Phase 6H — Public TikTok MVP

## Decision and scope

Phase 6G verified one real public-page download and owner-confirmed Telegram playback,
orientation and sound. PRs #60–64 were merged; this stage changes only admission and
configuration, not the verified downloader. Offline preparation made no real
TikTok/Telegram requests. A subsequent separately authorized public acceptance passed,
as recorded below; merge and deployment remain separate, unauthorized actions.

`TIKTOK_TELEGRAM_ENABLED` remains false by default. When enabled, full supported public
video URLs are available to any Telegram user, including in production configuration.
There is no TikTok test-user list or channel membership requirement. Instagram keeps
its independent restrictions. Short TikTok links remain unsupported.
The Compose template forwards only the feature flag and capacity, retaining false/2
defaults. No running container, real environment file or deployment is changed.

## Admission and ownership

The bot's single dispatcher owns one TikTok handler. Its event-loop-owned active-user
set replaces the single global busy flag. Checking capacity and reserving a user are
synchronous, with no intervening await. The default process capacity is two, at most
one operation per user; `TIKTOK_MAX_CONCURRENT_OPERATIONS` accepts integers 1–8. The
upper bound prevents an accidentally unbounded resource setting. Excess requests
receive an immediate busy response, without a waiting queue or extra worker.

Each admitted request owns its cancellation event, supervised worker and workspace.
The reservation spans progress notification, download, awaited upload and filesystem
cleanup. Repeated cancellation still waits for the executor/worker to settle before
deleting files or releasing capacity. Worker cleanup failure retains a quarantined
workspace and reservation; filesystem cleanup failure does likewise. Either blocks
new admission globally, without cancelling other already admitted operations.

The native 180-second operation deadline, 25 MiB file limit, existing network/body
budgets and exclusive export remain per operation. Upload retains its separate
120-second timeout. There is no retry, fallback, second media candidate or transport.
The capacity limit applies to one bot process/dispatcher, not multiple replicas.

## Verification and acceptance gate

**356 focused tests PASS**. The complete offline suite passed **1716 passed,
1 skipped** (191.87 s); the skipped case is the opt-in real YouTube smoke. A process-
inherited socket/DNS guard prevented external connections, including in Python workers.
Ruff lint/format, diff-check and compact scope/security review passed.

Seven new public-access/concurrency cases plus updated configuration and lifecycle
regressions cover public/disabled/production access, two real native workers against
synthetic HTTP and generated MP4, saturation without new workers, same-user rejection,
slot reuse, repeated-cancel isolation, independent files and quarantined reservations.
Existing sound/silent success, 403/429, truncation, upload timeout/error/unconfirmed
response and real process-group cancellation/reap remain covered, along with YouTube,
Instagram, native CLI and benchmark tests. No native/provider/transport/HTTP policy,
media preparation, dependency, CI workflow or MIT notice was changed.

The implementation was published in Draft PR #65 at
`6665b90f6057e2b08034aa6866ee83528378fa1a`. CI #39469733288 passed on that exact
HEAD: **1716 passed, 1 skipped**, Ruff lint/format PASS. Publication of the following
documentation-only acceptance update requires successful CI on its own exact HEAD.

## Owner-confirmed PUBLIC TIKTOK LIVE PASS

One separately authorized local Telegram test used a second Telegram account without
a personal allowlist. A full public video URL reached the existing dispatcher and
public TikTok handler with the feature enabled and capacity two. Public-page metadata
and original source ID passed, one media GET returned HTTP 200, and one acquisition
produced a complete **565,847-byte MP4**. Actual verification reported one H.264 video
stream and one AAC audio stream, 576×1024, duration 14 seconds; full FFmpeg decode
and Telegram preparation passed without transcoding.

One sendVideo attempt returned a confirmed video Message in the correct chat. The
file existed through the awaited API response. The owner subsequently confirmed on
the second account that playback, orientation and sound were correct. Metadata:
**1 request / 409,411 bytes**; media: **1 request / 565,847 bytes**; one acquisition,
exact counters. Native operation took 2.611 s; the controlled runner took 4.124 s.

The owner explicitly approved taking the first TikTok link from the existing queue.
The controlled poller read without an offset or queue acknowledgement/deletion and
passed exactly one real update through the unchanged dispatcher/handler. Later queued
events were not processed. Queue acknowledgement and replay prevention on a future
restart were not validated by this test; no further polling/queue action is authorized.

Polling stopped, the Bot API session closed, workers were reaped and private/caller
workspaces and media files were removed. Git, protected environment files and other
worktrees were preserved; both Docker containers remained exited. No retry, Embed
fallback, additional download/upload, merge or deployment was performed.

This closes **one public-user full-link Telegram scenario**, not a load test or proof
of scalability, short-link support, general TikTok reliability or production readiness.
Short links remain unsupported; earlier embed HTTP 429 and CDN 403 remain historical
limitations, not demonstrated as universally resolved by this success. PR #65 remains
Draft; final review/offline checks and exact-head CI prepare it for a separately
owner-authorized merge. Deployment requires its own decision.

## Final documentation-only preparation

Final PR review against main `fe59c1d` passed: public/default-off access and separate
Instagram restrictions, default two process slots/one per user, no-await admission,
independent workspaces, cancellation/timeout ownership and fail-closed quarantine
remain intact. Public-page provider/transport, budgets, other platform routes,
dependencies and CI are unchanged. Only this document, TESTING, TASKS and ROADMAP
are updated in the acceptance commit; no source/configuration change is included.

The repeated full offline suite passed **1716 passed, 1 skipped** in 186.73 s with
inherited external socket/DNS denial. Ruff lint/format, diff-check, privacy/security
review and **30 local documentation links/anchors** passed. No new real platform
request, polling, Docker operation or deployment was performed for this preparation.
Exact documentation-commit CI must pass before merge handoff; its result is recorded
in PR #65 checks. Merge still requires separate owner authorization.
