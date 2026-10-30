# P9-R2d HOSTKEY bot-only deployment — 2026-10-30

This records the completed owner-authorized controlled maintenance deployment on
2026-10-30. The documentation closeout uses that deployment evidence and performs
no new runtime inspection, SSH, Docker, configuration change or Telegram request.
The owner accepted unknown internal idle in the old build. Media downloads, LIVE
scenarios and diagnostics activation were outside the deployment scope.

## Preparation verified

- GitHub main `742bc105e923500fc0b22844bec2809c0c8fbc45`; post-merge CI 40952269982 success,
  checked before deployment and rechecked through GitHub during this documentation closeout.
- One VPS bot, no visible metadata/download/FFmpeg workers; no quarantine/cleanup/conflict markers
  in inspected logs. Internal idle remains unknown and accepted.
- Old source `f74dc6c933012b809d4e6dc33ed3f3bdadc39d34`: clean VPS source and 59 image file hashes
  matched.
- Old image `sha256:2f4a37b10a9a064e805200f2e57e79aa83ee221425c05e0aecef477ec0844f4a` pinned as
  `youtubedownloader-bot:rollback-p9-r2d-20261030`.
- New image `sha256:a8daabf3bd383740ede1138cfef0ec08802b2d2f27c409a5517daba7dffe350a`: 60 target
  hashes, 29 installed packages matching lock, EN/RU/ES catalogs verified offline with network
  disabled and no credentials.
- Private safe manifest retained on VPS. Existing project and both Compose files retained; permanent
  release override pins image ID. Rendered configuration differs only in bot image. Environment and
  resource limits unchanged; diagnostics defaults false.
- Docker 29.9.2 `stop --signal SIGTERM --timeout -1` verified on an isolated networkless Python
  process: graceful exit 0 after 12.07 seconds, beyond the usual 10-second timeout. Probe removed,
  no poller started.

## Deployment status

**Preflight PASS. TECHNICAL PASS**, checked at 2026-10-30 07:41:00 UTC (about 103 seconds after new
bot startup). **LIVE concurrency responsiveness: INCONCLUSIVE**. This is not P9-R2 LIVE acceptance.

- Old poller received SIGTERM at 07:39:00 UTC and exited 0 at 07:39:01.354 UTC. Old PID was absent;
  no visible owned workers remained. No SIGKILL was used.
- New bot started at 07:39:18.029 UTC, after confirmed old-process exit. New container
  `540665d0460c6e89f9700be63568a70aa401b12c2850fa76f392487e25bbb48c`: RUNNING, restart 0, OOM
  false, one Python bot process. Replacement used existing `youtubedownloader` project, both
  existing Compose files and the permanent release override with
  `--no-deps --no-build --pull never --force-recreate bot`.
- API container `69fdd93d5993de0e5d4af6d2098ff4639547e23318b56aa6ae024f94a7179749`: RUNNING,
  restart 0, OOM false; ID, image and volume mounts unchanged. No API state/volume operations
  performed.
- Exact environment comparison passed, including credentials compared privately without printing.
  Original `.env` and both Compose files have unchanged hashes. Bot mounts, network, restart policy
  and resource limits match baseline.
- Effective Settings: `DOWNLOAD_MAX_ACTIVE_REQUESTS=1`, Instagram/TikTok activation true,
  `APP_ENV=development`, `CONCURRENCY_DIAGNOSTICS=false`. Diagnostics variable remains absent from
  original environment; false is the verified effective default. No environment variable was added.
- Running-container source hashes match all 60 target files.
- Polling evidence: safe `platform=service, phase=polling, event=operation_started`; existing
  established bot-to-Local-API TCP connection; minimal `getMe` HTTP 200/ok and `getWebhookInfo` HTTP
  200/ok with no webhook. No polling failure/conflict events. Raw aiogram startup lines are
  intentionally suppressed by the source logging filter. No second getUpdates client was started.
  This verifies technical startup, not user-message delivery or LIVE acceptance.
- No new conflict/traceback/critical/error/quarantine/cleanup failure/delivery-unknown markers in
  inspected new-bot logs. Full retained old logs also passed the pre-stop safety-marker check.
- Private VPS evidence: release `releases/p9-r2d-742bc105` retains safe manifest, baseline
  comparisons, image verification, shutdown and post-deployment reports plus build/Compose logs and
  permanent image override. Future Compose operations must include this override; omitting it would
  select the older image from the retained base configuration. Rollback image is retained; rollback
  was not needed or tested.

## Limits and errors

The accepted maintenance risk includes interrupted in-flight user operations and stale pending
buttons; old internal idle was not proved. No new delivery claim follows from technical startup.
Media downloads and user LIVE scenarios performed: zero. Diagnostics activation: none.

An initial SSH login was rejected; the established deployment identity succeeded. An initial
verification expected unfiltered aiogram text and was corrected to the implemented safe-event
format; this was a verification-format issue, not a bot startup failure. Local Docker socket was
unavailable, so current MacBook container status could not be queried. No MacBook bot/API was
started and no local Docker daemon was started. No remote critical startup error was observed.

At the deployment checkpoint, local main remained clean at
`f74dc6c933012b809d4e6dc33ed3f3bdadc39d34`; all historical worktree registrations, including 19
prunable registrations, remain present. Deployment documentation is isolated on
`docs/p9-r2d-hostkey-deployment`. No commits or pushes were made during the runtime deployment
stage; the separately authorized documentation closeout publishes a docs-only commit and Draft PR.
Merge remains a separate owner decision.

## Documentation closeout

The docs-only closeout synchronizes this report, TASKS, ROADMAP, TESTING, the
operations entry point and development gates. Diff/Markdown structure, 136 internal
links/anchors, privacy and preservation checks passed before publication.
The Draft PR checks are the authority for its exact-head CI; they are separate from
[deployed-source CI #40952269982](https://github.com/ip52rus/social-video-downloader/actions/runs/40952269982).
No full local application suite is repeated for this documentation-only change.
No rollback rehearsal, user-message delivery, continuous uptime, broad reliability
or LIVE responsiveness result is inferred from these checks. Stop for independent
review after Draft PR publication and exact-head CI verification.
