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

Known runtime verification gap: the validated YouTube extraction path depends on
Deno/yt-dlp JavaScript challenge support, but the current Dockerfile does not install
Deno. Containerized YouTube extraction must be verified with the actual image or the
image must be updated deliberately in a separate technical change.

## Operational and recovery tests

A phase cannot be marked complete only because the happy path works. Remaining
operational checks include:

- restart behavior for the bot and Local Bot API Server;
- temporary Local Bot API/network failure recovery;
- upload failures and user-facing error behavior;
- cloud-to-local migration rehearsal with a separate test bot;
- local-to-cloud rollback rehearsal with a separate test bot;
- documented limits and resource observations for larger files when justified.

Telegram documents cloud-to-local migration with `logOut`, and documents `close` for
moving between Local Bot API Servers. Do not treat `close` as an officially documented
local-to-cloud rollback procedure.
