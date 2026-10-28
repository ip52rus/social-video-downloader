# Phase 9C: shared download protection

## Local acceptance and remaining limits

Status: **LOCAL ACCEPTED**. [PR #83](https://github.com/ip52rus/social-video-downloader/pull/83)
merged as `f74dc6c933012b809d4e6dc33ed3f3bdadc39d34`; post-merge CI
[#40333460016](https://github.com/ip52rus/social-video-downloader/actions/runs/40333460016)
SUCCESS. The 2026-10-26 local bot-only deployment received TECHNICAL PASS, with
Local Bot API/configuration/volume preserved and rollback prepared but not executed.
On 2026-10-28 the owner confirmed 5/5 LIVE PASS: rejection during pending choice
and active download, waiting-choice cancellation, YouTube delivery/playback and
delivery/playback of one Instagram video larger than 25 MiB. See the separate
[deployment](TESTING.md#phase-9c-local-deployment-2026-10-26) and
[owner acceptance](TESTING.md#phase-9c-owner-live-acceptance-2026-10-28) evidence.

Acceptance is limited to these local observations. It does not establish
load/stress reliability, failure recovery or a tested rollback, near-2 GB delivery,
or universal platform/network/client/language compatibility. The five LIVE cases
include no new TikTok acceptance. The restart-stale and quarantine limits below
remain in force. General Phase 9 stays **OPEN**.

## Reason and scope

The former Telegram Instagram gates imposed a separate 25 MiB file ceiling at
acquisition, preparation and delivery. Phase 9C replaces those gates with one
technical resource policy. The existing engines, network policy, formats, carousel
identity/selection contract, deadlines and ten-video carousel ceiling stay intact.

A single-process Telegram admission coordinator owns one unfinished request per
user across platforms. It reserves before metadata, retains the reservation while
choices are pending and through worker drain/delivery/cleanup, and rejects excess
work without a queue. Waiting choices reserve only a user/pending slot, not a
global worker or disk reservation. Validated callbacks acquire work atomically;
Busy preserves the original choice without consuming it or extracting again. `/cancel`
invalidates only an idle pending choice, never an executing worker. Uncertain
cleanup quarantines the reservation; expiry cannot release a running worker.
The coordinator is transport infrastructure, not part of the downloader core.

## Technical policy

Instagram/shared defaults: 512 MiB per file, 1 GiB per acquired or prepared
collection, 3 GiB workspace. YouTube defaults: 2,000,000,000 bytes per file, 4 GiB
received bytes and 8 GiB workspace, covering split streams, merge and preparation.
Admission defaults: 512 MiB free-disk reserve, four working requests, 128 total
user leases (including workers, pending choices and quarantine), a three-second
per-user link interval and at most one link-refusal notice per five seconds.
File size is additionally capped by the API
endpoint: 2,000,000,000 bytes for the existing Local Bot API configuration,
50,000,000 bytes for the cloud endpoint. No individual file may exceed 2 GB.
See [Telegram Local Bot API](https://core.telegram.org/bots/api#using-a-local-bot-api-server)
and [sendVideo](https://core.telegram.org/bots/api#sendvideo).

Instagram counts actual acquisition bytes, including responses without a truthful
Content-Length, and bounds preparation output and aggregate workspace use. Free
space is checked before admission and during bounded Instagram reads/preparation.
The native TikTok engine retains its own stricter acquisition caps. YouTube runs
the same provider and selectors in an owned POSIX acquisition process with bounded
actual writes and native HTTP response reads. Its child-only file guard includes
partials, fragments and split streams; an OS output cap protects FFmpeg merge and
Telegram preparation before writes exceed remaining workspace/file/free budgets.
A sticky budget refusal bypasses engine retry and preparation conversion fallback.
It cannot authorize another download. The consumed metadata snapshot keeps its
original timestamp and 180-second TTL; there is no extra extraction for a valid
snapshot. This new write boundary does not change format or quality selection.

## Lifecycle and evidence limits

The admission map is bounded, process-local and event-loop owned. No persistent
user identifiers, URLs, locale database, background queue or new external calls
are introduced. Existing validated stores remain authoritative for callback
ownership, binding, expiry and consume. The coordinator only attaches a matching
lease to a validated callback. Reference counts cover callbacks arriving before
the originating publication coroutine returns. Active and quarantined leases
cannot be cancelled by `/cancel`. Pending expiry uses the original 15-minute
store deadline and is reclaimed lazily on the next admission/cancel operation.

Restart loses choices and reservations; old buttons remain safely stale. An
operator must investigate quarantined cleanup before restarting; process restart
is not proof that an external worker has stopped. These checks provide bounded
offline evidence, not general production/load/recovery acceptance.

## Configuration

| Setting | Default | Validation / meaning |
| --- | --- | --- |
| `DOWNLOAD_MAX_FILE_BYTES` | 536870912 | Positive, at most 2,000,000,000; effective endpoint cap also applies |
| `DOWNLOAD_MAX_REQUEST_BYTES` | 1073741824 | Each acquired/prepared collection, at least the configured file cap |
| `DOWNLOAD_MAX_WORKSPACE_BYTES` | 3221225472 | At least request + configured file budget |
| `DOWNLOAD_MIN_FREE_BYTES` | 536870912 | Positive free-disk floor |
| `DOWNLOAD_MAX_ACTIVE_REQUESTS` | 4 | Integer 1–8; actual working requests, including quarantined workers |
| `DOWNLOAD_MAX_PENDING_REQUESTS` | 128 | Integer 1–1024; all user leases, independent of work capacity |
| `DOWNLOAD_NOTICE_INTERVAL_SECONDS` | 5 | Integer 1–300; link-refusal reply interval, first reply immediate |
| `YOUTUBE_MAX_FILE_BYTES` | 2000000000 | Independent YouTube cap, bounded by endpoint ceiling |
| `YOUTUBE_MAX_REQUEST_BYTES` | 4294967296 | Actual bytes read through native yt-dlp HTTP transport |
| `YOUTUBE_MAX_WORKSPACE_BYTES` | 8589934592 | Includes partials, split streams, merge and preparation output |
| `DOWNLOAD_LINK_INTERVAL_SECONDS` | 3 | Integer 1–300; links rejected before metadata, no sleeping/queue |

All byte settings are bounded integers (aggregate/workspace/reserve at most 16 GiB).
The shared file ceiling replaces Instagram-specific small gates; YouTube uses
its own endpoint-aware policy instead of inheriting the 512 MiB default.
Cloud and Local API use
the existing endpoint configuration; a configured local endpoint must actually
support local-mode uploads. Telegram's ceiling is not a promise that a file near
2 GB will complete within unchanged deadlines, available memory or disk budgets.
The original PR forwards the six shared settings through source Compose. Review
corrections do not change Compose: the five additional settings use their defaults
unless passed through the existing environment mechanism (or a separately approved
Compose environment override). A name in `.env` alone does not forward an unlisted
variable into a container. The separately authorized local rollout is recorded
above; this documentation closeout changes no runtime settings.

Admission conservatively requires the free reserve plus a full workspace budget
for each working request, even if some space is already in use. Pending choices
reserve no workspace; callbacks recheck free space when acquiring work. This can return
Busy earlier than strictly necessary. It is not a filesystem quota, RSS limit,
or protection from unrelated disk writers. The YouTube guard targets the installed
yt-dlp native write paths and current single-output FFmpeg commands; it is not a
general sandbox for arbitrary external downloaders or future multi-output tools.
Instagram checks actual streamed bytes and free space in bounded reads; preparation
keeps the existing OS output caps and fails closed on budget/deadline stops instead
of attempting conversion fallback. Exact exhaustion can be refused conservatively:
Instagram unknown-length streams and an FFmpeg output reaching its OS cap are
not accepted as evidence of a complete file. Near-ceiling LIVE delivery is unverified.

`/cancel` keeps the short link cooldown; cancelling does not bypass rate limiting.
No attempt to cancel a running upload/worker is made. Expired/cancelled buttons can
remain visible, but the authoritative store rejects them. No background message
cleanup, automatic retry, re-download or new persistence is introduced.

## Review boundaries

Implementation safety tests used synthetic responses, files, Telegram sessions and
controlled clocks, without new real platform requests or media downloads. The later
owner LIVE report is separate evidence. Existing format,
manifest/source-position, HTTP/header, retry, one-shot and pending-store contracts
are preserved. Additional global admission is deliberately stricter than the existing
per-platform gates, which remain in force. PR #83 is merged with its review
corrections and successful exact-head/post-merge CI. The separately authorized
local deployment and owner acceptance are recorded above; neither closes general
Phase 9 reliability. See
[offline testing evidence](TESTING.md#phase-9c-shared-limits-and-admission-offline).

## Independent review corrections

Review of `56222a9` identified three gaps: a 512 MiB post-download YouTube refusal,
waiting choices occupying all work slots, and unbounded repeated refusal messages.
The correction separates bounded user/pending leases from actual work admission,
reserves a worker atomically for validated callbacks and rate-limits link refusals.

YouTube needs its own endpoint-aware defaults (2,000,000,000 bytes/file, 4 GiB
acquisition and 8 GiB workspace) rather than inheriting Instagram's 512 MiB default.
Acquisition runs the existing provider/format selection in an owned short-lived
POSIX child, reusing the consumed metadata snapshot without another extraction.
A child-only write guard bounds Python output/partials/fragment assembly before
writes; FFmpeg inherits a per-output OS cap bounded by remaining workspace/free
space. Telegram preparation uses the same file/workspace budget. This transient
worker is required to scope write interception safely, with no global mutation in
the polling process, no new service, queue or persistent infrastructure. Owned
process-group cleanup precedes workspace deletion; uncertainty keeps quarantine.
Source-format, quality-ID and HTTP-header policies are unchanged.

Worker slots are held through owned-process/thread drain and cleanup. A bounded
YouTube process group must be reaped/confirmed absent before deleting its workspace.
If that cannot be confirmed, its temporary-directory finalizer is detached, the
workspace is preserved, and both user and work slots remain quarantined. There is
no automatic retry, recovery or workspace removal in this state. Existing preparation
threads still drain on cancellation; no new acquisition/worker deadline is introduced.
Refusal bookkeeping is bounded to 4096 in-memory entries with expiry/eviction; it
contains no persistent user data. Callback acknowledgements are not suppressed.
