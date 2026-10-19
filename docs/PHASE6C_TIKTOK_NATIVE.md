# Phase 6C: standalone native TikTok feasibility

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

The next proposed gate is one separately authorized **B-only** run through the same
CLI with one URL. It is not authorized by this offline change. Existing first-case
audio validation remains unchanged: B without an audio stream can report
`audio_required` after acquisition. No A rerun, fallback or policy adjustment.

## Next separately authorized B-only experiment

Use the existing Python environment and only the previously approved full B URL,
supplied through hidden stdin to `scripts/tiktok_native.py` in one invocation.
No URL files, shell arguments or reports. Exactly one run; no A rerun.

With that environment active and `PYTHONPATH=src`, after separate owner permission:

```bash
python -c 'import getpass,json; print(json.dumps([getpass.getpass("B full URL: ")]))' | python scripts/tiktok_native.py
```

No preliminary TikTok probes, alternate formats, repeats or policy edits during the
series. Missing state, forbidden host, HTTP error or incomplete file stops it.

Verify explicit embed source identity, full MP4 HTTP completeness, actual video
and audio/absent-audio via ffprobe, complete FFmpeg decode and existing preparation
compatibility. Metadata does not assert AAC or silence. Explicit separate-audio
metadata is recognized; if acquisition lacks muxed audio, report unsupported split
streams instead of discarding audio or silently declaring silence. No transcode
or extra audio acquisition in this first scope; incompatible media reports a
preparation limitation. No Telegram upload, watermark manipulation, merge or deploy.

GO requires actual complete MP4 plus stream/decode/preparation evidence, not metadata
alone. Until a separately authorized successful run, access, CDN availability,
embed stability, audio layouts and general reliability remain unverified.
