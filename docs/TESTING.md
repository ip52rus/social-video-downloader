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
- Automated suite: 122 passed in the latest recorded run.
- Ruff lint and format checks passed for src/social_video_downloader/providers/youtube.py and tests/test_youtube_provider.py.
- GitHub Actions quality job passed on PR #10 head commit 5b49c9455a71ec7d562c46db00e12a1172769dd8. A separate result for the merge commit was not confirmed.
- Real downloads were verified for a regular public YouTube video in VIDEO_WITH_AUDIO, VIDEO_ONLY, and AUDIO_ONLY modes.
- Shorts Lmv2jfPNvzE was verified in all three modes. ffprobe confirmed AV1 video (720×1280) and Opus audio (48 kHz, stereo) in the combined output, a video-only stream in VIDEO_ONLY, and an audio-only stream in AUDIO_ONLY.
- Additional successful Shorts smoke tests were recorded for VF_MOfnz7OY (formats 398+251) and osrN3A_Rdiw (formats 616+251 via HLS).
- A duplicate audio format ID issue was reproduced and fixed; a live selector check for 251-0/251 successfully downloaded Opus audio (48 kHz, stereo).

Additional deterministic tests are being added for extractor exceptions, generic download failures, post-processing failures, missing final output, and temporary-workspace cleanup. The validation branch's CI result is pending, so these tests are not yet recorded as passing.

These results are targeted smoke-test evidence. They do not establish a representative format matrix, comprehensive failure-path coverage, or broad provider reliability. Those checks remain acceptance criteria for Phase 2.
