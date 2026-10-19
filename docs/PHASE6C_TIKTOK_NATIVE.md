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

## Next separately authorized A/B experiment

Use the existing Python environment, only owner-approved full A and B, supplied
through hidden stdin to `scripts/tiktok_native.py` in one invocation. No URL files,
shell arguments or reports. Exactly one series; failure A stops before B.

With that environment active and `PYTHONPATH=src`, after separate owner permission:

```bash
python -c 'import getpass,json; print(json.dumps([getpass.getpass("A full URL: "),getpass.getpass("B full URL: ")]))' | python scripts/tiktok_native.py
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
