# Project Definition

## Product
Social Video Downloader is a free Telegram bot-service for downloading media from popular social platforms.

## Primary flow
User sends a supported URL, the service identifies the platform and media, downloads it, and returns the result.

## Scope
The product is focused on downloading. Video editing and manipulation inside Telegram are out of scope.

## Current product strategy
The current priority is building a useful downloader product with a strong Telegram experience and broader platform coverage. Access restrictions are intentionally deferred while the core downloader product is still maturing.

The Telegram UX should be capability-driven: minimum steps, provider-specific
capabilities, and consistent visual language. The bot should show only meaningful options
supported by the current platform and content. YouTube may expose Video/Audio and
video-quality choices, while Instagram, TikTok, or future platforms should skip audio or
quality screens when the provider/content has no useful choice.

Product analytics should exist to improve UX and technical decisions, but the privacy
principle is to collect product and technical statistics rather than users' viewing
history. Analytics should not store source URLs, video titles, channel or author names,
Telegram usernames, message text, or unnecessary personal data. Pseudonymous or anonymous
identity is sufficient for aggregate usage statistics.

## Monetization direction
Monetization and access control are future business-model decisions. A Telegram community-membership gate, an advertising gateway, optional paid/free models, or other access restrictions may be investigated later after the service has useful mature functionality. Advertising must remain modular and must not be coupled into provider implementations.

## Initial platforms
YouTube was the first provider. The provider architecture and Phase 2 validation gate are in place, including live matrix coverage for combined video/audio, selected-quality video-only, and audio-only outputs in two containers, as well as recorded regular-video and Shorts smoke tests and deterministic error-boundary coverage. This is targeted evidence rather than a guarantee of broad reliability across all YouTube content and platform conditions.
Phase 4 YouTube UX functional scope is ACCEPTED. Phase 5 Instagram is the next functional
development stage, beginning with provider feasibility work and an explicit Go/No-Go
decision before implementation; Phase 6 TikTok follows under the same feasibility gate.
Phase 4 analytics remains unfinished, and Phase 8 UX and Phase 9 reliability tasks remain
open.

## Current implementation boundary

Phase 4 functional scope is ACCEPTED as of 2026-10-15 for the recorded real Telegram
Video/Audio, playlist-context, landscape/portrait quality, M4A duration/playback and
interaction-protection cases. See
[TESTING.md](TESTING.md#phase-4-functional-acceptance-2026-10-15) for the tested revision,
evidence and limits. This does not close analytics or all UX work. Phase 8 retains choice
prompt/copy polish; Phase 9 remains open for HTTP 403 recovery, metadata blocking the
async event loop, network resilience, restart/recovery and monitoring. No architecture
or product-policy change is made by this acceptance record.
The downloader core, YouTube provider, and functional Telegram URL-to-download-to-delivery flow are implemented. A limited live flow through the Local Bot API Server was verified with a short video and an MP4 file of approximately 414.7 MB; the large file arrived and was confirmed playable. This does not establish reliability across all clients, codecs, file sizes, preview behavior, or deployment conditions, and does not prove project support up to 2 GB. Community-membership enforcement is not implemented and is not required during core product development. The project is not production-ready; consult ROADMAP.md and TASKS.md for the current stage and outstanding work.
