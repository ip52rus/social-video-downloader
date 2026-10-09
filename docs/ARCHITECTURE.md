# Architecture

## Target logical architecture
Telegram -> Application layer -> Download service -> Provider interface -> provider implementation -> media engine -> temporary storage.

## Telegram layer
Commands, messages, buttons, access checks, user-facing errors, and result delivery. It must not contain provider-specific download logic.

## Application layer
Orchestrates requests, validates input, selects providers, enforces policies, and returns transport-neutral results.

## Provider layer
Each provider owns URL recognition, metadata retrieval, media acquisition, and provider-specific quirks.

Providers report which output modes are supported: video with audio, video only, and audio only. They also expose selectable quality options when the platform allows them to be enumerated. Quality identifiers are provider-specific and opaque to the application and Telegram layers; each option also has a user-facing label.

A missing quality selection means automatic selection of the best available quality. If a provider cannot enumerate quality options, it may return an empty list, but it must still use the best available quality for an automatic download. Providers reject unsupported output modes and invalid quality identifiers through domain errors.

## Media engine
Responsible for download and media assembly. The first implementation uses yt-dlp and FFmpeg where appropriate.

## Evolution
The initial implementation may run in one process. Queues, workers, persistent storage, and distributed deployment are introduced only when measured requirements justify them.
