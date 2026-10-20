# Phase 6F — supervised public-page MP4 acquisition

## Architecture decision and scope

The Phase 6E public-page inspection obtained metadata from one authorized live
publication: HTTP 200, matching source ID, one admitted `playAddr`, one metadata
request and 405,981 body bytes. No media request was made. This is evidence for
metadata only, not MP4 availability or general TikTok reliability.

Add an explicit `--public-page` mode to the existing native CLI. Reuse its worker,
process-group supervisor, HTTP transport, acquisition, file verification and
cleanup instead of creating another downloader. The mode accepts one publication,
uses the strict public-page parser, and never selects embed or another source.
Its session retains the existing scoped, memory-only cookies for this operation.
The Phase 6E metadata-only entry point remains unable to fetch media. Provider,
Telegram, default embed CLI and benchmark do not opt into the new mode.

The worker imports the packaged engine rather than evaluating its file a second
time with `runpy`. This keeps its `Refusal` class identical to the parser/session's
class, so public-page errors retain their safe categories. Process creation,
group ownership, deadline, termination and reaping are unchanged.

Real TikTok requests and media acquisition are not authorized during development.
Offline verification and the separate live acceptance gate are recorded below.

## Explicit diagnostic interface

Only after separate owner authorization, from the selected worktree and existing
Python environment:

```bash
python -c 'import getpass,json; print(json.dumps([getpass.getpass("Approved full URL: ")]))' | PYTHONPATH=src python scripts/tiktok_native.py --public-page
```

The input is one JSON array containing exactly one full TikTok video URL. Other
case counts, combination with benchmark and file export are rejected before a
worker starts. No raw URL arguments, HTML files, locator logs or persistent cookies
are needed. The ordinary CLI and `--benchmark` retain their interfaces and paths.

One canonical public-page metadata resolution verifies the original item ID,
admits only that item's `playAddr` and makes one acquisition attempt. Signed path
and query are preserved. Explicit separate-audio metadata refuses before media
GET. There is no download/bitrate/embed fallback, retry, additional probe, mux or
conversion. Audio is optional; any actual track and its codec are measured by the
existing ffprobe path. A track does not establish audible sound.

The inherited session retains standard domain/path/secure cookie scope between
metadata and media and clears its memory jar at operation end. No manually widened
cookie scope, headers, CDN names, proxy, authentication or impersonation is added.

## Bounds and results

- 180 seconds for the supervised operation, then the existing bounded 5-second
  process cleanup; group termination precedes reap, with no signal to a reused PID.
- Metadata: 2 MiB per response, 4 MiB total; at most 6 HTTP attempts with redirects.
- Media: 25 MiB per file, 50 MiB total; at most 6 HTTP attempts with redirects and
  only one selected candidate/acquisition. No Range request or recovery download.
- Existing 128 MiB workspace ceiling, streaming byte counters, positive single
  Content-Length, no ambiguous/chunked media framing, exact body completeness,
  MP4 container/stream checks, bounded ffprobe/full FFmpeg decode and passthrough
  `prepare_telegram_video(..., allow_silent=True)` are reused.

Results expose only fixed error categories, source field, candidate count, source
identity outcome, safe CDN family/query/cookie booleans, actual media status,
body/request counters and bounded probe/preparation fields. Bytes count response
bodies read, not full network/TLS traffic. A forcibly terminated worker reports
`counts_exact=false`, rather than inventing partial counters. No raw exceptions,
HTML, signed locators, cookies, usernames, post IDs or IP addresses are reported.
Media/partials stay inside the owned workspace and are removed on success/failure;
parent cleanup also runs on timeout/cancellation. Unconfirmed cleanup refuses
success and preserves the existing quarantine policy rather than deleting under
a potentially live worker. Nothing is exported or uploaded to Telegram.

## Offline verification and live acceptance

20 new focused cases cover generated MP4 with/without audio through real workers,
probe/decode/passthrough, source ID and playAddr, metadata 403/429/schema/destination
errors, separate streams before GET, actual signed query/headers/cookie scope,
media 403/truncated framing/size limit, stream timeout/cancellation, cleanup,
counter exactness, privacy and explicit one-case input. Together with unchanged
public-page, native/benchmark and Telegram regressions: **208 focused PASS**.
All HTTP responses are synthetic and external sockets/DNS are denied, including
in Python workers. Full offline pytest: **1678 passed, 1 skipped**; Ruff lint/format
and diff/scope/security review PASS. Six supplemental fault injections cover
redirect boundaries, cookie scope, the metadata-only guard and worker error
categories. Exact-head publication CI is checked before handoff; see TESTING and
the Draft PR checks for results.

Before a live test, require exact committed HEAD, clean tracked files, existing
Python/FFmpeg, no stale workers, separate owner authorization and one approved full
URL through hidden stdin. Execute the mode once, keep all limits, and stop on any
refusal without retries or changing policy. Success must confirm real complete
MP4, original ID, actual streams/codecs, full decode, passthrough preparation and
process/workspace cleanup. Metadata alone is not GO, and this mode is not a bot
fallback, a general 429 solution or evidence of broad TikTok reliability.
