# yt-dlp stable upgrade and metadata A/B — 2026-10-30

## Scope and baseline

Owner-authorized dependency target: **2026.10.26**, verified as the latest official
non-prerelease on 2026-10-30. Baseline main `f804c2e` (merged PR #88), post-merge
[CI #41058700939](https://github.com/ip52rus/social-video-downloader/actions/runs/41058700939)
SUCCESS. The saved P9-R3b deployment checkpoint at **13:06:40 UTC** is
**TECHNICAL PASS**, source `f804c2e`, diagnostics=false. That is dated evidence,
not a new production inspection. This upgrade does not deploy anything.

P9-R3a remains OFFLINE VERIFIED. P9-R2 experimental series is CLOSED /
INCONCLUSIVE, LIVE responsiveness acceptance OPEN / INCONCLUSIVE. Phase 9 is OPEN.
The library update is independent of the diagnostic A/B outcome.

## Dependency changes

| Package | Before | After | Reason |
|---|---|---|---|
| yt-dlp | 2026.8.19 | 2026.10.26 | Approved official stable |
| certifi | 2026.7.22 | 2026.10.23 | New default extra requires >=2026.10.19; CA security update |
| Brotli | 1.2.0 | 1.2.1 | Upstream decoder security patch |

No other locked package versions change. yt-dlp-ejs stays 0.8.0, requests 2.34.2,
urllib3 2.8.0, aiogram 3.31.0 and aiohttp 3.14.4. curl-cffi is not added.
`pyproject.toml` pins the approved yt-dlp version exactly. Python remains 3.13;
Deno remains 2.9.7. The extractor runtime gate accepts Deno >=2.3.0; the optional
upstream Python `deno` extra is not used. Runtime verification is CPython/macOS;
this stage does not certify PyPy or rebuild the Linux production image.

Official sources: [yt-dlp release](https://github.com/yt-dlp/yt-dlp/releases/tag/2026.10.26),
[requirements](https://github.com/yt-dlp/yt-dlp/blob/2026.10.26/pyproject.toml),
[Deno runtime check](https://github.com/yt-dlp/yt-dlp/blob/2026.10.26/yt_dlp/utils/_jsruntime.py),
[certifi advisory](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2),
[Brotli security release](https://github.com/google/brotli/releases/tag/v1.2.1).
The security updates are not evidence that TLS caused the reported metadata failure.

## Bounded external metadata experiment

Exactly one extraction per version, in order A then B, for the owner-approved
public video `s6NUEu1x64I`. Runs used separate environments and empty home/cache
locations, identical Python 3.13.12, OpenSSL 3.0.18, Deno 2.9.7, EJS 0.8.0,
certifi 2026.10.23, Brotli 1.2.1 and all other installed distribution versions.
Only yt-dlp differed. Common updated TLS dependencies differ from production.
The host was local macOS, not HOSTKEY; IP/time/OS effects are not controlled away.

Each call used `download=False`, `process=False`, disabled cache, zero extractor/
download retries, no cookies, authorization, proxy, plugins or remote components.
Media download/result processing methods were forbidden. A 55-second supervisor
budget and 5-second cleanup reserve bounded each owned process group. Both groups
were confirmed absent, with no deadline escalation. No further attempt was made.

| Metric | A: 2026.08.19 | B: 2026.10.26 |
|---|---:|---:|
| Completed UTC | 13:32:17 | 13:32:32 |
| Extraction calls | 1 | 1 |
| Extractor result | Returned | Returned |
| Identity matches target | Yes | Yes |
| Formats reported | 97 | 102 |
| Metadata HTTP requests | 3 | 5 |
| Extraction plus validation duration, seconds | 3.698 | 6.508 |
| Snapshot validation | FAILED | FAILED |
| Serialization / IPC envelope / choice planning | NOT REACHED | NOT REACHED |
| Media acquisition | 0 | 0 |
| Owned process-group cleanup | Confirmed | Confirmed |

The failure stage is positively localized to snapshot validation in this harness.
The safe exception classifier returned `unclassified_failure`; the precise
predicate/type/size causing refusal was **not retained**. Raw metadata and exception
text were intentionally not saved, so they cannot be reconstructed after process
exit. No specific codec predicate, new unsupported type, corruption or application
bug is asserted. This is a shared baseline failure, not evidence of a new-version
regression. The standalone A/B harness is not the unmodified production child.

The updated extractor does **not** demonstrate restoration of the application's
metadata-to-buttons path. The production incident's cause remains UNKNOWN.
Initial-data/client incompatibility is less sufficient as a sole explanation:
both isolated extractors returned data, while both snapshot validations failed.
Neither result proves what the earlier HOSTKEY worker received.

### Minimal reproducer and evidence limits

The preserved operator harness performs this sequence once per isolated version:

```python
provider = YouTubeProvider()
options = provider._base_options()
options.update(cachedir=False, retries=0, fragment_retries=0, extractor_retries=0)
# URL is supplied only by a separately approved bounded metadata experiment.
req = request(url, "single-approved-metadata-ab-nonce")
with provider._new_ydl(options) as ydl:
    info = provider._read_raw_info(ydl, url)  # download=False, process=False
payload = response(req, info, monotonic())
validate_response(payload, req)  # observed failure boundary on both versions
```

This excerpt identifies the reproducible interface boundary; the preserved harness
also supplies the deadline, clean environment, media guards and safe output handling.
It is not an offline fixture for the exact discarded snapshot. A future attempt to
identify the precise predicate needs separate authorization and a predefined bounded
classifier. Do not rerun this excerpt, materialize lazy data, strip fields or relax
snapshot budgets/identity/version guards as part of this stage.

Sanitized operator artifacts are under the private evidence folder
`ytdlp-ab-20261030`: protocol/environment manifests, harness, per-arm results and
`result.json`. No raw metadata, signed URLs, titles, headers, cookies or exception
text is retained. Only sanitized conclusions are included in Git.

## Frozen installation and compatibility

The previous Dockerfile could retry a failed frozen sync with an unlocked sync,
or install an unpinned aiogram after an import failure. Both dependency fallbacks
are removed. Failure to install uv or import aiogram now fails the build. Both
project dependency sync commands remain `--frozen --no-dev`; no runtime updater
is introduced. Cache housekeeping does not install or resolve dependencies.

An offline project wheel build and fresh frozen no-dev installation passed;
all 29 runtime distributions match the lock. The installed wheel imports bot,
handlers, SDK and OwnedUploadFile; EN/RU/ES catalogs load; Deno 2.9.7 is detected
and accepted. No bot/poller is started. No Docker build or image replacement is
performed. Floating base OS/bootstrap tooling still prevents a bit-reproducible
Docker image claim; future deployment must inspect the actual built image.

## Verification and release decision

- Existing focused metadata/provider/IPC/cache/budget/cancellation/upload suite:
  **304 passed in 160.17 s**.
- Added actual upstream legacy/dedicated-script parser and cross-version IPC
  refusal checks: **4 passed**. No snapshot guard is weakened.
- Full offline suite: **3006 passed, 1 skipped in 456.71 s**. The skip is the
  opt-in real YouTube download matrix. Instagram/TikTok, admission/no-resend,
  cleanup/quarantine and upload ownership regressions are included.
- Ruff lint/format, diff/privacy and **144 internal Markdown links/anchors** passed.
- Exact-head CI is checked after Draft PR publication and recorded there; see
  [testing](TESTING.md#yt-dlp-stable-upgrade--2026-10-30).

Technical dependency compatibility, the external metadata experiment, merge,
production build/deployment and owner LIVE acceptance are separate gates. A Draft
PR is not deployment authorization or proof of recovery for the reported video.
Before a separately authorized deployment: retain the actual current image under a
unique rollback tag, verify the new frozen image/source and unchanged settings,
replace only bot after confirmed old process/worker completion, and preserve API
state. Rollback requires confirmed stopped ownership; uncertain media/cleanup is
STOP, never retry/delivery permission. No new production image is built here.
