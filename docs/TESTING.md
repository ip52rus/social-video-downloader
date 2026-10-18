# Testing Strategy

## Phase 4 functional acceptance (2026-10-15)

Status: **ACCEPTED for the tested functional scope**, as confirmed by the user. This is
real Telegram client evidence, separate from deterministic tests and provider-only live
checks. It does not mean exhaustive format coverage or production readiness.

Revision: main `ced1200bf2a81a1bb63c200e6441e8458d0af0df`, containing PR #41 and PR #42.
The existing Compose stack was deployed by rebuilding/recreating only `bot`; all 24
source files matched current main. Polling was active through the Local Bot API, with no
startup errors. The Local Bot API container/image and named volume were preserved.
No additional deployment or live test was performed for this documentation update.

| Accepted functionality | Evidence | Scope/limits |
| --- | --- | --- |
| Individual watch URL with playlist context | Video/Audio choices appeared and the intended individual video was delivered | The original `list` case worked; this is not playlist support |
| Video / Audio choices | User confirmed both flows in the real client | Only useful available qualities are shown; no exhaustive capability matrix |
| Landscape Medium | 936x720, class 720, 243 seconds, 19,389,783 bytes; user confirmed image/sound | Existing sanitized upload and Telegram response logs corroborate dimensions, duration and size |
| Portrait Medium | 720x1280, class 720; user confirmed image/sound | User-reported client result; exact size not recorded here |
| Portrait High | 1080x1920, class 1080; user confirmed image/sound | User-reported client result; exact size not recorded here |
| M4A audio | User confirmed M4A, playback and correct nonzero displayed duration | Exact passthrough/remux/transcode route is not established by the extension |
| Callback protection | A rapid second press did not deliver duplicate media and produced an unavailable-choice response | Does not independently prove two callbacks reached the server or the exact invocation count |
| Distinct-URL isolation | Two different source interactions delivered their respective audio files | Consumed inline buttons disappeared, so another press was not possible in that check |
| Local Bot API above 50 MB | Prior real-client delivery succeeded with playback | Historical evidence, not repeated on this revision; not proof of arbitrary sizes or 2 GB support |

Observed reliability issue, kept separate from playlist/quality acceptance: at 21:34:34
Moscow time, yt-dlp reported `HTTP Error 403: Forbidden` while fetching video data,
followed by `DownloadFailedError`. The terminal callback had reached downloading rather
than being rejected by the 15-minute interaction TTL. No traceback, DNS/timeout indicator,
or terminal acknowledgement/keyboard-cleanup failure was present in that log window.
The retry interaction succeeded, with delivery at 21:36:45. Exact runtime tier/options and
cache hit/miss were not logged; the nested Python exception class and the upstream reason
for 403 remain NOT VERIFIED. A roughly 13-minute wait exceeds the 180-second inspection
cache lifetime, so the original snapshot cannot remain valid for that first attempt;
this does not establish cache expiry as the cause of 403.

Verification categories and outstanding limits:

- The implementation gate remains 469 passed, 1 skipped with Ruff lint/format, quiet
  Compose config validation and diff check passing. These historical deterministic/local
  results are not new test runs for this documentation update.
- Missing/partial dimensions, unsafe-only video, audio-only fallback, BLOCKED and absence
  of unrestricted-best are covered by deterministic tests; rare real-media cases were
  not deliberately triggered. A post-PR #42 portrait Low result is NOT VERIFIED here.
- Real-client evidence covers the recorded cases, not every codec, orientation/tier
  combination, Telegram client or source. Source-metadata honesty, live injected API
  failures, production throughput and robust restart/network recovery are not established.
- Phase 8 owns obsolete choice-prompt cleanup and remaining UX polish. Phase 9 remains
  OPEN for intermittent HTTP 403/bounded recovery, synchronous metadata blocking the
  async event loop, network resilience, restart/recovery and monitoring. Existing analytics
  tasks remain unchecked; functional acceptance does not imply analytics implementation.

## Deterministic tests

Fast deterministic tests cover URL normalization, provider detection, filename
sanitization, configuration parsing, logging configuration, bot/dispatcher construction,
handler behavior, media preparation, upload-parameter extraction, and error mapping.

Current deterministic coverage includes:

- `tests/test_config.py` for required token handling, defaults, normalization, invalid
  values, token redaction in the settings repr, and immutability.
- `tests/test_bot.py` for bot and dispatcher construction, including default cloud Bot
  API and optional local API endpoint configuration.
- `tests/test_handlers.py` for `/start`, invalid links, unsupported domains, non-YouTube
  platform messaging, mocked download/delivery, safe error responses, and temporary
  workspace cleanup.
- `tests/test_download_service.py` for provider selection, URL normalization, delegation,
  and recognized platforms without configured providers.
- `tests/test_telegram_media.py` for compatible MP4 passthrough, H.264/AAC stream-copy
  remux for compatible non-MP4 input, remux-failure fallback to transcode, AV1/Opus
  transcoding to H.264/AAC, post-conversion verification, rotation-aware upload
  dimensions, missing audio, and FFmpeg failure mapping.

