# Architecture

## Target logical architecture
Telegram -> Telegram handlers -> application/download service -> provider interface -> provider implementation -> media engine -> temporary storage.

## Configuration and startup
Environment-based settings are validated before starting the application. The Telegram token is required, excluded from the settings representation, and must never be written to logs. The package entry point is python -m social_video_downloader; it configures standard-library logging, creates an aiogram bot and dispatcher, registers the Telegram router, and starts polling. Bot session cleanup runs when polling stops.

## Telegram layer
The aiogram router owns commands and text intake, user-facing validation responses, access checks, and result delivery. It must not contain provider-specific download logic. Currently /start explains usage, and text messages are treated as candidate URLs and validated against supported platform domains. Accepted links receive an explicit acknowledgement that downloading is not yet connected.

## Application layer
Orchestrates requests, validates input, selects providers, enforces policies, and returns transport-neutral results. Download orchestration is not connected to Telegram handlers yet.

## Provider layer
Each provider owns URL recognition, metadata retrieval, media acquisition, and provider-specific quirks.

Providers report which output modes are supported: video with audio, video only, and audio only. They also expose selectable quality options when the platform allows them to be enumerated. Quality identifiers are provider-specific and opaque to the application and Telegram layers; each option also has a user-facing label.

A missing quality selection means automatic selection of the best available quality. If a provider cannot enumerate quality options, it may return an empty list, but it must still use the best available quality for an automatic download. Providers reject unsupported output modes and invalid quality identifiers through domain errors.

## Media engine
Responsible for download and media assembly. The first implementation uses yt-dlp and FFmpeg where appropriate.

## Evolution
The initial implementation may run in one process. Queues, workers, persistent storage, and distributed deployment are introduced only when measured requirements justify them.
