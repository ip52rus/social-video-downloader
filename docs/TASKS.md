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
- [x] Smoke-test metadata extraction through real download runs for one public video.
- [x] Smoke-test video/audio merging with one public video.
- [ ] Validate Shorts.
- [ ] Validate a representative format matrix across relevant media cases.
- [ ] Validate provider failure scenarios and relevant error boundaries.

### Recorded verification evidence
- Real downloads succeeded for `VIDEO_WITH_AUDIO`, `VIDEO_ONLY`, and `AUDIO_ONLY` on one public video.
- `VIDEO_ONLY` output was checked with `ffprobe` and contained a video stream without audio.
- `AUDIO_ONLY` output was checked with `ffprobe` and contained an audio stream without video.
- The automated test suite passed: `120 passed`.
- `ruff check .` and `ruff format --check .` passed; 34 files were reported already formatted.
- These checks cover the recorded state at the time of verification. Re-run them after subsequent relevant changes.
- This evidence does not establish Shorts support, broad format compatibility, or complete failure-path coverage. Phase 2 remains open until the remaining acceptance criteria are met.

## Telegram
- [x] Select and pin Telegram framework/dependencies (`aiogram` 3.x).
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
