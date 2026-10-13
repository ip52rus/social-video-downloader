# Project Definition

## Product
Social Video Downloader is a free Telegram bot-service for downloading media from popular social platforms.

## Primary flow
User sends a supported URL, the service identifies the platform and media, downloads it, and returns the result.

## Scope
The product is focused on downloading. Video editing and manipulation inside Telegram are out of scope.

## Current product strategy
The current priority is building a useful downloader product with a strong Telegram experience and broader platform coverage. Access restrictions are intentionally deferred while the core downloader product is still maturing.

## Monetization direction
Monetization and access control are future business-model decisions. A Telegram community-membership gate, an advertising gateway, optional paid/free models, or other access restrictions may be investigated later after the service has useful mature functionality. Advertising must remain modular and must not be coupled into provider implementations.

## Initial platforms
YouTube was the first provider. The provider architecture and Phase 2 validation gate are in place, including live matrix coverage for combined video/audio, selected-quality video-only, and audio-only outputs in two containers, as well as recorded regular-video and Shorts smoke tests and deterministic error-boundary coverage. This is targeted evidence rather than a guarantee of broad reliability across all YouTube content and platform conditions. The next product work is download UX for YouTube modes/quality, then Instagram and TikTok provider feasibility work with explicit Go/No-Go decisions before implementation.

## Current implementation boundary
The downloader core, YouTube provider, and functional Telegram URL-to-download-to-delivery flow are implemented. A limited live flow through the Local Bot API Server was verified with a short video and an MP4 file of approximately 414.7 MB; the large file arrived and was confirmed playable. This does not establish reliability across all clients, codecs, file sizes, preview behavior, or deployment conditions, and does not prove project support up to 2 GB. Community-membership enforcement is not implemented and is not required during core product development. The project is not production-ready; consult ROADMAP.md and TASKS.md for the current stage and outstanding work.
