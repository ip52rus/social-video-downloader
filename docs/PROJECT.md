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
YouTube is the first provider. The provider architecture and targeted real-download checks are in place, including regular videos and Shorts in video-with-audio, video-only, and audio-only modes. The representative format matrix and failure scenarios are still being validated. Instagram and TikTok are planned next, subject to technical validation and an explicit assessment of feasibility and reliability.

## Current implementation boundary
The downloader core and YouTube provider exist, but the Telegram user flow and community-membership enforcement are not yet implemented. The project is not production-ready; consult ROADMAP.md and TASKS.md for the current gate and outstanding work.
