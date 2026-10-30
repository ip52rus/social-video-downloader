# Local Telegram Bot API Server

## P9-R2d deployment checkpoint — 2026-10-30

HOSTKEY bot-only deployment of `742bc105`: **TECHNICAL PASS** at 07:41 UTC.
Effective `CONCURRENCY_DIAGNOSTICS=false`; API identity/state, configuration and
resource limits preserved. **LIVE concurrency responsiveness: INCONCLUSIVE**.
No media downloads or Telegram LIVE scenarios were performed for deployment.
[Evidence and limits](P9_R2D_DEPLOYMENT.md). This dated record supersedes the older
bot image checkpoint below. The docs-only closeout performs no runtime inspection.

## HOSTKEY VPS checkpoint 2026-10-28

**Canonical operations record, reviewed for D1 on 2026-10-29.** Source release
`f74dc6c933012b809d4e6dc33ed3f3bdadc39d34` (PR #83); post-merge
[CI #40333460016](https://github.com/ip52rus/social-video-downloader/actions/runs/40333460016)
SUCCESS was rechecked read-only on GitHub in D1. No SSH, Docker inspection or API call
was performed in D1; all runtime assertions below are dated saved evidence.

### Deployment topology and sole poller

HOSTKEY is the designated sole production poller. The saved cutover report at
**2026-10-28 13:16:49 UTC**, 277.6 seconds after bot startup, confirms:

| Component | Recorded state |
|---|---|
| VPS bot | RUNNING, restart 0, OOM false; one bot service container |
| VPS Local Bot API | RUNNING, restart 0, OOM false |
| Local MacBook bot and API | STOPPED; original containers/configuration/volumes/images retained |
| Telegram | polling start event; getMe HTTP 200, configured identity match; no observed conflict |
| Network | no published Docker ports; Local API reachable through Compose service DNS only |
| Environment | mode 0600; source clean; Phase 9C expected settings matched |

The local SSH-authentication blocker was resolved when the owner made the trusted key
available through the macOS agent. Docker-group access was also resolved before build.
No private key was transferred. A dedicated read-only GitHub deploy key was created on
VPS. Host address, SSH identity/key files and private inventory belong in protected
operator storage, not copy-paste credentials in this document.

Owner-supplied host inventory: Ubuntu 24.04.5 LTS, 2 vCPU, 4 GiB RAM, 2 GiB swap,
60 GB NVMe; Docker 29.9.2/Compose v5.6.1. UFW permits inbound SSH only. These are dated
inventory/preparation observations, not current capacity measurements. Published
Docker ports can bypass UFW; preserve the absence of `ports`, not merely a firewall rule.

VPS bot image:
`sha256:2f4a37b10a9a064e805200f2e57e79aa83ee221425c05e0aecef477ec0844f4a`.
API image remains the pinned source Compose digest
`sha256:5d743d5c93b9e50ba5d3bc438350d9d78c1368587723aebbf0e353032f0865d1`.
Image preparation verified 61 source-file hashes, locked dependencies and EN/RU/ES
catalogs without starting a poller; SHA is not inferred solely from a mutable image tag.

Compose project: `youtubedownloader`, services `bot` / `telegram-bot-api`.
Named volume: `youtubedownloader_telegram-bot-api-data`, mounted only for API state at
`/var/lib/telegram-bot-api`. Local and VPS engines have distinct volume instances;
a matching name does not mean shared storage. Do not inspect/copy their contents into Git.

### Effective configuration versus source defaults

- Local API server `TELEGRAM_LOCAL=1`; bot endpoint `http://telegram-bot-api:8081`.
- `DOWNLOAD_MAX_ACTIVE_REQUESTS=1` on VPS; repository default is 4.
- Instagram/TikTok enabled; repository flags default false. TikTok platform capacity
  remains 2, but the global working cap of 1 limits actual admitted heavy work.
- `APP_ENV=development` is retained intentionally: current Settings rejects Instagram
  enabled with production mode. This is an existing activation policy, not a statement
  that the physical VPS is a development host. Do not change it as documentation cleanup.
- Link interval 3 s, notice interval 5 s, total leases 128; Instagram/shared file
  536870912 B, request 1073741824 B, workspace 3221225472 B, free reserve 536870912 B.
- YouTube: file 2000000000 B, request 4294967296 B, workspace 8589934592 B, effective
  endpoint ceiling also applied. TikTok retains native 25 MiB/file and 180 s budget.
- aiogram custom-endpoint timeout 1800 s is not a guarantee of complete operation
  duration; platform upload/worker deadlines remain separate and unchanged.

Real env names are `TELEGRAM_BOT_TOKEN`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`.
Earlier informal BOT_TOKEN/API_ID/API_HASH names are not alternative Settings variables.
Unlisted variables in `.env` are not automatically passed into the container; see
[Phase 9C forwarding](PHASE9C_DOWNLOAD_PROTECTION.md#configuration).

### Completed local-to-VPS Local API transfer

Saved read-only summaries show the authorized sequence:

1. Confirm local bot stopped and no VPS poller started; retain protected config,
   previous images/tags and a pre-close stopped-state backup.
2. Start **only** the old local API for official administration. `deleteWebhook`
   with `drop_pending_updates=false`: HTTP 200/true at 13:05:54 UTC.
3. `close`: HTTP 200/true at 13:06:21 UTC, no automatic retry. Stop old API afterward;
   both local services STOPPED before closed-state copy.
4. Export closed bot state, verify archive/source integrity, transfer/import into
   the prepared VPS volume while both VPS services remain stopped. Archive hash and
   imported file verification matched; state and backups remain private.
5. Start VPS API, confirm configured bot identity, then the sole VPS bot/poller.
   Observe startup, restart/OOM, safe errors, settings and absence of polling conflict.

Saved source reports: `hostkey-preparation-20261028t115810z/status.json`,
`offline-image-verification.json` and
`cutover-20261028t130349z-380b6130/{delete-webhook-result,close-result,closed-state-verification,vps-import-result,vps-cutover-technical-verification,local-final-preservation}.json`
under the private migration root. All were available at D1; the conclusions above
are preserved here so those local folders are not a knowledge prerequisite. Do not
publish private manifests, credentials, state archives or bot-state filenames.

### Future updates and rollback gates

This is a runbook, **not authorization to run commands**. Before a bot-only update:
confirm target exact-head CI, current image/config/volume identity, one poller and a
safe maintenance/idle window. Retain actual running image under a rollback tag;
build/check exact clean source separately without a poller. Replace only bot using
prebuilt image and the existing Compose project, with `--no-deps --no-build --pull never`.
The old poller must exit before the new process starts. Preserve API/volume/env.
Check polling/state/restart/OOM and safe startup errors; only then hand off owner LIVE.

MacBook rollback tags retained at migration:
`youtubedownloader-bot:rollback-pre-hostkey-20261028t130349z` and
`aiogram/telegram-bot-api:rollback-pre-hostkey-20261028t130349z`.
The earlier local Phase 9C bot image is
`sha256:49a66a1191b906aeba5817c6c2b157b3c469485d85c988fdf07499ed76b0dfae`.
Retention was verified then; D1 did not re-query either Docker engine. Rollback was
not executed/rehearsed. Do not treat old local API state as current VPS state.

A same-VPS **bot-image** rollback preserves the active API state and replaces only bot,
after stopping its failed process. Returning service to MacBook is a separate Local
API move: quiesce VPS bot, preserve current state/config, obtain successful official
API close on the active instance, stop it, transfer/verify the newly closed state,
then start destination API and exactly one poller. Do not start the old MacBook
containers casually or substitute the pre-migration snapshot for current state.
At 429, indeterminate close/copy, checksum mismatch, unknown worker ownership or
concurrent poller: STOP; no automatic retry, rollback guessing or volume overwrite.
Local-to-cloud rollback is a distinct unrehearsed procedure, not `close` alone.

### Limits and next verification

The technical record did not initiate media downloads. Owner later reports normal
TikTok works on HOSTKEY; this is narrow owner functional evidence, without a measured
multi-platform/server load matrix. No new VPS YouTube/Instagram 5/5 rerun is inferred.
The 2026-10-28 5/5 Phase 9C acceptance was explicitly **local**. No fresh production
health, global singleton guarantee across unknown hosts, restart/recovery/load/near-2 GB
or tested reverse migration is asserted. See [testing](TESTING.md#checkpoint-2026-10-29).

The remaining sections preserve general setup and earlier local/cloud evidence.
Their old readiness statements do not mean the HOSTKEY transfer is still pending.

## Purpose

Telegram's cloud Bot API has a much lower upload limit for bot file uploads than a
self-hosted Local Bot API Server. This project can use either Telegram's cloud Bot API
or a configured Bot API-compatible endpoint.

Leave `TELEGRAM_API_BASE_URL` unset to use the cloud Bot API. Set it to a private Local
Bot API endpoint to use local-server mode.

The Local Bot API Server is an infrastructure option. It is not, by itself, proof that
the project is production-ready or that every large video will upload successfully.

## Verified project state

The following earlier local facts were verified at their recorded stage; current
deployment is the dated HOSTKEY checkpoint above:

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
