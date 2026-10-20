# Phase 6H — Public TikTok MVP

## Decision and scope

Phase 6G verified one real public-page download and owner-confirmed Telegram playback,
orientation and sound. PRs #60–64 were merged; this stage changes only admission and
configuration, not the verified downloader. Public acceptance and deployment remain
separate gates. No real TikTok/Telegram requests are authorized for this implementation.

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

The reviewed branch is published as a Draft PR to main; exact committed-head CI is
required before handoff (see PR checks for its outcome). No real TikTok/Telegram call,
polling, Docker launch or deployment is performed. A future separately authorized
public acceptance test is required; earlier single-case LIVE PASS and synthetic
concurrency do not prove public reliability or production readiness. Previous embed
HTTP 429 and CDN 403 remain unresolved history.