Audit fallback checks in the Codex environment:

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q -p no:cacheprovider`: 189 passed, 1 skipped.
- `.venv/bin/ruff check . --no-cache`: passed.
- `.venv/bin/ruff format --check . --no-cache`: 50 files already formatted.

These fallback commands were used because `uv` was not available in the default PATH of
the Codex shell during the audit. This was an environment/tool discovery issue, not a
test failure.

Current preferred checks after locating `uv` at `/Users/user/.local/bin/uv`:

- `/Users/user/.local/bin/uv run pytest -q`: 190 passed, 1 skipped.
- `/Users/user/.local/bin/uv run ruff check .`: passed.
- `/Users/user/.local/bin/uv run ruff format --check .`: 50 files already formatted.

When `uv` is available in PATH, the standard project commands are:

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

## Focused Telegram callback resilience (2026-10-15)

Deterministic fault-injection coverage in `tests/test_handlers.py` verifies:

- Network/API failures during terminal acknowledgement and keyboard cleanup, separately
  and together, still start exactly one download with the exact stored URL/options.
- Repeated and concurrent terminal callbacks cannot start a second download; a failed
  atomic consume never starts one. Audio/video delivery is not retried.
- Mode-to-quality acknowledgement failure still attempts the keyboard edit; edit failure
  preserves unconsumed state and permits retrying the old mode button or using a quality
  keyboard whose edit reached Telegram before the response was lost.
- Metadata/domain-error notification failures do not rerun planning/download and log
  only original/Telegram exception categories. Cancellation and unrelated programming
  errors propagate through the new handlers.

Verification for this fix:

- Handler/store tests: 94 passed.
- `uv run pytest`: 303 passed, 1 skipped (opt-in external YouTube live matrix).
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: 57 files already formatted.
- `docker compose config --quiet`: passed; rendered configuration was not printed.
- `git diff --check`: passed.

These implementation-stage checks were unit/deterministic integration evidence without
a container rebuild. Subsequent functional client acceptance is recorded above. Forced
live Telegram network-failure recovery remains unverified; deterministic fault tests and
functional acceptance do not establish production reliability.

## M4A audio and duration (2026-10-15)

Network-free tests in `tests/test_telegram_audio.py`, `tests/test_youtube_provider.py`
and `tests/test_handlers.py` cover:

- Real yt-dlp selector evaluation against synthetic formats: native AAC/M4A preference,
  best ranked native choice, best-audio fallback and rejection of a codec-mislabelled
  native preference. Explicit audio IDs and existing video selectors remain covered.
- Native AAC/M4A passthrough, AAC stream-copy remux, incompatible-codec transcode,
  remux-failure fallback, actual container/codec verification rather than extension-only
  detection, invalid/corrupt input, FFmpeg failure and partial-output cleanup.
- Positive metadata duration; missing, zero, negative, boolean, NaN/infinite and
  out-of-range duration; container/stream and source/output probe fallback; omission
  when unknown; correct prepared path/duration sent through `answer_audio`.
- Safe preparation failure and request-workspace cleanup. Existing video delivery and
  PR #39 callback fault/concurrency tests remain passing.

`tests/integration/test_audio_preparation.py` adds four real local checks, using 0.35 s
synthetic tones or deliberately corrupt bytes exclusively in pytest temporary storage:

1. Native AAC/M4A: original file/hash preserved; exactly one ffprobe, zero preparation
   FFmpeg calls.
2. AAC/Matroska: one stream-copy FFmpeg call; output verified AAC/M4A; all encoded AAC
   packet SHA-256 hashes match the input. This does not claim decoded/timestamp identity.
3. Opus/WebM: one AAC encoding FFmpeg call; output verified AAC/M4A. Bitrate is capped
   without implying improved quality over the source.
4. Corrupt M4A: safe rejection, no output file.

Performance gate: native audio is neither remuxed nor transcoded. Successful conversions
use one input probe and one output verification, with duration in those same probes only
when needed. Failed remux recovery may require another FFmpeg call/output verification.
There is no large passthrough copy or standalone duration probe. Encoding caps are
128 kbps/stereo-or-other, 64 kbps/mono, limited by known source bitrate; unknown bitrate
uses the cap. Real encoding adds CPU/latency and may lose quality. Throughput, concurrency
and production latency were not benchmarked.

Verification:

- `uv run pytest`: 357 passed, 1 skipped. All four synthetic FFmpeg tests ran locally;
  they skip explicitly when FFmpeg/ffprobe are absent. The external YouTube test skipped.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: 60 files already formatted.
- `docker compose config --quiet`: passed, without rendering configuration.
- `git diff --check`: passed.

That implementation stage performed no live YouTube download, Telegram API call,
running-stack rebuild/restart or long transcoding benchmark. Subsequent M4A playback and
displayed-duration acceptance is recorded above; route-specific live verification and
production performance are not implied.

## YouTube watch URLs with playlist context (2026-10-15)

Network-free regressions in `tests/test_youtube_provider.py` cover:

- Ordinary single-video targets remain unchanged. Watch URLs with a valid single `v`
  and playlist `list` use the individual-video extraction target; unrelated query
  parameters retain their values and original escaping.
- Encoded parameter names/IDs, empty/repeated playlist context, invalid/missing/duplicate
  video IDs, playlist-only URLs, credentials, schemes, and deceptive hostnames.
- A fake extractor reproduces yt-dlp's unprocessed `_type=url` response and the former
  false `BLOCKED / no_useful_modes`. Canonicalized URLs instead produce identical
  `CHOOSE_MODE` plans with audio/video and unchanged Low/Medium/High choices.
- Both inspection orders share one cache entry. Downloads use the canonical target
  with or without a prior inspection and reuse the inspected snapshot.
- Metadata calls retain `download=False`, `process=False`, and `noplaylist=True`, never
  invoke fake media processing, and do not enumerate playlists. Installed yt-dlp's local
  extractor matching confirms the canonical targets select the video extractor.

Verification:

- `uv run pytest`: 417 passed, 1 skipped; 60 new parametrized regression cases. The
  opt-in external YouTube matrix was explicitly disabled; synthetic FFmpeg tests ran.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: 60 files already formatted.
- `docker compose config --quiet`: passed; rendered configuration was not printed.
- `git diff --check`: passed.

The checks used offline uv execution with a temporary cache directory because the
sandbox could not access the default uv cache. No dependency/configuration changes or
live YouTube/Telegram requests were made in that implementation stage. Compose was not
rebuilt then. Subsequent deployment and playlist-context functional acceptance are
recorded above; broad reliability remains open.

## YouTube quality-selection safety (2026-10-15)

Before implementation, two new regressions failed on the existing code: installed
yt-dlp selected landscape 1080-class for a portrait 720-class quality, and an empty
YouTube quality list produced `DIRECT_DOWNLOAD` with no quality ID. Both are now covered
as passing regressions.

Network-free provider/choice tests evaluate the installed yt-dlp selectors against
representative synthetic format dictionaries, not only selector strings. They cover:

- Portrait, landscape, square and mixed orientation; formats sharing a height with
  different short-side classes; deterministic dimension IDs and tier collapse.
- Exact dimensions through native H.264/MP4/AAC, progressive combined audio/video, and
  incompatible-codec/container fallbacks. Every video branch retains both dimensions;
  video-only sizes without a pairable audio stream are not offered for video-with-audio.
- Width-only, height-only, no dimensions, empty qualities, and only above-1080 video:
  safe audio-only remains available or the application blocks the request. The generic
  classifier retains `SINGLE_DIMENSION`; non-YouTube automatic policy remains unchanged.
- Missing video quality ID, disappeared dimensions or dimensions changed after cache
  expiry, and missing selector matches fail without unrestricted fallback.
- Existing playlist-context extraction/cache/download identity tests use concrete safe
  video IDs. The opt-in live matrix now also uses concrete video IDs; it is not run here.
- A single safe YouTube quality produces a direct plan with the exact provider ID and
  downloads through the same inspected snapshot without a second metadata extraction.

The enforcement is based on extracted dimensions. These tests cannot establish source
metadata honesty, actual encoded pixel dimensions, or future YouTube availability. The
short-side metric is not a limit on the longer side, encoded bytes, CPU, or latency.
Provider facts may still describe above-ceiling video; the YouTube application policy
excludes it from normal product choices. No media/network retry policy changes are made.

Verification:

- `uv run pytest`: 469 passed, 1 skipped. The external YouTube matrix was explicitly
  disabled; existing synthetic FFmpeg integration, M4A, video and callback fault tests ran.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: 60 files already formatted.
- `docker compose config --quiet`: passed; rendered configuration was not printed.
- `git diff --check`: passed.

uv ran offline with a temporary cache because the default cache is sandbox-restricted.
No dependency/configuration changes, live YouTube requests/downloads, Telegram calls,
or Compose rebuilds/restarts were performed in that implementation stage. Subsequent
functional client evidence is recorded above; rare live audio-fallback/BLOCKED cases and
broader network/recovery behavior remain unverified.

## PR #27 media-preparation validation

Deterministic automated coverage:

- Mock/runner tests confirm compatible non-MP4 H.264/AAC input uses FFmpeg stream-copy
  remux with `-c copy`.
- Deterministic coverage verifies remux command failure falls back to the transcode path.
- Focused media tests: `tests/test_telegram_media.py` passed with 12 tests.
- Full branch suite: 190 passed, 1 skipped.

Real local FFmpeg validation used `/usr/local/bin/ffmpeg` and
`/usr/local/bin/ffprobe`, version 9.0.2. All media was synthetic and created outside the
repository. These checks did not perform a YouTube network request, Telegram upload,
VPS/server benchmark, large-file validation, or 2 GB validation.

Case A - compatible MP4 passthrough:

- Input: MP4, H.264/AAC, 640x360, 8.0 seconds.
- `prepare_telegram_video()` returned the original file.
- Only ffprobe was invoked; there was no preparation FFmpeg invocation.
- The source file remained unchanged.
- Result: pass.

Case B - compatible MKV stream-copy remux:

- Input: Matroska, H.264/AAC, 640x360, 8.021 seconds.
- Output: MP4, H.264/AAC, 640x360, 8.0 seconds.
- The preparation command used stream mapping for the first video/audio streams,
  metadata mapping, `-c copy`, and `-movflags +faststart`.
- Exactly one preparation FFmpeg invocation ran; `libx264` was not invoked.
- Dimensions were preserved and the duration delta was approximately 0.021 seconds.
- Encoded H.264 packet payload hashes matched 240/240.
- Encoded AAC packet payload hashes matched 376/376.
- Decoded video framemd5 hashes matched 240/240.
- Exact decoded AAC checksum did not match because MKV and MP4 produced different AAC
  priming, timestamp, or frame-boundary interpretation.
- Result: pass for the intended stream-copy behavior, with the decoded AAC caveat above.

Case C - incompatible source fallback transcode:

- Input: Matroska, MPEG-4 video, AAC audio, 320x180, 5.021 seconds.
- Output: MP4, H.264/AAC, 320x180, 5.013 seconds.
- The original incompatible source was not returned.
- The real preparation command used `libx264`.
- The existing transcode path still worked.
- Result: pass.

The real validation does not prove whole-file byte identity, decoded audio bit identity,
lossless decoded audio equivalence, large-file behavior, or production performance. Real
FFmpeg remux-failure injection was not repeated; that fallback is covered by the
deterministic remux-failure test.

## YouTube external/live tests

External YouTube tests are opt-in and must not run without an explicit URL.

Set `YOUTUBE_LIVE_TEST_URL` only when intentionally running real YouTube downloads:

```bash
YOUTUBE_LIVE_TEST_URL="https://www.youtube.com/watch?v=..." uv run pytest tests/integration/test_youtube_live_matrix.py
```

Current YouTube verification snapshot:

- GitHub Actions run [37966225469](https://github.com/ip52rus/social-video-downloader/actions/runs/37966225469) passed 131 tests on merge commit f27051fded257b5f39056c45333b4fa8c50075a3; Ruff lint and format checks passed.
- Real regular-video downloads were verified in `VIDEO_WITH_AUDIO`, `VIDEO_ONLY`, and
  `AUDIO_ONLY` modes.
- Live matrix run on 2026-10-09 for `https://www.youtube.com/watch?v=dQw4w9WgXcQ` passed
  in 140.06 seconds. It verified combined video/audio MP4, selected-quality video-only
  output, and audio-only outputs in two distinct containers using ffprobe.
