# Phase 6C: standalone native TikTok feasibility

## Latest gate and shared-engine extraction

The separately authorized four-new-publication reliability benchmark on `511b538`
completed 4/4: complete MP4, verified H.264/AAC video/audio streams, full decode and
Telegram preparation passthrough, exact counters and cleanup. Four publications do
not establish general platform reliability; the earlier B's repeated CDN 403 remains
unexplained. These were native-only checks, without Telegram upload.

On the separate Phase 6D stacked branch, the same native implementation is moved
to `infrastructure/tiktok_native.py`; `scripts/tiktok_native.py` remains the public
CLI wrapper, including ordinary and benchmark interfaces. Network behavior, source
checks and limits below are preserved. Caller-workspace export and restricted
experimental Telegram integration are described in [Phase 6D](PHASE6D_TIKTOK_TELEGRAM.md).
Historical preparation/live instructions below do not authorize another run.

## Design and gate

PR #59's yt-dlp experiment is discontinued and remains unmerged/unchanged. Its
final authorized run returned HTTP 200 / 537 HTML body bytes with no recognized
metadata structure: 1 metadata request, 0 media requests, B not started. Neither
login/challenge nor a solution to the earlier CDN 403 was established.

This separate implementation investigates the public `/embed/v2/<post_id>` route.
It is not a MediaProvider, bot handler or DownloadService change. No live TikTok
request is authorized during implementation. Existing FFmpeg inspection and
`prepare_telegram_video(..., allow_silent=True)` are reused locally; no upload.

