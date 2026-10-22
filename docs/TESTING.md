# Testing Strategy

Instagram's narrow live evidence includes
[Item Selection LIVE acceptance 2026-10-22](#instagram-item-selection--live-acceptance-2026-10-22)
and the earlier [Instagram acceptance 2026-10-18](#instagram-live-acceptance-2026-10-18).
Earlier sections retain the evidence and open gates at each historical stage.

## Instagram Item Selection — LIVE acceptance 2026-10-22

### Offline implementation and CI

PR #70 is MERGED. Main at deployment was
`49f333eb3daff1d43fa2471e185e7071e8d179db`; its
[post-merge CI #39745923630](https://github.com/ip52rus/social-video-downloader/actions/runs/39745923630)
completed SUCCESS. Implementation verification was 77 focused tests PASS and
1946 passed / 1 skipped in the full offline suite, with Ruff and documentation
checks PASS. These are deterministic/CI results, not the LIVE evidence below.

### Separately authorized deployment

The existing main Telegram bot was updated to image
`sha256:0b969b218619564afabd8b517c2e6faca50d65308e688134543b91bf33b0d7c6`.
The previous running image is retained as
`youtubedownloader-bot:rollback-pre-instagram-items-49f333e`.
Local Bot API, volumes and protected local `.env` were preserved. The old polling
consumer exited before the replacement started; one main consumer was observed,
with no restart/OOM. Rollback was not performed or rehearsed. Image availability
is a recovery checkpoint, not proof of a tested rollback procedure.

### Owner-confirmed LIVE scenarios

On 2026-10-22 the owner manually tested one public Instagram carousel containing
two videos through the main Telegram bot. Both submissions used `img_index=2`,
which identifies the second original publication element, not the second video
after filtering photos.

| Scenario | Owner-confirmed result |
|---|---|
| A: “Только видео №2” | PASS: selected video delivered; playback, orientation and sound correct. |
| B: new submission → “Все видео из карусели” | PASS: both videos delivered; playback, orientation and sound correct. |

These are real user/Telegram confirmations, separate from synthetic tests and the
earlier metadata-only gate. No per-case duration, byte size, HTTP request count or
exact media-format measurement is attributed to these scenarios.

### Read-only post-LIVE health

Bot and Local Bot API were RUNNING, the expected image matched, and one main
polling consumer was observed. No restart/OOM, orphan media workers or residual
media files were found in the checked application workspaces. The checked log
window contained no acquisition, preparation, upload or cleanup failures or
critical process-failure evidence. `.env` and volumes were preserved; the rollback
image remained available. The health check performed no API calls or changes.

Since deployment, 5 Instagram operation starts and 5 completions were observed,
including two `download` operations. All 11 checked records conformed to the safe
structured schema. There are no correlation identifiers, so these aggregate events
cannot all be reliably attributed to the owner's two tests.

**Quarantine state: UNKNOWN.** The internal `_blocked` flag was not directly
inspected. No blocking symptoms were observed, but this does not turn UNKNOWN into
PASS. **Post-LIVE health verdict: INCOMPLETE**, solely because of this unverified flag.

Acceptance is limited to two choices on one two-video publication. Mixed PHOTO
Item Selection LIVE delivery, broader mobile/share-link/publication compatibility,
failure recovery, rollback rehearsal and high-load reliability remain unverified.
Foreign/expired/repeated callback and uncertain-upload safeguards retain their
offline evidence; these LIVE cases do not independently validate all fault paths.
Phase 5 and Phase 9 remain open. This documentation update performs no new LIVE
test, deployment or runtime/configuration change.

## Instagram Item Selection (offline)

`/p/` with one canonical positive decimal `img_index=N` offers all carousel videos
or only the confirmed VIDEO at original source position N. Photos retain positions;
a PHOTO selection offers only all available videos. An ordinary `/p/` still starts
whole-publication processing automatically. Reels retain their existing admission.
Selectors other than `img_index`, duplicates/conflicts, fragment selectors, malformed
encoding, zero/sign/whitespace/fraction/leading zeros, nested escaping, more than
32 query fields, more than 4096 URL characters and positions over 9 digits refuse.
Single percent-encoded keys/values are accepted unambiguously; `utm_source`, `psln`,
`rpxt` and benign share parameters are preserved as admissible input then stripped.

PUBLICATION selects every VIDEO; SINGLE_VIDEO has exactly one explicit original
position/child. Both retain the canonical URL, verified parent and entire ordered
manifest. Strict private IPC carries scope/position/child ID; fresh metadata must
match parent and every source position/ID/kind before any media GET. Arbitrary
subsets, missing/unknown identity and neighbouring-item fallback are refused.
The same acquisition/FFmpeg/delivery components, limits and confirmation barriers
are reused, including silent MP4 and no automatic retry after uncertain upload.

Typed Instagram pending choices are separate from YouTube ChoicePlan state. At
most 128 choices are held for 15 minutes. Opaque random callbacks bind user, chat
and prompt message; early/unbound, foreign, expired, replayed and post-restart
callbacks cannot download. Shared Instagram admission precedes acknowledgement
and consume; busy or failed-ack choices remain pending. Waiting for a user holds no
slot. Keyboard edit failure cannot re-enable a consumed choice. Cancellation waits
for owned worker cleanup/reap. A failed cleanup/reap propagates DownloadCleanupError,
quarantines directories without finalizer deletion, and retains the Instagram slot
until separate operator investigation; no paths or identities are logged.

Synthetic tests cover URL rejection, source positions with intervening photos,
metadata/identity changes, forged plans/IPC, exactly one selected media acquisition,
all-video regressions, foreign/stale/duplicate/concurrent/early callbacks, busy Reel
admission, acknowledgement/edit failures, bounded pending state, cancellation,
timeout, real child reap and cleanup failure. Full offline pipelines use local
H.264/AAC and silent MP4, the actual supervised worker/preparation and fake Telegram
confirmation for both actions; identities/callbacks must not appear in events.
Verification: **77 targeted PASS; full offline 1946 passed / 1 skipped**, 258.35 s.
External Python socket/DNS access was denied through inherited sitecustomize,
including worker processes; new tests additionally deny socket/DNS access. The
real opt-in YouTube test remained skipped. Ruff lint/format, diff-check, 70 local
documentation links/anchors and privacy/security/scope review PASS. PR #70 subsequently
merged and its post-merge CI succeeded as recorded in the LIVE acceptance section.

The earlier separately authorized parent metadata-only LIVE gate passed on one
2-VIDEO carousel with independent reinspection (6 metadata requests, no media GET).
It did not validate Item Selection acquisition or Telegram delivery. The implementation
PR itself performed no live platform request, download, Telegram API call, Docker
operation or deployment. The later separately authorized rollout and two VIDEO-only
LIVE choices are recorded above. Mixed PHOTO positioning/delivery and broader
compatibility remain open; no broad production-readiness claim is made.

## Instagram parent identity contract (offline)

Reason: the old selection compared child IDs, types, positions and count but could
accept a parent-only identity change because the publication URL came from input.
The adapter now captures raw product `pk` before yt-dlp mapping. Only a positive
integer or canonical ASCII decimal string (no bool, zero, sign, leading zero,
compound suffix or whitespace; at most 64 digits) is admitted. Its mapped shortcode
must be at most 28 characters and match the requested canonical `/p/` identity.
Present `code` must agree. The length bound excludes yt-dlp's special long/private
request-ID semantics. Input-derived `media_id` and fallback result `id` are never
response evidence. This boundary depends on installed yt-dlp `2026.8.19` internals;
extractor upgrades must rerun these source-shape tests.

Frozen inspection/selection carry a repr-hidden parent identity through private
stdin JSON. Strict IPC validation rejects missing/forged identity and malformed
plans; it never reconstructs identity from the URL. Both sides of acquisition
retain caller limits. Fresh metadata must match parent and the full ordered
manifest, including photos, before any media GET. Existing whole-publication-only
selection, preparation, exclusive output publication, worker cancellation/reap,
cleanup, upload confirmation and no-retry behavior are retained. Delivery also
rejects a plan without verified parent binding.

Deterministic tests exercise actual installed GraphQL and embedded-page JSON
extraction with fake responses, positive integer/string PK, optional matching code,
missing/malformed/mismatching parent, upstream input-ID fallback, mixed and
video-only manifests, parent-only changes with unchanged children, child/order/
type/count/unknown-element changes, private IPC, real child refusal/reap/cleanup,
repr and structured-log privacy. Existing local MP4 acquisition/preparation,
timeout/cancellation and fake Telegram tests remain regression evidence.
Verification: **67 parent-specific checks PASS**, 576 focused carousel/post/transport
regressions PASS; **full offline 1869 passed / 1 skipped**, 227.51 s. The focused
run preceded the final structured-log canary test; the full run includes it and
the shared contract validator. External Python sockets/DNS were blocked through
inherited sitecustomize, including worker processes; new parent tests additionally
deny socket/DNS calls. The opt-in real YouTube test remained skipped. Ruff lint
and format, diff-check, 44 local documentation links/anchors and scope/privacy/
security review PASS. Exact-head Draft PR CI is tracked in GitHub checks.

No real Instagram/Telegram requests or media downloads were performed. Public
`/p/` carousels whose metadata lack a usable PK will now be safely refused with the
existing message that the whole carousel cannot be downloaded safely; no media is
acquired or delivered. The frequency of this refusal is unknown without separately
authorized live evidence. Reels and single-video posts retain their existing path.
At the parent-contract stage item-selector URLs remained refused; ordinary
`utm_source`, `psln`, `rpxt` share parameters remained accepted. That PR did not
implement single-item download or new buttons; the later Item Selection stage is
recorded above.
At that earlier parent-only stage, explicit selection validation, parent/full-manifest
revalidation, source positions including photos, confirmed VIDEO/child identity,
callback ownership/expiry/one-shot consumption and uncertain-upload no-retry gates
still required implementation and offline verification; the later Item Selection
implementation and acceptance are recorded above.

## Phase 9A safe operational events (offline)

A read-only Docker audit preceded implementation on source main `50537ca`: both
services running, restart=0, OOM=false, original images/Local API volume retained.
CPU/RAM/disk and local logging-driver observations are snapshots, not load tests;
see [baseline and contract](DEVELOPMENT.md#phase-9a-operational-baseline-and-safe-events).
A private bounded scan confirmed old verbose upload/probe and aiogram identity
markers without printing raw data. Existing deployed logs were left untouched.

Deterministic tests cover fixed-field start/completion/failure, expected/unexpected
exceptions, measured monotonic duration, invalid measurements, suppressed library
identity/traceback records, safe polling conflict classification, quiet yt-dlp,
startup/session closure, failing output sinks without duplicate download/upload,
three-platform upload cancellation and TikTok quarantine retaining its reservation.
Synthetic URLs and sensitive canaries are used; no real user data or media is kept.
The broader focused regressions retain worker reap, cancellation, concurrent users,
independent workspaces, cleanup, Telegram uncertainty and all original routes.

Final verification: **355 focused PASS; full offline 1802 passed / 1 skipped**,
224.16 s. Ruff lint/format, diff-check, 47 local links/anchors and privacy/scope/security
review PASS. External Python socket/DNS denial is installed through inherited sitecustomize, including worker
children; the real opt-in YouTube smoke remains skipped. Local generated-media
FFmpeg tests are offline evidence, not a new platform/Telegram smoke. No downloader
network policy, quality, API, retry, ownership, admission or user message is changed.
Exact-head Draft PR quality CI is required before handoff and recorded in GitHub checks.
No live call, polling, container/env mutation, merge or deployment is part of Phase 9A.
The events do not establish inner HTTP statuses/counts, broad reliability, individual
concurrent-request correlation, continuous liveness, event-loop responsiveness or
stronger legacy YouTube thread-cancellation/upload-confirmation guarantees.

## YouTube cancellation safety (offline)

The offline snapshot feasibility gate separately reproduced a workspace race in the
legacy YouTube Telegram path: cancelling the coroutine awaiting `to_thread()` could
delete its `TemporaryDirectory` while its download thread still wrote files.

The narrow fix uses the existing default executor with copied context, retaining a
Future rather than a separate cancellable asyncio Task. The handler shields that
Future and, on cancellation, drains it before propagating cancellation and leaving
the workspace. Repeated cancellation cannot bypass the drain. Late worker exceptions
are retrieved without replacing cancellation or starting another download/media send.
The same local helper covers download, audio preparation, video preparation and probe.
Uncancelled errors retain existing user responses and best-effort probing behavior.

`tests/test_youtube_cancellation.py` uses synthetic files, fake Telegram and real
threads held by `threading.Event`. It verifies workspace retention until release,
worker completion before cleanup, repeated cancellation, success/late failure at each
stage, independent event-loop progress, successful Audio/Video delivery, context and
keyword propagation, and shutdown-style Task cancellation. Every test releases its
worker in a finalizer and joins the test executor; loop exception notifications are
checked for unhandled failures. No real platform or Telegram request is needed.

Verification: **24 new lifecycle tests; 283 focused PASS; full offline 1970 passed /
1 skipped**, 252.45 s. Python socket/DNS denial was inherited by child processes and
checked in an independent child; the opt-in real YouTube test remained skipped.
Ruff lint/format, diff-check, 53 local documentation links/anchors and scope/privacy
review PASS. Exact-head Draft PR CI is required and recorded in GitHub checks.
This change is not deployed and does not implement the metadata subprocess. A thread
that never finishes keeps its owning handler/workspace alive until process termination;
there is no timeout that deletes files while that thread is still running. This fixes
cleanup ordering, not hard cancellation, broad reliability or uncertain-upload policy.

## Phase 9B bounded YouTube metadata (offline)

Initial Telegram YouTube inspection now uses an async service path. Process-wide
admission is shared by application `DownloadService` instances and uses a nonblocking
lock: one metadata operation, no queue, refusal before spawn when busy/quarantined.
Cache hits use that same admission. Instagram/TikTok do not share this gate. The
existing synchronous core API, choice model, callbacks, format selectors and media
download/delivery pipeline remain available and unchanged in behavior, including
PR #72's ownership of file threads before workspace cleanup.

The admitted child runs only `extract_info(download=False, process=False)` in a new
POSIX session. It receives a small environment allowlist (runtime path/locale, Python
module path and bytecode/user-site controls), never Telegram credentials, HOME or
proxy variables. Request URL/nonce and response metadata travel only through pipes,
not argv/files/logs/callback data. Metadata retries and yt-dlp disk caching are disabled;
media download settings are not changed. Installed Deno launching uses inherited
process groups and `--no-code-cache`; offline tests simulate its lifecycle with Python.

The wire contract binds schema and installed yt-dlp version, canonical provider URL,
video identity, random operation nonce and original monotonic timestamp. Its typed
JSON trees preserve dict/list/tuple and explicitly adapted `HTTPHeaderDict` values.
Duplicate keys/header aliases, cycles, bytes/sets, unknown runtime classes, callable,
`LazyList`, and deferred URL/playlist results are refused. No pickle, arbitrary class
restoration, `default=str`, `sanitize_info` codec or IPC-error extraction fallback exists.
Limits: request 8 KiB, response 2 MiB, depth 32, 100,000 nodes, decoded snapshot 8 MiB,
and 64 MiB for cached graphs plus entry/key/dictionary overhead. These are not a hard
RSS cap: upstream extraction/Deno, transient JSON/copies, allocator overhead and
consumed snapshots in download threads need separate resource observation.

Cache read/copy/pop/publication use a short `RLock`, never held across network or
FFmpeg work. Planning uses a private snapshot copy rather than shared cache lookups;
a concurrent download cannot make the planner perform a new synchronous extraction.
Decode/validation/planning/publication run in one dedicated, admitted CPU executor,
with cancellation-safe Future ownership and no accumulating jobs. TTL remains 180
seconds from the original inspection timestamp, capacity 32, oldest-timestamp eviction
and consume-on-download. RAM refusal preserves live entries instead of extra eviction.
After expiry, the existing download thread freshly extracts and rechecks exact quality.

The default 60-second decision deadline allocates 55 seconds to spawn/extraction/IPC
and reserves cleanup time. TERM grants 0.5 seconds for child/Deno cleanup, then KILL
targets the owned group. Publication requires direct-child reap, group absence proven
by ESRCH (not merely successful `wait()` or signal delivery), and drained pipe EOF.
EPERM remains present/unknown. Repeated cancellation cannot skip cleanup. Unknown
spawn/group/pipe cleanup retains handles and quarantines metadata admission until an
operator decision. A late OS spawn keeps an owner for one cleanup attempt; no automatic
retry/unblock occurs. Safety draining of finite CPU work and indeterminate OS spawn
can outlive the decision deadline; they are not abandoned to claim a hard timeout.

Offline tests cover successful and cached planning; same/different users; admission;
concurrent snapshot consumption; production worker extraction mode/environment;
malformed/partial/oversized IPC and request; crash/no response; unsupported objects;
spawn failure and cancellation before/during spawn; repeated cancellation; TERM/KILL
and a real group descendant; transient EPERM; quarantine/late spawn; pipe draining;
publication only after cleanup; fixed logging fields and no sensitive payload output.
Test-owned groups, executor threads and late tasks are joined/reaped in finalizers,
with loop errors checked for unhandled exceptions.

The parity matrix uses 13 source-shaped fixture sets and the actual installed yt-dlp
`process_ie_result`, selectors, native HTTP/DASH downloaders, local FFmpeg merger and
ffprobe. Fake HTTP returns locally generated media. Original/restored ChoicePlan,
Video/Audio/tiers, dimensions, exact IDs, M4A, playlist context, headers/protocol,
selected formats and local output streams are compared. A valid cached download must
not call parent extraction; expiry retains fresh extraction and exact-ID rejection.
Local tiny media stand in for transport; their physical resolution is not evidence
of real YouTube quality, playback or delivery. No LIVE or Telegram request is tested.

Final verification on Python 3.13.12 / yt-dlp 2026.08.19: **377 focused passed**
(85.99 s), including **94 new** codec, ownership, parity and responsiveness cases;
**full offline 2064 passed / 1 skipped**, 338.42 s. External Python socket/DNS calls
were denied through inherited sitecustomize, including children; the opt-in real
YouTube case stayed skipped. Reap/group/pipe checks, executor joins, unhandled-loop
error checks, Ruff lint/format, diff-check, local links/anchors and privacy/scope
review passed. The parity matrix exercised 54 paired local downloads. The exact-head
Draft PR CI result is recorded in GitHub checks, not assumed from local pytest.

Three offline measurements per path used a two-second synthetic inspection and an
independent existing callback handler with fake Telegram. Callback latency is lateness
relative to its planned 50-ms wakeup. Heartbeat statistics below are the median of
three per-operation maxima and their overall maximum, not a percentile of all ticks.

| Measurement, ms | Legacy p50 / max | Subprocess p50 / max |
| --- | --- | --- |
| Callback lateness | 1960.74 / 1960.83 | 1.00 / 1.81 |
| Heartbeat maximum lag | 2000.24 / 2000.28 | 7.79 / 62.37 |
| Operation duration, p50 | 2010.77 | 2686.60 |

The isolated path adds interpreter/IPC overhead while keeping the event loop available.
Absolute timings vary with machine load; these are offline scheduling measurements,
not real Telegram latency, a load test or a general availability guarantee.
No merge, Docker operation, environment change or deployment is part of this stage.

## Public deployment Stage D acceptance

After PR #66 merged, source main `389258cee9cf966be531ae5d6d60b192a59bcdb2`
passed [post-merge CI #39517532808](https://github.com/ip52rus/social-video-downloader/actions/runs/39517532808).
That quality workflow runs Ruff lint/format and the full pytest suite; prior full
network-blocked offline evidence remains **1769 passed / 1 skipped**, recorded below.
Deployment and these real Telegram tests were separately authorized after offline
verification; they are not synthetic test results.

| One sequential deployed case | Telegram delivery | Owner full playback / orientation / sound | Cleanup |
|---|---|---|---|
| TikTok `vm` short link | PASS | PASS / PASS / PASS | PASS |
| Instagram public Reel | PASS | PASS / PASS / PASS | PASS |
| YouTube short video, standard video/quality flow | PASS | PASS / PASS / PASS | PASS |

The deployed public-page TikTok path retained its source/media verification and
preparation gates. Delivery/playback was confirmed by the owner for all three cases;
the YouTube successful delivery marker was also observed in existing logs. No raw
Telegram responses or native diagnostic reports were captured for the TikTok and
Instagram cases. Detailed HTTP counts/statuses, byte totals, codecs and operation
latencies were not independently measured in this smoke stage and are not inferred
from earlier tests. No additional test request or automatic retry was initiated.

Read-only post-test checks found no active test worker/FFmpeg, temporary media or
download workspace. Bot and Local Bot API remained RUNNING, with no restart, OOM or
runtime error observed. Container/image identity, API volume mount and rollback image
were preserved. Git and `.env` were unchanged during Stage D; an external IDE workspace
file change was observed and left untouched.

The subsequent configuration finalization changed only TikTok true/2 in the existing
local Git-ignored `.env`, preserving all other content and mode 0600. Compose
validation and private resolved-config comparison, with both TikTok shell variables
removed, confirmed true/2, Instagram=true, APP_ENV=development and the existing Local
API endpoint; all other resolved settings stayed unchanged. No restart, recreation,
Telegram API call, download or additional live smoke was performed for finalization.
See [operator configuration](DEVELOPMENT.md#deployed-public-tiktok-configuration).

**PUBLIC DEPLOYMENT ACCEPTED** is scoped to these three scenarios. It does not prove
high-load behavior, broad platform reliability, `vt` live support, recovery/rollback
rehearsal or universal resolution of previous TikTok HTTP 429/403 failures.

## Phase 6I short TikTok share links (offline and controlled LIVE)

Short-reference tests use synthetic HTTP parsed by the real HTTP parser, generated
local MP4 and fake Telegram. Exact vm/vt host/path admission and capability planning
are network-free. Tests cover both hosts, multiple redirects, cycles/hop limits,
ambiguous Location, external/IP/login/photo destinations, public-IP/TLS policy,
identity mismatch, deadline/request budget refusal and no short/Embed/CLI fallback.
Redirect bodies are not read; scoped cookies are transferred only within the current
publication and cleared on error. Full links retain one metadata resolution without
short-link overhead. Reports/messages contain no tokens, locators, HTML or cookies.

Actual supervised workers exercise short-link MP4/decode/preparation/upload lifetime,
two concurrent short-link users with separate workspaces, hard timeout and cancellation
while short HTTP resolution is demonstrably active, worker reap and caller cleanup.
Synthetic admission tests additionally hold two slots, reject third/same-user work
before network, and keep a cancelled resolver's slot until ownership settles without
interrupting the other user's upload. Existing quarantine/repeated-cancel, silent/full
video, HTTP/framing limits, embed/benchmark, YouTube and Instagram remain regressions.

**53 targeted PASS; full offline 1769 passed / 1 skipped**, 227.63 s, with inherited
external socket/DNS denial in Python workers. Ruff lint/format, diff-check, local
links and privacy/scope/security review PASS. AST/source review confirms existing
transport/framing/acquisition/verification, supervisor exchange/reap, native policy
constants, public parser, configuration, dependencies, CI and MIT notice unchanged.
Implementation HEAD `b08f57d` passed CI #39511176476 (1769 passed / 1 skipped).
The offline stage performed no real TikTok/Telegram, polling, Docker or media download.
See [Phase 6I design and limitations](PHASE6I_TIKTOK_SHORT_LINKS.md).

### SHORT-LINK LIVE PASS on the implementation HEAD

A separately authorized local Telegram test processed one new `vm.tiktok.com`
mobile-app share link on `b08f57d`. The short redirect returned 301; final publication
validation and public-page metadata/source identity passed (page HTTP 200). One
`playAddr` candidate produced one complete MP4 via HTTP 200: 1,049,546 bytes,
one H.264 video stream and one AAC audio stream, 720×720, 14 seconds. Full FFmpeg
decode and passthrough preparation passed. One sendVideo returned a confirmed video
Message in the correct chat, with the file present through the response. The owner
confirmed playback, orientation and sound.

Metadata: 2 attempts / 415,102 body bytes; media: 1 attempt / 1,049,546 bytes;
one acquisition and one upload attempt, exact counters. Unread redirect bodies,
headers and wire overhead are excluded from body-byte counters. Native operation:
3.409 s; controlled runner: 643.211 s including waiting for the owner's message,
not a measured download/upload duration. Polling/session, worker/FFmpeg and both
workspaces were cleaned; containers stayed exited. No retry, fallback, merge or
deployment. With owner approval, old updates stayed unacknowledged and untouched;
only a new approved-link update was fed once to the existing dispatcher. Restart
replay prevention and ordinary polling acknowledgement were not validated.

Live evidence covers one `vm` link only. `vt` has offline coverage, no separate live
test; broader mobile-link coverage, high-load behavior and general reliability are
unverified. Previous HTTP 429/403 remain possible. See
[the detailed acceptance](PHASE6I_TIKTOK_SHORT_LINKS.md#owner-confirmed-short-link-live-pass).

Final docs-only preparation repeated the full network-blocked suite: **1769 passed,
1 skipped**, 219.88 s. Ruff lint/format, diff-check, local links, privacy/security and
final PR review passed. No Python/configuration/dependency/CI changes or new real
platform calls were made. Exact new documentation-head CI is required before handoff
(PR #66 checks); merge and deployment remain separate owner decisions.

## Phase 6H public TikTok MVP (offline and controlled LIVE)

**356 focused PASS; full offline 1716 passed / 1 skipped**, 191.87 s. The skipped
case is the opt-in real YouTube smoke. External socket/DNS operations were blocked
by an inherited Python guard, including in native workers. Ruff lint/format,
diff-check and compact scope/security review PASS. Exact committed-head PR CI is
required before handoff; the PR checks record the final publication result.

Seven new public-access/concurrency cases and updated configuration/lifecycle tests
verify public access without user lists, disabled-by-default routing, TikTok allowed
in production while Instagram remains guarded, validated process capacity, two real
supervised workers using synthetic HTTP/generated MP4, third/same-user rejection,
slot reuse, independent files and cancellation, retained quarantine and global blocking
on cleanup failure. Existing native sound/silent, metadata/media 403/429, truncation,
size, upload timeout/error/unconfirmed delivery, repeated process-group cancellation,
CLI/benchmark, YouTube and Instagram regressions all pass. The tests verify actual
worker reap and file ownership through upload; no live Telegram API is used.

Only TikTok admission/configuration changes: public-page parser, provider, transport,
network/framing/budget policy, preparation, dependencies, CI and MIT notice are
unchanged. Compose only forwards default-off/default-two settings; no Docker command
starts or changes a container. Offline preparation performed no live acceptance or
deployment. The subsequent separately authorized public test is recorded below;
historical earlier controlled LIVE evidence and 429/403 limits remain below.
See [Phase 6H](PHASE6H_TIKTOK_PUBLIC_MVP.md).

### PUBLIC TIKTOK LIVE PASS on the implementation HEAD

CI #39469733288 passed on `6665b90f6057e2b08034aa6866ee83528378fa1a`:
1716 passed / 1 skipped; Ruff lint/format PASS. The subsequent owner-authorized local
test processed one full public-video link from a second Telegram account without a
personal allowlist. Public-page metadata/source ID, complete MP4, full decode and
passthrough preparation passed. One media GET returned 200; the 565,847-byte MP4 had
one H.264 video/AAC audio stream, 576×1024, duration 14 seconds as verified by the
engine. One sendVideo returned a confirmed video Message in the correct chat, with
the local input present through the API response. The owner confirmed normal playback,
orientation and sound on the second account.

Metadata 1 request / 409,411 bytes; media 1 request / 565,847 bytes; one acquisition
and one upload attempt, exact counters. Native operation: 2.611 s; controlled runner:
4.124 s. Polling/session, worker reap, media and workspace cleanup PASS. Containers
remained exited; no retry, fallback, merge or deployment.

The owner-approved queued link was read without offset/acknowledgement/deletion and
fed once through the existing dispatcher/handler; later events were not processed.
Queue acknowledgement or replay prevention on later restarts was not tested. No
additional queue/polling action is implied. The controlled case establishes public
access and real delivery, not scalable concurrency, short-link support, all-publication
support or general TikTok reliability. Earlier 429/403 outcomes remain historical
limits.

Final docs-only preparation repeated the full network-blocked suite: **1716 passed,
1 skipped**, 186.73 s. Ruff lint/format, diff-check, privacy/security and final PR
review passed; 30 local documentation links/anchors were checked without errors.
Source, configuration, dependencies, CI and other worktrees were not changed. Exact
new documentation-head CI is required before handoff (see PR #65 checks); merge and
deployment are not authorized by this acceptance.

## Phase 6G public-page Telegram acceptance (offline and controlled LIVE)

**226 focused PASS**, including 19 new provider/export/fault/CLI cases. Tests use
synthetic real-parser HTTP, generated H.264/AAC and silent MP4, the real supervised
worker, existing provider and fake Telegram. The full success path verifies file
lifetime until `answer_video` completes and actual worker reap before publication.
Failure cases verify metadata 403/429, missing/invalid/ambiguous state, identity
mismatch, missing playAddr, forbidden CDN, explicit separate audio, media 403,
truncated framing and size refusal. Domain/user errors contain no raw source data.
Counters prove one metadata resolution and at most one media acquisition, no embed
request/fallback/retry; partial/private/caller files are cleaned after refusal.

Existing integration cases now exercise public-page success and overwrite refusal;
default embed export and CLI/benchmark remain covered. The prior internal export
rejection is replaced by safe public export after reap plus three CLI export-denial
cases. Existing repeated cancellation/timeout, upload failure/uncertain response,
quarantine/blocking, allowlist/production guards and platform regressions pass.
Socket/DNS denial is inherited by Python workers. Ruff lint/format, diff and compact
scope/security review PASS. Parser, transport/policy constants, verification,
supervisor lifecycle, handler/config/bot wiring, platforms, dependencies and MIT
notice remain unchanged; only the internal page-export admission is broadened.
Exact-head GitHub CI must pass before handoff; only its PR base filter is extended
to `feat/tiktok-public-page-mp4` for the new stacked Draft PR.

Full offline suite with inherited socket/DNS denial: **1696 passed, 1 skipped**
(the opt-in real YouTube smoke), 190.10 s. Ruff lint/format, diff-check and
scope/security review PASS. Publication CI is verified on the exact committed HEAD
and reported in GitHub checks and the handoff; no live delivery acceptance is implied.

Offline preparation made no real TikTok/Telegram calls, started no polling/Docker
and performed no deployment. Separately authorized Phase 6F native evidence is one
571,013-byte H.264/AAC MP4, 576×1024, 12 s per CLI, one metadata request / 410,890
bytes and one media request (200), 5.506 s with exact counters/decode/passthrough/
cleanup PASS. Metadata HTTP status was not separately exposed. That gate proved
one native download; it did not by itself prove Telegram delivery.

The subsequent owner-authorized Phase 6G test on
`5896383b4123983da85ea2f1cebe46f48a119b9d` passed real Telegram delivery: one queued
owner message, one public-page metadata request / 411,812 bytes, one media GET
(200) / 571,013 bytes and one acquisition. Original ID and Content-Length passed;
actual H.264/AAC streams, 576×1024, 12 s per engine, full FFmpeg decode and passthrough
preparation passed. Metadata HTTP status was not separately exposed. Exactly one
sendVideo returned a confirmed video Message in the correct chat; file lifetime
covered upload. Native operation took 2.863 s, handler/delivery 5.432 s, exact counters
and private/caller workspace cleanup passed. Polling/session/worker/FFmpeg stopped;
containers remained exited. The owner confirmed normal playback, orientation and
sound. No retries, embed fallback, merge or deployment occurred.

**Phase 6G controlled LIVE PASS** closes that single-case end-to-end gate. It is not
proof of broad publication support, general TikTok reliability, resolution of the
earlier embed 429 cause or production readiness. Feature flag remains off by default
with a development/test-only user allowlist. Further live runs, staged merge and
deployment require separate authorization.
See [Phase 6G](PHASE6G_TIKTOK_PUBLIC_PAGE_TELEGRAM.md).

## Phase 6F public-page MP4 preparation (offline)

**20 new cases, 208 focused PASS** with synthetic real-parser HTTP and generated
local MP4. The explicit `--public-page` mode verifies sound/silent files through
the actual worker, ffprobe, full FFmpeg decode and passthrough preparation. Failure
cases cover metadata 403/429, identity/schema/missing playAddr/forbidden CDN,
separate streams before GET, media 403, incomplete Content-Length, size refusal,
timeout/cancellation, exact counters and owned cleanup. Signed-query/header/cookie
checks use actual outbound requests; reports omit source locators, HTML and IDs.
Existing public-page metadata-only, native/embed/benchmark and Telegram cases pass.

Six additional temporary offline fault injections pass: forbidden page-to-embed
and media-to-external redirects before another connection, allowed same-domain
cookie forwarding, metadata-only media denial and public worker 403/429 categories.
AST comparison confirms 11 core functions/classes and eight network/resource
constants unchanged, including Session, DNS/TLS pinning, framing, verifier and
supervisor exchange. The public parser is unchanged. Provider, handler, CLI
wrapper, dependencies, config example and MIT notice are byte-identical to base.

Full suite with inherited external socket/DNS denial: **1678 passed, 1 skipped**
(opt-in real YouTube smoke), 181.24 s. Ruff lint/format and diff/scope/security review
PASS. CI's PR base filter adds only `feat/tiktok-public-page-prototype`, allowing the
new stacked Draft PR to run unchanged jobs. Exact committed-head CI must pass before
handoff; its result is recorded in GitHub checks and the handoff report.
No real TikTok/Telegram request, media download, Docker operation or deployment
occurred in preparation. Its subsequent owner-authorized native MP4 live gate passed
as recorded above; subsequent real Telegram acceptance is recorded in Phase 6G above.
See [Phase 6F](PHASE6F_TIKTOK_PUBLIC_PAGE_MP4.md).

## Phase 6E public-page prototype (offline and separately authorized metadata-only)

Controlled Telegram attempts after Phase 6D received owner messages and stopped
on embed metadata HTTP 429, before media GET/acquisition/upload. Polling/session/
workspace cleanup completed. This is an observed HTTP refusal, not proof that
Telegram changes HTTP headers, that cookies are required or that a public page
will succeed. No real delivery/playback acceptance is closed by those attempts.

**45 new focused cases pass** with synthetic wire responses, the real HTTP parser
and inherited socket/DNS denial. Coverage includes actual CLI/provider outbound
request equality for tracking queries, installed yt-dlp schema/mapper comparison,
original identity checks, intact signed queries, script/JSON ambiguity, inert/comment
markers, status/photo/private refusals, hostile destinations/redirects, HTTP 403/429
without retry, body/request/deadline budgets, scoped cookie destruction, no media
phase request and fixed-category parser errors without raw data. Existing native
CLI/benchmark and Telegram regressions are retained unchanged.

Source review: PR #60 and #61 URL/Session/pinned transport/cookie/framing ASTs match;
the prototype changes no engine, handler, CLI, header, cookie or dependency policy.
Only schema facts were studied in pinned Cobalt and installed yt-dlp; no upstream
AGPL implementation was copied. Ruff lint/format and diff-check pass. The CI base
filter includes `feat/tiktok-telegram-integration` so this separate stacked Draft PR
receives the same checks without changing PR #61. Final full suite with inherited
external socket/DNS denial: **1658 passed, 1 skipped** (opt-in real YouTube test),
including all original native CLI/benchmark/Telegram regressions. Exact-head CI
must also pass before handoff. No test worker or FFmpeg process may remain.

The prototype initially had no live entry point. The subsequent separately
authorized metadata-only call on `4265328` returned HTTP 200, valid universal JSON,
matching ID and one admitted `playAddr`: one request / 405,981 bytes, no media
request, 2.632 s supervised elapsed time, exact counters and cleanup PASS. This
does not establish general improvement to 429; page-based MP4 availability was
subsequently checked only in the single separately authorized Phase 6F case above.
`inspect_public_page()` stays metadata-only; any new live call requires separate
approval and owned process supervision. See [Phase 6E](PHASE6E_TIKTOK_PUBLIC_PAGE.md).

## Phase 6D restricted TikTok integration (offline)

The preceding separately authorized native reliability benchmark on `511b538`
passed 4/4 new publications: complete MP4, one actual video/audio stream, H.264/AAC,
FFmpeg decode and preparation passthrough. Metadata: 4 requests / 1,142,585 bytes;
media: 4 requests / 14,460,237 bytes; four acquisitions, 19.152 s, exact counters and
cleanup PASS. This is native live evidence, not Telegram delivery or population-wide
reliability; earlier B still returned 403 in its two authorized experiments.

Phase 6D uses synthetic HTTP, generated local MP4 and fake Telegram clients under
inherited external socket/DNS denial. **143 focused cases pass**: the 103 original
CLI/benchmark cases plus 40 integration cases. Tests verify local provider capabilities,
silent/sound output, file lifetime through upload, exclusive publication, 403/oversize/
incomplete response, flag/access/config guards, actual dispatcher routing, uncertain
Telegram response, upload error/timeout and cancellation. Repeated cancellation with
live/exited group leaders confirms termination/reap and continued event-loop progress.
Injected OS cleanup refusal blocks work and quarantines rather than deleting files;
the test emergency-cleans its own processes and workspace.

Full offline suite: **1613 passed, 1 skipped** (opt-in live YouTube test), including
existing YouTube/Instagram and local FFmpeg checks. Ruff lint/format and diff-check
pass. Scope review confirms unchanged native resolver, transport, preparation,
network/resource constants and complete MIT attribution; no dependency changes.
Exact-head CI must also pass on the new stacked Draft PR before handoff; the CI
pull-request base filter includes `feat/tiktok-native-public` for this purpose.
No real TikTok/Telegram call, Docker operation, polling or deployment is performed
by these tests. A separately authorized restricted Telegram live test remains open.

## Phase 6C native TikTok (offline)

Separate from discontinued PR #59, the native CLI uses the embed-state schema
from inspected MIT tt-dlp sources, not its downloader/retry framework. All new
tests deny external socket connections and use synthetic `HTTPResponse` wire
data or generated local media. No TikTok/Telegram request, Docker or deployment.

The focused set covers full URL admission, explicit source ID/missing or duplicate
state, play/bitrate/download/urls layouts, split-audio evidence, strict video-host
admission, forbidden redirects, mixed private/reserved DNS answers and exact pinned
IPv4 plus original TLS SNI/hostname verification. Cookie tests exercise host-only,
domain/path/secure scoping, cross-CDN non-forwarding and isolated operation jars.
Real HTTP parser cases reject missing/duplicate length, truncated and chunked media;
byte caps apply to returned bodies and partial files are removed. 403/429 do not
retry or select another format. Identity mismatch stops before media GET/B.

Two generated MP4 fixtures exercise both public worker cases through actual
ffprobe, full FFmpeg decode and `prepare_telegram_video(..., allow_silent=True)`:
audio in A and no audio stream in B, passthrough without conversion, followed by
owned workspace removal. A missing audio stream fails A; explicit split-audio
evidence cannot be silently treated as silence. Deadline with an exited leader/
live descendant and interrupt cleanup are also covered, with emergency test cleanup.

Offline evidence does not prove embed availability, anonymous-cookie sufficiency,
CDN access, real audio behavior, Telegram delivery or production reliability.
Results: **44 focused cases passed**; full suite with external sockets forbidden:
**1514 passed, 1 skipped** (opt-in external YouTube test), including local
FFmpeg/ffprobe. Ruff lint/format, diff, local documentation targets, MIT notice
comparison and security/scope review pass. Exact-head GitHub CI is checked after
publication. Only a separately authorized real A/B experiment can close the live gate.

Photo-placeholder regression: the old key-presence check was reproduced failing on
valid synthetic video with `imagePost=null`. Both photo keys and both source levels
now accept only null/empty object/empty array placeholders, while still requiring
valid video data and admitted candidates. Filled image lists, unknown/malformed or
conflicting structures, identity mismatch, no extra HTTP requests and sanitized
failure results are covered. Updated offline verification: **72 focused cases
passed**, full suite **1542 passed, 1 skipped**, with an inherited Python audit
hook denying socket connections/DNS and synthetic HTTP/local FFmpeg only. Ruff
lint/format, diff and security/scope checks pass. Code outside `resolve()` is
unchanged; exact-head CI is verified after publication.

The first owner-authorized native live run was **BLOCKED** on A:
`unsupported_photo`, one metadata request / 281,910 bytes, 1.376 s, no media request
or acquisition, B not run, exact counters and successful cleanup. HTML was not
retained; the actual photo-field values and media availability remain unknown.
No TikTok/Telegram request or Docker operation was made for the offline fix.

The next separately authorized A/B run on `85ab929` was **PARTIAL PASS**: A complete
1,097,768-byte MP4, one video/audio stream, FFmpeg decode and Telegram passthrough
PASS; B metadata PASS but media GET 403. Aggregate: 5.149 s, metadata 2 requests /
566,367 bytes, media 2 requests / 1,097,768 bytes, 2 acquisitions, exact counters,
cleanup PASS. Reported constant codec labels were not independent measurements.

The targeted CDN diagnostic patch is offline only. Synthetic HTTP parser responses
cover candidate source/deduplication, success/403 statuses, scoped cookie presence
across redirects, missing measurements after send failure, safe per-case counters,
no additional HTTP/retry, secret exclusion and owned worker/workspace cleanup.
Generated local MP4s verify actual ffprobe codec reporting; isolated synthetic probe
results cover non-default, missing, unknown and invalid codec names. Network policy,
preparation and FFmpeg behavior are unchanged. Verification: **85 focused passed**;
full suite **1555 passed, 1 skipped** with the inherited socket/DNS audit guard.
Ruff lint/format and diff checks PASS. Differential offline review confirmed
identical outbound HTTP/headers/cookie scope/redirects/counters and candidate
selection before/after the patch. Exact-head CI is checked after publication.

The authorized B-only run on `f3213d6` was **BLOCKED**: one candidate from `urls`,
CDN family tiktokcdn-eu.com, query present, no cookies sent, media HTTP 403. Metadata
1 request / 286,670 bytes; media 1 request / zero bytes; one acquisition; 1.788 s,
exact counters and cleanup PASS. No file inspection or audio validation occurred.

Reliability preparation adds only an explicit benchmark mode; no further live test.
**103 focused cases PASS** with external sockets forbidden. Synthetic wire and
generated local media cover continuation after 403, separate cookie jars, source
provenance, exact case/aggregate counters, no repeated media GET, required/optional
audio, shared metadata/media request/byte/deadline caps, partial-error file cleanup,
cleanup-error stopping, input validation, public worker and normal CLI compatibility.
Private markers are excluded from reports. Full offline suite: **1573 passed,
1 skipped** (external YouTube opt-in), with inherited socket/DNS denial. Ruff
lint/format and diff checks PASS. Differential scope review confirmed ordinary
fail-fast output/request compatibility and unchanged resolver/transport/policies/
limits/supervisor. Exact-head CI is verified after publication. No Docker/Telegram
operation or real TikTok request is part of this preparation.

## Phase 4 functional acceptance (2026-10-15)

Status: **ACCEPTED for the tested functional scope**, as confirmed by the user. This is
real Telegram client evidence, separate from deterministic tests and provider-only live
checks. It does not mean exhaustive format coverage or production readiness.

Revision: main `ced1200bf2a81a1bb63c200e6441e8458d0af0df`, containing PR #41 and PR #42.
The existing Compose stack was deployed by rebuilding/recreating only `bot`; all 24
source files matched current main. Polling was active through the Local Bot API, with no
startup errors. The Local Bot API container/image and named volume were preserved.
No additional deployment or live test was performed for this documentation update.

| Accepted functionality | Evidence | Scope/limits |
| --- | --- | --- |
| Individual watch URL with playlist context | Video/Audio choices appeared and the intended individual video was delivered | The original `list` case worked; this is not playlist support |
| Video / Audio choices | User confirmed both flows in the real client | Only useful available qualities are shown; no exhaustive capability matrix |
| Landscape Medium | 936x720, class 720, 243 seconds, 19,389,783 bytes; user confirmed image/sound | Existing sanitized upload and Telegram response logs corroborate dimensions, duration and size |
| Portrait Medium | 720x1280, class 720; user confirmed image/sound | User-reported client result; exact size not recorded here |
| Portrait High | 1080x1920, class 1080; user confirmed image/sound | User-reported client result; exact size not recorded here |
| M4A audio | User confirmed M4A, playback and correct nonzero displayed duration | Exact passthrough/remux/transcode route is not established by the extension |
| Callback protection | A rapid second press did not deliver duplicate media and produced an unavailable-choice response | Does not independently prove two callbacks reached the server or the exact invocation count |
| Distinct-URL isolation | Two different source interactions delivered their respective audio files | Consumed inline buttons disappeared, so another press was not possible in that check |
| Local Bot API above 50 MB | Prior real-client delivery succeeded with playback | Historical evidence, not repeated on this revision; not proof of arbitrary sizes or 2 GB support |

Observed reliability issue, kept separate from playlist/quality acceptance: at 21:34:34
Moscow time, yt-dlp reported `HTTP Error 403: Forbidden` while fetching video data,
followed by `DownloadFailedError`. The terminal callback had reached downloading rather
than being rejected by the 15-minute interaction TTL. No traceback, DNS/timeout indicator,
or terminal acknowledgement/keyboard-cleanup failure was present in that log window.
The retry interaction succeeded, with delivery at 21:36:45. Exact runtime tier/options and
cache hit/miss were not logged; the nested Python exception class and the upstream reason
for 403 remain NOT VERIFIED. A roughly 13-minute wait exceeds the 180-second inspection
cache lifetime, so the original snapshot cannot remain valid for that first attempt;
this does not establish cache expiry as the cause of 403.

Verification categories and outstanding limits:

- The implementation gate remains 469 passed, 1 skipped with Ruff lint/format, quiet
  Compose config validation and diff check passing. These historical deterministic/local
  results are not new test runs for this documentation update.
- Missing/partial dimensions, unsafe-only video, audio-only fallback, BLOCKED and absence
  of unrestricted-best are covered by deterministic tests; rare real-media cases were
  not deliberately triggered. A post-PR #42 portrait Low result is NOT VERIFIED here.
- Real-client evidence covers the recorded cases, not every codec, orientation/tier
  combination, Telegram client or source. Source-metadata honesty, live injected API
  failures, production throughput and robust restart/network recovery are not established.
- Phase 8 owns obsolete choice-prompt cleanup and remaining UX polish. Phase 9 remains
  OPEN for intermittent HTTP 403/bounded recovery, synchronous metadata blocking the
  async event loop, network resilience, restart/recovery and monitoring. Existing analytics
  tasks remain unchecked; functional acceptance does not imply analytics implementation.

## Deterministic tests

Fast deterministic tests cover URL normalization, provider detection, filename
sanitization, configuration parsing, logging configuration, bot/dispatcher construction,
handler behavior, media preparation, upload-parameter extraction, and error mapping.

Current deterministic coverage includes:

- `tests/test_config.py` for required token handling, defaults, normalization, invalid
  values, token redaction in the settings repr, and immutability.
- `tests/test_bot.py` for bot and dispatcher construction, including default cloud Bot
  API and optional local API endpoint configuration.
- `tests/test_handlers.py` for `/start`, invalid links, unsupported domains, non-YouTube
  platform messaging, mocked download/delivery, safe error responses, and temporary
  workspace cleanup.
- `tests/test_download_service.py` for provider selection, URL normalization, delegation,
  and recognized platforms without configured providers.
- `tests/test_telegram_media.py` for compatible MP4 passthrough, H.264/AAC stream-copy
  remux for compatible non-MP4 input, remux-failure fallback to transcode, AV1/Opus
  transcoding to H.264/AAC, post-conversion verification, rotation-aware upload
  dimensions, missing audio, and FFmpeg failure mapping.

Audit fallback checks in the Codex environment:

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q -p no:cacheprovider`: 189 passed, 1 skipped.
- `.venv/bin/ruff check . --no-cache`: passed.
- `.venv/bin/ruff format --check . --no-cache`: 50 files already formatted.

These fallback commands were used because `uv` was not available in the default PATH of
the Codex shell during the audit. This was an environment/tool discovery issue, not a
test failure.

Current preferred checks after locating `uv` at `/Users/user/.local/bin/uv`:

- `/Users/user/.local/bin/uv run pytest -q`: 190 passed, 1 skipped.
- `/Users/user/.local/bin/uv run ruff check .`: passed.
- `/Users/user/.local/bin/uv run ruff format --check .`: 50 files already formatted.

When `uv` is available in PATH, the standard project commands are:

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

## Focused Telegram callback resilience (2026-10-15)

Deterministic fault-injection coverage in `tests/test_handlers.py` verifies:

- Network/API failures during terminal acknowledgement and keyboard cleanup, separately
  and together, still start exactly one download with the exact stored URL/options.
- Repeated and concurrent terminal callbacks cannot start a second download; a failed
  atomic consume never starts one. Audio/video delivery is not retried.
- Mode-to-quality acknowledgement failure still attempts the keyboard edit; edit failure
  preserves unconsumed state and permits retrying the old mode button or using a quality
  keyboard whose edit reached Telegram before the response was lost.
- Metadata/domain-error notification failures do not rerun planning/download and log
  only original/Telegram exception categories. Cancellation and unrelated programming
  errors propagate through the new handlers.

Verification for this fix:

- Handler/store tests: 94 passed.
- `uv run pytest`: 303 passed, 1 skipped (opt-in external YouTube live matrix).
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: 57 files already formatted.
- `docker compose config --quiet`: passed; rendered configuration was not printed.
- `git diff --check`: passed.

These implementation-stage checks were unit/deterministic integration evidence without
a container rebuild. Subsequent functional client acceptance is recorded above. Forced
live Telegram network-failure recovery remains unverified; deterministic fault tests and
functional acceptance do not establish production reliability.

## M4A audio and duration (2026-10-15)

Network-free tests in `tests/test_telegram_audio.py`, `tests/test_youtube_provider.py`
and `tests/test_handlers.py` cover:

- Real yt-dlp selector evaluation against synthetic formats: native AAC/M4A preference,
  best ranked native choice, best-audio fallback and rejection of a codec-mislabelled
  native preference. Explicit audio IDs and existing video selectors remain covered.
- Native AAC/M4A passthrough, AAC stream-copy remux, incompatible-codec transcode,
  remux-failure fallback, actual container/codec verification rather than extension-only
  detection, invalid/corrupt input, FFmpeg failure and partial-output cleanup.
- Positive metadata duration; missing, zero, negative, boolean, NaN/infinite and
  out-of-range duration; container/stream and source/output probe fallback; omission
  when unknown; correct prepared path/duration sent through `answer_audio`.
- Safe preparation failure and request-workspace cleanup. Existing video delivery and
  PR #39 callback fault/concurrency tests remain passing.

`tests/integration/test_audio_preparation.py` adds four real local checks, using 0.35 s
synthetic tones or deliberately corrupt bytes exclusively in pytest temporary storage:

1. Native AAC/M4A: original file/hash preserved; exactly one ffprobe, zero preparation
   FFmpeg calls.
2. AAC/Matroska: one stream-copy FFmpeg call; output verified AAC/M4A; all encoded AAC
   packet SHA-256 hashes match the input. This does not claim decoded/timestamp identity.
3. Opus/WebM: one AAC encoding FFmpeg call; output verified AAC/M4A. Bitrate is capped
   without implying improved quality over the source.
4. Corrupt M4A: safe rejection, no output file.

Performance gate: native audio is neither remuxed nor transcoded. Successful conversions
use one input probe and one output verification, with duration in those same probes only
when needed. Failed remux recovery may require another FFmpeg call/output verification.
There is no large passthrough copy or standalone duration probe. Encoding caps are
128 kbps/stereo-or-other, 64 kbps/mono, limited by known source bitrate; unknown bitrate
uses the cap. Real encoding adds CPU/latency and may lose quality. Throughput, concurrency
and production latency were not benchmarked.

Verification:

- `uv run pytest`: 357 passed, 1 skipped. All four synthetic FFmpeg tests ran locally;
  they skip explicitly when FFmpeg/ffprobe are absent. The external YouTube test skipped.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: 60 files already formatted.
- `docker compose config --quiet`: passed, without rendering configuration.
- `git diff --check`: passed.

That implementation stage performed no live YouTube download, Telegram API call,
running-stack rebuild/restart or long transcoding benchmark. Subsequent M4A playback and
displayed-duration acceptance is recorded above; route-specific live verification and
production performance are not implied.

## YouTube watch URLs with playlist context (2026-10-15)

Network-free regressions in `tests/test_youtube_provider.py` cover:

- Ordinary single-video targets remain unchanged. Watch URLs with a valid single `v`
  and playlist `list` use the individual-video extraction target; unrelated query
  parameters retain their values and original escaping.
- Encoded parameter names/IDs, empty/repeated playlist context, invalid/missing/duplicate
  video IDs, playlist-only URLs, credentials, schemes, and deceptive hostnames.
- A fake extractor reproduces yt-dlp's unprocessed `_type=url` response and the former
  false `BLOCKED / no_useful_modes`. Canonicalized URLs instead produce identical
  `CHOOSE_MODE` plans with audio/video and unchanged Low/Medium/High choices.
- Both inspection orders share one cache entry. Downloads use the canonical target
  with or without a prior inspection and reuse the inspected snapshot.
- Metadata calls retain `download=False`, `process=False`, and `noplaylist=True`, never
  invoke fake media processing, and do not enumerate playlists. Installed yt-dlp's local
  extractor matching confirms the canonical targets select the video extractor.

Verification:

- `uv run pytest`: 417 passed, 1 skipped; 60 new parametrized regression cases. The
  opt-in external YouTube matrix was explicitly disabled; synthetic FFmpeg tests ran.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: 60 files already formatted.
- `docker compose config --quiet`: passed; rendered configuration was not printed.
- `git diff --check`: passed.

The checks used offline uv execution with a temporary cache directory because the
sandbox could not access the default uv cache. No dependency/configuration changes or
live YouTube/Telegram requests were made in that implementation stage. Compose was not
rebuilt then. Subsequent deployment and playlist-context functional acceptance are
recorded above; broad reliability remains open.

## YouTube quality-selection safety (2026-10-15)

Before implementation, two new regressions failed on the existing code: installed
yt-dlp selected landscape 1080-class for a portrait 720-class quality, and an empty
YouTube quality list produced `DIRECT_DOWNLOAD` with no quality ID. Both are now covered
as passing regressions.

Network-free provider/choice tests evaluate the installed yt-dlp selectors against
representative synthetic format dictionaries, not only selector strings. They cover:

- Portrait, landscape, square and mixed orientation; formats sharing a height with
  different short-side classes; deterministic dimension IDs and tier collapse.
- Exact dimensions through native H.264/MP4/AAC, progressive combined audio/video, and
  incompatible-codec/container fallbacks. Every video branch retains both dimensions;
  video-only sizes without a pairable audio stream are not offered for video-with-audio.
- Width-only, height-only, no dimensions, empty qualities, and only above-1080 video:
  safe audio-only remains available or the application blocks the request. The generic
  classifier retains `SINGLE_DIMENSION`; non-YouTube automatic policy remains unchanged.
- Missing video quality ID, disappeared dimensions or dimensions changed after cache
  expiry, and missing selector matches fail without unrestricted fallback.
- Existing playlist-context extraction/cache/download identity tests use concrete safe
  video IDs. The opt-in live matrix now also uses concrete video IDs; it is not run here.
- A single safe YouTube quality produces a direct plan with the exact provider ID and
  downloads through the same inspected snapshot without a second metadata extraction.

The enforcement is based on extracted dimensions. These tests cannot establish source
metadata honesty, actual encoded pixel dimensions, or future YouTube availability. The
short-side metric is not a limit on the longer side, encoded bytes, CPU, or latency.
Provider facts may still describe above-ceiling video; the YouTube application policy
excludes it from normal product choices. No media/network retry policy changes are made.

Verification:

- `uv run pytest`: 469 passed, 1 skipped. The external YouTube matrix was explicitly
  disabled; existing synthetic FFmpeg integration, M4A, video and callback fault tests ran.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: 60 files already formatted.
- `docker compose config --quiet`: passed; rendered configuration was not printed.
- `git diff --check`: passed.

uv ran offline with a temporary cache because the default cache is sandbox-restricted.
No dependency/configuration changes, live YouTube requests/downloads, Telegram calls,
or Compose rebuilds/restarts were performed in that implementation stage. Subsequent
functional client evidence is recorded above; rare live audio-fallback/BLOCKED cases and
broader network/recovery behavior remain unverified.

## PR #27 media-preparation validation

Deterministic automated coverage:

- Mock/runner tests confirm compatible non-MP4 H.264/AAC input uses FFmpeg stream-copy
  remux with `-c copy`.
- Deterministic coverage verifies remux command failure falls back to the transcode path.
- Focused media tests: `tests/test_telegram_media.py` passed with 12 tests.
- Full branch suite: 190 passed, 1 skipped.

Real local FFmpeg validation used `/usr/local/bin/ffmpeg` and
`/usr/local/bin/ffprobe`, version 9.0.2. All media was synthetic and created outside the
repository. These checks did not perform a YouTube network request, Telegram upload,
VPS/server benchmark, large-file validation, or 2 GB validation.

Case A - compatible MP4 passthrough:

- Input: MP4, H.264/AAC, 640x360, 8.0 seconds.
- `prepare_telegram_video()` returned the original file.
- Only ffprobe was invoked; there was no preparation FFmpeg invocation.
- The source file remained unchanged.
- Result: pass.

Case B - compatible MKV stream-copy remux:

- Input: Matroska, H.264/AAC, 640x360, 8.021 seconds.
- Output: MP4, H.264/AAC, 640x360, 8.0 seconds.
- The preparation command used stream mapping for the first video/audio streams,
  metadata mapping, `-c copy`, and `-movflags +faststart`.
- Exactly one preparation FFmpeg invocation ran; `libx264` was not invoked.
- Dimensions were preserved and the duration delta was approximately 0.021 seconds.
- Encoded H.264 packet payload hashes matched 240/240.
- Encoded AAC packet payload hashes matched 376/376.
- Decoded video framemd5 hashes matched 240/240.
- Exact decoded AAC checksum did not match because MKV and MP4 produced different AAC
  priming, timestamp, or frame-boundary interpretation.
- Result: pass for the intended stream-copy behavior, with the decoded AAC caveat above.

Case C - incompatible source fallback transcode:

- Input: Matroska, MPEG-4 video, AAC audio, 320x180, 5.021 seconds.
- Output: MP4, H.264/AAC, 320x180, 5.013 seconds.
- The original incompatible source was not returned.
- The real preparation command used `libx264`.
- The existing transcode path still worked.
- Result: pass.

The real validation does not prove whole-file byte identity, decoded audio bit identity,
lossless decoded audio equivalence, large-file behavior, or production performance. Real
FFmpeg remux-failure injection was not repeated; that fallback is covered by the
deterministic remux-failure test.

## YouTube external/live tests

External YouTube tests are opt-in and must not run without an explicit URL.

Set `YOUTUBE_LIVE_TEST_URL` only when intentionally running real YouTube downloads:

```bash
YOUTUBE_LIVE_TEST_URL="https://www.youtube.com/watch?v=..." uv run pytest tests/integration/test_youtube_live_matrix.py
```

Current YouTube verification snapshot:

- GitHub Actions run [37966225469](https://github.com/ip52rus/social-video-downloader/actions/runs/37966225469) passed 131 tests on merge commit f27051fded257b5f39056c45333b4fa8c50075a3; Ruff lint and format checks passed.
- Real regular-video downloads were verified in `VIDEO_WITH_AUDIO`, `VIDEO_ONLY`, and
  `AUDIO_ONLY` modes.
- Live matrix run on 2026-10-09 for `https://www.youtube.com/watch?v=dQw4w9WgXcQ` passed
  in 140.06 seconds. It verified combined video/audio MP4, selected-quality video-only
  output, and audio-only outputs in two distinct containers using ffprobe.
- Shorts were verified in all three modes; additional successful Shorts smoke tests were
  recorded for `VF_MOfnz7OY` and `osrN3A_Rdiw`.
- A duplicate audio format ID issue was reproduced and fixed; selector `251-0/251`
  successfully downloaded Opus audio.

This is targeted evidence, not proof of broad YouTube reliability across all content and
platform conditions.

## Telegram cloud/live tests

The default bot configuration uses Telegram's cloud Bot API when `TELEGRAM_API_BASE_URL`
is unset. Deterministic tests do not exercise a real Telegram cloud upload or polling
session.

Cloud live checks should cover:

- bot polling;
- a small public YouTube URL;
- user-facing error behavior;
- playback on relevant Telegram clients;
- behavior when cloud upload limits are reached.

## Telegram Local Bot API live tests

The Local Bot API path has limited live evidence:

- Local Telegram Bot API Server was started.
- The bot ran and polled through the Local Bot API endpoint.
- A short vertical YouTube video completed the live download -> Telegram delivery flow.
- An approximately 414.7 MB MP4 was delivered to Telegram and was playable.
- The large tested file was H.264/AAC, 1920x1080, and approximately 1649 seconds long.

This verifies only the observed scenario. It does not prove project support for arbitrary
files up to Telegram's official Local Bot API Server upload ceiling of 2000 MB.
Different Telegram clients may render previews differently, so preview behavior is not a
fully controlled application guarantee.

## Docker/runtime tests

Docker/Compose checks should include:

```bash
docker compose config --quiet
docker compose build bot
```

Docker was found at `/Applications/Docker.app/Contents/Resources/bin/docker` during the
tool-location check. Current safe validation:

- `/Applications/Docker.app/Contents/Resources/bin/docker compose config --quiet`: passed.

A Compose configuration check does not prove polling, download, extraction, upload, or
large-file behavior.

Containerized YouTube runtime validation:

Previous diagnostic state:

- The bot image had yt-dlp 2026.8.19 and yt-dlp-ejs 0.8.0, but no Deno, Node, Bun, or
  QuickJS executable.
- Raw yt-dlp verbose output reported `JS runtimes: none`.
- A controlled metadata simulation for
  `https://www.youtube.com/watch?v=dQw4w9WgXcQ` still succeeded.
- yt-dlp warned that YouTube extraction without a supported JavaScript runtime is
  deprecated and may have reduced format availability.
- The diagnostic result was classified as a confirmed degraded gap.

After adding Deno:

- The bot image installs pinned Deno 2.9.7 at `/usr/local/bin/deno`.
- Runtime checks found Deno 2.9.7 in the final image; Node, Bun, and QuickJS remained
  absent.
- Raw yt-dlp verbose simulation reported `JS runtimes: deno-2.9.7`.
- yt-dlp reported `[jsc:deno]` challenge solving using Deno.
- The previous missing-JavaScript-runtime warning was absent.
- Controlled `yt-dlp --verbose --simulate` for
  `https://www.youtube.com/watch?v=dQw4w9WgXcQ` succeeded without a full media download
  and selected format `401+251`.
- `YouTubeProvider.extract_metadata()` succeeded inside the container through the
  existing metadata-only `extract_info(..., download=False, process=False)` path while
  using the configured `js_runtimes={"deno": {}}`.
- A disposable Compose `bot` service container exposed the same Deno-enabled runtime.

This validation used one controlled public YouTube URL and metadata/simulation only. It
did not download complete YouTube media, upload to Telegram, prove broad YouTube
reliability, prove resilience to future YouTube platform changes, or benchmark VPS
throughput.

## Production Reliability tests

The Phase 3 functional Telegram MVP is complete, but production reliability is a later
phase and cannot be inferred from the happy path. Remaining operational checks include:

- restart behavior for the bot and Local Bot API Server;
- temporary Local Bot API/network failure recovery;
- upload failures and user-facing error behavior;
- cloud-to-local migration rehearsal with a separate test bot;
- local-to-cloud rollback rehearsal with a separate test bot;
- documented limits and resource observations for larger files when justified;
- monitoring, resource, and deployment limits when the deployment model is defined.

Telegram documents cloud-to-local migration with `logOut`, and documents `close` for
moving between Local Bot API Servers. Do not treat `close` as an officially documented
local-to-cloud rollback procedure.

## Experimental Instagram Reel provider (2026-10-16)

The first Phase 5 PR adds an injectable `InstagramProvider`; the bot's default registry
and Telegram handlers remain unchanged. See [the agreed scope](PHASE5_INSTAGRAM_REELS.md).

Network-free tests in `tests/test_instagram_provider.py` cover canonical Reel URL
identity, explicit host/path validation, rejection of collections/redirects/images and
private/auth-gated/DRM results, usable-format classification, optional metadata,
unsupported options, cache reuse/expiry/bounds, one-file acquisition and workspace cleanup.
A lazy playlist raises if enumerated; it is rejected without touching its entries.
An expired Reel snapshot that becomes a playlist cannot start acquisition. Synthetic
HTTP 403/429 and login-required exceptions produce safe errors without an application
retry or authentication fallback. Missing/empty/extra/partial/symlink outputs fail safely.
Upstream logger messages are suppressed; fixtures use synthetic IDs and `.invalid` URLs.

A real local yt-dlp processor/selector test receives synthetic extractor dictionaries:
it chooses one admitted direct MP4, preferring non-silent/unknown over higher-resolution
explicit silence in the same compatibility group, and excludes audio-only
and image alternatives. Extraction and file acquisition are replaced with local stubs;
this does not test Instagram network extraction or the CDN.

`tests/integration/test_instagram_pipeline.py` uses one-second 64x96 MP4 fixtures and an
invalid-file case in pytest temporary storage. All pass through injected `DownloadService` and real local
yt-dlp processing, with acquisition replaced by a fixture copy. Actual ffprobe and the
existing Telegram preparation helper verify:

- H.264/AAC MP4 passes unchanged: identical bytes, one preparation ffprobe and zero
  preparation FFmpeg calls. Upload width/height/duration come from actual file probing
  despite absent extractor duration, dimensions and codecs.
- A real video-only fixture is rejected by default; explicit `allow_silent=True` now
  passes it through unchanged with correct upload metadata. Corrupt bytes are rejected.
  The caller workspace is removed in every case by the existing request workspace boundary.

Initial implementation verification in an existing Python 3.13 / yt-dlp 2026.08.19 environment, using the feature
checkout's `src` via `PYTHONPATH=src` and explicitly disabling the external YouTube test:

- Provider and synthetic pipeline checks: 85 passed.
- Full pytest suite: 554 passed, 1 skipped (opt-in external YouTube live matrix).
- Ruff lint and formatting checks: passed.
- `git diff --check`: passed.

No real Instagram metadata/media request, live YouTube request, Telegram call, container
command, dependency installation/update or running-stack change was performed. Synthetic
local FFmpeg checks do not establish real Reel availability, Telegram delivery, account
restrictions, rate-limit recovery, throughput, production reliability or broad format
coverage. Retries of zero and a per-socket timeout are not a whole-operation deadline
and do not restrict an extractor to one internal HTTP request.

### PR #44 direct-format selection review follow-up

P1/P2 regressions run the actual installed yt-dlp 2026.08.19 format processor/selector
against synthetic metadata. Only extractor output and acquisition are stubbed; a network
attempt raises immediately. The new checks cover:

- Implicit `.m3u8`, uppercase/signed HLS, DASH `.mpd`, `.f4m`, explicit HLS/DASH protocols,
  fragment lists (including empty lists), manifest locators and DASH representation markers.
  Unsupported candidates never reach `process_info`, with or without a valid direct MP4
  alternative. Signed direct MP4 URLs without a path extension remain accepted.
- H.264/AAC ahead of equal-resolution VP9/AAC and higher-resolution unknown-audio formats;
  incomplete codecs ahead of already-known incompatible codecs; both fallback classes;
  native yt-dlp quality ordering within each class. Reversing extractor format order does
  not change the expected choice. Only one selected format reaches acquisition.
- The then-current explicit no-audio rejection (superseded by the silent-video policy
  below), collection/redirect rejection, optional metadata,
  cache/expiry, workspace cleanup and synthetic transport preparation remain covered.

The initial regressions reproduced both findings before the provider correction. Follow-up
verification uses the existing Python environment, `PYTHONPATH=src`, bytecode/cache writes
disabled and the external YouTube test explicitly disabled:

- Focused Instagram provider/synthetic pipeline: 127 passed.
- Full suite: 596 passed, 1 skipped (opt-in external YouTube matrix).
- Ruff lint/format and `git diff --check`: passed.

No new Instagram/YouTube network requests, media acquisition, Telegram delivery, dependency
changes or Docker commands were performed for this correction. Metadata-based format
selection does not prove actual stream presence or compatibility; real acquisition through
this provider and Telegram activation/acceptance remain separate outstanding gates.

### Incomplete direct-MP4 metadata follow-up

The subsequent real provider smoke, reported in the handoff, made one anonymous metadata
extraction and zero media-acquisition attempts. It returned one video result with 13
formats, none admitted; three had unknown video codecs and incomplete dimensions. The
other ten formats' exact rejection reasons were not established. No Instagram access
error was reported. This evidence is a failed inspection, not a successful provider
download or proof that all rejected formats were otherwise admissible.

Offline inspection of installed yt-dlp 2026.08.19 confirms `_extract_product_media` can
map `video_versions` to direct locators without width, height, codecs or an explicit
extension. `has_audio=False` maps to explicit `acodec="none"`; DASH variants are added
separately from `video_dash_manifest`. A synthetic direct `.mp4` product passed through
that actual local mapping reproduces `MetadataExtractionError` on main; the correction
admits it as unknown compatibility, not confirmed H.264/AAC or proven stream presence.

New offline cases use that real extractor mapping plus yt-dlp processing with stubbed
acquisition and a network-forbidden opener. They cover absent/complete/partial dimensions,
mixed direct/DASH output, explicit video/audio absence, HLS/DASH and non-MP4 locators,
signed direct MP4 with a declared extension, one acquisition and unchanged unknown fields.
Existing preference/manifest regressions remain green. Synthetic actual-file checks
also reject silently audio-free and corrupt files through existing preparation helpers.

Verification (external YouTube test disabled; no Instagram requests):

- Focused provider/synthetic pipeline: 143 passed (16 additional cases).
- Full suite: 612 passed, 1 skipped (opt-in external YouTube matrix).
- Ruff lint/format and `git diff --check`: passed.

No live extraction/download, Docker operation, dependency change or Telegram call was
performed for this fix. The real formats' complete fields are unavailable in this evidence, so matching
the local defect to the prior live rejection remains a hypothesis requiring a newly
authorized bounded provider smoke. Instagram remains disabled in the default bot.

### Real corrected-provider Reel smoke (2026-10-16)

After PR #45, one separately authorized anonymous smoke tested main
`4885ee651790d70222acb3c490d2ed367ed4637c` through `InstagramProvider` and
`DownloadService`, not standalone yt-dlp. Current source was mounted read-only in an
isolated short-lived container using the existing bot image/runtime; Python 3.13.16,
yt-dlp 2026.08.19 and FFmpeg/ffprobe 7.1.5. The existing Compose services were unchanged.

| Observation | Verified result |
|---|---|
| Scope | One public Reel, one extraction and one acquisition; no retry |
| Formats | 13 returned, 3 admitted, 10 rejected as manifest/fragment candidates |
| Choice plan | `DIRECT_DOWNLOAD`, `VIDEO_WITH_AUDIO`, no audio/quality menus |
| Actual file | MP4 H.264/AAC, 720x1280, 11.282041 seconds, 1,317,210 bytes (1.256189 MiB) |
| Integrity/preparation | ffprobe PASS, full FFmpeg decode PASS, existing preparation passthrough |
| Upload parameters | width 720, height 1280, integer duration 11; no upload performed |
| Timings | extraction 1.991 s, plan 2.248 s, download 1.278 s, total 5.251 s |
| Safety | 25 MiB streaming byte guard and 180 s deadline; temporary media/container/scripts removed |
| Warning | `CSRF_TOKEN_UNAVAILABLE`, nonfatal; no error recorded |

Selected codec/dimension metadata was incomplete; actual H.264/AAC and geometry came
from file probing. The later format-rejection counts describe this run only, not the
unretained format fields of the earlier failed attempt. This PASS proves one real Reel
through the implemented provider, not general Instagram reliability, subjective playback
or Telegram delivery. It predates the single-video `/p/` extension below.

### Single-video post extension — offline validation only

The same provider now accepts canonical `/p/<id>/` URLs, subject to single-video result
validation before acquisition. Tests use installed yt-dlp 2026.08.19 `extract_info` with
`download=False, process=False`, the real Instagram `_real_extract`/`_extract_product`
classification, synthetic JSON responses and a network-forbidden opener. Only the JSON
fixture branch is selected; no HTTP impersonation handler or real network access is used.

Fixtures establish a top-level video for a single-video product, playlists for multi-video,
mixed-media, photo-only and one-entry carousels, and a no-video error for a single photo
or empty product. Rejected results never reach yt-dlp result processing/acquisition.
Additional raw-result tests cover empty playlists, `entries` regardless of type,
redirects, unknown types, private/auth-gated metadata and DRM. No first entry is selected.

Shared cases now run for both Reel and post URLs: canonical tracking removal, snapshot
reuse/expiry/bounds, unsupported options, safe filenames, failure cleanup, manifest
rejection and actual yt-dlp compatibility-priority selection. Separate path identities
cannot collide in the cache. Synthetic FFmpeg integration covers valid H.264/AAC,
silently audio-free and corrupt actual files for both paths; existing preparation is reused.
The default provider registry and Telegram handlers are unchanged.

Current offline verification with the external YouTube matrix explicitly disabled:

- Focused Instagram provider/synthetic preparation: 259 passed.
- Full pytest suite: 728 passed, 1 skipped (opt-in external YouTube matrix).
- 116 additional parameterized/regression cases compared with main.
- Ruff lint and format checks: PASS.
- `git diff --check`, documentation consistency and security/scope review: PASS.

No live Instagram/YouTube requests, dependency changes, Docker operations or Telegram
calls are part of this extension. Real `/p/` support remains UNVERIFIED pending a separately
authorized smoke. At that stage carousel groups/order/splitting were product scope only;
later video-only acquisition and offline delivery evidence is recorded below. Photos
remain outside acquisition/delivery scope.

### Carousel inspection/selection — deterministic validation

`tests/test_instagram_carousel.py` exercises actual installed Instagram `_real_extract`
and product mapping with synthetic JSON responses and a network-forbidden opener.
The production per-instance extractor adapter is installed as in the real inspection path.
Result processing/media acquisition raise immediately in the fixture runtime.

Coverage: all-video counts 1/2/5/10/11/21 without truncation; conservative mixed/photo-only
fixtures; empty/UNKNOWN/conflicting entries; missing/unsupported video locators; malformed,
duplicate/missing/mismatched IDs; upstream reordering/schema loss; unavailable/DRM source
fields; immutable ordered plans; tracking/cache identity, TTL and bounds; `img_index`,
malformed/ambiguous references rejected before extraction/cache; instance isolation.
Existing provider/YouTube/media preparation/callback regressions run in the full suite.
No external platform calls, images/videos, dependency changes, Docker operations or
Telegram requests are part of this implementation's tests.

The preceding separately authorized live metadata gate inspected one five-video carousel
via two URL variants, once with `img_index=3`: 2 extractions, 3 HTTP requests each, no retry,
zero result processing or acquisition. All five positions had `video_versions`, unique
stable IDs/order and 3 direct MP4 candidates each; total mapped formats were 9/10/7/7/7.
Both variants returned the full playlist with identical request targets and ordered IDs;
response bodies were not byte-identical. `img_index` reached the extractor but was not
honored upstream. No actual frontend index semantics, photo/mixed classification or
media downloadability was established. CSRF-token warning was nonfatal. The adapter
introduced here has deterministic validation only; this prior experiment is not its live test.


Verification for this carousel-inspection stage (live YouTube matrix explicitly disabled):

- New carousel inspection/selection cases: 103 passed.
- Full regression suite: 831 passed, 1 skipped (opt-in external YouTube matrix).
- Ruff lint/format, diff, local documentation links and security/scope review: PASS.
- No new live extraction or media acquisition was performed for this implementation.


### Corroborated carousel PHOTO classification — offline follow-up

Separate live metadata evidence after PR #47 concerns one 20-entry publication, not a
broad platform matrix. The first one-shot check returned 17 VIDEO and UNKNOWN at 8/9/18,
with intact original ID/order mapping and BLOCKED / unknown_item. A separately authorized
one-shot source diagnostic found strict integer `media_type=1` plus coherent image
versions/nonempty candidates at those positions, with no `is_video` or video
versions/codec/duration/manifest fields. Representative VIDEO entries had type 2 and
nonempty video versions/manifest; both groups had image versions. Both checks performed
zero media acquisition. This evidence supports the combined PHOTO rule for that shape.

The correction is tested without network via the installed extractor and the existing
network/processing/acquisition-forbidden Runtime. Tests include the observed PHOTO shape,
a 20-entry fixture selecting exactly 17 VIDEO at 1–7, 10–17, 19–20, numeric evidence,
invalid image structures/locators, malformed numeric/string markers, video contradictions,
and unchanged explicit-photo behavior. The former UNKNOWN case for valid numeric-plus-
image evidence is retained as a PHOTO acceptance case; image-only UNKNOWN remains tested.
Existing unsupported VIDEO, identity, unavailable/private/DRM, cache, reference and
single-video/YouTube/Telegram regressions remain part of the suite.

At completion of that offline fix, live mixed-selection remained OPEN. The subsequent
metadata-only gate below closes it for one publication; no live carousel acquisition or
Telegram delivery is claimed.


Verification of this focused classification fix (no live platform calls):

- 39 additional deterministic cases; carousel suite: 142 passed.
- Carousel plus existing Instagram provider/preparation tests: 401 passed.
- Full regression suite: 870 passed, 1 skipped (opt-in external YouTube matrix disabled).
- Ruff lint/format, diff, documentation links and security/scope review: PASS.
- Application AST comparison: only `_classify` changed; extraction, identity/order,
  cache, URL handling, domain contracts, registry and Telegram handlers are unchanged.


### Final mixed-carousel classification — real metadata-only PASS

2026-10-16, production source `1e08478646057326284ff410ea23f2ca312b4f2f`, read-only mount
hash-verified (27 Python files); Python 3.13.16, yt-dlp 2026.08.19, curl_cffi absent.
One top-level anonymous extraction, three observed HTTP requests, no retries/acquisition.
Observed: playlist with 20 items; 17 VIDEO; PHOTO at 8/9/18 with media_type_photo plus
image_versions evidence; zero UNKNOWN. Source/mapped/plan ID uniqueness and order PASS.
READY, issue=None, selected 1–7, 10–17, 19–20; three direct MP4 candidates per VIDEO.
All A–L acceptance checks passed. Extraction 3.460 s, plan 3.716 s, process 4.851 s;
CSRF_TOKEN_UNAVAILABLE warning only. No media bytes/files or Telegram calls, temporary
runtime removed, Git/Compose unchanged. This closes classification for one publication,
not real multi-video downloading or broad reliability.

### Ordered carousel acquisition — network-forbidden deterministic validation

`tests/test_instagram_acquisition.py` exercises production plan revalidation, the installed
yt-dlp selector and HTTP downloader, synthetic in-memory HTTP responses and actual local
ffprobe on generated MP4 files. No external Instagram/Telegram calls occur. Child-process
tests inject only a fixture provider and run the production execution boundary, including
POSIX per-file limits, timeout/cancellation cleanup and safe output publication.

Coverage includes 1/2/5/10/11/20/21 selected videos; mixed 20-item ordering with 17 videos;
PHOTO-only, UNKNOWN/unsupported/unavailable/DRM and forged/reference plans; refreshed and
expired facts; changed IDs/order/count/types; HLS/DASH/manifests/fragments; codec priority
and signed direct MP4 fallback; absent audio/video, corrupt files; empty/missing/extra/
symlink/directory outputs; failures at first/middle/last child; per-file/cumulative/temp
byte budgets with absent or misleading Content-Length; hard deadline and repeated
cancellation; publication rollback/collision protection; unrelated-file preservation.
The real HTTP reader is bounded before writes, not just a progress-hook simulation.

Successful files are caller-owned until deleted. Filesystem hard-link support and POSIX
process groups are required. Tests do not prove full decoding of arbitrary media,
concurrent production capacity, crash recovery, real multi-video acquisition or Telegram
preparation/group delivery. No acquisition-stage conversion is implemented.

Verification of this acquisition stage (no live external calls):

- New acquisition tests: 74 passed, including real child entry point/OS file limits.
- Full suite: 944 passed, 1 skipped (external YouTube live matrix not enabled).
- Existing Instagram/Reel/single-post, YouTube, M4A, Telegram callback and video delivery
  regressions passed; existing synthetic FFmpeg integration checks ran in the full suite.
- Ruff lint/format, git diff check, local documentation links and security/scope review: PASS.
- No source/dependency/config/deployment changes outside the documented acquisition scope.
- At this implementation stage, live multi-video acquisition and Telegram groups were
  NOT VERIFIED; the later bounded three-video acquisition is recorded below.


### Silent Instagram video policy — deterministic validation

The user approved MP4 video with optional audio for Reels, single-video `/p/` and carousel
VIDEO entries. The preceding real metadata diagnostic found three VIDEO entries with
boolean has_audio=False, correctly mapped to acodec="none": 3 direct MP4 candidates per
entry rejected solely for audio absence; 23 additional manifest-derived formats also
rejected for fragment markers, mapped totals 11/11/10. One extraction, three metadata
HTTP requests, zero acquisition; actual files/streams were not inspected. These are
pre-change metadata facts, not live validation of the new admission policy.

Network-forbidden tests now admit explicit silence, preserve unknown audio metadata,
exercise installed extractor mapping and actual yt-dlp selection for Reels/posts, and
retain rejection of explicit video absence, hostile locators, DRM, HLS/DASH and fragments.
Ranking tests cover H.264/AAC priority, non-silent/unknown preference within compatibility
groups, stable native quality order for silent-only candidates and intentional compatible
silent H.264 preference over less compatible VP9/AAC in another group.

The carousel fixtures cover READY for three silent VIDEO with three direct candidates
each, with/without rejected DASH variants, plus mixed PHOTO/VIDEO ordering. Actual local
H.264 silent MP4 passes ffprobe acquisition validation and retains identical bytes with
no audio stream added. Video+audio still passes; audio-only/corrupt/wrong-container media
and invalid video/dimensions/present-audio codecs fail. Existing limits, deadline, repeated
cancellation, output checks, rollback and unrelated-file preservation remain tested.

Single-video integration explicitly supplies acodec="none", acquires the synthetic file
unchanged and confirms actual H.264 video without audio. Default Telegram preparation
rejects it for missing audio; the later optional-audio tests explicitly opt in and
verify byte-preserving passthrough. Neither path proves Telegram delivery.
The subsequent real acquisition and local preparation evidence are recorded below.
No external extraction/download or Telegram API request is part of these tests.


Verification of silent-video support:

- Focused provider/carousel/acquisition/synthetic integration suite: 563 passed.
- Full suite: 1032 passed, 1 skipped (opt-in external YouTube matrix not enabled).
- Net test-case increase: 88; obsolete silent-rejection cases were replaced by positive
  coverage and explicit negative cases for audio-only/manifest content.
- Existing YouTube, M4A, video delivery, callback fault handling, limits and cancellation
  regressions: PASS. Ruff lint/format, diff, documentation links and security/scope: PASS.
- At this stage real silent acquisition/preparation and albums were NOT VERIFIED;
  subsequent evidence below closes only the explicitly tested acquisition/preparation scope.


### First real silent carousel acquisition — narrowly verified

After PR #50, one authorized three-video experiment on production main
`055fced0bdf337a5b04132600cc803321db59c80` passed through the real planning and async
acquisition services. Two metadata extractions (planning and fresh revalidation), six
observed metadata HTTP opens, three media requests, zero retries or Telegram calls.
READY / issue=None; VIDEO 1/2/3, no PHOTO/UNKNOWN, three direct MP4 candidates each;
identity/order passed before and after acquisition.

| Original position | Bytes | Actual streams | Dimensions | Duration | ffprobe |
|---|---:|---|---|---:|---|
| 1 | 613050 | H.264, no audio | 720x960 | 5.041667 s | PASS |
| 2 | 738479 | H.264, no audio | 720x960 | 5.041667 s | PASS |
| 3 | 609669 | H.264, no audio | 720x960 | 5.041667 s | PASS |

All containers were MP4. Total 1,961,198 bytes; planning 2.22 s, acquisition 6.90 s,
validation complete at 9.53 s (12.42 s including disposable runtime lifecycle).
Limits 3 videos, 30 MiB/file, 75 MiB received, 90 MiB temporary, 180 s held. HTTP body/file
hashes matched, proving no transformation of those bytes. Nonfatal csrf_token_unavailable
warnings only. Successful files, scripts and runtime were removed; original Compose IDs,
start times and mounts were unchanged. No real Telegram preparation or playback occurred.
Only this small acquisition gate is closed; larger collections/general reliability remain open.

### Optional-audio video preparation — local generated media

`tests/test_telegram_media.py` exercises the explicit opt-in, audio-required default,
actual-container checks, malformed codecs/dimensions/stream metadata, both remux-fallback
audio states, rejected audio-only media, absent versus invalid audio, accidental output
audio changes, partial-file cleanup/interruption, and preservation of existing outputs.

`tests/integration/test_video_preparation.py` uses real local FFmpeg/ffprobe on generated
H.264/AAC and silent H.264 MP4/MKV, incompatible silent MPEG-4 and audio-bearing sources.
Passthrough keeps the exact source path/bytes and invokes no FFmpeg; remux preserves
encoded packet hashes; conversion uses existing H.264/AAC settings and never adds audio.
Prepared route fixtures pass full local decoding. Rotated fixtures verify displayed
orientation through passthrough, remux and transcode. Video-only upload dimensions and
duration need no audio. Synthetic Reel and single-video `/p/` integration retains default
silent rejection and separately verifies explicit opt-in passthrough.

These are offline helper/provider tests, not Telegram sends. Instagram remains disabled;
Real Telegram albums, actual client playback, larger-carousel reliability and broader
platform availability remain NOT VERIFIED; later offline transport tests are recorded below. No live Instagram or Telegram calls in this stage.


Optional-audio stage verification (offline, existing local dependencies):

- Focused helper/local-media/synthetic Instagram integration tests: 98 passed.
- Full suite: 1112 passed, 1 skipped (external YouTube matrix disabled); net +80 cases.
- Sixteen real local media integration cases used FFmpeg/ffprobe 9.0.2; synthetic files
  only. Six route cases also passed full local decode; no subjective/client playback claim.
- Ruff lint/format, diff, documentation links/anchors and security/scope review: PASS.
- YouTube, M4A/audio, callback/delivery, Instagram and acquisition regressions passed.
- Only the preparation module changed in application code; handlers, registry, providers,
  acquisition, dependencies and Compose are unchanged. No live platform requests.

### PR #51 P2 — collision-safe derivative ownership

The previous destination existence check did not establish ownership: FFmpeg `-y`
and failure cleanup could overwrite/delete a file created later by another operation.
Regression tests reproduced this before the fix. Each conversion now stages privately
on the destination filesystem and validates that file before atomic exclusive hard-link
publication. FFmpeg never receives the shared destination path. Publication failure
does not trigger another conversion, and cleanup only removes private staging paths.
Hard links are required; unsupported filesystems fail safely without a copy/overwrite
fallback. A successful link transfers the final name to the request/caller workspace;
there is no filesystem-wide transaction or crash-recovery claim.

Deterministic tests cover pre-existing and late destinations (remux and transcode),
a file/symlink created at the publication boundary, two preparations synchronized
after output validation (exactly one winner), unsupported-link failure, remux fallback
within one private directory, and KeyboardInterrupt/CancelledError while an unrelated
final file exists. Existing failure cleanup/passthrough tests remain; real local media
tests verify final filename, private FFmpeg paths, silent remux/transcode and cleanup.


P2 correction verification (offline): net +10 deterministic cases; focused preparation/
local-media/Instagram pipeline suite 108 passed; full suite 1122 passed, 1 skipped
(external YouTube matrix disabled). Sixteen real local FFmpeg/ffprobe cases still pass,
including silent remux/transcode and audio-bearing defaults. Ruff lint/format, diff,
documentation and security/scope review PASS. No external platform or Telegram calls.


### Offline carousel Telegram delivery

`tests/test_telegram_carousel.py` uses an injected sender and actual aiogram models,
with network connections forbidden. Transport unit tests mock only the preparation
boundary; real local preparation/limits are separately exercised below. Sizes 1,2,3,9,
10,11,12,20,21,25 verify exact operation sequence/order, FSInputFile paths, streaming
flags and per-video upload metadata. Mixed PHOTO positions retain video order. Any
first/middle/last preparation failure prevents every send. Invalid/incomplete plans,
files, outputs, resource bounds, source IDs/order, ambiguous responses and timeouts
fail safely. Send failure after confirmed batches reports partial progress and stops;
there is no automatic retry or rollback of successful Telegram requests. Tests verify
cleanup of owned prepared files and preservation of originals/unrelated collision files,
including cancellation and repeated cancellation while reaping a preparation child.

`tests/integration/test_carousel_delivery.py` uses generated local silent/audio MP4,
H.264 MKV and incompatible MPEG-4 MKV through the actual preparation child/FFmpeg/ffprobe,
then mocked senders. It checks byte-preserving passthrough, mixed audio states, remux/
transcode, upload metadata, preparation failures at every position, real OS output caps,
per-file/aggregate/workspace/count limits and cleanup. No real Telegram, Instagram
extraction/acquisition, bot polling or deployment changes are part of these tests.

PR #51 is merged; the earlier real three-video acquisition remains narrow external
evidence only. Mock send success does not establish real Telegram album delivery,
client playback, larger Instagram collection reliability or production readiness.


Offline delivery verification:

- Net +80 deterministic cases: 66 transport/validation/process tests and 14 actual local
  preparation integration cases. All passed; aiogram 3.31.0 objects/interfaces inspected.
- Full suite: 1202 passed, 1 skipped (external YouTube matrix explicitly disabled).
- Existing local video preparation, M4A/audio, YouTube, callback/delivery and Instagram
  acquisition regressions passed. Full suite ran with external socket connections denied
  in the pytest process; preparation children only execute local file/pipe media commands.
- Ruff lint/format, diff, local documentation links/anchors and security/scope review: PASS.
- Original Compose container IDs/start times/mounts unchanged. No live Instagram/Telegram
  requests, polling, deployment, provider registration or dependency changes.

## Reel-only Telegram MVP offline checks

`tests/test_instagram_reel_handler.py` uses existing synthetic provider fixtures and
forbids socket connections. It verifies disabled/default behavior, explicit per-dispatcher
injection, strict configuration, raw URL intent and `/p/` rejection, playlist/photo/private/
redirect rejection, acquisition/preparation failure, one send with real FSInputFile and
probe parameters, no send retry, cleanup, and repeated cancellation while the worker
still owns admission/workspace. Response-body accounting is tested without size headers;
real exec'd FFmpeg demonstrates the per-file write backstop. Generated local silent and
audio-bearing H.264 MP4 pass unchanged; an incompatible silent sample uses the existing
conversion helper without adding audio. Existing YouTube/callback suites remain required.

No actual Instagram extraction/download or Telegram API call is evidence for this stage.
The prior real Reel provider smoke is unchanged evidence. Full request hard deadlines,
production capacity and `/p/`/carousel routing remain open. A subsequent separately
authorized one-Reel delivery/client smoke is recorded below.

Verification on this branch: 32 new Reel MVP cases passed; focused handler/config/bot/
YouTube regression suite 142 passed; full suite 1234 passed, 1 skipped (external YouTube
live matrix disabled). Full pytest ran with socket connections forbidden. Ruff lint and
format, diff, local documentation links and security/scope checks PASS. Existing YouTube
delivery/callback function bodies, provider registry, acquisition/preparation APIs,
dependencies and Compose are unchanged.

## Main-bot Compose smoke preparation

PRs #53/#54 are merged. The separately authorized smoke used the existing main bot with
a bot-only restart, not another bot or poller. One canonical Reel was delivered and the
user confirmed playback, orientation and sound. Temporary Reel files were removed;
polling and Local Bot API stayed healthy. Exact file size/time were not captured. This
is one external case, not broad reliability or `/p/`/album validation.

Validate Compose using an empty env file and synthetic credential placeholders, retaining
resolved JSON only in process memory. Check absent flag -> false, explicit true -> true,
only bot receives it, and all other settings/services equal the base configuration.
Current APP_ENV=development, Local Bot API, Settings production guard and 25 MiB Reel
limit are preserved. Do not print resolved real credentials or run up/build/restart.
This configuration check is not live Telegram or Instagram evidence.

Verification: Compose false/true resolution and full base-config comparison PASS using
synthetic placeholders with real `.env` excluded. Existing offline suite: 1234 passed,
1 skipped; Ruff lint/format, diff, documentation and security/scope checks PASS. No live
requests, environment changes or container lifecycle operations were performed.

## Reel share-link regression

The initial full share URL failed before acquisition because of `psln`. The correction
uses the existing provider canonicalizer, accepting/removing irrelevant query keys, bare
flags and harmless anchors. Known item selectors remain rejected in query keys and
selector-shaped fragments, including case/percent-encoded forms. The 32-field parsing
bound, approved hosts, HTTP(S), Reel paths, credential and unsupported-port checks remain.
Carousel query policy is unchanged. Network-forbidden handler tests assert that the
provider receives only the canonical URL and a successful synthetic acquisition sends
exactly once and cleans its workspace. The exact reported URL is also checked offline;
committed fixtures use a synthetic tracking value instead of the original opaque value.
That implementation stage had no live calls or deployment changes. PR #55 was later
merged at `0a87beeaa8acb302b74e980946778608856b13f6` and separately deployed. The
user confirmed delivery, playback, orientation and sound for the full Reel URL with
`utm_source`/`psln`; size/time were not recorded. This narrow evidence does not cover
`/p/`, albums or broad reliability. No new live call occurs in the current correction.

Verification: net +34 cases; Reel handler 66 passed, combined handler/config/bot suite
176 passed, full suite 1268 passed and 1 skipped (external YouTube matrix disabled).
Full pytest forbids socket connections. Local FFmpeg/ffprobe, YouTube, callbacks and
delivery regressions passed. Ruff lint/format, diff, documentation and scope/security PASS.

## PR #56 Instagram /p/ Telegram routing validation

`tests/test_instagram_post_telegram.py` adds network-forbidden tests for
whole-publication three-video route selection, position preservation, known
`psln` tracking-key acceptance, owned
workspace cleanup, conservative item/unknown-query rejection, blocked unknown
items, single-video post reuse, uncertain album send without retry, and the
shared per-dispatcher Instagram admission slot. The prior
`test_posts_stay_outside_this_integration` expectation is replaced with
a positive delegation check; public Reels retain their existing tests.

Baseline before review corrections on the feature branch with GitHub Actions: Ruff lint PASS, Ruff
format PASS, and full pytest with FFmpeg/ffprobe installed: 1277 passed,
1 skipped (opt-in external YouTube matrix). The prior GitHub run without
FFmpeg skipped 114 additional media cases, which motivated this CI change.
This confirms offline and deterministic local-media checks, not Telegram
client album playback. No new real Instagram extraction, media acquisition or live
Telegram album send has been performed. The three-silent-video media
acquisition gate remains separately verified; real album delivery and playback
remain unverified.

### PR #56 independent-review corrections — offline

The post-routing tests now use the installed extractor/production source adapter with
synthetic JSON to verify positive single-video and mixed/all-video inspection. Single
silent/audio MP4 fixtures run actual local FFmpeg/ffprobe preparation and consume one
validated snapshot without duplicate extraction. Negative cases preserve is_private,
needs_auth and DRM evidence, UNKNOWN/unsupported entries, malformed/missing source facts,
identity loss and selector rejection. A permissive second extraction is deliberately
available in the fixture and must never be called for a blocked result.

Event-controlled metadata tests cancel during the first request, repeat cancellation,
expire the inspection timeout and inject a request failure. No second request, media
stage or send starts; the shared slot remains held until the blocked worker exits.
Clock-controlled tests account for inspection time before acquisition and single-file
work. Acknowledgement timeouts cannot start media stages after the deadline. Deadline
tests cover preparation and in-flight upload, caller-file preservation,
workspace cleanup and uncertain-delivery feedback without retry. These checks do not
claim forced interruption of native calls, live `/p/` delivery or client album playback.

Local correction verification: net +43 deterministic cases over the 1277-case baseline;
full suite **1320 passed, 1 skipped** (external YouTube opt-in), and focused
post/Reel/Telegram-preparation tests **204 passed**. The extended Instagram
provider/inspection/acquisition/delivery and local FFmpeg/ffprobe suite passed
**777 tests**; YouTube/provider/handler/bot/config regressions passed **242 tests**.
Python 3.13.12, yt-dlp
2026.08.19, aiogram 3.31.0 and local FFmpeg/ffprobe 9.0.2 were used. Socket
connections were forbidden in the pytest process. Ruff lint/format and diff checks
PASS. These local results do not replace exact-head CI or repeat independent review.

### PR #56 source-shape follow-up — offline

The installed yt-dlp 2026.08.19 product mapper filters non-dictionary carousel members.
With no remaining members it can return the parent's video formats as a single video,
discarding evidence that carousel_media was present. Direct installed-mapper tests
record this behavior; the production adapter now rejects invalid source shapes before
that mapping and requires a complete, ordered, identity-consistent playlist afterward.

New negative fixtures include `[None]`, strings, empty/nonempty objects, empty lists,
invalid members before/after valid ones, present null, booleans, numbers and nested
collections, all with admissible parent video_versions. An absent field is tested by
the existing successful single-post path; present null is explicitly not absence.
Additional mapper-drift cases remove entries, drop/reorder items or produce a false
single result. Both carousel inspection APIs are covered for drift. Handler checks
assert zero single-worker calls, carousel acquisition/delivery, media sends and repeat
extraction. Invalid list counts remain available; empty lists stay blocked as NO_VIDEOS.

Before the fix, the new 40-case source-shape subset produced **29 failed, 11 passed**;
after the fix, **40 passed**. Two additional positive variants inspect three silent
videos, alone or mixed with a confirmed PHOTO, preserving every video position/identity.
Focused carousel/post/Reel tests: **303 passed**. All fixtures are synthetic and
network-forbidden; no new live Instagram or Telegram evidence is introduced.

Final local verification: net **+42 cases**, full pytest **1362 passed, 1 skipped**
(external YouTube opt-in); extended Instagram/provider/inspection/acquisition/delivery
and local FFmpeg/ffprobe **819 passed**; YouTube/handlers/bot/config **242 passed**.
Socket connections were forbidden. Ruff lint/format, diff, documentation and
security/scope checks PASS. Only `_extract_product` changes in application code;
format/classification policies, product limits, cancellation and transport are unchanged.
Exact-head GitHub CI and a separate independent review remain required after publication.

### PR #56 immutable source facts — offline fault injection

Before calling the installed product mapper, the adapter snapshots the original
count and ordered frozen ItemEvidence values: source ID, expected mapped ID,
VIDEO/PHOTO/UNKNOWN kind, evidence signals and unavailability. Parent availability
is also retained before mapping. Expected values are never recomputed from the
mutable source after mapping; mismatches produce INVALID_METADATA, not a single
fallback or a shortened READY selection. The classifier and identity policy are reused
unchanged; no full upstream payload is copied in production.

Eleven fault-injection scenarios mutate the input in place before the real installed
yt-dlp mapper runs: remove UNKNOWN, reorder entries, replace an ID, promote UNKNOWN,
change PHOTO to VIDEO, change video/image evidence, or remove is_private, needs_auth,
has_drm or restricted availability. Both inspection APIs assert INVALID_METADATA,
the initial count and empty selection/cache. Handler tests assert no acquisition,
preparation, Telegram media send, repeated extraction or partial delivery. Two
unmodified mapper controls preserve all-video and mixed VIDEO/PHOTO selections;
existing real-local single-post, silent-video, Reel and cancellation tests are retained.

These 35 new cases produced **33 failed, 2 passed** before the correction and
**35 passed** afterward. This is synthetic fault injection, not evidence that
unmodified yt-dlp 2026.08.19 mutates these facts, nor an observed Instagram exploit.
There is no new live Instagram acquisition or Telegram delivery evidence. Independent
review is still required; live `/p/` and album playback remain NOT VERIFIED.

Final local verification: net **+35 cases**, full pytest **1397 passed, 1 skipped**
(external YouTube opt-in); extended Instagram/provider/inspection/acquisition/delivery
and local FFmpeg/ffprobe **854 passed**; YouTube/handlers/bot/config **242 passed**.
The existing Python 3.13.12 environment, yt-dlp 2026.08.19 and FFmpeg/ffprobe 9.0.2
were used. All runs forbid socket connections; no dependencies were changed. Ruff
lint/format, diff, documentation and security/scope checks PASS. Only the metadata
adapter changes in application code; provider/service/transport contracts, resource
limits and cancellation/deadline handling are unchanged. Exact-head GitHub CI is
verified separately after push; it does not replace final independent review.

### Post share-link admission correction — offline

PR #56 subsequently passed final independent review, merged at
`20d14441a2b7ea906ed2a0abc83679d25d9f2d32` and was separately deployed only to bot.
All 88 checked image paths matched main, polling started without conflicts, and Local
Bot API identity/start/mounts/restart count were preserved. This is technical deployment
evidence, not successful real `/p/` delivery. The user then reported reference-policy
refusals for a single post and a carousel; their exact URLs were not provided.

The old service rejected unknown query keys, bare flags under strict query parsing,
and every fragment, unlike the Reel policy. The same synthetic 132-case control set
produced **69 failed, 63 passed** before the fix and **132 passed** afterward. These
include updated metadata-refusal tests that must now reach inspection rather than
stop at share-query admission. No claim is made about the users' actual parameters.

Reel and post entry points now share one domain URL intent guard, preserving provider
host/path/credential/port validation. Query keys are percent-decoded and matched
case-insensitively against img_index, media_id, item_id, carousel_index, index and slide;
selector-shaped fragments and repeatedly escaped names remain blocked. Malformed
percent escapes, unnamed fields and more than 32 query fields fail closed. Unknown
non-selector keys, bare flags and ordinary anchors are stripped before the canonical
publication reaches extraction; correctly escaped literal percent signs remain allowed.

Tests cover canonical provider URLs, one planning extraction, shared cache identity,
zero acquisition/media sends for blocked references, single silent/audio video success,
three-video and mixed-carousel order, PHOTO exclusion, and UNKNOWN/private/auth/DRM/
malformed-source refusal with full share URLs. Existing immutable-source, deadline,
acquisition, preparation, delivery, YouTube and full Reel-share regressions remain in place.
All tests are offline with socket connections denied. No real platform request,
deployment or additional polling is part of this fix. Corrected real `/p/` delivery
and Telegram album playback remain NOT VERIFIED.

Final verification with the existing Python 3.13.12 / yt-dlp 2026.08.19 / aiogram
3.31.0 environment and real local FFmpeg/ffprobe 9.0.2: net **+73 cases**, full pytest
**1470 passed, 1 skipped** (external YouTube opt-in); extended Instagram/provider/
inspection/acquisition/delivery/local-media **927 passed**; YouTube/handlers/URL/bot/
config **267 passed**. Ruff lint/format, diff, documentation and security/scope checks
PASS. Exact-head CI is checked after publication; independent review, merge and
deployment of this fix remain separate decisions.

## Instagram live acceptance 2026-10-18

Status: **ACCEPTED for the two tested cases**, confirmed by the project owner using
the running Telegram bot after PR #57 deployment. Revision:
`13da14d6f1ea9378d776543c94b22b7b716630d3`.

| Real user test | Owner-confirmed result |
| --- | --- |
| One single-video `/p/` publication, full share link | Accepted without the previous URL refusal; video delivered and played normally. The owner described processing as sufficiently fast; exact time was not measured. |
| One three-video carousel, previously rejected full share link | All three videos delivered in one Telegram album, in original order; all played normally and remained silent, matching the originals. |

These are real user/client observations, separate from the prior network-forbidden
offline suite (1470 passed, 1 skipped), local FFmpeg/ffprobe fixtures and provider-only
acquisition experiments. PR #57 passed independent review, merged at the revision
above, and passed post-merge CI #39151964361 before the separately authorized bot-only
deployment. This documentation change does not repeat any external-platform test.

Only these single-post and three-video-album acceptance cases are closed. Exact URLs
and query combinations were not supplied for this record; no new source IDs or user
data are retained. Exact processing times, file sizes, codecs, request counts and live
cleanup telemetry were not recorded; earlier acquisition metrics are not attributed
to these tests. No additional orientation/audio observation is inferred for the single
video beyond normal playback.

Still open: other publication shapes, mixed PHOTO/VIDEO Telegram delivery, larger or
multi-batch albums, other clients/devices, file-size boundaries, failure/recovery and
load behavior, broad Instagram availability and production capacity. Item selectors
remain blocked; defaults, product limits and the production-mode guard are unchanged.
