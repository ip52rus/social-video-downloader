# Local Telegram Bot API Server

## Purpose

Telegram's cloud Bot API has a much lower upload limit for bot file uploads than a
self-hosted Local Bot API Server. This project can use either Telegram's cloud Bot API
or a configured Bot API-compatible endpoint.

Leave `TELEGRAM_API_BASE_URL` unset to use the cloud Bot API. Set it to a private Local
Bot API endpoint to use local-server mode.

The Local Bot API Server is an infrastructure option. It is not, by itself, proof that
the project is production-ready or that every large video will upload successfully.

## Verified project state

The following facts have been verified in the current project environment:

- Local Telegram Bot API Server was started.
- The bot ran through the Local Bot API endpoint.
- Polling worked through the Local Bot API endpoint.
- A short vertical YouTube video completed the live download -> Telegram delivery flow.
- An approximately 414.7 MB MP4 completed Telegram delivery and was playable.
- The large tested MP4 used H.264 video and AAC audio, had 1920x1080 dimensions, and
  was approximately 1649 seconds long.

This is limited verification evidence for the tested files and environment. It does not
prove support for arbitrary files up to 2000 MB, production reliability, concurrent
load behavior, recovery behavior, or performance characteristics. Different Telegram
clients may display video previews differently, so preview rendering must not be
documented as fully controlled by the application.

## Official server capability vs project evidence

Telegram's official Local Bot API Server documentation states that a local server can:

- download files without a size limit;
- upload files up to 2000 MB.

Those are official server capabilities. The project's verified range is currently only
the observed live test range, including the approximately 414.7 MB MP4 described above.
Do not advertise validated project support up to 2000 MB until reproducible end-to-end
tests have confirmed it in the intended deployment environment.

## Requirements and prerequisites

Before running the local server, verify:

- Docker and Docker Compose are installed and available.
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_API_ID`, and `TELEGRAM_API_HASH` are configured through
  environment variables or an untracked `.env` file.
- Sufficient disk space is available for downloads, temporary files, Local Bot API Server
  data, and concurrent jobs.
- The bot and Local Bot API Server can reach each other over the intended private network.
- Secrets are not committed, logged, copied into screenshots, or placed in shell history.
- Migration and rollback procedures have been rehearsed with a separate test bot.

Use the official [Telegram Bot API server repository](https://github.com/tdlib/telegram-bot-api)
for server source code and build details.

## Client configuration

### Cloud Bot API

Leave `TELEGRAM_API_BASE_URL` unset:

```bash
unset TELEGRAM_API_BASE_URL
```

### Local endpoint on the same host

For a bot process running on the same host and able to reach the local server through
loopback:

```bash
export TELEGRAM_API_BASE_URL="http://127.0.0.1:8081"
```

The address `127.0.0.1` refers to the network namespace of the process making the
connection. It is not interchangeable with a Docker Compose service name.

### Local endpoint in the project Compose setup

The current Compose layout uses an internal service name:

```text
http://telegram-bot-api:8081
```

When `TELEGRAM_API_BASE_URL` is present, the bot enables aiogram local-server mode with
`TelegramAPIServer.from_base(..., is_local=True)` and applies
`TELEGRAM_API_TIMEOUT_SECONDS`. The timeout defaults to 1800 seconds and must be an
integer from 1 to 86400.

Increasing a timeout does not solve insufficient disk space, network failures,
Telegram-side restrictions, incompatible client behavior, or other resource constraints.

## Docker Compose environment

The repository includes a local `compose.yaml` for running:

- `telegram-bot-api`: Local Telegram Bot API Server.
- `bot`: the Social Video Downloader bot.

Current layout:

- The bot connects to `http://telegram-bot-api:8081` over the private Compose network.
- The Bot API endpoint is exposed only to other Compose services with `expose`, not
  published to the host by default.
- Local Bot API Server state/data is stored in the `telegram-bot-api-data` named volume.
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_API_ID`, and `TELEGRAM_API_HASH` are provided through
  environment interpolation.
- Runtime secrets belong in environment variables or an untracked `.env`, not in source.

Validate Compose configuration without starting services:

```bash
docker compose config --quiet
```

Build the bot image:

```bash
docker compose build bot
```

A successful configuration check, build, or container start does not prove end-to-end
Telegram delivery. Polling, download, media preparation, upload, restart/recovery, and
rollback behavior must be verified separately.

Do not publish the Local Bot API Server endpoint externally unless explicitly required
and secured. Do not expose an unauthenticated Bot API endpoint to the public internet.

## Migrating from cloud Bot API to local server

Telegram documents the cloud-to-local transition through `logOut`.

Safe migration outline:

1. Stop competing bot processes so the bot is not polling concurrently.
2. Confirm the local server configuration without printing or sharing secrets.
3. Call Telegram Bot API `logOut` on the cloud endpoint using a credential-safe client.
4. After successful `logOut`, start the bot against the Local Bot API endpoint.
5. Confirm polling and run the required delivery tests.
6. Monitor logs, disk usage, request failures, and user-visible delivery results.

According to the official Telegram Bot API documentation, after successful cloud
`logOut`, the bot can immediately log in on the local server. The bot cannot log in to
the cloud Bot API again for 10 minutes.

Do not perform migration with a production bot until the process has been rehearsed with
a separate test bot.

## Rollback and local server moves

Telegram's documentation explicitly describes:

- cloud -> local migration with `logOut`;
- closing a bot instance before moving from one Local Bot API Server to another Local Bot
  API Server with `close`.

The same documentation section does not provide a complete official local -> cloud
rollback procedure for this project's operational use case. Do not describe `close` as
an officially documented local -> cloud rollback operation.

Before relying on rollback in production:

1. Rehearse the complete local -> cloud rollback with a separate test bot.
2. Verify the exact behavior of the deployed Local Bot API Server version.
3. Account for the documented 10-minute cloud login restriction after cloud `logOut`.
4. Confirm polling and video delivery after the rollback.
5. Record the tested procedure and failure modes.

Rollback is an operational procedure that must be verified, not inferred from the
cloud-to-local migration alone.

## Required validation before production use

The Local Bot API path is not production-ready until these checks are completed and
recorded:

- Repeatable polling and delivery through the private local endpoint.
- Restart behavior for both bot and Local Bot API Server.
- Recovery after temporary network or server failures.
- Upload failure handling and user-facing error behavior.
- Additional Telegram clients, including mobile clients.
- Incompatible-codec preparation and delivery.
- Dockerized YouTube extraction behavior, including the required JavaScript runtime path.
- Larger-file tests only when justified by host resources and operational need.
- Separate cloud-to-local migration and local-to-cloud rollback rehearsals with a test bot.

For each large-file test, record source size, duration, codecs, dimensions, total
processing time, peak disk usage where available, result, and errors.

## Official references

- [Telegram Bot API documentation: Using a Local Bot API Server](https://core.telegram.org/bots/api#using-a-local-bot-api-server)
- [Telegram Bot API server source code](https://github.com/tdlib/telegram-bot-api)
