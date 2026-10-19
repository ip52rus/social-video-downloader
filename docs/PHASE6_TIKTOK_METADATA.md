# Phase 6B-0: isolated TikTok metadata harness

## Design and reason

The experiment needs request and redirect controls that yt-dlp's normal extraction
path does not provide. `scripts/tiktok_metadata.py` therefore retains the installed
TikTok extractors and mapper but replaces their HTTP boundary with a small stdlib
transport. It is not imported by the application, registered as a provider, or
connected to Telegram. No dependency or deployed configuration changes are needed.

Phase 6B-2 uses a separate acquisition CLI because the metadata entry point must
remain unable to download media. The new CLI reuses the metadata admission and
source-ID checks and the same process-group supervisor. Its separate HTTP handler
pins a validated public IPv4 address while retaining TLS hostname verification.
Only `v16-webapp-prime.tiktok.com` and `v19-webapp-prime.tiktok.com` media hosts are
admitted initially, never arbitrary public hosts or a wildcard CDN suffix. These
specific hosts occur in upstream [issue 13771](https://github.com/yt-dlp/yt-dlp/issues/13771)
and [issue 15891](https://github.com/yt-dlp/yt-dlp/issues/15891); reports establish
observed endpoints, not availability or reliability. A different host requires a
separate reviewed decision, not an automatic fallback.

For the metadata CLI, only HTTPS `www.tiktok.com/@user/video/<digits>` and `vm.tiktok.com/<token>` /
`vt.tiktok.com/<token>` are admitted. Tracking query/fragment data is stripped.
Every redirect is checked before opening its target; at most two hops are allowed.
Only these page paths are permitted, never API, CDN or media paths. Full-video
redirects must retain the video identity. Short links use HEAD, then the resolved
full page uses GET. No general URL support is intended.

The metadata transport disables environment proxies, automatic redirects, cookie persistence
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

In the metadata CLI, `process=False`, explicit no-probe configuration and the restrictive HTTP boundary
prevent media acquisition and format probes. Codec/audio values are **extractor
metadata only**, including upstream defaults; missing metadata is unknown, not
proof of silence. That CLI runs no ffprobe, remux or transcode. Reports retain only case
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
enable impersonation, supply cookies or add requests. The limited repeat below
does not close broader URL coverage or any eventual provider decision.

## First authorized attempt and offline correction

After independent P2 re-review passed, the first authorized metadata-only series
stopped on `cookies_forbidden` after one HTTP response containing Set-Cookie. No
HTML body was read and later cases were not attempted. This established neither
a cookie requirement nor a challenge/login requirement; no media was acquired.

The response-header correction is verified only offline, using real yt-dlp mapping
and synthetic HTTP responses. It does not weaken cookie-use, challenge or network
boundaries. Focused independent review and separate authorization are required
before another live series. No repeat experiment is part of this correction.

The correction subsequently passed focused independent review. One separately
authorized repeat with the owner's two full URLs A and B succeeded: two
extractions, two HTTP attempts, 795,225 metadata body bytes, 3.355 seconds,
`counts_exact=true`. A exposed seven MP4 and one MP3 formats; B exposed nine MP4
and one MP3. Each had two HTTPS H.264/AAC MP4 candidates without a probe marker.
One additional format per case was marked for probing; no probes were run.
AAC metadata for B does not establish audible sound. No media was downloaded;
short-link feasibility remains untested. This is metadata feasibility for two
cases, not a TikTok Provider GO or download/playback evidence.

## Phase 6B-2: offline acquisition preparation

`scripts/tiktok_acquisition.py` is a separate experimental CLI. The metadata CLI's
`run()` and command continue to select only its metadata worker. A private shared
supervisor owns and terminates/reaps either CLI's fixed worker; no application
provider, handler, configuration, dependency or deployment changes are involved.

The acquisition CLI admits exactly two distinct full video URLs supplied by the
operator, in A/B order. It cannot prove external owner authorization: the operator
must use only the separately approved A and B. No URLs or IDs are embedded in Git.
It reuses the existing metadata limits and pre-mapping source-ID guard. Before
mapping, an immutable set records only source play/bitrate URLs. The first mapped
HTTPS MP4 H.264/AAC format without `__needs_testing` must belong to that set and
pass the narrow media-host policy above. There is no second extraction, probe,
format fallback, cookie use, Referer/credential forwarding or retry.

Each metadata/media connection uses the isolated pinned HTTPS handler. It rejects
non-global/reserved/multicast and mixed public/private DNS answers, connects one
validated IPv4 sockaddr without another lookup, and retains certificate/hostname
verification and SNI for the original hostname. IPv6-only destinations are blocked.
Media paths must be under `/video/` without encoded/ambiguous path segments.
Redirects (at most two per acquisition) are checked before opening the next target;
only the same explicit host set is permitted. Up to six media HTTP attempts can
occur across the two one-attempt acquisitions, including redirects. Metadata's
8-request budget is separate. CDN availability and the actual A/B media hosts
have not been confirmed by this offline stage; an unlisted host blocks the run.

| Bound | Enforced policy |
| --- | --- |
| Videos / acquisitions | Exactly two distinct full URLs, at most one acquisition each; fail-fast |
| Media file / total received bodies | 25 MiB / 50 MiB; bounded reads before writes, independent of Content-Length |
| Workspace | 128 MiB ceiling; only two originals (at most 50 MiB), no conversion outputs |
| Wall time | **180 s for the whole series**, deliberately tighter than the authorized 360 s ceiling, retaining the existing hard metadata bound |
| External tools | ffprobe at most 20 s per call; complete FFmpeg decode at most 30 s, always within remaining series time |
| Cleanup | Existing process-group termination/reap (up to 5 additional seconds), then parent-owned temporary-directory cleanup |

File size is checked on disk; a worker-only POSIX file-size limit is a backstop.
Media responses require exactly one Content-Length containing an unsigned decimal
length (outer spaces/tabs are allowed). Duplicate lengths, comma-combined values,
malformed/negative lengths and any Transfer-Encoding are refused before body reads.
This includes valid chunked responses; responses without Content-Length are also
refused because connection EOF alone cannot establish completeness. These are
deliberate limitations of this experiment, not reasons to retry another format.
Reads remain bounded by the file, aggregate and workspace budgets as well as the
declared body length. Success requires exactly that many returned bytes, before
ffprobe or preparation. Earlier EOF yields `incomplete_media_response`, cleans the
partial file and stops before B, even if the prefix is a decodable MP4. A complete
body at the byte cap can pass without an extra read. Neither Content-Length nor
ffprobe replaces the streaming resource limits or proves download availability.
Counts describe returned HTTP body bytes, not total network traffic or buffers.
No global concurrency, memory or production-capacity guarantees are claimed.

ffprobe opens local MOV/MP4 only, with file/pipe protocols, and reports actual stream
counts, codecs, dimensions and duration. A must contain an audio stream; B may or
may not. Stream presence does not prove audible sound. Compatible MP4 is passed to
the existing `prepare_telegram_video(..., allow_silent=True)`; its runner forbids
conversion. Incompatible media is reported and blocked. Full local video/audio
decode runs to the null muxer, never an upload or transcoding output.

The parent creates an exclusive temporary directory, retains ownership through
worker completion and removes originals/partials even after ordinary failure,
timeout or interruption. It never cleans a caller-supplied directory. OS-level
termination or filesystem cleanup failures are explicit blocking results; if worker
termination is unconfirmed, its workspace is retained rather than removed under
an active writer. Repeated interrupts are masked during cleanup. Such a result
requires operator attention, never an automatic retry or a successful verdict.

### Separately authorized live procedure

Do not run the acquisition CLI during this offline preparation. After independent
review and a new explicit live authorization, use the existing environment in this
worktree and submit only the previously approved A and B through hidden stdin:

```bash
python -c 'import getpass,json; print(json.dumps([getpass.getpass("A full URL: "),getpass.getpass("B full URL: ")]))' | python scripts/tiktok_acquisition.py
```

Run exactly once. Do not split cases, reset budgets, retry or replace URLs. A
blocking failure stops before B. Retain only sanitized JSON counters, per-case
elapsed time, sizes, actual probe results, decode/preparation status and cleanup
status. Check worker absence and unchanged Git/protected files after exit. The
workspace is removed before the result is returned, so no media is retained.
Docker must stay stopped; no Telegram polling/upload is part of the experiment.
Real acquisition, audible sound, client playback and provider readiness remain
unverified until separately evidenced; this preparation authorizes none of them.
