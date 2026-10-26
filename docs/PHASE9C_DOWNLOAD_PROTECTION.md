# Phase 9C: shared download protection

## Reason and scope

The former Telegram Instagram gates imposed a separate 25 MiB file ceiling at
acquisition, preparation and delivery. Phase 9C replaces those gates with one
technical resource policy. The existing engines, network policy, formats, carousel
identity/selection contract, deadlines and ten-video carousel ceiling stay intact.

A single-process Telegram admission coordinator owns one unfinished request per
user across platforms. It reserves before metadata, retains the reservation while
choices are pending and through worker drain/delivery/cleanup, and rejects excess
work without a queue. Waiting choices reserve global capacity too. `/cancel`
invalidates only an idle pending choice, never an executing worker. Uncertain
cleanup quarantines the reservation; expiry cannot release a running worker.
The coordinator is transport infrastructure, not part of the downloader core.

## Technical policy

Shared configurable defaults: 512 MiB per file, 1 GiB per acquired or prepared collection,
3 GiB workspace, 512 MiB free-disk reserve, four unfinished requests, and a
three-second per-user link interval. File size is additionally capped by the API
endpoint: 2,000,000,000 bytes for the existing Local Bot API configuration,
50,000,000 bytes for the cloud endpoint. No individual file may exceed 2 GB.
See [Telegram Local Bot API](https://core.telegram.org/bots/api#using-a-local-bot-api-server)
and [sendVideo](https://core.telegram.org/bots/api#sendvideo).

Instagram counts actual acquisition bytes, including responses without a truthful
Content-Length, and bounds preparation output and aggregate workspace use. Free
space is checked before admission and during bounded Instagram reads/preparation.
The native TikTok engine retains its own stricter acquisition caps. YouTube's
existing acquisition engine is unchanged; shared admission/disk reservation and
preparation/delivery size validation do not establish a new streaming cap for that engine.

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
| `DOWNLOAD_MAX_ACTIVE_REQUESTS` | 4 | Integer 1–8; includes pending and quarantined requests |
| `DOWNLOAD_LINK_INTERVAL_SECONDS` | 3 | Integer 1–300; links rejected before metadata, no sleeping/queue |

All byte settings are bounded integers (aggregate/workspace/reserve at most 16 GiB).
The file ceiling is shared rather than Instagram-specific. Cloud and Local API use
the existing endpoint configuration; a configured local endpoint must actually
support local-mode uploads. Telegram's ceiling is not a promise that a file near
2 GB will complete within unchanged deadlines, available memory or disk budgets.
The source Compose file forwards these optional settings; this change does not edit
a deployed environment, run Docker, enable Instagram in production or increase timeouts.

Admission conservatively requires the free reserve plus a full workspace budget
for every admitted request, even if some space is already in use. This can return
Busy earlier than strictly necessary. It is not a filesystem quota, RSS limit,
hard cap on legacy YouTube streaming, or protection from unrelated disk writers.
Instagram checks actual streamed bytes and free space in bounded reads; preparation
keeps the existing OS output caps and fails closed on budget/deadline stops instead
of attempting conversion fallback. An exactly exhausted unknown-length stream may
be refused conservatively by the existing byte-guard behavior.

`/cancel` keeps the short link cooldown; cancelling does not bypass rate limiting.
No attempt to cancel a running upload/worker is made. Expired/cancelled buttons can
remain visible, but the authoritative store rejects them. No background message
cleanup, automatic retry, re-download or new persistence is introduced.

## Review boundaries

Safety tests use synthetic responses, files, Telegram sessions and controlled clocks;
no new real platform requests or media downloads are performed. Existing format,
manifest/source-position, HTTP/header, retry, one-shot and pending-store contracts
are preserved. Additional global admission is deliberately stricter than the existing
per-platform gates, which remain in force. Full CI and independent review are
required before merge; deployment and LIVE acceptance require separate authorization.
See [testing evidence](TESTING.md#phase-9c-shared-limits-and-admission-offline).
