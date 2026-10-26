# Security Policy

## Secrets
Secrets must be supplied through environment variables or an approved secret manager. Never commit tokens, API keys, passwords, private keys, session files, or cookies.

Telegram secrets and credentials include the bot token, `TELEGRAM_API_ID`, and
`TELEGRAM_API_HASH`. Compose files must reference them through environment
interpolation, not hardcoded values.

`.env` and `.env.*` files must remain untracked. `.env.example` may be tracked because it
contains only variable names and empty or non-secret example values.

## Personal data
Do not commit user IDs, email addresses, phone numbers, private usernames, downloaded media, logs containing personal data, or local paths exposing personal information.

## Runtime data
Downloaded media, temporary files, logs, and local databases are runtime data and must not be version-controlled.

Telegram Local Bot API Server working data, named volumes, downloaded media,
temporary download directories, generated audio/video artifacts, and Bot API runtime
state are runtime data and must not be committed.

## Telegram data
Treat Telegram identifiers, messages, usernames, submitted URLs, and media metadata as potentially sensitive runtime data. Do not place real user data into fixtures or documentation.

Keep the Local Bot API endpoint private by default. Do not publish an unauthenticated
Bot API endpoint to the public internet unless an explicit deployment design secures and
limits access.

## Docker build context

The Docker build context must not contain secrets. `.dockerignore` must exclude `.env`,
`.env.*`, virtual environments, caches, temporary directories, media artifacts, and local
runtime data while allowing `.env.example` to document required variables.

## Security gate
Before each release inspect changed files, review the Git diff, search for credential-like strings, confirm ignored runtime files, review dependency changes, and verify logs do not expose secrets or unnecessary personal data.

## Isolated native TikTok experiment

Phase 6C admits only a verified embed identity and constrained video-CDN names,
with public-IPv4 pinning, original TLS hostname verification and pre-connect
redirect checks. One publication owns a memory-only, scope-checked cookiejar;
browser/account cookies, persistent sessions, proxies and challenge solvers are
excluded. Signed locators and HTML are never logged. Owned process/workspace,
body-size and HTTP completeness controls are described in
[Phase 6C](PHASE6C_TIKTOK_NATIVE.md). These are experiment boundaries, not a
production sandbox or evidence of real platform reliability.
Benchmark continuation is only to another explicitly approved publication with a
fresh session, never a retry/fallback. All cases consume the original shared limits;
case cleanup failure stops further work. No benchmark live call is implicit.

Phase 6D reuses that engine without another HTTP implementation. TikTok delivery is
off by default, development/test only, and restricted to an explicit test-user
allowlist; an empty list denies everyone and production activation is rejected.
Native work runs outside the event loop in a supervised group. Cancellation waits
for executor completion before deleting its workspace. Upload has a separate timeout,
confirmed API response requirement and no automatic retry. Failed process cleanup
refuses success, blocks further TikTok work and quarantines owned files rather than
deleting under a potentially live worker. Filesystem cleanup failure also blocks work.
User messages contain fixed safe categories, without raw exceptions/locators or
diagnostic data. No CDN/cookie/header/dependency or production-registry expansion.
See [Phase 6D](PHASE6D_TIKTOK_TELEGRAM.md) for the separate live acceptance gate.

The isolated Phase 6E adapter admits only the current canonical public page and
inherits the existing pinned transport and scoped cookies. It refuses media phase
requests, other metadata paths and unsafe redirects. JSON parsing never evaluates
script code; duplicate/missing state and ID mismatch fail closed. Raw HTML, locators
and parser messages are not logged. It supplies no bot integration or live CLI.
Any future live call must be explicitly authorized and process-supervised; socket
timeouts/cooperative checks are not a hard deadline for DNS. No bypass, fallback,
header/cookie policy expansion, new CDN or dependency is introduced.

The explicit Phase 6F public-page acquisition mode uses that same native transport,
host/DNS/TLS/redirect policy, scoped cookiejar and Content-Length completeness checks.
It accepts one publication, verifies the original ID before media admission, uses
only its `playAddr`, and refuses explicit separate streams before acquisition.
The existing 180-second supervisor and bounded termination/reap own its private
workspace, including on interruption. The metadata-only entry point still forbids
media; embed/benchmark do not opt in. Phase 6G explicitly selects acquisition in the
provider through the internal API, without exposing CLI export. No retries,
fallback, header changes or new destinations/credentials are introduced. Reports
contain only fixed categories, bounded probe fields, safe CDN families and body
counters; body counters do not measure full TLS/network traffic. Live MP4 validation
requires separate authorization. See [Phase 6F](PHASE6F_TIKTOK_PUBLIC_PAGE_MP4.md).

Phase 6G allows the existing internal verified-file export for explicit public-page
operations. CLI input has no export surface. TikTokProvider opts in without embed
fallback, parser errors become fixed domain errors, and the existing handler retains
flag/allowlist/production guards and file ownership until upload finishes/unwinds.
Exclusive publication occurs only after worker termination/reap; failures retain
existing quarantine/blocking and no-retry behavior. Transport, headers/cookie scope,
pinning/TLS, redirects, framing, budgets and supervisor are unchanged. Native live
success is not real Telegram delivery. See [Phase 6G](PHASE6G_TIKTOK_PUBLIC_PAGE_TELEGRAM.md).

