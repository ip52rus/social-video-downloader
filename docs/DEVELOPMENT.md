# Development Workflow

## Source of truth
During active development, the local repository is the primary working state. GitHub is the synchronized remote history and checkpoint after a verified stage. Before work, inspect the current branch and working tree, understand any unrelated local changes, and preserve them.

After a stage is implemented and verified, synchronize the remote history by committing and pushing the reviewed local result, then confirm the GitHub branch and CI state match the intended change.

## Stage workflow
1. Read the relevant roadmap, task decomposition, architecture, testing guidance, and applicable agent rules before implementation.
2. Confirm the current stage, its acceptance criteria, dependencies, and outstanding checks. Do not skip an unmet roadmap gate without explicitly documenting the reason and obtaining a decision where needed.
3. Make a small, focused local implementation or configuration change on an appropriate branch.
4. Synchronize documentation with the verified implementation state. Update `docs/TASKS.md` after every completed stage and before starting the next stage. Update `docs/ROADMAP.md` when phase status, gates, dependencies, scope, or the next step changes. Update any other document made inaccurate by the change.
5. Run the relevant tests and quality checks. Perform external-platform or end-to-end checks when required by the acceptance criteria.
6. Review implementation results and distinguish verified behavior from assumptions and untested cases.
7. Review the exact diff, changed-file list, test results, documentation consistency, and security implications.
8. Commit the coherent change atomically with a Conventional Commit message.
9. Push the branch, then verify the GitHub branch state and CI result.

## Documentation requirements
- Documentation updates are part of the stage's definition of done.
- A task may be marked complete only when its acceptance criteria have evidence supporting completion.
- Keep partial work unchecked and describe the checks still outstanding.
- Identify the type and scope of verification: unit tests, deterministic integration tests, real external-platform tests, or Telegram end-to-end tests.
- For external-platform tests, record the scope of the evidence and distinguish application regressions from platform changes or transient network failures.
- Do not claim broad reliability based on one successful URL or one happy-path test.
- If a stage is not complete, preserve its in-progress status and state the remaining acceptance criteria.
- Do not defer routine documentation synchronization to an unspecified future cleanup task.

## Branches
Use `feature/name`, `fix/name`, `refactor/name`, or `docs/name` for non-trivial work.

## Permanent worktrees

All new project Git worktrees must live in permanent storage, for example
`~/PycharmProjects/social-video-downloader-worktrees/`. Never create working
worktrees in `/private/tmp`, `/tmp` or automatically cleaned temporary directories.
This is a standing rule for all future agent tasks, not a phase-specific exception.
Historical damaged directories and private preservation archives remain untouched;
unknown historical untracked/ignored data is not claimed recovered.

## Commits
Use Conventional Commit prefixes. One coherent change per commit.

## Pre-commit checklist
- Relevant tests and checks pass, or outstanding failures are explicitly documented.
- Diff and changed-file list reviewed.
- No secrets or personal data.
- No generated files or accidental media.
- `docs/TASKS.md` and `docs/ROADMAP.md` accurately reflect the verified progress.
- Other affected documentation is updated.
- Commit message describes the actual change.

## Synchronization
After each commit, verify the commit SHA and branch state. After each push, verify the remote branch and CI. Do not overwrite unrelated local work while synchronizing.

## Public TikTok configuration

