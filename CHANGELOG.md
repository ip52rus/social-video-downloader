# Changelog

## Unreleased
- Add Docker Compose configuration for the bot and Local Bot API Server, keeping the API endpoint on the internal Compose network.
- Add Docker build-context protection with `.dockerignore` so local secrets, runtime data, caches, and generated media are excluded while `.env.example` remains available.
- Add environment examples for Telegram API application credentials, optional local Bot API endpoint, and configurable local API request timeout.
- Synchronize project documentation with the local-first development policy, Local Bot API deployment layout, security requirements, and remaining Dockerized extraction verification gap.
- Prepare Telegram video uploads as H.264/AAC MP4 when source codecs or container are incompatible; verify converted output and preserve already-compatible MP4 files without re-encoding.
- Deliver prepared media as Telegram video messages with streaming support rather than generic documents.
- Add deterministic compatibility tests for passthrough, transcoding, output verification, and processing failures.
- Connect Telegram YouTube URL intake to the provider-selection download service and deliver prepared media as Telegram video messages.
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
- GitHub Actions run [37974061474](https://github.com/ip52rus/social-video-downloader/actions/runs/37974061474) passed lint, format, and deterministic tests for Telegram download orchestration and file-delivery handling.
- Live YouTube evidence is limited to a small set of public URLs and does not establish broad platform reliability.
- A real Telegram flow through the Local Bot API Server was verified with a short video and an MP4 file of approximately 414.7 MB. The large file was H.264/AAC, 1920x1080, approximately 1649 seconds long, arrived in Telegram, and was confirmed playable. This is a limited scenario, not validated support for files up to 2000 MB.
- Additional Telegram client checks, failure/recovery scenarios, Dockerized extraction verification, restart and rollback rehearsal, and justified larger-file testing remain outstanding. Community-membership access control is a separate planned phase.
