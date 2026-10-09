# Local Telegram Bot API Server: setup and rollout

## Decision

The delivery strategy is based on file size, not video duration:

- Cloud Bot API: keep the current default for files that fit its upload limit (about 50 MB).
- Local Bot API Server: planned path for files larger than the cloud upload limit and up to the server's documented 2000 MB upload ceiling.
- User-account automation for files above 2 GB: deferred until actual demand justifies a separate security and reliability review.

The current code supports an optional API base URL, but this document does not mean the local server has been installed or enabled.

## Prerequisites

1. A host with enough disk space for concurrent downloads, temporary files, and the Bot API server's working data. The current downloader can hold the original and a converted copy at the same time.
2. Telegram API application credentials (`api_id` and `api_hash`) obtained through Telegram's developer portal. These belong to the Local Bot API Server configuration and must not be committed.
3. The existing bot token, stored only in the runtime environment or a secret manager.
4. The official [Telegram Bot API server repository](https://github.com/tdlib/telegram-bot-api) and its current build/run instructions.

## Network and security

- Bind the API endpoint to loopback or a private network whenever possible.
- Do not expose an unauthenticated Bot API endpoint to the public internet.
- Keep `api_id`, `api_hash`, and the bot token out of source control, logs, issue comments, and screenshots.
- If the bot process and API server run in separate containers, verify networking and file-path behavior explicitly. Do not enable local file-path mode without confirming that the paths are valid from the server's point of view.
- The bot currently uses long polling, so a public webhook endpoint is not required for the initial rollout.

## Client configuration

Leave `TELEGRAM_API_BASE_URL` unset to use the cloud Bot API.

When the Local Bot API Server is running and reachable, set the variable to its private base URL, for example:

    export TELEGRAM_API_BASE_URL="http://127.0.0.1:8081"

Then restart the bot process. The client configuration in this project enables aiogram's local-server mode when the variable is present. The example assumes both processes can reach the same loopback interface; it must be adjusted if they run in separate containers or hosts.

## Required rollout tests

1. Confirm the server is healthy and the bot can poll through the configured endpoint.
2. Send a known-compatible video smaller than 50 MB; verify playback and logs.
3. Send a known-compatible video larger than 50 MB; verify it is uploaded without a compression pass.
4. Test a larger file, increasing size gradually and stopping well below the configured host's disk/RAM limits before attempting files near 2 GB.
5. Test a codec-incompatible file to verify that media preparation still works.
6. Restart both processes and verify polling recovers.
7. Unset `TELEGRAM_API_BASE_URL`, restart the bot, and verify rollback to the cloud API.
8. Record actual upload size, duration, codecs, upload time, disk peak, and any Telegram errors.

Do not advertise support for 2 GB until a real end-to-end test confirms it in the deployed environment.

## Operational limits

The Local Bot API Server removes the cloud Bot API's 50 MB upload restriction, but it does not remove local disk, network, timeout, Telegram media, or application resource limits. The downloader's current temporary workspace and media-preparation path must be evaluated with large files before production use.