- Shorts were verified in all three modes; additional successful Shorts smoke tests were
  recorded for `VF_MOfnz7OY` and `osrN3A_Rdiw`.
- A duplicate audio format ID issue was reproduced and fixed; selector `251-0/251`
  successfully downloaded Opus audio.

This is targeted evidence, not proof of broad YouTube reliability across all content and
platform conditions.

## Telegram cloud/live tests

The default bot configuration uses Telegram's cloud Bot API when `TELEGRAM_API_BASE_URL`
is unset. Deterministic tests do not exercise a real Telegram cloud upload or polling
session.

Cloud live checks should cover:

- bot polling;
- a small public YouTube URL;
- user-facing error behavior;
- playback on relevant Telegram clients;
- behavior when cloud upload limits are reached.

## Telegram Local Bot API live tests

The Local Bot API path has limited live evidence:

- Local Telegram Bot API Server was started.
- The bot ran and polled through the Local Bot API endpoint.
- A short vertical YouTube video completed the live download -> Telegram delivery flow.
- An approximately 414.7 MB MP4 was delivered to Telegram and was playable.
- The large tested file was H.264/AAC, 1920x1080, and approximately 1649 seconds long.

This verifies only the observed scenario. It does not prove project support for arbitrary
files up to Telegram's official Local Bot API Server upload ceiling of 2000 MB.
Different Telegram clients may render previews differently, so preview behavior is not a
fully controlled application guarantee.

## Docker/runtime tests

Docker/Compose checks should include:

```bash
docker compose config --quiet
docker compose build bot
```

Docker was found at `/Applications/Docker.app/Contents/Resources/bin/docker` during the
tool-location check. Current safe validation:

- `/Applications/Docker.app/Contents/Resources/bin/docker compose config --quiet`: passed.

A Compose configuration check does not prove polling, download, extraction, upload, or
large-file behavior.

Containerized YouTube runtime validation:

Previous diagnostic state:

- The bot image had yt-dlp 2026.8.19 and yt-dlp-ejs 0.8.0, but no Deno, Node, Bun, or
  QuickJS executable.
- Raw yt-dlp verbose output reported `JS runtimes: none`.
- A controlled metadata simulation for
  `https://www.youtube.com/watch?v=dQw4w9WgXcQ` still succeeded.
- yt-dlp warned that YouTube extraction without a supported JavaScript runtime is
  deprecated and may have reduced format availability.
- The diagnostic result was classified as a confirmed degraded gap.

After adding Deno:

- The bot image installs pinned Deno 2.9.7 at `/usr/local/bin/deno`.
- Runtime checks found Deno 2.9.7 in the final image; Node, Bun, and QuickJS remained
  absent.