Phase 6H explicitly removes the historical TikTok-only user allowlist and production
activation guard. The feature remains off by default; enabling it exposes supported
public-video downloads to any Telegram user. Instagram restrictions are unchanged.
There is no subscription gate. `TIKTOK_MAX_CONCURRENT_OPERATIONS` defaults to two
and validates 1–8 per bot process, with one operation per user and immediate rejection
at capacity. Admission check/reservation has no await, and no queue is introduced.
User IDs exist only in transient admission state, without logging/persistence.
Each operation has its own cancellation event, worker and workspace. A reservation
is released only after owned worker completion and safe filesystem cleanup; unsafe
cleanup quarantines files, retains that reservation and blocks new TikTok operations.
Existing admitted requests retain independent ownership. Original native limits,
exclusive export, network policy, 120-second upload bound and no-retry behavior stay
unchanged. These are process-local controls, not distributed capacity management or
proof of platform availability. Public live acceptance/deployment require separate
authorization; see [Phase 6H](PHASE6H_TIKTOK_PUBLIC_MVP.md).

Phase 6I permits short-reference resolution only inside the admitted worker. Exact
HTTPS vm/vt hosts and bounded alphanumeric token paths are accepted; query, fragment,
credentials, ports and unknown paths are refused. Every redirect destination is
validated before connect, using the original public-IPv4 pinning and TLS/SNI checks.
Only short intermediates or a full video accepted by `native.publication()` are
allowed; external hosts, IP literals, login/photo/media destinations and cycles fail
closed. Redirect bodies are ignored, not executed or saved, and headers retain the
existing cap. The original redirect/request budget applies, with a 20-second
cooperative short-resolution deadline inside the hard 180-second worker bound.
No header/CDN/cookie-policy expansion is introduced. Standard scoped anonymous cookies
stay operation-local and are cleared on all outcomes. Tokens/queries, publication
locators, HTML and cookie values are absent from reports/user errors. No short-link
network activity occurs in admission/planning; capacity, cancellation, quarantine
and upload ownership remain unchanged. See [Phase 6I](PHASE6I_TIKTOK_SHORT_LINKS.md).

## Experimental Instagram provider

The first Reel provider uses only anonymous extraction: no supplied cookies, browser
sessions, credentials, authentication fallback or persistent yt-dlp cache. Only the
explicit Instagram Reel host/path allowlist reaches the pinned Instagram extractor.
Collections and redirects are rejected before media acquisition. Upstream locator URLs
are runtime data, not fixtures or logs; raw yt-dlp messages are suppressed. Acquisition
uses an isolated temporary workspace, a fixed internal filename and generated safe output
names. No titles or source IDs are interpolated into output paths; symlinks and extra
outputs are rejected. This provider is not registered in the default bot yet.


## Instagram Item Selection

Only an unambiguous `img_index` is admitted for a public carousel. Full parent and
ordered manifest identity are retained for both all-video and one-original-position
scopes and freshly revalidated before media acquisition. No arbitrary subset or
fallback item is permitted. Opaque bounded process-local choices bind user, chat
and Telegram prompt message, have a 15-minute TTL and consume atomically once.
Callbacks contain no publication/media/account identifiers or locators. Admission
reserves the shared Instagram slot before acknowledgement/consume; failed ack/busy
requests retain their choice, while early/foreign/expired/replayed callbacks cannot
start media work. Existing fixed operation-event fields remain the Instagram
logging contract.
If worker reap or owned cleanup is unconfirmed, opt-in quarantine keeps files and
the Instagram slot until operator investigation. Quarantine is not permission to
force-delete files or retry uncertain uploads. No transport, cookie, authentication,
proxy, allowlist or dependency changes are introduced by this feature.

## TikTok native refusal event

The exact `social_video_downloader.tiktok_diagnostics` logger is an additional narrow
sink allowlist, separate from the unchanged general operation-event schema. Each
failed native export emits at most one WARNING containing fixed reason/stage values,
a bounded metadata HTTP status and body/request counters. The formatter reconstructs
this schema again and discards arbitrary fields/exception text. Unknown values are
not serialized as external strings. There are no URLs, video/user IDs, cookies,
headers, bodies, signed locators, request identifiers or traceback output. Missing
worker reports and inexact counters stay unknown. Sink failure does not change the
refusal, retry, deadline or worker cleanup. See
[diagnostic boundaries](TIKTOK_METADATA_DIAGNOSTICS.md).

## Phase 9C admission and resource boundary

Shared request leases and bounded rate bookkeeping keep Telegram user identifiers
only in process memory, never in logs or persistent storage. Bounded user leases
include pending choices; separate global work reservations include quarantined
cleanup but exclude idle choices. Link-refusal notices are throttled; no queue.
`/cancel` cannot
interrupt workers/uploads, bypass ownership or revive a consumed callback.

Instagram byte guards account actual bodies independently of Content-Length and
retain format/identity, output-size, workspace and cleanup checks. Configuration has
an absolute 2,000,000,000-byte individual file ceiling and a smaller cloud endpoint
cap; aggregate budgets are finite. Admission/free-space checks are conservative
accounting, not OS disk quotas, RSS isolation or guarantees against unrelated disk
writers. YouTube acquisition reuses the existing engine in a short-lived owned
POSIX child. Write interception is child-local; preparation uses capped/reaped
FFmpeg processes. Private bounded IPC carries the original snapshot; response
bodies/URLs are not logged or persisted by the guard. Policy-only control files
remain in the owned temporary workspace. Failed group cleanup preserves that root
and quarantines both slots; it never deletes a potentially live writer workspace.
This targets native yt-dlp writes/current FFmpeg outputs, not arbitrary external
programs or RSS. No new HTTP calls, headers, cookies, retry/fallback or production
activation bypass are introduced.
See [limits and lifecycle](PHASE9C_DOWNLOAD_PROTECTION.md).
