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
- Automated suite: 131 passed in GitHub Actions run [37965947548](https://github.com/ip52rus/social-video-downloader/actions/runs/37965947548) on validation branch commit `6d4dccb08bd8208efa75da617638364bc51b59e4`.
- Ruff lint and format checks passed for src/social_video_downloader/providers/youtube.py and tests/test_youtube_provider.py.
- GitHub Actions quality job passed on PR #10 head commit 5b49c9455a71ec7d562c46db00e12a1172769dd8. A separate result for the merge commit was not confirmed.
- Real downloads were verified for a regular public YouTube video in VIDEO_WITH_AUDIO, VIDEO_ONLY, and AUDIO_ONLY modes.
- Shorts Lmv2jfPNvzE was verified in all three modes. ffprobe confirmed AV1 video (720×1280) and Opus audio (48 kHz, stereo) in the combined output, a video-only stream in VIDEO_ONLY, and an audio-only stream in AUDIO_ONLY.
- Additional successful Shorts smoke tests were recorded for VF_MOfnz7OY (formats 398+251) and osrN3A_Rdiw (formats 616+251 via HLS).
- A duplicate audio format ID issue was reproduced and fixed; a live selector check for 251-0/251 successfully downloaded Opus audio (48 kHz, stereo).

Ruff lint and format checks passed in the same CI run. Deterministic tests now cover extractor exceptions, generic download failures, post-processing failures, missing final output and workspace cleanup, plus five format-layout cases spanning progressive, adaptive AVC/VP9/AV1 and AAC/Opus, video-only, audio-only, and unusable formats. These tests do not substitute for real YouTube downloads across a representative format/media matrix.

These results are targeted smoke-test evidence. They do not establish a representative format matrix, comprehensive failure-path coverage, or broad provider reliability. Those checks remain acceptance criteria for Phase 2.


### Opt-in live YouTube format matrix

The live test in `tests/integration/test_youtube_live_matrix.py` is skipped during ordinary CI unless `YOUTUBE_LIVE_TEST_URL` is set. It requires a public, non-live video that exposes all three output modes, a selectable video quality, and at least two audio containers, plus an installed `ffprobe`.

Run it locally with:

```bash
YOUTUBE_LIVE_TEST_URL='https://www.youtube.com/watch?v=dQw4w9WgXcQ' uv run pytest tests/integration/test_youtube_live_matrix.py -q -s
```

The test downloads combined video/audio, a selected video-only quality, and audio-only outputs in two distinct containers; `ffprobe` verifies actual streams, codecs, dimensions/sample rate, and expected output containers. Files are created under pytest's temporary directory and removed after the test. A skipped test is not acceptance evidence: record a successful live run and classify any failure as an application issue, platform restriction/change, or transient network failure. Do not repeat already verified Shorts cases merely to rerun this matrix.