- Raw yt-dlp verbose simulation reported `JS runtimes: deno-2.9.7`.
- yt-dlp reported `[jsc:deno]` challenge solving using Deno.
- The previous missing-JavaScript-runtime warning was absent.
- Controlled `yt-dlp --verbose --simulate` for
  `https://www.youtube.com/watch?v=dQw4w9WgXcQ` succeeded without a full media download
  and selected format `401+251`.
- `YouTubeProvider.extract_metadata()` succeeded inside the container through the
  existing metadata-only `extract_info(..., download=False, process=False)` path while
  using the configured `js_runtimes={"deno": {}}`.
- A disposable Compose `bot` service container exposed the same Deno-enabled runtime.

This validation used one controlled public YouTube URL and metadata/simulation only. It
did not download complete YouTube media, upload to Telegram, prove broad YouTube
reliability, prove resilience to future YouTube platform changes, or benchmark VPS
throughput.

## Production Reliability tests

The Phase 3 functional Telegram MVP is complete, but production reliability is a later
phase and cannot be inferred from the happy path. Remaining operational checks include:

- restart behavior for the bot and Local Bot API Server;
- temporary Local Bot API/network failure recovery;
- upload failures and user-facing error behavior;
- cloud-to-local migration rehearsal with a separate test bot;
- local-to-cloud rollback rehearsal with a separate test bot;
- documented limits and resource observations for larger files when justified;
- monitoring, resource, and deployment limits when the deployment model is defined.

Telegram documents cloud-to-local migration with `logOut`, and documents `close` for
moving between Local Bot API Servers. Do not treat `close` as an officially documented
local-to-cloud rollback procedure.

## Experimental Instagram Reel provider (2026-10-16)

The first Phase 5 PR adds an injectable `InstagramProvider`; the bot's default registry
and Telegram handlers remain unchanged. See [the agreed scope](PHASE5_INSTAGRAM_REELS.md).

Network-free tests in `tests/test_instagram_provider.py` cover canonical Reel URL
identity, explicit host/path validation, rejection of collections/redirects/images and
private/auth-gated/DRM results, usable-format classification, optional metadata,
unsupported options, cache reuse/expiry/bounds, one-file acquisition and workspace cleanup.
A lazy playlist raises if enumerated; it is rejected without touching its entries.
An expired Reel snapshot that becomes a playlist cannot start acquisition. Synthetic
HTTP 403/429 and login-required exceptions produce safe errors without an application
retry or authentication fallback. Missing/empty/extra/partial/symlink outputs fail safely.
Upstream logger messages are suppressed; fixtures use synthetic IDs and `.invalid` URLs.

A real local yt-dlp processor/selector test receives synthetic extractor dictionaries:
it chooses one admitted direct MP4, preferring non-silent/unknown over higher-resolution
explicit silence in the same compatibility group, and excludes audio-only
and image alternatives. Extraction and file acquisition are replaced with local stubs;
this does not test Instagram network extraction or the CDN.

`tests/integration/test_instagram_pipeline.py` uses one-second 64x96 MP4 fixtures and an
invalid-file case in pytest temporary storage. All pass through injected `DownloadService` and real local
yt-dlp processing, with acquisition replaced by a fixture copy. Actual ffprobe and the
existing Telegram preparation helper verify:

- H.264/AAC MP4 passes unchanged: identical bytes, one preparation ffprobe and zero
  preparation FFmpeg calls. Upload width/height/duration come from actual file probing
  despite absent extractor duration, dimensions and codecs.
- A real video-only fixture is rejected by default; explicit `allow_silent=True` now
  passes it through unchanged with correct upload metadata. Corrupt bytes are rejected.
  The caller workspace is removed in every case by the existing request workspace boundary.

Initial implementation verification in an existing Python 3.13 / yt-dlp 2026.08.19 environment, using the feature
checkout's `src` via `PYTHONPATH=src` and explicitly disabling the external YouTube test:

- Provider and synthetic pipeline checks: 85 passed.
- Full pytest suite: 554 passed, 1 skipped (opt-in external YouTube live matrix).
- Ruff lint and formatting checks: passed.
- `git diff --check`: passed.

No real Instagram metadata/media request, live YouTube request, Telegram call, container
command, dependency installation/update or running-stack change was performed. Synthetic
local FFmpeg checks do not establish real Reel availability, Telegram delivery, account
restrictions, rate-limit recovery, throughput, production reliability or broad format
coverage. Retries of zero and a per-socket timeout are not a whole-operation deadline
and do not restrict an extractor to one internal HTTP request.

### PR #44 direct-format selection review follow-up

P1/P2 regressions run the actual installed yt-dlp 2026.08.19 format processor/selector
against synthetic metadata. Only extractor output and acquisition are stubbed; a network
attempt raises immediately. The new checks cover:

- Implicit `.m3u8`, uppercase/signed HLS, DASH `.mpd`, `.f4m`, explicit HLS/DASH protocols,
  fragment lists (including empty lists), manifest locators and DASH representation markers.
  Unsupported candidates never reach `process_info`, with or without a valid direct MP4
  alternative. Signed direct MP4 URLs without a path extension remain accepted.
- H.264/AAC ahead of equal-resolution VP9/AAC and higher-resolution unknown-audio formats;
  incomplete codecs ahead of already-known incompatible codecs; both fallback classes;
  native yt-dlp quality ordering within each class. Reversing extractor format order does
  not change the expected choice. Only one selected format reaches acquisition.
- The then-current explicit no-audio rejection (superseded by the silent-video policy
  below), collection/redirect rejection, optional metadata,
  cache/expiry, workspace cleanup and synthetic transport preparation remain covered.

The initial regressions reproduced both findings before the provider correction. Follow-up
verification uses the existing Python environment, `PYTHONPATH=src`, bytecode/cache writes
disabled and the external YouTube test explicitly disabled:

- Focused Instagram provider/synthetic pipeline: 127 passed.
- Full suite: 596 passed, 1 skipped (opt-in external YouTube matrix).
- Ruff lint/format and `git diff --check`: passed.

No new Instagram/YouTube network requests, media acquisition, Telegram delivery, dependency
changes or Docker commands were performed for this correction. Metadata-based format
selection does not prove actual stream presence or compatibility; real acquisition through
this provider and Telegram activation/acceptance remain separate outstanding gates.

### Incomplete direct-MP4 metadata follow-up

The subsequent real provider smoke, reported in the handoff, made one anonymous metadata
extraction and zero media-acquisition attempts. It returned one video result with 13
formats, none admitted; three had unknown video codecs and incomplete dimensions. The
other ten formats' exact rejection reasons were not established. No Instagram access
error was reported. This evidence is a failed inspection, not a successful provider
download or proof that all rejected formats were otherwise admissible.

