# Social Video Downloader

Free Telegram bot-service for downloading media from popular social platforms.

## Project status

The transport-independent downloader core and the first YouTube provider are implemented. YouTube has passed targeted real-download smoke tests for regular videos and Shorts, including video-with-audio, video-only, and audio-only modes. The automated test suite has 122 passing tests in the latest recorded run.

**Current stage: YouTube provider validation.** A representative format matrix and provider failure/error-boundary scenarios remain open. The Telegram bot flow and community-membership access control have not yet been implemented.

See [the roadmap](docs/ROADMAP.md), [task checklist](docs/TASKS.md), and [testing strategy](docs/TESTING.md) for verified evidence and remaining acceptance criteria.
