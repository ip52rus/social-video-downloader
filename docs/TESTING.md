# Testing Strategy

## Unit tests
Fast deterministic tests for URL normalization, provider detection, filename sanitization, configuration parsing, and error mapping.

## Integration tests
Provider metadata extraction, media download, video/audio merging, and temporary workspace cleanup. External tests must not require personal credentials.

## End-to-end tests
Use only where they provide meaningful coverage, including Telegram URL submission, access control, delivery, and failure handling.

## Quality gates
A phase cannot be marked complete only because the happy path works. Relevant negative cases and resource/error boundaries must be covered.

## External platforms
Distinguish application regressions, provider/platform changes, and temporary network failures. Record external changes before modifying unrelated code.

### Current YouTube verification snapshot
- GitHub Actions run [37966225469](https://github.com/ip52rus/social-video-downloader/actions/runs/37966225469) passed 131 tests on merge commit `f27051fded257b5f39056c45333b4fa8c50075a3`; Ruff lint and format checks passed.
- Real regular-video downloads were verified in VIDEO_WITH_AUDIO, VIDEO_ONLY, and AUDIO_ONLY modes.
- Live matrix run on 2026-10-09 for https://www.youtube.com/watch?v=dQw4w9WgXcQ: `1 passed in 140.06s`. The test verified combined video/audio MP4, selected-quality video-only output, and audio-only outputs in two distinct containers using ffprobe.
- Shorts Lmv2jfPNvzE was verified in all three modes. Additional successful Shorts smoke tests were recorded for VF_MOfnz7OY and osrN3A_Rdiw.
- A duplicate audio format ID issue was reproduced and fixed; selector 251-0/251 successfully downloaded Opus audio.

The Phase 2 acceptance gate is satisfied by the combination of the live output-mode/container matrix, recorded Shorts and regular-video smoke tests, and deterministic error-boundary/format-layout tests. This is targeted evidence, not proof of broad reliability across all YouTube content and platform conditions.

### Telegram configuration tests
`tests/test_config.py` covers missing/blank token rejection, defaults, normalization of environment/log-level values, invalid values, token redaction from the settings repr, and settings immutability. These are deterministic tests; no Telegram API request is made. The configuration foundation does not yet constitute a working bot entry point or an end-to-end Telegram test.