Offline inspection of installed yt-dlp 2026.08.19 confirms `_extract_product_media` can
map `video_versions` to direct locators without width, height, codecs or an explicit
extension. `has_audio=False` maps to explicit `acodec="none"`; DASH variants are added
separately from `video_dash_manifest`. A synthetic direct `.mp4` product passed through
that actual local mapping reproduces `MetadataExtractionError` on main; the correction
admits it as unknown compatibility, not confirmed H.264/AAC or proven stream presence.

New offline cases use that real extractor mapping plus yt-dlp processing with stubbed
acquisition and a network-forbidden opener. They cover absent/complete/partial dimensions,
mixed direct/DASH output, explicit video/audio absence, HLS/DASH and non-MP4 locators,
signed direct MP4 with a declared extension, one acquisition and unchanged unknown fields.
Existing preference/manifest regressions remain green. Synthetic actual-file checks
also reject silently audio-free and corrupt files through existing preparation helpers.

Verification (external YouTube test disabled; no Instagram requests):

- Focused provider/synthetic pipeline: 143 passed (16 additional cases).
- Full suite: 612 passed, 1 skipped (opt-in external YouTube matrix).
- Ruff lint/format and `git diff --check`: passed.

No live extraction/download, Docker operation, dependency change or Telegram call was
performed for this fix. The real formats' complete fields are unavailable in this evidence, so matching
the local defect to the prior live rejection remains a hypothesis requiring a newly
authorized bounded provider smoke. Instagram remains disabled in the default bot.

### Real corrected-provider Reel smoke (2026-10-16)

After PR #45, one separately authorized anonymous smoke tested main
`4885ee651790d70222acb3c490d2ed367ed4637c` through `InstagramProvider` and
`DownloadService`, not standalone yt-dlp. Current source was mounted read-only in an
isolated short-lived container using the existing bot image/runtime; Python 3.13.16,
yt-dlp 2026.08.19 and FFmpeg/ffprobe 7.1.5. The existing Compose services were unchanged.

| Observation | Verified result |
|---|---|
| Scope | One public Reel, one extraction and one acquisition; no retry |
| Formats | 13 returned, 3 admitted, 10 rejected as manifest/fragment candidates |
| Choice plan | `DIRECT_DOWNLOAD`, `VIDEO_WITH_AUDIO`, no audio/quality menus |
| Actual file | MP4 H.264/AAC, 720x1280, 11.282041 seconds, 1,317,210 bytes (1.256189 MiB) |
| Integrity/preparation | ffprobe PASS, full FFmpeg decode PASS, existing preparation passthrough |
| Upload parameters | width 720, height 1280, integer duration 11; no upload performed |
| Timings | extraction 1.991 s, plan 2.248 s, download 1.278 s, total 5.251 s |
| Safety | 25 MiB streaming byte guard and 180 s deadline; temporary media/container/scripts removed |
| Warning | `CSRF_TOKEN_UNAVAILABLE`, nonfatal; no error recorded |

Selected codec/dimension metadata was incomplete; actual H.264/AAC and geometry came
from file probing. The later format-rejection counts describe this run only, not the
unretained format fields of the earlier failed attempt. This PASS proves one real Reel
through the implemented provider, not general Instagram reliability, subjective playback
or Telegram delivery. It predates the single-video `/p/` extension below.

### Single-video post extension — offline validation only

The same provider now accepts canonical `/p/<id>/` URLs, subject to single-video result
validation before acquisition. Tests use installed yt-dlp 2026.08.19 `extract_info` with
`download=False, process=False`, the real Instagram `_real_extract`/`_extract_product`
classification, synthetic JSON responses and a network-forbidden opener. Only the JSON
fixture branch is selected; no HTTP impersonation handler or real network access is used.

Fixtures establish a top-level video for a single-video product, playlists for multi-video,
mixed-media, photo-only and one-entry carousels, and a no-video error for a single photo
or empty product. Rejected results never reach yt-dlp result processing/acquisition.
Additional raw-result tests cover empty playlists, `entries` regardless of type,
redirects, unknown types, private/auth-gated metadata and DRM. No first entry is selected.

Shared cases now run for both Reel and post URLs: canonical tracking removal, snapshot
reuse/expiry/bounds, unsupported options, safe filenames, failure cleanup, manifest
rejection and actual yt-dlp compatibility-priority selection. Separate path identities
cannot collide in the cache. Synthetic FFmpeg integration covers valid H.264/AAC,
silently audio-free and corrupt actual files for both paths; existing preparation is reused.
The default provider registry and Telegram handlers are unchanged.

Current offline verification with the external YouTube matrix explicitly disabled:

- Focused Instagram provider/synthetic preparation: 259 passed.
- Full pytest suite: 728 passed, 1 skipped (opt-in external YouTube matrix).
- 116 additional parameterized/regression cases compared with main.
- Ruff lint and format checks: PASS.
- `git diff --check`, documentation consistency and security/scope review: PASS.

No live Instagram/YouTube requests, dependency changes, Docker operations or Telegram
calls are part of this extension. Real `/p/` support remains UNVERIFIED pending a separately
authorized smoke. At that stage carousel groups/order/splitting were product scope only;
later video-only acquisition and offline delivery evidence is recorded below. Photos
remain outside acquisition/delivery scope.

### Carousel inspection/selection — deterministic validation

`tests/test_instagram_carousel.py` exercises actual installed Instagram `_real_extract`
and product mapping with synthetic JSON responses and a network-forbidden opener.
The production per-instance extractor adapter is installed as in the real inspection path.
Result processing/media acquisition raise immediately in the fixture runtime.

Coverage: all-video counts 1/2/5/10/11/21 without truncation; conservative mixed/photo-only
fixtures; empty/UNKNOWN/conflicting entries; missing/unsupported video locators; malformed,
duplicate/missing/mismatched IDs; upstream reordering/schema loss; unavailable/DRM source
fields; immutable ordered plans; tracking/cache identity, TTL and bounds; `img_index`,
malformed/ambiguous references rejected before extraction/cache; instance isolation.
Existing provider/YouTube/media preparation/callback regressions run in the full suite.
No external platform calls, images/videos, dependency changes, Docker operations or
Telegram requests are part of this implementation's tests.

The preceding separately authorized live metadata gate inspected one five-video carousel
via two URL variants, once with `img_index=3`: 2 extractions, 3 HTTP requests each, no retry,
zero result processing or acquisition. All five positions had `video_versions`, unique
stable IDs/order and 3 direct MP4 candidates each; total mapped formats were 9/10/7/7/7.
Both variants returned the full playlist with identical request targets and ordered IDs;
response bodies were not byte-identical. `img_index` reached the extractor but was not
honored upstream. No actual frontend index semantics, photo/mixed classification or
media downloadability was established. CSRF-token warning was nonfatal. The adapter
introduced here has deterministic validation only; this prior experiment is not its live test.