Source reference: [tt-dlp](https://github.com/bajaam/tt-dlp/tree/08a1f42abf11ff3c969e0af323644bb6fbcc7cf7),
MIT, inspected `client.py`, `downloader.py`, `models.py`, `targets.py` and their tests.
The source uses the `__FRONTITY_CONNECT_STATE__` script's
`source.data[embed_path].videoData.itemInfos`. Its URL normalization handles bitrate,
play and download addresses; it uses an HTTP CookieJar even without a cookie file.
Its retries, profile queues, user cookies, automatic redirects, metadata refresh
and unbounded downloads are not adopted. Upstream permits a missing item ID to
fall back to the requested ID; our resolver requires an explicit matching source ID.
The embed schema/address approach (including `video.urls`) and plain HTTP User-Agent are adapted with the
complete [MIT notice](../licenses/tt-dlp-MIT.txt). Presence of code/tests is not live
download evidence.

## Network and resource boundary

Only HTTPS full `www.tiktok.com/@user/video/<decimal_id>` input. Tracking is removed;
story selectors and non-public content are rejected. The only metadata destination
is the current ID's exact embed route. JSON is parsed, never evaluated as JS.
Missing/duplicate scripts, duplicate JSON keys and mismatched identity refuse.
Photo fields (`imagePost` / `imagePostInfo`, in itemInfos or videoData) may be absent
or contain only a null, empty object or empty array placeholder. These placeholders
do not establish video: the existing video structure/candidate checks still apply.
A nonempty `images` array of nonempty image objects refuses as `unsupported_photo`;
other significant, malformed or conflicting photo structures refuse as
`metadata_schema`. No image URL is fetched or used as a video candidate.

Media destinations must originate in that item's recognized video address fields.
Only a numbered `v` video label (optionally a letter and bounded hyphen segments)
under `tiktokcdn.com`, `tiktokcdn-us.com`, `tiktokcdn-eu.com`, or a numbered web/webapp
label under `tiktok.com`, is admitted. No arbitrary subdomain, wildcard shared CDN,
API, localhost or literal IP. Paths need not contain `/video/` or end in `.mp4`.
The domain families appear in [upstream response evidence](https://github.com/yt-dlp/yt-dlp/issues/17393);
[video-host examples](https://github.com/davidteather/TikTok-Api/issues/490) include
numbered tiktokcdn hosts. Such reports justify a narrow experiment policy, not a
claim that all labels work. Unlisted hosts stop rather than extend policy at runtime.

All DNS IPv4 answers must be global/unicast. Connect to exactly one checked address,
with the original hostname retained for SNI/certificate verification; no second
DNS lookup, proxy or TLS impersonation. Redirect destinations are revalidated before
opening; two hops per request, no retry/fallback. Signed media queries stay intact.

Each publication owns a fresh memory-only CookieJar with domain/path/secure checks,
strict host-only scope and acceptance limited to the recognized platform domains.
Cookies are never manually copied across domain families, persisted or reported.
No browser cookies, accounts, challenge code or third-party API is involved.

Ceilings: 2 unique videos, 180 s total plus 5 s process cleanup, 2 MiB metadata per
response / 4 MiB total, 6 metadata HTTP attempts and 6 media attempts including
redirects, 25 MiB media per file / 50 MiB total, 128 MiB workspace. One selected
candidate per video. Body counters measure returned HTTP body bytes, not TLS/wire
traffic. Media requires one positive Content-Length and no Transfer-Encoding;
truncated, duplicate/invalid-length, chunked and unknown-length media refuse.

Only the already-reviewed private process-group ownership/termination pattern is
adapted from PR #59: native DNS/network/FFmpeg calls need a hard deadline. No yt-dlp
extractor, HTTP framework or old metadata/acquisition flow is imported. The parent
owns workspace removal after group termination, including error/interrupt paths.

## First native live result and next gate

The owner's one authorized native A/B run stopped on A with `unsupported_photo`:
one metadata HTTP attempt, 281,910 body bytes, 1.376 seconds, zero media requests/
acquisitions/bytes, exact counters and completed workspace cleanup. B was not run.
The HTML was not retained, so its photo-field values are unknown. The old resolver
refused on key presence alone; an offline regression reproduced that false refusal
with null/empty placeholders. The fix does not prove that A will now resolve or
download. Another live run needs new owner authorization; no live request was made
during the photo-classification patch.

The next authorized A/B run on `85ab929` was **PARTIAL PASS**: A yielded a complete
1,097,768-byte MP4, one video and one audio stream, full FFmpeg decode and Telegram
preparation passthrough. B resolved one candidate but its media GET returned 403.
The series took 5.149 s, with 2 metadata requests / 566,367 body bytes, 2 media
requests / 1,097,768 body bytes, 2 acquisitions, exact counters and successful
cleanup. No retry occurred. The old constant codec labels were not independent
codec measurements; B's server-side refusal reason remains unknown.

## Safe CDN diagnostics (offline patch)

Results now include `candidate_source` (playAddr, bitrateInfo, downloadAddr or urls),
the existing unique candidate count (recognized addresses before host admission),
and `media_http`, a bounded ordered list for
the media HTTP attempts already performed. Each record exposes only a normalized
`cdn_family`, `has_query`, `cookie_sent` and actual response `status`. Cookie presence
is recorded only after the request send returns; status only after a response is
received. Unmeasured fields are null, not assumed false/success. Redirects produce
separate records; no cookie values, full hosts, paths, queries or response bodies
are included. This does not add requests or read an error response body.

Per-case `counts` are differences of the existing operation counters, including
metadata/media attempts, returned body bytes and acquisitions; the aggregate counters
and `counts_exact` keep their existing meaning. Attempts are budget reservations,
so a DNS/connect/send failure can count without an HTTP response. Bodies left
unread (including 403 error bodies) contribute zero; this is not total wire traffic.
Forced worker termination can still make counters incomplete (`counts_exact=false`).

`video_codec` / `audio_codec` now come from the existing inspection's `codec_name`,
not constants. Only a finite vocabulary of known codec names (maximum 9 characters)
is reported. Missing, malformed, oversized or unrecognized names become null;
an absent audio stream remains `absent`. Measured names also survive a later
preparation failure. These diagnostic rules do not change decode/preparation or
authorize conversion. There is no new ffprobe invocation for reporting.

These fields cannot establish why a server sent 403 (signature/session/region/access
rules), whether cookies are sufficient, or the contents/codecs of an unavailable
file. No HTML, cookie value, signed URL, publication identity or IP is retained.

The separately authorized B-only run on `f3213d6` also stopped at media HTTP 403:
one candidate from `urls`, `tiktokcdn-eu.com`, query present, cookies not sent.
Metadata: 1 request / 286,670 bytes; media: 1 request / 0 bytes; one acquisition,
1.788 s, exact counters and cleanup PASS. No full file or audio verification.
This does not identify the refusal's cause or establish that cookies are required.
No further request for B is part of the reliability plan.

## Media source comparison (read-only research)

References: MIT [tt-dlp client](https://github.com/bajaam/tt-dlp/blob/08a1f42abf11ff3c969e0af323644bb6fbcc7cf7/src/tt_dlp/client.py)
(`_address_urls`, `video_urls`, `normalize_item`) and
[downloader](https://github.com/bajaam/tt-dlp/blob/08a1f42abf11ff3c969e0af323644bb6fbcc7cf7/src/tt_dlp/downloader.py);
[Cobalt](https://github.com/imputnet/cobalt/blob/a636575b09de1fc55d9b8cd98cac88f5f2f16b42/api/src/processing/services/tiktok.js)
(analysis only; no AGPL implementation copied); locally installed yt-dlp
2026.08.19, `TikTokBaseIE._extract_web_formats` / `_parse_aweme_video_web`.
The [upstream version source](https://github.com/yt-dlp/yt-dlp/blob/2026.08.19/yt_dlp/extractor/tiktok.py)
is a reference; findings use the actual installed code.

| Field | Evidence and limitation |
| --- | --- |
| `playAddr` | Playback candidate in all three projects. tt-dlp accepts strings and address containers; yt-dlp also handles web `src` layouts. Cobalt normally selects this field. No access guarantee. |
| `bitrateInfo.PlayAddr` | Alternative playback representations. tt-dlp sorts by declared pixel area before playAddr; yt-dlp extracts formats and notes some video-only/unplayable layouts; Cobalt optionally selects H.265. Quality/codec metadata does not prove a complete muxed file. |
| `downloadAddr` | Additional candidate in tt-dlp. yt-dlp labels its web download representation watermarked and requiring testing; API forms differ. No automatic watermark removal or network test is adopted. |
| `video.urls` | Explicit final address source in tt-dlp, supporting string/list and `urlList`/`UrlList`/`urls` containers. The inspected Cobalt/TikTok web-format paths do not consume this input field. Cobalt's returned `urls` is its own output property, not evidence about embed `video.urls`. Meaning/access conditions across embed layouts remain unproven; B's 403 does not make the field invalid. |

Our existing selection stays playAddr, bitrateInfo in source order, downloadAddr,
then urls, deduplicated with first-source provenance and exact destination admission.
There is an evidence-based alternative for publications that actually expose an
admitted playAddr/bitrateInfo/downloadAddr in the same identity-verified metadata.
Those addresses are already considered offline; no additional endpoint, synthesized
URL, changed priority, refresh, retry or network fallback is added. B exposed one
unique candidate, so no demonstrated alternative for B exists.

tt-dlp compares a present ID but can substitute the requested ID when missing;
our resolver requires the source ID itself. Cobalt's inspected service uses itemStruct
but has no equivalent explicit source-ID equality check. yt-dlp's web mapper returns
the caller's ID, so that mapped ID alone is insufficient. Our pre-selection identity
check stays unchanged. tt-dlp keeps a cookie-aware opener and retries/refreshes;
Cobalt carries public-page cookies into its media context; yt-dlp uses Referer and
its shared HTTP context, with additional authenticated/API behavior outside our scope.
Signed URL, session, region or expiry restrictions are possible, not established for B.
Merely discovering HTTPS metadata is not download evidence. No upstream access-policy
workarounds or AGPL code were incorporated.

## Reliability benchmark mode (offline preparation)

Reason: test independent publications despite a case-local failure, without enlarging
the network/resource boundary or integrating a provider. `--benchmark` is explicit;
the ordinary URL-array interface retains two-case fail-fast behavior and its original
first-case audio requirement.

Benchmark stdin is a JSON array of **1–4** objects, each with exactly `url` and boolean
`require_audio`. Only owner-supplied full public video URLs, distinct source IDs and
explicit per-case expectations are accepted before worker creation. Use new videos,
not A/B, and never select/search for examples automatically. Do not persist the input.

Each case gets one existing embed resolution, one selected media candidate, one
acquisition and its own fresh memory-only session. Failed cases do not trigger
retries or alternate URLs: processing moves to the next approved publication.
Owned case files are removed before continuing; cookie jars are cleared. Cleanup
failure stops the series. Shared request/byte exhaustion and the original deadline
stop before another case; `stop_reason` and `requested_cases` explain unprocessed
cases. Failed cases still count against the common budgets.

Limits remain **180 s + bounded cleanup, 6 metadata / 6 media HTTP attempts including
redirects, 2 MiB metadata/response and 4 MiB total, 25 MiB/file, 50 MiB media total,
128 MiB workspace**. Four cases are a ceiling, not a promise that budgets permit all
four. Input/output size bounds, DNS/TLS/headers/cookies/redirect/framing policy and
the process supervisor are unchanged. No media/metadata request is made in this task.

`require_audio=true` requires an actual audio stream. False allows audio or its
absence; it never asserts audible silence. Split-audio metadata still cannot cause
another acquisition or muxing. Existing decode/preparation is reused without conversion.
The benchmark preserves measured stream counts/codecs and HTTP completeness/bytes
even if subsequent verification reports `audio_required` or preparation failure.
`source_identity` is true after successful resolution, false for a source-ID refusal,
and null if no reliable identity result is available. Other missing measurements
remain absent/null, not guessed. No private input, IDs, raw HTML, full host/IP,
cookie or signed URL is reported. Existing per-case/aggregate counters and exactness
flags apply; interrupted workers may yield incomplete counters. A partial result
has exit status 1 even when later cases passed; do not rerun because of that status.

## Next separately authorized reliability experiment

Before any network call the owner must approve up to four **new** URLs and the audio
expectation for each, plus one common run. A and B must not be reused. Inspect exact
HEAD, clean tracked state, existing interpreter/FFmpeg, absence of workers and exited
containers. Do not perform preliminary probes, dependency changes or policy edits.

After separate authorization, the following hidden-input example is suitable only
when its expectation list matches the owner's approved cases (edit that list, not
the tool; shorter lists are allowed):

```bash
python -c 'import getpass,json; expected=[True,True,False,False]; print(json.dumps([{"url":getpass.getpass(f"Approved NEW URL {i+1}: "),"require_audio":required} for i,required in enumerate(expected)]))' | PYTHONPATH=src python scripts/tiktok_native.py --benchmark
```

Run once, report every processed case and early-stop budgets, then verify process/
workspace cleanup and unchanged Git/environment. No Telegram upload, merge or deploy.
Real complete MP4, streams, full decode and preparation are necessary for successful
cases. A small sample estimates only its tested surface, not production reliability
or a general platform GO. This preparation authorizes no real benchmark.
