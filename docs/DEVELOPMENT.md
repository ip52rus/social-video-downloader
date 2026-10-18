# Development Workflow

## Source of truth
During active development, the local repository is the primary working state. GitHub is the synchronized remote history and checkpoint after a verified stage. Before work, inspect the current branch and working tree, understand any unrelated local changes, and preserve them.

After a stage is implemented and verified, synchronize the remote history by committing and pushing the reviewed local result, then confirm the GitHub branch and CI state match the intended change.

## Stage workflow
1. Read the relevant roadmap, task decomposition, architecture, testing guidance, and applicable agent rules before implementation.
2. Confirm the current stage, its acceptance criteria, dependencies, and outstanding checks. Do not skip an unmet roadmap gate without explicitly documenting the reason and obtaining a decision where needed.
3. Make a small, focused local implementation or configuration change on an appropriate branch.
4. Synchronize documentation with the verified implementation state. Update `docs/TASKS.md` after every completed stage and before starting the next stage. Update `docs/ROADMAP.md` when phase status, gates, dependencies, scope, or the next step changes. Update any other document made inaccurate by the change.
5. Run the relevant tests and quality checks. Perform external-platform or end-to-end checks when required by the acceptance criteria.
6. Review implementation results and distinguish verified behavior from assumptions and untested cases.
7. Review the exact diff, changed-file list, test results, documentation consistency, and security implications.
8. Commit the coherent change atomically with a Conventional Commit message.
9. Push the branch, then verify the GitHub branch state and CI result.

## Documentation requirements
- Documentation updates are part of the stage's definition of done.
- A task may be marked complete only when its acceptance criteria have evidence supporting completion.
- Keep partial work unchecked and describe the checks still outstanding.
- Identify the type and scope of verification: unit tests, deterministic integration tests, real external-platform tests, or Telegram end-to-end tests.
- For external-platform tests, record the scope of the evidence and distinguish application regressions from platform changes or transient network failures.
- Do not claim broad reliability based on one successful URL or one happy-path test.
- If a stage is not complete, preserve its in-progress status and state the remaining acceptance criteria.
- Do not defer routine documentation synchronization to an unspecified future cleanup task.

## Branches
Use `feature/name`, `fix/name`, `refactor/name`, or `docs/name` for non-trivial work.

## Commits
Use Conventional Commit prefixes. One coherent change per commit.

## Pre-commit checklist
- Relevant tests and checks pass, or outstanding failures are explicitly documented.
- Diff and changed-file list reviewed.
- No secrets or personal data.
- No generated files or accidental media.
- `docs/TASKS.md` and `docs/ROADMAP.md` accurately reflect the verified progress.
- Other affected documentation is updated.
- Commit message describes the actual change.

## Synchronization
After each commit, verify the commit SHA and branch state. After each push, verify the remote branch and CI. Do not overwrite unrelated local work while synchronizing.

## Controlled main-bot Reel smoke

PR #53 is merged. The user chose the existing main Telegram bot for one approved public
Reel smoke and accepted a short planned bot-container restart. No separate bot,
standalone container, watchdog framework or alternate poller is part of this plan.

Compose forwards `INSTAGRAM_TELEGRAM_ENABLED: ${INSTAGRAM_TELEGRAM_ENABLED:-false}`
only to bot. An absent flag stays false. Compose already sets `APP_ENV=development`;
the existing Settings enabled+production guard is retained. Local Bot API routing,
credentials, dependencies and volumes stay unchanged. Do not edit a real `.env` as
part of this PR or run deployment commands during configuration preparation.

After independent PR review/merge, the separately performed deployment procedure is:

1. Confirm no active user download; plan the short main-bot interruption.
2. Update server source to reviewed main.
3. Set `INSTAGRAM_TELEGRAM_ENABLED=true` in the existing protected server environment.
4. Rebuild/recreate only bot using `docker compose up -d --build --no-deps bot`.
5. Confirm normal polling and YouTube behavior before the Reel smoke.
6. Submit exactly one explicitly approved public Reel to the existing main bot.
7. Inspect errors, file size and actual Telegram client playback; do not retry an ambiguous send.
8. If rollback is needed, restore the flag to false and recreate only bot with `--no-deps`.

Do not restart/recreate telegram-bot-api or modify its volume. The 25 MiB Reel limit
and cooperative thread-cancellation limitation remain; no hard whole-request watchdog
or production-reliability guarantee is introduced. `/p/` and carousel routing stay pending.
After PR #54, the separately authorized bot-only deployment and one canonical-Reel smoke
passed. The user confirmed delivery, playback, orientation and sound; temporary files
were cleaned and Local Bot API was unchanged. Exact size/time were not recorded. The
initial share URL was rejected on `psln`. PR #55 subsequently merged at
`0a87beeaa8acb302b74e980946778608856b13f6` and was separately deployed to the existing
bot. The user confirmed delivery, playback, orientation and sound for the full Reel
share URL with `utm_source` and `psln`; size and processing time were not recorded.
This is one Reel case, not `/p/` or album validation or general Instagram reliability.
No further restart or live test is authorized by these historical records.

## Opt-in Instagram /p/ and album routing

The existing `INSTAGRAM_TELEGRAM_ENABLED` opt-in is reused: no second bot,
new token, Compose service or polling loop. PR #56 passed final independent review,
merged at `20d14441a2b7ea906ed2a0abc83679d25d9f2d32` and was separately deployed
by replacing only bot. Startup/polling and source identity passed; Local Bot API was
unchanged. Real `/p/` and album delivery/playback remain unverified.

Accepted public `/p/` publication links pass through the conservative carousel
selection policy. The offline share-link follow-up aligns `/p/` with Reels: irrelevant
query keys, bare share flags and ordinary fragments are stripped. Known item selectors
are rejected case-insensitively after percent decoding in query keys and selector-shaped
fragments, before extraction. Malformed references and the 32-field bound remain blocked.
A single-video post must be positively confirmed by the source
adapter and existing video validators; it consumes the same verified snapshot in the
bounded single-file worker. BLOCKED never authorizes fallback or another extraction.
The adapter checks source `carousel_media` before mapping: a present value must be a
complete flat list and must survive mapping with the same count, identities and order.
Malformed/nested collections block with INVALID_METADATA; an empty list has NO_VIDEOS.
An absent field permits positive single-video inspection; present null is not absence.
A READY video carousel goes through the bounded
multi-file acquisition and Telegram delivery; PHOTOs are skipped only after
positive classification, UNKNOWN items block everything, and no video is silently
truncated. Initial limits are 10 selected videos, 25 MiB/file and 100 MiB total.
One active Instagram operation per dispatcher; no automatic retry after a
possibly delivered album.

The initial inspection uses the existing cooperative guard and cancellation event.
Its 300-second operation window starts before extraction and is not restarted for
acquisition, preparation or upload; the single-file 180-second work and 120-second
send caps remain. Pending native/network calls may delay cancellation, but the slot
and workspace remain owned until real worker completion. Do not replace this with
thread abandonment or claim hard native-call termination.

Do not rebuild/restart either running container, edit server environment or
perform real external calls as part of this share-link fix. It requires independent
review and its own merge/deployment decision. A separately approved
bot-only rollout/smoke may follow review and tests, with full-client album
playback checked before broader use.
