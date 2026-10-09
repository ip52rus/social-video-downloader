# Testing Strategy

## Unit tests
Fast deterministic tests for URL normalization, provider detection, filename sanitization, configuration parsing, logging configuration, bot/dispatcher construction, handler behavior, and error mapping.

## Integration tests
Provider metadata extraction, media download, video/audio merging, and temporary workspace cleanup. External tests must not require personal credentials.

## End-to-end tests
Use only where they provide meaningful coverage, including Telegram URL submission, access control, delivery, and failure handling.

## Quality gates

A phase cannot be marked complete only because the happy path works. Relevant negative cases and resource/error boundaries must be covered.

## External platforms

Distinguish application regressions, provider/platform changes, and temporary network failures. Record external changes before modifying unrelated code.

### Current YouTube verification snapshot

- GitHub Actions run [37966225469](https://github.com/ip52rus/social-video-downloader/actions/runs/37966225469) passed 131 tests on merge commit f27051fded257b5f39056c45333b4fa8c50075a3; Ruff lint and format checks passed.
- Real regular-video downloads were verified in VIDEO_WITH_AUDIO, VIDEO_ONLY, and AUDIO_ONLY modes.
- Live matrix run on 2026-10-09 for https://www.youtube.com/watch?v=dQw4w9WgXcQ passed in 140.06 seconds. It verified combined video/audio MP4, selected-quality video-only output, and audio-only outputs in two distinct containers using ffprobe.
- Shorts were verified in all three modes; additional successful Shorts smoke tests were recorded for VF_MOfnz7OY and osrN3A_Rdiw.
- A duplicate audio format ID issue was reproduced and fixed; selector 251-0/251 successfully downloaded Opus audio.

The Phase 2 acceptance gate is satisfied by the live output-mode/container matrix, recorded Shorts and regular-video smoke tests, and deterministic error-boundary/format-layout tests. This is targeted evidence, not proof of broad reliability across all YouTube content and platform conditions.

### Telegram playback compatibility tests

- `tests/test_telegram_media.py` covers compatible MP4 passthrough, AV1/Opus transcoding to H.264/AAC, conversion of non-MP4 containers, post-conversion verification, missing audio, and FFmpeg failure mapping.
- `tests/test_handlers.py` verifies video-message delivery with streaming support and temporary workspace cleanup.
- These deterministic tests do not prove playback on every Telegram client. After deployment, repeat a live test on desktop and iPhone.

### Telegram deterministic tests

- `tests/test_config.py` covers required token handling, defaults, normalization, invalid values, token redaction in the settings repr, and immutability.
- `tests/test_logging_config.py` verifies that the configured level and fixed log format are passed to the logging setup without including the bot token.
- `tests/test_bot.py` verifies bot and dispatcher construction, including default cloud Bot API and optional local API endpoint configuration.
- `tests/test_handlers.py` covers /start, invalid links, unsupported domains, non-YouTube platform messaging, successful mocked download/delivery, safe error responses, and temporary workspace cleanup.
- `tests/test_download_service.py` covers provider selection, URL normalization, delegation, and recognized platforms without configured providers.
- GitHub Actions run [37974061474](https://github.com/ip52rus/social-video-downloader/actions/runs/37974061474) passed lint, format, and the deterministic test suite for this implementation.

These deterministic tests do not exercise a real YouTube download from the Telegram process, Telegram network upload, or polling against Telegram. A manual test-bot end-to-end check remains outstanding and is required before Phase 3 can be accepted.

### Local Bot API Server rollout gate

The optional endpoint is unit-tested, but it is not enabled by default and does not mean a Local Bot API Server has been deployed. Before switching the live bot, verify server installation and private network reachability, bot polling against the local endpoint, uploads below and above 50 MB, a file close to the intended maximum, restart behavior, and rollback to the cloud endpoint.
