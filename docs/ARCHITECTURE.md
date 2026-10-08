# Architecture

## Target logical architecture
Telegram -> Application layer -> Download service -> Provider interface -> provider implementation -> media engine -> temporary storage.

## Telegram layer
Commands, messages, buttons, access checks, user-facing errors, and result delivery. It must not contain provider-specific download logic.

## Application layer
Orchestrates requests, validates input, selects providers, enforces policies, and returns transport-neutral results.

## Provider layer
Each provider owns URL recognition, metadata retrieval, media acquisition, and provider-specific quirks.

## Media engine
Responsible for download and media assembly. The first implementation uses yt-dlp and FFmpeg where appropriate.

## Evolution
The initial implementation may run in one process. Queues, workers, persistent storage, and distributed deployment are introduced only when measured requirements justify them.