TikTok remains disabled by default. `TIKTOK_TELEGRAM_ENABLED=true` enables supported
full public-video URLs for any Telegram user, including in production configuration.
`TIKTOK_TEST_USER_IDS` is removed and has no effect. Set
`TIKTOK_MAX_CONCURRENT_OPERATIONS` to an integer 1–8 (default 2) for the single bot
process; each user can hold only one operation through download, upload and cleanup.
There is no waiting queue. Do not increase native time/size budgets or HTTP retries.
Cleanup failure blocks new TikTok requests and retains quarantine for operator
inspection; do not force-delete workspaces while a worker may still own them.
The Compose template forwards the flag/capacity with false/2 defaults. The separately
authorized deployed environment now persists true/2 as described below; repository
defaults remain unchanged.
Instagram's separate opt-in/production restriction is unchanged. Phase 6H passed
one separately authorized full-link public-user live case. Phase 6I additionally
admits HTTPS `vm.tiktok.com`/`vt.tiktok.com` share links with one alphanumeric token
and no query/fragment. Expansion starts only in the admitted supervised worker and
shares the original operation budgets. A separately authorized test passed for one
`vm` mobile share link, including Telegram delivery and owner playback/orientation/
sound confirmation; `vt` remains offline-only. Broader mobile-link/high-load behavior
and general reliability remain unverified. Diagnostic
embed/public-page CLI and benchmark retain their full-link interfaces. See
[Phase 6I](PHASE6I_TIKTOK_SHORT_LINKS.md).

### Deployed public TikTok configuration

