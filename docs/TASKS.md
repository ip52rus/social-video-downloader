# Task Decomposition

## Foundation
- [x] Create GitHub repository.
- [x] Establish README.
- [x] Establish AGENTS.md.
- [x] Establish Git ignore and environment example.
- [x] Document product definition.
- [x] Document architecture.
- [x] Document roadmap.
- [x] Document security, development, and testing policies.
- [x] Add CI.
- [x] Add dependency management.

## Downloader Core
- [x] Define domain models.
- [x] Define provider interface.
- [x] Define platform-independent download modes and quality options.
- [x] Extend provider contract for mode and quality discovery.
- [x] Implement URL normalization.
- [x] Implement platform detection.
- [x] Implement safe filename generation.
- [x] Implement temporary workspace lifecycle.
- [x] Define error taxonomy.
- [x] Add unit tests for models, errors, provider contract, URL handling, filenames, and workspace lifecycle.
- [x] Add integration harness.

## YouTube
- [x] Move the provider implementation into the provider architecture.
- [x] Smoke-test metadata extraction through real download runs for public videos.
- [x] Smoke-test video/audio merging with public videos.
- [x] Validate Shorts with real downloads.
- [ ] Validate a representative format matrix across relevant media cases. An opt-in live test is available at `tests/integration/test_youtube_live_matrix.py`; a successful real-platform run is still outstanding.
- [ ] Validate provider failure scenarios and relevant error boundaries.

### Recorded verification evidence
- A public YouTube video was downloaded successfully in VIDEO_WITH_AUDIO, VIDEO_ONLY, and AUDIO_ONLY modes.
- VIDEO_ONLY output was checked with ffprobe and contained a video stream without audio.
- AUDIO_ONLY output was checked with ffprobe and contained an audio stream without video.
- Shorts https://www.youtube.com/shorts/Lmv2jfPNvzE (Секрет от Мироновой, 20 seconds) was tested in all three download modes:
  - VIDEO_WITH_AUDIO: ffprobe confirmed AV1 video (720×1280) and Opus audio (48 kHz, stereo); duration about 20.13 seconds.
  - VIDEO_ONLY: ffprobe confirmed an AV1 video stream without audio.
  - AUDIO_ONLY: ffprobe confirmed an Opus audio stream (48 kHz, stereo) without video; duration about 20.14 seconds.
- Additional Shorts smoke tests succeeded for VF_MOfnz7OY using formats 398+251, and osrN3A_Rdiw using 616+251 via HLS. The latter was merged to NEVER GIVE UP 🙌.mp4; the recorded process exit code was 0.
- Deno 2.9.7 was detected during the recorded Shorts checks; no missing-JavaScript-runtime warning was observed.
- The duplicate audio format ID issue was reproduced and fixed in PR #10. The selector 251-0/251 successfully downloaded audio from one public YouTube video; ffprobe confirmed Opus, 48 kHz, stereo.
- GitHub Actions CI run [37965947548](https://github.com/ip52rus/social-video-downloader/actions/runs/37965947548) passed 131 tests on validation branch commit `6d4dccb08bd8208efa75da617638364bc51b59e4`; Ruff lint and format checks also passed.
- Ruff lint and format checks passed for src/social_video_downloader/providers/youtube.py and tests/test_youtube_provider.py.
- GitHub Actions quality job passed on PR #10 head commit 5b49c9455a71ec7d562c46db00e12a1172769dd8. This is evidence for the PR head, not a separate CI result for the merge commit.
- Deterministic provider tests now pass for extractor exceptions, generic download failures, post-processing failures, missing final output, temporary-workspace cleanup, and five representative format-layout cases (progressive, adaptive AVC/VP9/AV1 with AAC/Opus, video-only, audio-only, and unusable formats). These are network-free tests; the real YouTube format/media matrix remains outstanding.
- These are targeted smoke tests and automated checks, not evidence of broad provider reliability or complete coverage.

## Telegram
- [x] Select and pin Telegram framework/dependencies (aiogram 3.x).
- [ ] Implement configuration loading.
- [ ] Implement /start.
- [ ] Implement URL intake.
- [ ] Implement state and progress handling.
- [ ] Implement result delivery.
- [ ] Implement user-facing errors.

## Access control
- [ ] Define required Telegram community.
- [ ] Implement membership check.
- [ ] Test member, non-member, leave, and rejoin behavior.
- [ ] Fail closed on membership-check errors where appropriate.