Verification for this carousel-inspection stage (live YouTube matrix explicitly disabled):

- New carousel inspection/selection cases: 103 passed.
- Full regression suite: 831 passed, 1 skipped (opt-in external YouTube matrix).
- Ruff lint/format, diff, local documentation links and security/scope review: PASS.
- No new live extraction or media acquisition was performed for this implementation.


### Corroborated carousel PHOTO classification — offline follow-up

Separate live metadata evidence after PR #47 concerns one 20-entry publication, not a
broad platform matrix. The first one-shot check returned 17 VIDEO and UNKNOWN at 8/9/18,
with intact original ID/order mapping and BLOCKED / unknown_item. A separately authorized
one-shot source diagnostic found strict integer `media_type=1` plus coherent image
versions/nonempty candidates at those positions, with no `is_video` or video
versions/codec/duration/manifest fields. Representative VIDEO entries had type 2 and
nonempty video versions/manifest; both groups had image versions. Both checks performed
zero media acquisition. This evidence supports the combined PHOTO rule for that shape.

The correction is tested without network via the installed extractor and the existing
network/processing/acquisition-forbidden Runtime. Tests include the observed PHOTO shape,
a 20-entry fixture selecting exactly 17 VIDEO at 1–7, 10–17, 19–20, numeric evidence,
invalid image structures/locators, malformed numeric/string markers, video contradictions,
and unchanged explicit-photo behavior. The former UNKNOWN case for valid numeric-plus-
image evidence is retained as a PHOTO acceptance case; image-only UNKNOWN remains tested.
Existing unsupported VIDEO, identity, unavailable/private/DRM, cache, reference and
single-video/YouTube/Telegram regressions remain part of the suite.

At completion of that offline fix, live mixed-selection remained OPEN. The subsequent
metadata-only gate below closes it for one publication; no live carousel acquisition or
Telegram delivery is claimed.


Verification of this focused classification fix (no live platform calls):

- 39 additional deterministic cases; carousel suite: 142 passed.
- Carousel plus existing Instagram provider/preparation tests: 401 passed.
- Full regression suite: 870 passed, 1 skipped (opt-in external YouTube matrix disabled).
- Ruff lint/format, diff, documentation links and security/scope review: PASS.
- Application AST comparison: only `_classify` changed; extraction, identity/order,
  cache, URL handling, domain contracts, registry and Telegram handlers are unchanged.


### Final mixed-carousel classification — real metadata-only PASS

2026-10-16, production source `1e08478646057326284ff410ea23f2ca312b4f2f`, read-only mount
hash-verified (27 Python files); Python 3.13.16, yt-dlp 2026.08.19, curl_cffi absent.
One top-level anonymous extraction, three observed HTTP requests, no retries/acquisition.
Observed: playlist with 20 items; 17 VIDEO; PHOTO at 8/9/18 with media_type_photo plus
image_versions evidence; zero UNKNOWN. Source/mapped/plan ID uniqueness and order PASS.
READY, issue=None, selected 1–7, 10–17, 19–20; three direct MP4 candidates per VIDEO.
All A–L acceptance checks passed. Extraction 3.460 s, plan 3.716 s, process 4.851 s;
CSRF_TOKEN_UNAVAILABLE warning only. No media bytes/files or Telegram calls, temporary
runtime removed, Git/Compose unchanged. This closes classification for one publication,
not real multi-video downloading or broad reliability.

### Ordered carousel acquisition — network-forbidden deterministic validation

`tests/test_instagram_acquisition.py` exercises production plan revalidation, the installed
yt-dlp selector and HTTP downloader, synthetic in-memory HTTP responses and actual local
ffprobe on generated MP4 files. No external Instagram/Telegram calls occur. Child-process
tests inject only a fixture provider and run the production execution boundary, including
POSIX per-file limits, timeout/cancellation cleanup and safe output publication.

Coverage includes 1/2/5/10/11/20/21 selected videos; mixed 20-item ordering with 17 videos;
PHOTO-only, UNKNOWN/unsupported/unavailable/DRM and forged/reference plans; refreshed and
expired facts; changed IDs/order/count/types; HLS/DASH/manifests/fragments; codec priority
and signed direct MP4 fallback; absent audio/video, corrupt files; empty/missing/extra/
symlink/directory outputs; failures at first/middle/last child; per-file/cumulative/temp
byte budgets with absent or misleading Content-Length; hard deadline and repeated
cancellation; publication rollback/collision protection; unrelated-file preservation.
The real HTTP reader is bounded before writes, not just a progress-hook simulation.

Successful files are caller-owned until deleted. Filesystem hard-link support and POSIX
process groups are required. Tests do not prove full decoding of arbitrary media,
concurrent production capacity, crash recovery, real multi-video acquisition or Telegram
preparation/group delivery. No acquisition-stage conversion is implemented.

Verification of this acquisition stage (no live external calls):

- New acquisition tests: 74 passed, including real child entry point/OS file limits.
- Full suite: 944 passed, 1 skipped (external YouTube live matrix not enabled).
- Existing Instagram/Reel/single-post, YouTube, M4A, Telegram callback and video delivery
  regressions passed; existing synthetic FFmpeg integration checks ran in the full suite.
- Ruff lint/format, git diff check, local documentation links and security/scope review: PASS.
- No source/dependency/config/deployment changes outside the documented acquisition scope.
- At this implementation stage, live multi-video acquisition and Telegram groups were
  NOT VERIFIED; the later bounded three-video acquisition is recorded below.


### Silent Instagram video policy — deterministic validation

The user approved MP4 video with optional audio for Reels, single-video `/p/` and carousel
VIDEO entries. The preceding real metadata diagnostic found three VIDEO entries with
boolean has_audio=False, correctly mapped to acodec="none": 3 direct MP4 candidates per
entry rejected solely for audio absence; 23 additional manifest-derived formats also
rejected for fragment markers, mapped totals 11/11/10. One extraction, three metadata
HTTP requests, zero acquisition; actual files/streams were not inspected. These are
pre-change metadata facts, not live validation of the new admission policy.

Network-forbidden tests now admit explicit silence, preserve unknown audio metadata,
exercise installed extractor mapping and actual yt-dlp selection for Reels/posts, and
retain rejection of explicit video absence, hostile locators, DRM, HLS/DASH and fragments.
Ranking tests cover H.264/AAC priority, non-silent/unknown preference within compatibility
groups, stable native quality order for silent-only candidates and intentional compatible
silent H.264 preference over less compatible VP9/AAC in another group.

