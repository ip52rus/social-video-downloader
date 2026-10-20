# Phase 6D: experimental TikTok delivery (offline implementation)

Historical stage record: [Phase 6H](PHASE6H_TIKTOK_PUBLIC_MVP.md) supersedes the
TikTok test-user/production guards and single-operation admission described here.
The original verification and owner-only live evidence below remain unchanged.

Phase 6G switches the existing provider to explicit public-page acquisition while
retaining this handler, activation rules and ownership model. The following Phase
6D evidence describes the earlier embed implementation. See
[Phase 6G](PHASE6G_TIKTOK_PUBLIC_PAGE_TELEGRAM.md) for current preparation and the
still-open real Telegram acceptance gate.

## Subsequent controlled live evidence

Owner-authorized local attempts on this revision reached the native embed endpoint
but received HTTP 429 before media GET/acquisition/upload. Owner messages were
received, progress/error messages confirmed, polling stopped, API sessions closed
and native workspaces/processes cleaned. Video delivery and playback remain unverified.
No fallback or handler change follows from this evidence. The separate offline-only
[Phase 6E prototype](PHASE6E_TIKTOK_PUBLIC_PAGE.md) investigates public-page metadata;
it is not connected to this handler and does not establish a solution to HTTP 429.

## Design decision

Phase 6C's separately authorized four-new-publication benchmark passed 4/4, with
complete MP4, video/audio streams, H.264/AAC, decode and passthrough preparation.
This small sample does not establish general reliability; the earlier B repeatedly
returned CDN 403. No real platform call is authorized during this implementation.

The CLI currently owns and removes its files. Reusing its return value in a handler
would therefore lose the upload artifact. Move its engine into the package without
duplicating HTTP code. Keep the CLI/benchmark as compatibility entry points. For the
provider, one verified silent-capable download is supervised in an owned subprocess
group; only after termination/reap may its file be atomically linked into the caller's
workspace. The caller owns that exported file until upload completes or fails.

A dispatcher-local handler admits only configured test users, serializes TikTok
work, runs the synchronous provider outside the event loop, signals cancellation
to the supervisor and waits for cleanup even under repeated cancellation. Upload
has its own timeout and no retry. Existing inspection/preparation remains inside
the bounded native operation; no second unbounded FFmpeg path is added.

The feature is off by default, forbidden in production, and empty user allowlists
deny everyone. No production provider registry or Instagram activation changes.
The only user option is standard video, including silent video; planning is local
and performs no extra metadata request. No quality/audio menu, cookies from users,
proxy, challenge, new CDN host, dependency, service or polling loop is introduced.

This PR is stacked on PR #60. Neither PR #60 nor main is changed or merged. Docker,
real TikTok/Telegram operations and deployment remain forbidden. Verification and
the next separately authorized acceptance gate are recorded below.

## Components and activation

`infrastructure/tiktok_native.py` owns the single native engine/HTTP transport;
`scripts/tiktok_native.py` is its compatibility entry point. Ordinary CLI and
benchmark input/output policies remain available. `TikTokProvider` implements the
existing provider protocol with a local generic capability descriptor, standard
video only, and no quality/audio menu. The descriptor performs no HTTP. Initially
download used one embed resolution; Phase 6G now explicitly selects one public-page
resolution, verifies source identity and downloads only its admitted `playAddr`.
Silent files are accepted. The verified original is exported without conversion.

`TelegramTikTokHandler` is dispatcher-local and handles only TikTok. YouTube,
Instagram and the default DownloadService registry retain their existing behavior.
Activation requires `TIKTOK_TELEGRAM_ENABLED=true`, `APP_ENV=development` or `test`,
and membership in `TIKTOK_TEST_USER_IDS` (comma-separated positive Telegram user IDs).
The flag defaults false; enabling in production is a configuration error. An empty
allowlist admits nobody. User IDs are not included in configuration representations.
There is no deployment/Compose change in this stage.

## Ownership, limits and failures

The provider accepts an existing caller-owned directory. The worker writes only
inside its own private subdirectory. After native verification and process-group
termination/reap, a fixed-name hard link publishes the file exclusively; an existing
destination is never overwritten. The private subdirectory is then removed.

The handler holds its single active slot and caller workspace while its executor
future settles. Cancellation signals the supervisor and waits even after repeated
cancellation. It does not abandon a thread or delete files under an active worker.
Upload begins only after worker cleanup, retains the file until the awaited API
operation finishes or unwinds, and has a separate 120-second timeout. A returned
Telegram Message with video and matching chat is required; uncertain upload outcomes
are never automatically retried. Notices have a 10-second timeout.

Native ceilings remain 180 seconds plus bounded 5-second process cleanup, 25 MiB
per file, 50 MiB media total, 128 MiB workspace, 2 MiB per metadata response / 4 MiB
total and six metadata/six media HTTP attempts. One candidate, no retry/fallback,
unchanged CDN admission, DNS pinning, TLS, redirects, cookies and HTTP completeness.
These are returned-body counters, not a bound on full TLS/network traffic.

If the OS refuses process cleanup, success is refused, subsequent TikTok work in
that dispatcher is blocked and the owned workspace is quarantined for operator
inspection rather than removed under a possibly live process. Filesystem cleanup
errors also block further TikTok work. This exceptional state requires intervention;
it is not represented as successful cancellation. No raw native exception, locator,
HTML, cookie or identifier is included in user messages or error logs.

## Verification and next gate

Targeted offline verification: 143 passed (103 existing CLI/benchmark cases plus
40 integration cases). Tests use synthetic HTTP, local generated MP4s, fake Telegram
clients and inherited external socket/DNS denial. They exercise sound/silent media,
403/size/truncation, exclusive file export, allowlists/production guard, upload error,
unconfirmed response/timeout, repeated cancellation with live or exited group leader,
and explicit OS cleanup failure with emergency test-owned termination.

Full offline suite and quality/CI evidence are recorded in [TESTING](TESTING.md).
The CI pull-request base filter also includes the native feature branch so this
stacked PR receives the same checks; job permissions and dependencies are unchanged.
The complete tt-dlp MIT notice remains in `licenses/tt-dlp-MIT.txt`.

Next: independent review, then separately authorize controlled Telegram acceptance
for allowed test users. Neither offline tests nor the earlier four native downloads
prove real Telegram delivery. No polling, upload, deployment or additional TikTok
request is authorized by this implementation.
