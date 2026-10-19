# Phase 6B-0: isolated TikTok metadata harness

## Design and reason

The experiment needs request and redirect controls that yt-dlp's normal extraction
path does not provide. `scripts/tiktok_metadata.py` therefore retains the installed
TikTok extractors and mapper but replaces their HTTP boundary with a small stdlib
transport. It is not imported by the application, registered as a provider, or
connected to Telegram. No dependency or deployed configuration changes are needed.

Only HTTPS `www.tiktok.com/@user/video/<digits>` and `vm.tiktok.com/<token>` /
`vt.tiktok.com/<token>` are admitted. Tracking query/fragment data is stripped.
Every redirect is checked before opening its target; at most two hops are allowed.
Only these page paths are permitted, never API, CDN or media paths. Full-video
redirects must retain the video identity. Short links use HEAD, then the resolved
full page uses GET. No general URL support is intended.

The transport disables environment proxies, automatic redirects, cookie persistence
and impersonation. All Set-Cookie response headers, including duplicates, are
discarded before yt-dlp sees the response; their presence alone is not a refusal.
No CookieProcessor is installed. Outgoing Cookie/credential headers, extractor
`_set_cookie` calls, challenge-solver invocation, login redirects, mobile API calls
and unexpected requests still abort the series. There are no retries. A blocked
ordinary page is a useful feasibility result, not permission to bypass its checks.

## Bounds and evidence

One invocation is one series: up to 3 URLs, 4 extractor calls, 8 HTTP requests
(including redirect hops), 180 seconds, 2 MiB per response body and 8 MiB total
response bodies. These ceilings can only be reduced through `Limits` in offline
tests. Request counts measure transport-open attempts, not wire captures; failed
DNS/TLS attempts still consume the budget. Bodies are read incrementally; absent
or false Content-Length does not lift
the cap. An exact-cap response is conservatively rejected. Only identity-encoded
HTML is read; redirect/HEAD bodies are not consumed. Byte counts describe bytes
returned by the response reader, not TLS overhead or kernel/network buffers.

A parent process owns a private worker process group and kills/reaps it on deadline
or interruption. This bounds stalled native/network calls without adding a bot
runtime process manager. To retain safe ownership of the group ID, pipe exchange
and `waitid(..., WNOWAIT)` leave the leader unreaped until group termination,
including when it has already exited but descendants remain. POSIX with `waitid`
and `WNOWAIT` is required (available in the local macOS and Linux CI environments).
Darwin's zombie-only-group error is accepted only after reaping and probing that
the group is absent; no terminating signal is sent using a released PGID. Cleanup
errors remain explicit `cleanup_failed` results, never successful inspection.
Startup counts toward the deadline; bounded cleanup can
take up to five additional seconds. Progress counters after a
forced stop are marked inexact: received-byte counts may be lower bounds. There
are no global memory, concurrency, wire-byte or production-capacity guarantees.

`process=False`, explicit no-probe configuration and the restrictive HTTP boundary
prevent media acquisition and format probes. Codec/audio values are **extractor
metadata only**, including upstream defaults; missing metadata is unknown, not
proof of silence. No ffprobe, remux or transcode occurs. Reports retain only case
numbers, within-series pseudonyms, technical format categories, counters, elapsed
time and sanitized errors. URLs, actual IDs, usernames, descriptions and cookies
are not printed or persisted. Input URLs exist transiently in process memory.
The web mapper's source `itemStruct.id` must be a decimal string matching the
validated full URL before mapping. Missing, malformed or mismatched identity
blocks inspection, including after short-link resolution, without another request.

## Phase 6B-1: separate authorization required

Do not run this against TikTok during Phase 6B-0. After separate approval, supply
exactly the approved cases: A (full public video with sound), A-short (short link
to A), B (full public silent video). The owner must provide/approve actual URLs;
none are chosen by the tool. Provide a JSON array through stdin, for example via
an interactive stdin producer without putting URLs in shell history:

```bash
python -c 'import getpass,json; print(json.dumps([getpass.getpass("Approved URL: ") for _ in range(3)]))' | python scripts/tiktok_metadata.py
```

Use the existing project virtual environment. The supported CLI always starts its
supervised worker. Do not call private worker functions for a real experiment.
One invocation covers the entire series; do not split/retry failures to reset
budgets. The deadline starts after stdin is supplied. Exit 0 means metadata
inspection completed; exit 1 means a sanitized failure. Neither proves media
acquisition, actual audio streams, Telegram playback or provider readiness.

If the default ceilings, cookie-use refusal or narrow page allowlist prevent inspection,
record BLOCKED and review the specific obstacle. Do not silently broaden hosts,
enable impersonation, supply cookies or add requests. Phase 6B-1 and any eventual
provider decision remain pending.

## First authorized attempt and offline correction

After independent P2 re-review passed, the first authorized metadata-only series
stopped on `cookies_forbidden` after one HTTP response containing Set-Cookie. No
HTML body was read and later cases were not attempted. This established neither
a cookie requirement nor a challenge/login requirement; no media was acquired.

The response-header correction is verified only offline, using real yt-dlp mapping
and synthetic HTTP responses. It does not weaken cookie-use, challenge or network
boundaries. Focused independent review and separate authorization are required
before another live series. No repeat experiment is part of this correction.
