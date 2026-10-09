# Social Video Downloader

Free Telegram bot-service for downloading media from popular social platforms.

## Project status

The transport-independent downloader core and YouTube provider are implemented. The YouTube provider's Phase 2 validation gate has passed: recorded real downloads cover regular videos and Shorts, all three output modes, two audio containers in the live matrix, and deterministic provider error-boundary tests. The latest recorded GitHub Actions suite passed 131 tests with Ruff lint/format checks; the opt-in live matrix also passed locally on a public regular video.

**Current stage: Telegram MVP.** The Telegram bot flow and community-membership access control have not yet been implemented. This project is not production-ready, and a successful matrix on one URL does not establish broad YouTube reliability.

See [the roadmap](docs/ROADMAP.md), [task checklist](docs/TASKS.md), and [testing strategy](docs/TESTING.md) for evidence, limitations, and remaining work.
