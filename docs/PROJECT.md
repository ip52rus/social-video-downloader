# Project Definition

## Product
Social Video Downloader is a free Telegram bot-service for downloading media from popular social platforms.

## Primary flow
User sends a supported URL, the service identifies the platform and media, downloads it, and returns the result.

## Scope
The product is focused on downloading. Video editing and manipulation inside Telegram are out of scope.

## Access model
Planned access is tied to membership in the project's Telegram community. Leaving removes direct access; rejoining restores it.

## Monetization direction
The service is planned to remain free. A separate advertising gateway may later offer compliant advertising actions before downloads. Advertising must remain modular.

## Initial platforms
YouTube is the first provider because its download path has already been validated locally with yt-dlp, Deno/EJS, and FFmpeg. Instagram and TikTok are planned next subject to technical validation.