PR #66 merged at main `389258cee9cf966be531ae5d6d60b192a59bcdb2`, with successful
[post-merge CI #39517532808](https://github.com/ip52rus/social-video-downloader/actions/runs/39517532808).
The separately authorized deployment built bot image
`sha256:9941db2d71db21635a1d2a90348de9360a829f714c31f7c2e9ce0eaf220e043a`
from that source. The previous image
`sha256:a4c2d2636f3660aa48b9c0e00d7134960eb78903f0e8a89af31fb92febd5663c`
is retained under `youtubedownloader-bot:rollback-pre-tiktok-389258c`.
Image retention is rollback preparation, not evidence of a tested rollback.

Cloud logout succeeded, followed by a successful Local Bot API getMe from the private
Compose network. The existing API container/image and
`youtubedownloader_telegram-bot-api-data` volume were preserved. Updated bot polling
uses `http://telegram-bot-api:8081`; both services were left running. Do not repeat
the migration or modify the API volume as routine configuration maintenance.

The existing protected local `.env` now contains only these two newly persisted
non-secret settings; its other values and mode 0600 were preserved:

```dotenv
TIKTOK_TELEGRAM_ENABLED=true
TIKTOK_MAX_CONCURRENT_OPERATIONS=2
```

The `.env` remains ignored and untracked; it is not supplied by this documentation PR.
Do not copy credentials or a real `.env` into Git. The running bot already used true/2
from deployment's process-local overrides; persisting them did not alter that process.
Private Compose verification removed both variables from the command environment,
then checked `docker compose -p youtubedownloader config --quiet` and resolved values:
true/2, `INSTAGRAM_TELEGRAM_ENABLED=true`, `APP_ENV=development` and the same Local API
endpoint. No other resolved configuration changed. Future standard Compose recreation
from this project directory will retain true/2 without manual command-line overrides,
provided those variables are not overridden by the shell or a different env file.
Never print full resolved Compose configuration: it includes credentials.

Stage D's three sequential live cases (TikTok short link, Instagram Reel and YouTube
video) passed delivery plus owner-confirmed full playback, orientation and sound;
worker/file cleanup passed, with no observed restart/OOM/runtime errors. See
[acceptance and evidence limits](TESTING.md#public-deployment-stage-d-acceptance).
Persistence and this docs update performed no restart/recreation/build, new platform
or Telegram request, or deployment. Future operational changes require separate
authorization; retaining a rollback image does not authorize starting it or clearing
pending Telegram updates. Broad reliability, high load, `vt` live coverage and recovery
remain unverified; historic TikTok HTTP 429/403 are not universally eliminated.

## Controlled main-bot Reel smoke

PR #53 is merged. The user chose the existing main Telegram bot for one approved public
Reel smoke and accepted a short planned bot-container restart. No separate bot,
standalone container, watchdog framework or alternate poller is part of this plan.

Compose forwards `INSTAGRAM_TELEGRAM_ENABLED: ${INSTAGRAM_TELEGRAM_ENABLED:-false}`
only to bot. An absent flag stays false. Compose already sets `APP_ENV=development`;
the existing Settings enabled+production guard is retained. Local Bot API routing,
credentials, dependencies and volumes stay unchanged. Do not edit a real `.env` as
part of this PR or run deployment commands during configuration preparation.

After independent PR review/merge, the separately performed deployment procedure is:

1. Confirm no active user download; plan the short main-bot interruption.
2. Update server source to reviewed main.
3. Set `INSTAGRAM_TELEGRAM_ENABLED=true` in the existing protected server environment.
4. Rebuild/recreate only bot using `docker compose up -d --build --no-deps bot`.
5. Confirm normal polling and YouTube behavior before the Reel smoke.
6. Submit exactly one explicitly approved public Reel to the existing main bot.
7. Inspect errors, file size and actual Telegram client playback; do not retry an ambiguous send.
8. If rollback is needed, restore the flag to false and recreate only bot with `--no-deps`.

Do not restart/recreate telegram-bot-api or modify its volume. At that historical stage,
the 25 MiB Reel limit and cooperative thread-cancellation limitation remained; no hard whole-request watchdog
or production-reliability guarantee is introduced. At that Reel-only stage, `/p/` and
carousel routing were pending.
After PR #54, the separately authorized bot-only deployment and one canonical-Reel smoke
passed. The user confirmed delivery, playback, orientation and sound; temporary files
were cleaned and Local Bot API was unchanged. Exact size/time were not recorded. The
initial share URL was rejected on `psln`. PR #55 subsequently merged at
`0a87beeaa8acb302b74e980946778608856b13f6` and was separately deployed to the existing
bot. The user confirmed delivery, playback, orientation and sound for the full Reel
share URL with `utm_source` and `psln`; size and processing time were not recorded.
This is one Reel case, not `/p/` or album validation or general Instagram reliability.
No further restart or live test is authorized by these historical records.

## Opt-in Instagram /p/ and album routing

The existing `INSTAGRAM_TELEGRAM_ENABLED` opt-in is reused: no second bot,
new token, Compose service or polling loop. PR #56 passed final independent review,
merged at `20d14441a2b7ea906ed2a0abc83679d25d9f2d32` and was separately deployed
by replacing only bot. Startup/polling and source identity passed; Local Bot API was
unchanged. PR #57 subsequently merged at `13da14d6f1ea9378d776543c94b22b7b716630d3`
and was separately deployed only to bot. On 2026-10-18 the owner confirmed one
full-link single-post video and one ordered three-video silent album, all with normal
playback. See [the limited acceptance](TESTING.md#instagram-live-acceptance-2026-10-18).

Accepted public `/p/` publication links pass through the conservative carousel
selection policy. The merged PR #57 share-link fix aligns `/p/` with Reels: irrelevant
query keys, bare share flags and ordinary fragments are stripped. Other known item selectors remain rejected case-insensitively after percent decoding
in query keys and selector-shaped fragments, before extraction. The Item Selection
path below admits only one unambiguous `img_index`; malformed references and the
32-field bound remain blocked.
A single-video post must be positively confirmed by the source
adapter and existing video validators; it consumes the same verified snapshot in the
bounded single-file worker. BLOCKED never authorizes fallback or another extraction.
The adapter checks source `carousel_media` before mapping: a present value must be a
complete flat list and must survive mapping with the same count, identities and order.
Malformed/nested collections block with INVALID_METADATA; an empty list has NO_VIDEOS.
An absent field permits positive single-video inspection; present null is not absence.
A READY video carousel goes through the bounded
multi-file acquisition and Telegram delivery; PHOTOs are skipped only after
positive classification, UNKNOWN items block everything, and no video is silently
truncated. Initial limits are 10 selected videos, 25 MiB/file and 100 MiB total.
One active Instagram operation per dispatcher; no automatic retry after a
possibly delivered album.

The initial inspection uses the existing cooperative guard and cancellation event.
Its 300-second operation window starts before extraction and is not restarted for
acquisition, preparation or upload; the single-file 180-second work and 120-second
send caps remain. Pending native/network calls may delay cancellation, but the slot
and workspace remain owned until real worker completion. Do not replace this with
thread abandonment or claim hard native-call termination.

Do not rebuild/restart either running container, edit server environment or
perform real external calls as part of the acceptance-documentation update. The two
owner-confirmed cases do not authorize additional deployments, tests or limit changes.
Broader publication/client/size coverage and production capacity remain unverified.


## Phase 9A operational baseline and safe events

### Decision and deployed baseline

Use standard-library logging at the existing lifecycle boundaries. No external
monitoring, metrics server, healthcheck, queue or worker pool is justified by the
current evidence. The main process can be checked with read-only Docker inspect;
one-shot stats/disk observations are not a load test or capacity guarantee.

Audit against GitHub main `50537ca61c7084f107c6f3a75335170b3317323e` (the merge of
PR #67) found the primary local checkout still at deployed source `389258c`; only
five documentation files differ. It was left unchanged. Both existing containers
were RUNNING, restart count 0, OOM=false. Bot image remained the prepared deployment
image recorded above; Local API identity/mount and rollback image were preserved.
The point-in-time sample was:

| Observation | Bot | Local Bot API |
|---|---|---|
| CPU | 0.00% | 1.17% |
| RAM | 506.3 MiB | 54.66 MiB |
| Explicit container CPU/RAM cap | None | None |
| Logging driver / explicit options | local / none | local / none |

Docker reported 16 CPUs and about 7.75 GiB RAM; host free disk was about 78.6 GiB.
Docker reported images 3.073 GB, writable containers 6.787 MB, volumes 64.35 kB and
build cache 3.281 GB. These are snapshots, not reserved capacity or safe limits.
Compose defines no logging options. Docker documents local-driver defaults of five
20 MB files and compression, but retention/rotation was not experimentally tested:
[Docker local logging driver](https://docs.docker.com/engine/logging/drivers/local/).
No daemon or Compose logging configuration was changed.

A bounded private scan of 500 existing log lines found one legacy upload/probe
record, one legacy Telegram video-metadata record, five update-identity markers
and seven bot-identity markers, with no traceback marker. These logs were not
printed, copied into Git, deleted or rewritten. This branch does not sanitize
historical logs or change the running image; deployment remains a separate decision.

### Event contract and interpretation

The configured Python sink emits JSON with exactly `platform`, `event`, `phase`,
`category` and `elapsed_ms`. Platforms are youtube/instagram/tiktok; service denotes
bot lifecycle or polling errors. Events are operation_started, operation_completed
and operation_failed. Phases come from the fixed source allowlist: metadata,
download, prepare, download_prepare, prepare_upload, upload, cleanup, notification,
polling, session_close or unknown. Categories use trusted exception types, never
exception text, class-name strings, causes, external JSON or HTTP payloads.

Durations use monotonic time, in milliseconds, for the observed lifecycle including
owned cleanup/error notices. Ancillary notification/polling failures without a
measured start have null duration; invalid/unbounded measurements also become null.
Docker timestamps can supply wall-clock ordering. LOG_LEVEL=INFO retains starts
and successful completions; higher levels intentionally hide lower-level events.

YouTube planning emits a separate metadata operation, excluding user choice time.
Delivery then observes download, preparation, upload and workspace exit. A completed
planning operation is not delivery. Existing best-effort probe failure is a separate
prepare failure and does not block upload. A missing YouTube video response is
reported as unconfirmed_upload without changing the old user flow or retry policy.
Audio delivery retains its existing API-return checks; no stronger confirmation is
implied. Reel/TikTok workers combine download and preparation, so their inner HTTP
and FFmpeg stages are not guessed. Instagram post inspection is metadata; carousel
preparation/upload is a combined prepare_upload phase. No user or operation IDs are
recorded; concurrent operations cannot be individually correlated from these logs.

Service operation_started/polling means entry into the existing polling call, not
authentication, successful getUpdates, a heartbeat or event-loop responsiveness.
The exact aiogram fetch-error template is converted to safe typed categories
(including Telegram conflict, authorization, rate-limit and network errors).
Other unstructured aiogram/library messages are dropped. Startup failures exit
nonzero without an exception traceback. No new polling retry or network request is
introduced. Configure_logging installs the owned safe root sink, replacing existing
root handlers; embedders must not attach an unfiltered sink afterwards.

No URL, media/user/chat/update identity, filename/path, token, header, cookie,
ffprobe/yt-dlp JSON or traceback is serialized. The YouTube yt-dlp logger also
suppresses its direct console output. Sink failure cannot trigger retries, change
user messages or bypass cleanup; no stderr traceback is printed for a sink error.
This is not a general scrubber for arbitrary subprocess/native stderr or Local API
logs. No claim of complete historical-log confidentiality is made.

### Lifecycle boundaries and next gate

Existing TikTok admission (two per process, one per user), worker group supervision,
180-second native cap, 120-second upload cap, exclusive export, cancellation/reap,
quarantine and fail-closed blocking are unchanged. Reels keep their existing single
slot, cooperative bounded executor and 180/120-second limits; posts retain their
shared operation window and carousel transport limits. YouTube keeps existing
choices, to_thread delivery/preparation and callbacks. No timeout, network policy,
format/quality, downloader/API retry or upload confirmation behavior was changed.

A failed/cancelled event reports the observed handler outcome, not independent
proof of thread/process reap. In particular, the existing YouTube to_thread path
has no owned-thread hard cancellation guarantee, and its synchronous metadata
planning still runs on the event loop. Phase 9A does not repair these architectural
debts. Phase 9B should first measure event-loop/callback responsiveness offline with
a deliberately blocked synthetic metadata provider and a concurrent asyncio ticker,
then decide the smallest bounded ownership/cancellation change with acceptance
criteria before implementation. Native worker/cancellation diagnostics, HTTP counts,
latency percentiles, availability, event-loop lag, load capacity and automated
recovery remain unmeasured. Do not infer them from process state or smoke PASS.

Verification and exact-head CI are recorded in
[Phase 9A testing](TESTING.md#phase-9a-safe-operational-events-offline).
No live request, container restart/recreation/build, env change or deployment is
part of this stage. Inspect logs privately; never paste raw deployed logs into PRs.


## Instagram Item Selection

Public `/p/` with one valid `img_index=N` is inspected as an entire carousel before
showing “Все видео из карусели” / “Только видео №N”. N is an original position,
including photos; a selected PHOTO offers only the all-video action. Ordinary
publication links still download all videos without a confirmation step. Reels do
not acquire this new reference behavior. See [policy and evidence](TESTING.md#instagram-item-selection-offline).

`CarouselScope.PUBLICATION` retains the existing all-video policy. SINGLE_VIDEO
requires a requested original position and exactly its confirmed child; both carry
parent identity and a complete manifest. The shared validator, IPC and delivery
checks enforce scope, not arbitrary subsets. No quality/MP3 option is introduced.
InstagramChoiceStore is a small separately typed process-local store, not YouTube
pending state. It uses random opaque IDs, owner/chat/message binding, 15-minute TTL,
128-entry capacity and locked one-shot removal. Buttons before message binding are
refused safely. The same event-loop Instagram slot covers metadata inspection and,
after a valid callback, acquisition through upload/cleanup, but not human choice
waiting. Busy/failed-ack callbacks do not consume a choice. A consumed callback
never retries, even if keyboard removal or upload confirmation fails.

At that Item Selection stage, limits were 10 videos, 25 MiB/file and 100 MiB total.
Phase 9C supersedes the byte budgets in source; the ten-video ceiling is retained.
Oversized or incomplete publications refuse rather than silently truncate. Worker
cleanup uncertainty preserves opt-in quarantine workspaces and keeps the Instagram
handler blocked; investigate ownership/reap before any separately authorized manual
cleanup or restart. No automatic recovery, data deletion or retry is performed.


## Phase 9B deployed baseline 2026-10-23

This is the later deployed baseline; the Phase 9A audit and earlier deployment
records above retain their historical meaning. The separately authorized bot-only
rollout of main `04a07ba85883b992a9e9f06c36e586326e410e29` (PR #73, including PR #72)
concluded **PHASE 9B DEPLOYMENT — TECHNICAL PASS** on 2026-10-23.

| Deployment checkpoint | Value |
| --- | --- |
| Bot image | `sha256:2931d1e016405c237c4fab1b844f1a68bf977d2fc3f34cf2057bd9a5268437f4` |
| Previous bot image | `sha256:0b969b218619564afabd8b517c2e6faca50d65308e688134543b91bf33b0d7c6` |
| Rollback tag | `youtubedownloader-bot:rollback-pre-phase9b-04a07ba-20261023t091719z` |

The deployment report confirmed one bot replacement, previous poller shutdown before
new startup, source identity by 48 file hashes, RUNNING state, restart 0 / OOM false
and startup/polling events without observed new startup/conflict errors. Local Bot API
container/image/config/mounts, named volume, feature flags, endpoint, credentials and
runtime configuration were preserved. `.env`, `.idea/workspace.xml`, other worktrees
and the preservation archive were unchanged. These are deployment-time observations,
not new checks performed by this documentation update or proof of current availability.
Rollback was prepared but **not executed or rehearsed**. Deployment included no
platform downloads or Telegram delivery tests.

A separately authorized one-attempt two-account test later produced **LIVE FUNCTIONAL
SMOKE — PASS** and **LIVE CONCURRENCY RESPONSIVENESS — INCONCLUSIVE**. Callback overlap
was not proven and latency was not measured; no final download choice or retry was
made. See the [review, CI, deployment and LIVE record](TESTING.md#phase-9b-review-deployment-and-live-acceptance-2026-10-23).
General reliability/load/recovery remain unverified and Phase 9 OPEN. Phase 8 is a
candidate next direction only after a separate owner decision, not an automatic step.

## Phase 9C shared request admission and technical limits

[Phase 9C](PHASE9C_DOWNLOAD_PROTECTION.md) supersedes historical Instagram byte
budgets, without changing activation rules or currently running services. Configure
`DOWNLOAD_MAX_FILE_BYTES`, `DOWNLOAD_MAX_REQUEST_BYTES`,
`DOWNLOAD_MAX_WORKSPACE_BYTES`, `DOWNLOAD_MIN_FREE_BYTES`,
`DOWNLOAD_MAX_ACTIVE_REQUESTS`, `DOWNLOAD_LINK_INTERVAL_SECONDS`,
`DOWNLOAD_MAX_PENDING_REQUESTS`, `DOWNLOAD_NOTICE_INTERVAL_SECONDS`, and
`YOUTUBE_MAX_FILE_BYTES` / `YOUTUBE_MAX_REQUEST_BYTES` / `YOUTUBE_MAX_WORKSPACE_BYTES`
through the existing environment mechanism; defaults and consistency checks are in
the design.
No real `.env` changes, Docker operations or LIVE downloads are part of implementation.

The router's localization middleware surrounds the new message/callback admission
middleware. Admission reserves synchronously before metadata; validated callbacks
reuse the original user lease and locale, acquiring a separate worker atomically
when available. Busy preserves pending choices without extraction or consume.
Waiting choices occupy only the bounded user-lease map, not global work capacity.
`/cancel` invalidates only idle pending choices; it leaves the short
link cooldown intact. Lazy expiry cannot release a running callback or owned worker.
Quarantined cleanup retains both its user's slot and global capacity. Investigate
worker ownership and workspace safety before any separately authorized operational
recovery; restarting is not itself proof of cleanup. An unconfirmed worker/process-group
stop or cleanup can retain a lease indefinitely
and preserves its workspace. This is intentionally fail-closed. YouTube acquisition
uses an owned POSIX child with scoped write interception, not global file hooks in
the polling process. Preparation retains its existing drain-on-cancel thread ownership.
See the design for the additional settings not forwarded by source Compose and
for conservative disk reservations. No Docker/configuration changes are applied.
