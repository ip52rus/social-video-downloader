# Changelog

## Unreleased
- Connect Telegram YouTube URL intake to the provider-selection download service and attempt to deliver downloaded files as Telegram documents.
- Add safe user-facing download and upload error messages, non-blocking download execution, and per-request temporary-file cleanup.
- Add deterministic tests for provider selection, URL normalization, Telegram download orchestration, error responses, and cleanup.
- Add Telegram /start and text-based URL intake with supported-platform recognition, user-facing validation responses, and deterministic handler tests.
- Add standard-library logging configuration and a minimal aiogram bot/dispatcher polling entry point, with deterministic construction/configuration tests.
- Add validated environment-based settings for Telegram bot configuration, app environment, and log level, with deterministic tests.
- Record successful opt-in live YouTube output-mode/container matrix verification and close the Phase 2 validation gate with explicit evidence limits.
- Fix explicit YouTube audio selection for duplicate normalized format IDs by trying the suffixed format ID and falling back to the raw ID.
- Add regression coverage for YouTube audio format IDs 140 and 251.
- Implement the YouTube provider behind the provider architecture, including metadata extraction, selectable output modes/quality options, media download, and stream assembly through yt-dlp/FFmpeg where applicable.
- Add real-download verification evidence for regular YouTube videos and Shorts across video-with-audio, video-only, and audio-only modes.
- Add deterministic provider tests for extractor/download/post-processing failures, missing output, cleanup, and representative format layouts.
- Add a deterministic integration test covering URL handling, provider interaction, safe filenames, and temporary workspace cleanup.
- Add platform-independent download modes, quality options, and automatic best-available quality selection to the provider contract.
- Add safe cross-platform filename generation and automatically cleaned temporary workspaces with unit tests.
- Establish repository governance, project documentation, Python tooling, dependency management, and CI.
- Add downloader domain models, error taxonomy, provider interface, URL normalization, and unit tests.

## Verification notes
- GitHub Actions run [37966225469](https://github.com/ip52rus/social-video-downloader/actions/runs/37966225469) passed 131 tests and Ruff lint/format checks on merge commit f27051fded257b5f39056c45333b4fa8c50075a3.
- Opt-in live matrix passed locally on 2026-10-09 for https://www.youtube.com/watch?v=dQw4w9WgXcQ in 140.06 seconds. It verified combined MP4, selected-quality video-only output, and audio-only output in two containers using ffprobe.
- Live evidence is limited to a small set of public URLs and does not establish broad platform reliability. The Telegram download/delivery code is implemented in the current work, but its CI results and real test-bot end-to-end flow remain outstanding. Access control remains unimplemented and is a separate planned phase.
