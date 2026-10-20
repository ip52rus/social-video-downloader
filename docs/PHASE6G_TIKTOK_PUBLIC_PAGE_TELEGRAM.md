# Phase 6G — public-page provider and restricted Telegram delivery

## Decision before implementation

The separately authorized Phase 6F call on `f31fdb5` obtained one complete MP4:
571,013 body bytes, one H.264 video/AAC audio stream, 576×1024, duration 12 seconds
as reported by the CLI, full decode and passthrough preparation. One metadata
request read 410,890 bytes; one media request returned 200. The operation took
5.506 seconds with exact counters and successful process/workspace cleanup.
Metadata status was not separately exposed by that CLI. This is one native live
case, not real Telegram delivery or a general solution to HTTP 429.

Reuse the existing internal `run()` / `download_video()` export path for explicit
public-page acquisition. The provider opts into that path; no downloader, HTTP
transport or Telegram handler is added. Keep CLI input diagnostic-only: it has no
export argument and cannot accept caller workspace settings through stdin.

Publication remains an exclusive hard link into the caller's existing workspace,
only after verified media and worker-group termination/reap. The existing handler
owns the exported file through the awaited upload and preserves cancellation,
blocking and quarantine semantics. Existing native limits, scoped cookies, CDN,
DNS/IP/TLS/redirect/framing rules and default embed/benchmark remain unchanged.
Public-page selection is explicit in the provider, with no embed fallback or retry.

Real TikTok/Telegram calls, polling, Docker, deployment and merge are not authorized
during preparation. The next gate requires separate owner authorization after
offline verification and exact-head CI.

## Current path and ownership

`TikTokProvider.download_prepared()` explicitly requests
`download_video(..., public_page=True)`. The original `DownloadedMedia` metadata
and width/height/duration parameters are retained. Local capability planning and
canonicalization do not fetch metadata. New public-page parser failures map into
existing safe metadata/domain errors; HTTP/media/timeout/cleanup categories retain
their existing handling. No raw parser exception or locator is surfaced.

`run(public_page=True, output_dir=...)` accepts one publication and an existing
caller-owned directory under the original path checks. The worker resolves only
the canonical page, validates original identity, selects its admitted `playAddr`,
acquires once, verifies completeness/streams, fully decodes and prepares passthrough.
Explicit separate streams refuse before GET; audio is optional. Native headers,
operation-local cookies, pinned transport and all budgets are unchanged.

After group termination and reap, the existing fixed-name `os.link` publishes
`tiktok.mp4` exclusively. File collisions refuse without overwriting, and failed
publication/cleanup rolls back only owned output under the original policy. The
provider returns a verified file, not a path already deleted by the diagnostic CLI.
The CLI still accepts only URL arrays and known modes; arguments or stdin objects
cannot select output paths. Ordinary embed and benchmark retain their paths.

The unchanged handler runs the provider in its owned executor, waits for completion
even on repeated cancellation and retains the exported file throughout awaited
`answer_video` (Telegram sendVideo). The returned Message must have video and match
the chat. Upload timeout remains 120 seconds with no retry for errors/uncertain
responses. Cleanup failure quarantines the workspace and blocks later TikTok work;
no files are removed under a potentially live worker. No real Telegram API is
invoked during offline tests.

Activation is unchanged: disabled by default, development/test only, explicit
`TIKTOK_TEST_USER_IDS` membership required, empty list denies everyone and production
activation fails configuration. No user IDs, tokens, environment files, polling,
additional clients, handlers, menus or dependencies are introduced.

## Verification and next gate

**226 focused tests PASS**, including 19 new provider/export/fault/CLI cases. The
prior blanket internal public-page-export rejection case is replaced by successful
safe internal export checks and three explicit CLI export-denial cases. Real-parser
synthetic HTTP, generated sound/silent MP4 and fake Telegram exercise the full
handler path, verified file lifetime/reap, exact counters, one metadata/media
operation, parser/source/CDN/separate-stream errors, metadata 403/429, media 403,
truncation and size limits, privacy and owned cleanup. Existing timeout/repeated
cancellation, upload error/unconfirmed response, quarantine/blocking, flag/access,
native CLI/benchmark and platform regressions remain part of the focused/full runs.
External sockets/DNS are denied, including in Python workers.

AST comparison confirms the parser, 15 engine functions/classes and policy constants
unchanged; the supervisor differs only by permitting public-page export admission.
Handler, config, bot wiring, working platforms, media helpers, dependencies and MIT
notice remain byte-identical. Full offline suite: **1696 passed, 1 skipped**; Ruff
lint/format, diff-check and scope/security PASS. See TESTING for evidence and limits.
Exact committed-head GitHub CI is required before handoff; only the CI
PR base filter is extended to the parent branch, with unchanged jobs/permissions.

The next gate is one separately owner-authorized local Telegram test on exact HEAD,
with stopped Docker/other pollers, process-local development settings and owner-only
allowlist. One supplied previously successful URL is processed once, without probes,
retries or upload fallback. Require actual metadata/media verification, confirmed
Telegram video Message, worker/session/workspace cleanup, and manual playback/audio
confirmation. Native success and fake Telegram tests do not close that live gate.
