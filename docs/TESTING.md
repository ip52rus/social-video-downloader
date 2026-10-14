# Testing Strategy

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

These are unit and deterministic integration checks, not real Telegram network-failure
tests. Existing containers were not rebuilt/restarted; real-client revalidation of the
changed code remains outstanding. No claim of Phase 4 completion or production
reliability follows from this bounded fix.

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
