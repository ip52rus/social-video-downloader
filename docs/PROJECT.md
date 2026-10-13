# Project Definition

## Product
Social Video Downloader is a free Telegram bot-service for downloading media from popular social platforms.

## Primary flow
User sends a supported URL, the service identifies the platform and media, downloads it, and returns the result.

## Scope
The product is focused on downloading. Video editing and manipulation inside Telegram are out of scope.

## Access model
Planned access is tied to membership in the project's Telegram community. Leaving removes direct access; rejoining restores it. Membership is intended to be an ongoing condition of access, not a requirement to actively post or participate.

## Monetization direction
The service is planned to remain free. A separate advertising gateway may later offer compliant advertising actions before downloads. Advertising must remain modular.

## Initial platforms
YouTube was the first provider. The provider architecture and Phase 2 validation gate are in place, including live matrix coverage for combined video/audio, selected-quality video-only, and audio-only outputs in two containers, as well as recorded regular-video and Shorts smoke tests and deterministic error-boundary coverage. This is targeted evidence rather than a guarantee of broad reliability across all YouTube content and platform conditions. Instagram and TikTok are planned next, subject to technical validation and an explicit assessment of feasibility and reliability.

## Current implementation boundary
The downloader core, YouTube provider, and basic Telegram URL-to-download-to-delivery flow are implemented. A limited live flow through the Local Bot API Server was verified with a short video and an MP4 file of approximately 414.7 MB; the large file arrived and was confirmed playable. This does not establish reliability across all clients, codecs, file sizes, preview behavior, or deployment conditions, and does not prove project support up to 2 GB. Community-membership enforcement is not implemented and remains planned for Phase 4. The project is not production-ready; consult ROADMAP.md and TASKS.md for the current stage and outstanding work.
