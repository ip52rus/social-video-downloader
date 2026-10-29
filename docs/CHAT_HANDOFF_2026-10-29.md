# Social Video Downloader — Chat Handoff 2026-10-29

This is a self-contained checkpoint for a new ChatGPT conversation and Codex agent
without the old chat or private research folders. Read it with [AGENTS.md](../AGENTS.md).
It preserves the state at **29 October 2026**, not a permanent assertion of current
production health. Recheck authorized source/CI facts when resuming; do not connect
to production or repeat external experiments merely to refresh this document.

## 1. Name, purpose and concept

Social Video Downloader is a Telegram-first service: send a supported public media
link, make only useful choices, receive the file in the chat. The product is a
working bounded multi-platform MVP, not a universal downloader. Editing video in
Telegram is out of scope. The owner decides product/stage boundaries; ChatGPT helps
plan and assess evidence; Codex implements only the authorized task. Tests, LIVE,
review, merge and deployment are distinct gates. Passing one never authorizes another.

## 2. Repository and stack

Repository: [ip52rus/social-video-downloader](https://github.com/ip52rus/social-video-downloader).
Source checkpoint main: `f74dc6c933012b809d4e6dc33ed3f3bdadc39d34`, PR #83 merge.
Python >=3.13,<3.14, uv/uv.lock, aiogram 3 + I18n/gettext/Babel, yt-dlp with yt-dlp-ejs,
stdlib native TikTok HTTP, FFmpeg/ffprobe and pinned Deno 2.9.7. Hatchling packages PO/MO
resources; pytest/pytest-asyncio/Ruff are dev tools. Dockerfile uses python:3.13-slim,
Deno stage, apt FFmpeg and `/opt/venv/bin/python bot.py`. Source uses locked dependency
sync; existing Dockerfile also contains fallbacks, so do not claim perfect hermetic
builds or change it in a docs task. Snapshot image verification reported aiogram 3.31.0,
Babel 2.18.0, yt-dlp2026.8.19; those are dated installed versions, not future update policy.

## 3. Product decisions and commercial model

Current service is free. Capability-driven UX: minimum actions, platform-specific
meaningful choices, consistent localized messages. No mandatory language selection,
user-language database, ads/paywall or membership check exists. Future commercial
options remain design choices, not approved revenue features. Only free self-hosted
OSS with reviewed commercial-compatible licensing is eligible for new Short Drama
mechanisms; no paid/freemium API, SaaS, closed component or remote downloader service.
Software license rights do not grant platform access or rights to redistribute content.

## 4. User journey and commands

One short /start lists only enabled platforms. A link is validated and admitted
before heavy metadata. YouTube may show Video/Audio then available video quality;
audio normally needs no quality step, and trivial choices download directly.
Instagram/TikTok normally download directly; Instagram img_index selection may offer
all videos or the video at original position N. /cancel cancels only an idle waiting
choice; it never promises to stop an executing worker. Repeated links receive a
localized active/rate/busy refusal before extraction; repeated notices are throttled.
A completed safely cleaned request permits a new one. No queue is created.

YouTube uses the same message as choice/status card. Success means confirmed delivery;
unknown delivery never becomes success/failure and never causes automatic resend.
Telegram edit failure must not restart media. Restart loses in-memory interactions:
old buttons refuse safely with localized next action, but may remain visually stale.

## 5. Architecture and ownership

Domain models/errors/URLs and `services/download.py` stay independent of Telegram.
Provider interface lives in `providers/base.py`; providers YouTube/Instagram/TikTok
supply media-specific behavior. `handlers.py` assembles Telegram routes and platform
adapters. `download_protection.py` owns single-process cross-platform admission;
`telegram_interactions.py` and `telegram_instagram_interactions.py` validate pending
choices; `telegram_i18n.py` owns request presentation context. No Redis/database or
cross-host distributed lease exists.

YouTube metadata runs in `infrastructure/youtube_metadata_worker.py` with bounded
snapshot IPC, separate finite planning executor and `services/youtube_metadata.py`
cache. Phase 9C acquisition is owned POSIX work in `youtube_bounded.py` with
`youtube_write_budget.py`; media preparation/probe executor work drains through
cancellation. Instagram uses isolated metadata/acquisition and immutable parent/child
manifest contracts. TikTok uses `tiktok_native.py`, public-page parser and short-link
resolver inside an owned worker process group. Never delete a workspace while its
worker may still own it; cleanup uncertainty quarantines work and retains admission.
See [architecture](ARCHITECTURE.md) for detailed existing contracts.

## 6. Implemented platforms and defaults

YouTube is in the default registry. Instagram/TikTok Telegram activation is explicit
and defaults false in source config. The saved HOSTKEY environment enabled both;
this is not an invitation to change defaults. `APP_ENV=development` is intentionally
retained because Instagram enabled+production mode is rejected by current Settings.
Physical production location and APP_ENV are separate concepts. New platform/provider
work remains gated; Short Drama is not part of ordinary TikTok support.

## 7. YouTube state

Normal videos and Shorts have narrow historical download/delivery evidence. Playlist
context on a watch URL does not download a playlist. Choices use stable quality IDs
and the existing quality-tier policy; high is not unlimited 4K/8K. Video-only technical
capability is hidden from the normal UI; audio delivers verified M4A/AAC when selected.
Media preparation prefers H.264/AAC MP4 passthrough, verified stream-copy remux when
compatible, then existing conversion fallback. Do not confuse this YouTube pipeline
with Instagram/TikTok passthrough-only restrictions.

Phase 9B fixed initial synchronous metadata/planning event-loop blocking. Metadata
cache retains 180 s TTL, 32 entries, original snapshot age and consume-on-download.
Worker budget60s including cleanup (55s extraction/spawn/IPC + reserved cleanup),
request8KiB/response2MiB, depth32/nodes100000/decoded8MiB per snapshot,64MiB cache.
These are not a hard RSS ceiling on yt-dlp/Deno. LIVE concurrency responsiveness
remains INCONCLUSIVE from a single attempt, not evidence the old defect returned.
Phase 9C separately bounds actual acquisition/merge/preparation writes and worker drain.
Intermittent HTTP403 and broader platform/failure stability remain open.

## 8. Instagram state

Public Reels, public single-video /p/, guarded carousel video delivery and explicit
img_index choices are implemented. Photos are never downloaded/delivered. Source
positions include photos. Missing/conflicting manifest, parent identity, availability
or unknown child kind fails closed; no fallback can silently substitute a single item.
Ten-video ceiling remains. Compatible MP4 with optional audio is supported without
inventing audio or changing codecs. Existing production activation guard is retained.
Historical narrow LIVE: Reel, one single post, three-video silent album, and both
all/selected choices on one two-video post. Phase 9C owner additionally accepted one
Instagram file >25MiB. No claim of all carousels, mixed-photo delivery, clients or limits.
The old fixed 25MiB gates were replaced, not made unlimited; common technical caps apply.

## 9. Ordinary TikTok state

Native public-page extractor supports strict `/@author/video/id` and protected vm/vt
share references (single alphanumeric token, no query/fragment). Expansion occurs only
inside the admitted worker. Full-page metadata identity and supported CDN/HTTPS/DNS/
IP/TLS/framing restrictions apply; no separate streams or uncontrolled retries.
Native caps remain25MiB/file,50MiB received total,180 s acquisition,128MiB workspace;
Telegram upload has its own bounded stage. Phase 9C did not remove these native caps.

Historical media403/metadata429/missing-state failures are retained. Five October25
failures had phase download_prepare/category metadata_unavailable; later diagnostics
identified three missing_public_state responses HTTP200/~1.5KiB, no media GET.
Owner observed failure through Kazakhstan VPN and success after Netherlands exit;
network dependence is observed, causal mechanism and all regional IP behavior unknown.
Owner later confirms ordinary TikTok downloads on HOSTKEY; this is narrow functional
confirmation, not universal reliability. Keep PR81 allowlisted diagnostics intact.

## 10. Deferred Short Drama

**DEFERRED / SERVER RESOLVER BLOCKED / RESEARCH PRESERVED.**
Read [canonical research](research/TIKTOK_SHORT_DRAMA.md) only when assigned this work.
Target drama7698874781395096594/episode1 maps explicitly to item/video7698876141532237070,
author fatefultwistus, API duration113 s. Official authorized desktop Chrome returned
filled item_list playback metadata (H.264/MP4,12,704,993B). Anonymous episode calls found
the correct target but no playback; some recorded IsPreview=true. Browser v16/v19/blob
resources are not proven identical. No isolated complete media file was obtained.
S1:86 offline PASS/Ruff, HTTP0; S2:15 offline checks/Ruff, HTTP0, NO-GO another anonymous
LIVE on current evidence. Need for login is UNKNOWN. This is not global impossibility.

A future narrow JSON resolver could reuse the existing protected downloader/worker;
source retrieval is the missing proof. No broad API guessing, signing, session export,
paid server or new downloader from scratch. Current native GET has no Range and
expects200; observed browser206 does not prove plain-GET compatibility. Do not weaken
security/status checks. No active monitoring or reopening until separate owner decision.

## 11. Telegram and Local Bot API

The bot uses aiogram long polling. Custom `TELEGRAM_API_BASE_URL` selects local-client
mode; `TELEGRAM_LOCAL=1` belongs to the Local API server container. In Compose the bot
calls `http://telegram-bot-api:8081`; API state is a persistent named volume, not source.
Source environment names: TELEGRAM_BOT_TOKEN, TELEGRAM_API_ID, TELEGRAM_API_HASH;
never paste values into chat/Git/logs. A historical 414.7MB playable transfer is not
near-2GB support. Source policy caps Local API files at2,000,000,000B, cloud50,000,000B.
Close is for Local API instance moves, not a complete local-to-cloud rollback recipe.
See [official-procedure project record](LOCAL_BOT_API.md).

## 12. Docker

Two Compose services, bot and telegram-bot-api; API image is pinned10.3 digest and
state volume mounted at /var/lib/telegram-bot-api. No source `ports` publication; expose
is internal. Keep API private: UFW alone does not protect Docker-published ports.
Bot-only updates must preserve API image/container/volume/env and use a preverified
image without rebuilding dependencies during replacement. Old poller exits first.
Do not run Docker actions as part of documentation, research or CI acceptance.

## 13. HOSTKEY VPS

Owner inventory: Ubuntu 24.04.5LTS,2 vCPU,4 GiB RAM,2 GiB swap,60 GB NVMe; Docker 29.9.2,
Compose 5.6.1. Trusted key-based SSH and docker-group access were established; earlier
SSH-agent failure was resolved. Separate read-only GitHub deploy key created on VPS;
MacBook private key not transferred. Secret env transferred/adapted through SSH,
mode0600. Addresses, key locations and private operator paths belong in protected
inventory. D1 did not SSH, inspect runtime, change server config or run API requests.

## 14. Production checkpoint and sole poller

Saved cutover report: **TECHNICAL PASS, 2026-10-28 13:16:49 UTC**. VPS bot/API running,
restart0/OOMfalse, one bot container, polling started, getMe identity verified,
no polling conflicts/critical API errors observed in that window. Bot image
`sha256:2f4a37b10a9a064e805200f2e57e79aa83ee221425c05e0aecef477ec0844f4a`;
source hashes checked against f74dc6c. Compose project youtubedownloader, named volume
youtubedownloader_telegram-bot-api-data. Distinct host volumes are not shared storage.

MacBook bot and API **retained STOPPED** after successful deleteWebhook with
pending updates preserved → close200/true → stop old API → verify/transfer closed
state → start VPS API → sole VPS poller. Config/volume/backups/images/rollback tags
retained. No reverse migration/rollback rehearsal performed. Current health after
that record is not independently reverified; sole-poller status is the designated
and checked scope, not proof no unknown host anywhere uses the token.
Do not start MacBook rollback containers without a controlled move of current API state.

## 15. Phase 9C download protection

One unfinished Telegram user request across platforms starts before expensive
metadata. A waiting choice reserves the user/total lease, not a global worker slot.
Validated callbacks acquire work atomically; Busy preserves the choice and avoids
extraction/consume. TTL15 min is not renewed; /cancel invalidates only idle choice.
Worker/delivery/cleanup or quarantine retains resources until safely resolved.
No queue. Leases are process-local and lost on restart; no multi-instance coordination.
First rejected link gets a response; repeated notices throttle to5s, link cooldown3s.
Bounded total leases128, refusal bookkeeping4096; these are not persistent user records.

Source global working cap4, HOSTKEY cap**1**. Instagram/shared file512MiB,request1GiB,
workspace3GiB,free reserve512MiB. YouTube file2,000,000,000B,request4 GiB,workspace8GiB,
endpoint cap also applies. Actual streamed bytes/writes include absent/false length,
partials, split streams, merge/FFmpeg output. Sticky budget refusal does not retry.
Admission conservatively reserves full workspace/free-space budgets. TikTok retains
stricter native limits. Defaults/validation/Compose forwarding are in
[Phase 9C policy](PHASE9C_DOWNLOAD_PROTECTION.md). Unlisted env names are not forwarded
merely by adding them to .env; new configuration changes need their own approval.

## 16. Phase 8 localization and UX

E1a gettext/aiogram I18n/Babel foundation; E1b EN/RU/ES messages/buttons/captions;
E2 format→quality text+keyboard in same message; E3 noninteractive publication →
confirmed message binding → interactive edit; E4 one greeting/evidence-based terminal
states/consumed UI retirement; E5 focused copy and final audit; PR82 owner acceptance.
New messages use Telegram sender language_code, region-normalized locale and English
fallback for unsupported/malformed/missing values. Valid callbacks retain original
locale after ownership/chat/message/TTL validation; invalid ones use current sender.
No inference of actual Telegram-client UI language, /language, personal preference DB
or external translator. ContextVar isolation restores on cancellation/exceptions.
PO/MO and wheel resources are tested. RU owner LIVE, EN/ES automated-only accepted gap.

## 17. Important completed PRs

| PR | Purpose | Merge/source checkpoint |
|---|---|---|
| [#68](https://github.com/ip52rus/social-video-downloader/pull/68) | fixed-field operational events | merged |
| [#69](https://github.com/ip52rus/social-video-downloader/pull/69), [#70](https://github.com/ip52rus/social-video-downloader/pull/70), [#71](https://github.com/ip52rus/social-video-downloader/pull/71) | parent identity, Item Selection, narrow LIVE docs | merged |
| [#72](https://github.com/ip52rus/social-video-downloader/pull/72) | drain owned YouTube file work | `01ffe0e` |
| [#73](https://github.com/ip52rus/social-video-downloader/pull/73), [#74](https://github.com/ip52rus/social-video-downloader/pull/74) | bounded metadata isolation, evidence docs | `04a07ba` for #73; both merged |
| [#75](https://github.com/ip52rus/social-video-downloader/pull/75), [#76](https://github.com/ip52rus/social-video-downloader/pull/76) | i18n foundation, activation | `efb4f324`, `08d726d` |
| [#77](https://github.com/ip52rus/social-video-downloader/pull/77), [#78](https://github.com/ip52rus/social-video-downloader/pull/78) | E2/E3 | `b7462f8`, `bbfdf85` |
| [#79](https://github.com/ip52rus/social-video-downloader/pull/79), [#80](https://github.com/ip52rus/social-video-downloader/pull/80) | E4/E5 | `177f11e`, `082986e` |
| [#81](https://github.com/ip52rus/social-video-downloader/pull/81) | allowlisted TikTok refusal diagnostics | `b55a019` |
| [#82](https://github.com/ip52rus/social-video-downloader/pull/82) | Phase 8 MVP acceptance | `aa5ecf9` |
| [#83](https://github.com/ip52rus/social-video-downloader/pull/83) | Phase 9C + independent review corrections | `f74dc6c` |

PR83 includes 56222a9 initial work and 349d20e review fixes. Not all historical Drafts
are merged: old discontinued TikTok harness #59 is not our production provider.
[PR84](https://github.com/ip52rus/social-video-downloader/pull/84) remains OPEN/Draft at
D1 audit, head b5bfe0ffcf9b280c781a724ad59a2e1667b0c717, docs-only local9C closeout.
D1 overlaps its four files and extends the checkpoint; neither PR is merged/closed by
D1. Reviewer/owner must reconcile ordering before merge, not cherry-pick blindly.

## 18. HEAD and evidence refresh

Main was clean on f74dc6c and matched GitHub refs/heads/main during D1 read-only audit.
D1 lives in a separate docs branch/worktree; its exact HEAD/CI is in the PR, avoiding
self-referential commit hashes in this document. Source baseline is not changed by a
new docs commit. Check current branch/HEAD/status/remote PR before resuming; do not
reset/restore/fetch into main or infer uncommitted work from GitHub.

## 19. Git/worktree incidents

At D1 start152 tracked main files matched S1/S2, checkout clean,19 registrations
reported `prunable gitdir file points to non-existent location`. Owner accepts their
unchanged state; no claim all19 come from known incidents. Earlier damaged TikTok
worktrees have private preservation archives/manifests; untracked/ignored loss and
causes remain UNKNOWN. No prune/remove/repair/gc/cleanup/restoration is authorized.
New worktrees must be in permanent storage; never /tmp or /private/tmp. D1 adds one
explicit permanent docs worktree without altering prior entries. Check existing
registrations, main files, private env/IDE fingerprints before/after stages; stop for
new damage or unexpected changes. No archive or unrelated worktree may be modified.

## 20. Tests and CI

GitHub Actions runs Python 3.13, uv sync --locked, Ruff lint/format, apt FFmpeg and full
pytest on PRs. Live YouTube tests are opt-in and skipped without explicit variables.
Baseline post-merge CI40333460016 is SUCCESS on exact f74dc6c (rechecked D1). Historical
focused/full counts belong to their stage, not a reconstructed current total. See
[TESTING](TESTING.md) for counts and evidence limits. Unit, deterministic real-FFmpeg,
external-platform smoke, Telegram end-to-end, deployment and owner acceptance differ.
D1 is docs-only: link/anchor/diff/privacy/scope checks, no repeated local full pytest;
exact docs-head CI required before handoff. Synthetic Short Drama tests do not prove
remote acquisition, decoding, rights or server availability.

## 21. Confirmed LIVE evidence

- Phase 9B: one 2026-10-23 owner two-account functional smoke PASS; metadata/options and
  expected stale notification. Callback/metadata overlap/latency unmeasured, hence
  responsiveness INCONCLUSIVE. Observed5.174s was whole metadata operation, not latency.
- Phase 8: E3 owner PASS without supplied case/client/language counts; E4 one short
  greeting, available-platform list, playable YouTube and sent card without old buttons.
  Final owner acceptance covers YouTube selection/delivery/card, one Instagram Reel,
  shared UX and TikTok in the working network. RU only LIVE; historical carousel cases
  retained separately, not repeated E5 acceptance of all shapes.
- Phase 9C local technical PASS 2026-10-26; owner local LIVE 2026-10-28 **5/5 PASS**:
  duplicate during waiting choice, /cancel choice, playable YouTube, duplicate during
  active download, playable Instagram >25MiB. Owner report, not an agent retest.
- HOSTKEY migration TECHNICAL PASS 2026-10-28; no agent media tests. Owner later reports
  ordinary TikTok works there. Do not relocate the local 5/5 acceptance to VPS.

Confirmed cases need not be repeated without a concrete regression/acceptance reason.
No client, size, timing or platform matrix is invented where owner did not supply it.

## 22. Unfinished reliability checks

Phase 9 OPEN: measured LIVE concurrency responsiveness; network/API/upload failures;
bot/API restart, worker drain and quarantine handling; reverse migration/rollback;
disk/RAM/CPU/load; additional clients; long/near-limit files. No crash-safe persistent
request/ownership recovery or distributed singleton mechanism. Cleanup and delivery
fault contracts have offline evidence, not broad operational rehearsal. Persistent
workers or uncertain delivery cannot be “fixed” by deleting directories/retrying.

## 23. Channel/group membership

Membership enforcement is not implemented and not required during core product work.
Do not add getChatMember checks, required channel joins, settings or access prompts
under a reliability/docs task. Future gate belongs to Phase 10 product/design approval.

## 24. Future monetization and analytics

Phase 10 may investigate modular advertising, optional paid/free models and membership;
no provider-coupled ads, billing infrastructure or plan is approved. Phase 4 analytics
backlog is privacy-conscious product/technical aggregates, not viewing history.
No URLs/titles/authors/usernames/chat text or unnecessary identifiers; no database,
Redis, Kafka, SaaS or storage provider is selected. >Telegram-limit storage/link fallback
is a future design direction only, not S3/R2 commitment or >2GB capability.

## 25. Main technical risks

Upstream extraction/schema/network/IP changes; signed-source expiry/binding; live
metadata responsiveness not measured; uncertain upload confirmations; hung external
work and quarantine; in-memory state lost on restart; visually stale buttons; limited
VPS RAM/disk; configuration drift; client/codec variation; untested reverse Local API
move; credential leakage; content rights and platform terms. Do not turn a narrow
successful file/browser observation into a universal reliability/legal claim.

## 26. Changes forbidden without scope

No merge/deployment, SSH/server config, Docker restart/cleanup, .env/key/token/session
access/transfer, new production poller, LIVE download, cookie import/login automation,
DRM/payment/CAPTCHA bypass, endpoint guessing, scope expansion or destructive Git.
Keep Phase 9C byte/time/disk/admission/cleanup safeguards. Do not change format/quality
or activation policy to make a test pass. Existing explicit session authorization
persists, but documentation/history is never a standing operational permission.

## 27. Canonical document map

[PROJECT](PROJECT.md): product/current boundary; [ARCHITECTURE](ARCHITECTURE.md): code
contracts; [ROADMAP](ROADMAP.md)/[TASKS](TASKS.md): stages and verified tasks;
[DEVELOPMENT](DEVELOPMENT.md): workflow/historical implementation;
[TESTING](TESTING.md): dated evidence; [SECURITY](SECURITY.md): privacy/guards;
[LOCAL_BOT_API](LOCAL_BOT_API.md): setup, HOSTKEY, update/rollback boundaries;
[PHASE9C_DOWNLOAD_PROTECTION](PHASE9C_DOWNLOAD_PROTECTION.md): exact limits;
[INTERNATIONALIZATION](INTERNATIONALIZATION.md)/[TRANSLATIONS](TRANSLATIONS.md): locale
contracts/copy; [PHASE8_UX_ACCEPTANCE](PHASE8_UX_ACCEPTANCE.md): MVP acceptance;
[Short Drama](research/TIKTOK_SHORT_DRAMA.md): deferred complete R&D;
[CHANGELOG](../CHANGELOG.md): verified change history. Historical Phase 5/6 documents
remain useful stage records, not standalone current operational instructions.

## 28. NEXT DEVELOPMENT STAGE

**Phase 9 — remaining Production Reliability; first unclosed evidence gate: measured
LIVE callback concurrency responsiveness from Phase 9B.** This is the retained open
gate in ROADMAP/TASKS, not a newly invented Phase 9D or permission to start it. Then
scope network/upload, restart/recovery, cleanup, resources/load and rollback work;
no strict new ordering beyond owner approval is inferred. Membership/monetization,
analytics, more providers and Short Drama remain deferred.

Dependencies: accept/reconcile D1 and overlapping docs PR84; retain reviewed f74dc6c
behavior, current single-poller topology and Phase 9C cap1; obtain separate approval
for any current production read-only checks, LIVE or configuration change. Completed
prerequisites: metadata isolation/offline tests/CI, Phase 8 accepted UX, Phase 9C local
5/5 and dated HOSTKEY technical startup. These do not close this responsiveness gate.

Minimal next scope: first review existing focused tests and design a bounded
observation protocol that proves metadata/callback overlap and measures latency
without triggering media twice or weakening admission. A previously pending choice
may legitimately receive Busy while another user's metadata holds the sole worker;
measure callback handling, not successful admission. Agree latency criterion before
LIVE. No worker/core rewrite, queue, rate-cap increase or broad test campaign.

PASS: known overlapping window, measured callback latency within the preregistered
owner-approved criterion, expected Busy/stale policy, no duplicate download or lease
leak; separate evidence for each claim. FAIL: reproduced blocking/ownership/delivery
regression or criterion breach, then narrowly diagnose. INCONCLUSIVE: overlap or
measurement not demonstrated. STOP: unexpected production health/poller, active work
at risk, secrets, quota/access issue, new Git damage or scope/budget overrun.

Tests: existing metadata/callback/admission/TTL/pre-binding/cancellation suites first;
add synthetic overlap/fault regression only for a demonstrated gap. Ruff/diff/privacy
and exact-head full CI for a code fix; no repeated full local suite without reason.
Any real Telegram/platform probe needs **separate LIVE authorization**; this handoff
is not that permission. Prefer small PRs: (1) protocol/evidence documentation, (2) a
focused fix only if confirmed, (3) authorized observation report. If no code issue,
no speculative fix PR is needed. Broader recovery/load gates remain separate.

## 29. Immediate task for the next Codex agent

Wait for owner acceptance/instruction; do not start automatically. Read the canonical
order, verify checkout/branch and the accepted19 records without repair, then state
that the next retained main gate is Phase 9 responsiveness/reliability. Prepare only
the specifically authorized protocol/audit or targeted fix. Keep owner LIVE cases,
CI and server health evidence separate. Do not resume Short Drama or operate HOSTKEY
just because the new chat has no context. If needed source reports are missing,
label SOURCE NOT AVAILABLE; never reconstruct raw private data from guesses.

## 30. Instructions for a new ChatGPT conversation

Use this handoff as the dated starting point, source code/CI as current implementation
authority and the owner as scope authority. Ask which narrow Phase 9 task is authorized
before directing implementation/LIVE. Preserve accepted MVP limitations and unclosed
reliability gates. Treat official Chrome Short Drama success as new positive evidence
with an unresolved server gap, not a reason to replay old probes. Never request
credentials or full signed URLs. Explain discrepancies and evidence categories
clearly; do not label unknowns PASS or copy old tool permissions into a new stage.
The success criterion is safe continuity from Git docs, not dependence on old chats.
