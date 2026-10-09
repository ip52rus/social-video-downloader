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
- The opt-in live-matrix CI test is intentionally skipped when `YOUTUBE_LIVE_TEST_URL` is not set. The PR #13 head and merge-commit workflows passed with that test skipped.
- Real regular-video downloads were verified in VIDEO_WITH_AUDIO, VIDEO_ONLY, and AUDIO_ONLY modes.
- Live matrix run on 2026-10-09 for https://www.youtube.com/watch?v=dQw4w9WgXcQ:
  `YOUTUBE_LIVE_TEST_URL='https://www.youtube.com/watch?v=dQw4w9WgXcQ' uv run pytest tests/integration/test_youtube_live_matrix.py -q -s` → `1 passed in 140.06s`.
- The live matrix downloaded combined video/audio MP4, a selected-quality video-only output, and audio-only outputs in two distinct containers. ffprobe verified the actual streams, codec names, video dimensions, audio sample rate, and expected audio containers.
- Shorts Lmv2jfPNvzE was verified in all three modes. ffprobe confirmed AV1 video (720×1280) and Opus audio (48 kHz, stereo) in the combined output, a video-only stream in VIDEO_ONLY, and an audio-only stream in AUDIO_ONLY.
- Additional successful Shorts smoke tests were recorded for VF_MOfnz7OY (formats 398+251) and osrN3A_Rdiw (formats 616+251 via HLS).
- A duplicate audio format ID issue was reproduced and fixed; a live selector check for 251-0/251 successfully downloaded Opus audio (48 kHz, stereo).

Deterministic tests cover extractor exceptions, generic download failures, post-processing failures, missing final output and workspace cleanup, plus five format-layout cases spanning progressive, adaptive AVC/VP9/AV1 and AAC/Opus, video-only, audio-only, and unusable formats.

The Phase 2 acceptance gate is satisfied by the combination of the live output-mode/container matrix, recorded Shorts and regular-video smoke tests, and deterministic error-boundary/format-layout tests. This is targeted acceptance evidence, not proof of broad reliability: the live matrix has been run against one regular public video. It does not establish behavior for every codec/container combination, geo-/age-restricted media, all live-stream conditions, or transient YouTube/platform changes. Re-run the live matrix after material provider or yt-dlp changes, and classify future failures as application issues, platform restrictions/changes, or transient network failures.

### Opt-in live YouTube format matrix

The live test in `tests/integration/test_youtube_live_matrix.py` is skipped during ordinary CI unless `YOUTUBE_LIVE_TEST_URL` is set. It requires a public, non-live video that exposes all three output modes, a selectable video quality, and at least two audio containers, plus an installed `ffprobe`.

Run it locally with:

```bash
YOUTUBE_LIVE_TEST_URL='https://www.youtube.com/watch?v=dQw4w9WgXcQ' uv run pytest tests/integration/test_youtube_live_matrix.py -q -s
```

The test downloads combined video/audio, a selected video-only quality, and audio-only outputs in two distinct containers; `ffprobe` verifies actual streams, codecs, dimensions/sample rate, and expected output containers. Files are created under pytest's temporary directory and removed after the test. A skipped test is not acceptance evidence. Choose a different public non-live URL only if a fixture no longer exposes the required modes or containers.
