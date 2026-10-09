# Changelog

## Unreleased
- Fix explicit YouTube audio selection for duplicate normalized format IDs by trying the suffixed format ID and falling back to the raw ID.
- Add regression coverage for YouTube audio format IDs 140 and 251.
- Implement the YouTube provider behind the provider architecture, including metadata extraction, selectable output modes/quality options, media download, and stream assembly through yt-dlp/FFmpeg where applicable.
- Add real-download verification evidence for regular YouTube videos and Shorts across video-with-audio, video-only, and audio-only modes.
- Add a deterministic integration test covering URL handling, provider interaction, safe filenames, and temporary workspace cleanup.
- Add platform-independent download modes, quality options, and automatic best-available quality selection to the provider contract.
- Add safe cross-platform filename generation and automatically cleaned temporary workspaces with unit tests.
- Establish repository governance, project documentation, Python tooling, dependency management, and CI.
- Add downloader domain models, error taxonomy, provider interface, URL normalization, and unit tests.

## Verification notes
- Latest recorded automated test suite: 122 passed.
- Ruff lint and format checks passed for the changed YouTube provider and its tests.
- GitHub Actions quality job passed on PR #10 head commit 5b49c9455a71ec7d562c46db00e12a1172769dd8.
- Live checks cover a small set of public YouTube URLs and do not establish broad platform reliability. The representative format matrix and provider failure scenarios remain open.