The carousel fixtures cover READY for three silent VIDEO with three direct candidates
each, with/without rejected DASH variants, plus mixed PHOTO/VIDEO ordering. Actual local
H.264 silent MP4 passes ffprobe acquisition validation and retains identical bytes with
no audio stream added. Video+audio still passes; audio-only/corrupt/wrong-container media
and invalid video/dimensions/present-audio codecs fail. Existing limits, deadline, repeated
cancellation, output checks, rollback and unrelated-file preservation remain tested.

Single-video integration explicitly supplies acodec="none", acquires the synthetic file
unchanged and confirms actual H.264 video without audio. Default Telegram preparation
rejects it for missing audio; the later optional-audio tests explicitly opt in and
verify byte-preserving passthrough. Neither path proves Telegram delivery.
The subsequent real acquisition and local preparation evidence are recorded below.
No external extraction/download or Telegram API request is part of these tests.


Verification of silent-video support:

- Focused provider/carousel/acquisition/synthetic integration suite: 563 passed.
- Full suite: 1032 passed, 1 skipped (opt-in external YouTube matrix not enabled).
- Net test-case increase: 88; obsolete silent-rejection cases were replaced by positive
  coverage and explicit negative cases for audio-only/manifest content.
- Existing YouTube, M4A, video delivery, callback fault handling, limits and cancellation
  regressions: PASS. Ruff lint/format, diff, documentation links and security/scope: PASS.
- At this stage real silent acquisition/preparation and albums were NOT VERIFIED;
  subsequent evidence below closes only the explicitly tested acquisition/preparation scope.


### First real silent carousel acquisition — narrowly verified

After PR #50, one authorized three-video experiment on production main
`055fced0bdf337a5b04132600cc803321db59c80` passed through the real planning and async
acquisition services. Two metadata extractions (planning and fresh revalidation), six
observed metadata HTTP opens, three media requests, zero retries or Telegram calls.
READY / issue=None; VIDEO 1/2/3, no PHOTO/UNKNOWN, three direct MP4 candidates each;
identity/order passed before and after acquisition.

| Original position | Bytes | Actual streams | Dimensions | Duration | ffprobe |
|---|---:|---|---|---:|---|
| 1 | 613050 | H.264, no audio | 720x960 | 5.041667 s | PASS |
| 2 | 738479 | H.264, no audio | 720x960 | 5.041667 s | PASS |
| 3 | 609669 | H.264, no audio | 720x960 | 5.041667 s | PASS |

All containers were MP4. Total 1,961,198 bytes; planning 2.22 s, acquisition 6.90 s,
validation complete at 9.53 s (12.42 s including disposable runtime lifecycle).
Limits 3 videos, 30 MiB/file, 75 MiB received, 90 MiB temporary, 180 s held. HTTP body/file
hashes matched, proving no transformation of those bytes. Nonfatal csrf_token_unavailable
warnings only. Successful files, scripts and runtime were removed; original Compose IDs,
start times and mounts were unchanged. No real Telegram preparation or playback occurred.
Only this small acquisition gate is closed; larger collections/general reliability remain open.

### Optional-audio video preparation — local generated media

`tests/test_telegram_media.py` exercises the explicit opt-in, audio-required default,
actual-container checks, malformed codecs/dimensions/stream metadata, both remux-fallback
audio states, rejected audio-only media, absent versus invalid audio, accidental output
audio changes, partial-file cleanup/interruption, and preservation of existing outputs.

`tests/integration/test_video_preparation.py` uses real local FFmpeg/ffprobe on generated
H.264/AAC and silent H.264 MP4/MKV, incompatible silent MPEG-4 and audio-bearing sources.
Passthrough keeps the exact source path/bytes and invokes no FFmpeg; remux preserves
encoded packet hashes; conversion uses existing H.264/AAC settings and never adds audio.
Prepared route fixtures pass full local decoding. Rotated fixtures verify displayed
orientation through passthrough, remux and transcode. Video-only upload dimensions and
duration need no audio. Synthetic Reel and single-video `/p/` integration retains default
silent rejection and separately verifies explicit opt-in passthrough.

These are offline helper/provider tests, not Telegram sends. Instagram remains disabled;
Real Telegram albums, actual client playback, larger-carousel reliability and broader
platform availability remain NOT VERIFIED; later offline transport tests are recorded below. No live Instagram or Telegram calls in this stage.


Optional-audio stage verification (offline, existing local dependencies):

- Focused helper/local-media/synthetic Instagram integration tests: 98 passed.
- Full suite: 1112 passed, 1 skipped (external YouTube matrix disabled); net +80 cases.
- Sixteen real local media integration cases used FFmpeg/ffprobe 9.0.2; synthetic files
  only. Six route cases also passed full local decode; no subjective/client playback claim.
- Ruff lint/format, diff, documentation links/anchors and security/scope review: PASS.
- YouTube, M4A/audio, callback/delivery, Instagram and acquisition regressions passed.
- Only the preparation module changed in application code; handlers, registry, providers,
  acquisition, dependencies and Compose are unchanged. No live platform requests.

### PR #51 P2 — collision-safe derivative ownership

The previous destination existence check did not establish ownership: FFmpeg `-y`
and failure cleanup could overwrite/delete a file created later by another operation.
Regression tests reproduced this before the fix. Each conversion now stages privately
on the destination filesystem and validates that file before atomic exclusive hard-link
publication. FFmpeg never receives the shared destination path. Publication failure
does not trigger another conversion, and cleanup only removes private staging paths.
Hard links are required; unsupported filesystems fail safely without a copy/overwrite
fallback. A successful link transfers the final name to the request/caller workspace;
there is no filesystem-wide transaction or crash-recovery claim.

Deterministic tests cover pre-existing and late destinations (remux and transcode),
a file/symlink created at the publication boundary, two preparations synchronized
after output validation (exactly one winner), unsupported-link failure, remux fallback
within one private directory, and KeyboardInterrupt/CancelledError while an unrelated
final file exists. Existing failure cleanup/passthrough tests remain; real local media
tests verify final filename, private FFmpeg paths, silent remux/transcode and cleanup.


P2 correction verification (offline): net +10 deterministic cases; focused preparation/
local-media/Instagram pipeline suite 108 passed; full suite 1122 passed, 1 skipped
(external YouTube matrix disabled). Sixteen real local FFmpeg/ffprobe cases still pass,
including silent remux/transcode and audio-bearing defaults. Ruff lint/format, diff,
documentation and security/scope review PASS. No external platform or Telegram calls.


### Offline carousel Telegram delivery

`tests/test_telegram_carousel.py` uses an injected sender and actual aiogram models,
with network connections forbidden. Transport unit tests mock only the preparation
boundary; real local preparation/limits are separately exercised below. Sizes 1,2,3,9,
10,11,12,20,21,25 verify exact operation sequence/order, FSInputFile paths, streaming
flags and per-video upload metadata. Mixed PHOTO positions retain video order. Any
first/middle/last preparation failure prevents every send. Invalid/incomplete plans,
files, outputs, resource bounds, source IDs/order, ambiguous responses and timeouts
fail safely. Send failure after confirmed batches reports partial progress and stops;
there is no automatic retry or rollback of successful Telegram requests. Tests verify
cleanup of owned prepared files and preservation of originals/unrelated collision files,
including cancellation and repeated cancellation while reaping a preparation child.

`tests/integration/test_carousel_delivery.py` uses generated local silent/audio MP4,
H.264 MKV and incompatible MPEG-4 MKV through the actual preparation child/FFmpeg/ffprobe,
then mocked senders. It checks byte-preserving passthrough, mixed audio states, remux/
transcode, upload metadata, preparation failures at every position, real OS output caps,
per-file/aggregate/workspace/count limits and cleanup. No real Telegram, Instagram
extraction/acquisition, bot polling or deployment changes are part of these tests.

PR #51 is merged; the earlier real three-video acquisition remains narrow external
evidence only. Mock send success does not establish real Telegram album delivery,
client playback, larger Instagram collection reliability or production readiness.


Offline delivery verification:

- Net +80 deterministic cases: 66 transport/validation/process tests and 14 actual local
  preparation integration cases. All passed; aiogram 3.31.0 objects/interfaces inspected.
- Full suite: 1202 passed, 1 skipped (external YouTube matrix explicitly disabled).
- Existing local video preparation, M4A/audio, YouTube, callback/delivery and Instagram
  acquisition regressions passed. Full suite ran with external socket connections denied
  in the pytest process; preparation children only execute local file/pipe media commands.
- Ruff lint/format, diff, local documentation links/anchors and security/scope review: PASS.
- Original Compose container IDs/start times/mounts unchanged. No live Instagram/Telegram
  requests, polling, deployment, provider registration or dependency changes.

## Reel-only Telegram MVP offline checks

`tests/test_instagram_reel_handler.py` uses existing synthetic provider fixtures and
forbids socket connections. It verifies disabled/default behavior, explicit per-dispatcher
injection, strict configuration, raw URL intent and `/p/` rejection, playlist/photo/private/
redirect rejection, acquisition/preparation failure, one send with real FSInputFile and
probe parameters, no send retry, cleanup, and repeated cancellation while the worker
still owns admission/workspace. Response-body accounting is tested without size headers;
real exec'd FFmpeg demonstrates the per-file write backstop. Generated local silent and
audio-bearing H.264 MP4 pass unchanged; an incompatible silent sample uses the existing
conversion helper without adding audio. Existing YouTube/callback suites remain required.

No actual Instagram extraction/download or Telegram API call is evidence for this stage.
The prior real Reel provider smoke is unchanged evidence. Full request hard deadlines,
production capacity and `/p/`/carousel routing remain open. A subsequent separately
authorized one-Reel delivery/client smoke is recorded below.

Verification on this branch: 32 new Reel MVP cases passed; focused handler/config/bot/
YouTube regression suite 142 passed; full suite 1234 passed, 1 skipped (external YouTube
live matrix disabled). Full pytest ran with socket connections forbidden. Ruff lint and
format, diff, local documentation links and security/scope checks PASS. Existing YouTube
delivery/callback function bodies, provider registry, acquisition/preparation APIs,
dependencies and Compose are unchanged.

## Main-bot Compose smoke preparation

PRs #53/#54 are merged. The separately authorized smoke used the existing main bot with
a bot-only restart, not another bot or poller. One canonical Reel was delivered and the
user confirmed playback, orientation and sound. Temporary Reel files were removed;
polling and Local Bot API stayed healthy. Exact file size/time were not captured. This
is one external case, not broad reliability or `/p/`/album validation.

Validate Compose using an empty env file and synthetic credential placeholders, retaining
resolved JSON only in process memory. Check absent flag -> false, explicit true -> true,
only bot receives it, and all other settings/services equal the base configuration.
Current APP_ENV=development, Local Bot API, Settings production guard and 25 MiB Reel
limit are preserved. Do not print resolved real credentials or run up/build/restart.
This configuration check is not live Telegram or Instagram evidence.

Verification: Compose false/true resolution and full base-config comparison PASS using
synthetic placeholders with real `.env` excluded. Existing offline suite: 1234 passed,
1 skipped; Ruff lint/format, diff, documentation and security/scope checks PASS. No live
requests, environment changes or container lifecycle operations were performed.

## Reel share-link regression

The initial full share URL failed before acquisition because of `psln`. The correction
uses the existing provider canonicalizer, accepting/removing irrelevant query keys, bare
flags and harmless anchors. Known item selectors remain rejected in query keys and
selector-shaped fragments, including case/percent-encoded forms. The 32-field parsing
bound, approved hosts, HTTP(S), Reel paths, credential and unsupported-port checks remain.
Carousel query policy is unchanged. Network-forbidden handler tests assert that the
provider receives only the canonical URL and a successful synthetic acquisition sends
exactly once and cleans its workspace. The exact reported URL is also checked offline;
committed fixtures use a synthetic tracking value instead of the original opaque value.
This correction has no live Instagram/Telegram evidence and no deployment changes.

Verification: net +34 cases; Reel handler 66 passed, combined handler/config/bot suite
176 passed, full suite 1268 passed and 1 skipped (external YouTube matrix disabled).
Full pytest forbids socket connections. Local FFmpeg/ffprobe, YouTube, callbacks and
delivery regressions passed. Ruff lint/format, diff, documentation and scope/security PASS.

## Draft Instagram /p/ Telegram routing validation

`tests/test_instagram_post_telegram.py` adds network-forbidden tests for
whole-publication three-video route selection, position preservation, known
`psln` tracking-key acceptance, owned
workspace cleanup, conservative item/unknown-query rejection, blocked unknown
items, single-video post reuse, uncertain album send without retry, and the
shared per-dispatcher Instagram admission slot. The prior
`test_posts_stay_outside_this_integration` expectation is replaced with
a positive delegation check; public Reels retain their existing tests.

Verification on the feature branch with GitHub Actions: Ruff lint PASS, Ruff
format PASS, and full pytest with FFmpeg/ffprobe installed: 1277 passed,
1 skipped (opt-in external YouTube matrix). The prior GitHub run without
FFmpeg skipped 114 additional media cases, which motivated this CI change.
This confirms offline and deterministic local-media checks, not Telegram
client album playback. No new real Instagram extraction, media acquisition or live
Telegram album send has been performed. The three-silent-video media
acquisition gate remains separately verified; real album delivery and playback
remain unverified.
