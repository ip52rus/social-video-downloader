# Project Definition

## Product and authority

Social Video Downloader is a free Telegram-first media downloader, repository
[ip52rus/social-video-downloader](https://github.com/ip52rus/social-video-downloader).
Users submit supported public links and receive verified media in the same chat.
Video editing inside Telegram is out of scope. The owner approves stage boundaries;
implementation, LIVE, merge and deployment are distinct gates in [AGENTS.md](../AGENTS.md).

Current documentation checkpoint: **2026-11-03**. **Deployed, not pre-launch.** The Telegram bot [@GetThatVideo_bot](https://t.me/GetThatVideo_bot) is running on HOSTKEY VPS under Docker Compose with an internal Local Telegram Bot API Server. The last saved P9-R4 technical postflight was **PASS on 2026-10-31 at 08:23:43 UTC**, source `1df3fc129c6880555bc021cbbade74c6ce1fe14a` (merged [PR #89](https://github.com/ip52rus/social-video-downloader/pull/89), [post-merge CI SUCCESS](https://github.com/ip52rus/social-video-downloader/actions/runs/41067317374)), image `sha256:f93a3f497ad23761397f557bb849b73eff85e8c57665c9efad8b40d244aedde3` (linux/amd64). Previous image and rollback tag are retained. One poller, bot/API RUNNING, restart 0/OOM false were recorded; MacBook bot/API containers remain stopped. **This is a dated checkpoint, not a fresh 2026-11-03 server-health check.**

## Current accepted product

- **Phase 8 MVP — ACCEPTED WITH DOCUMENTED LIMITATIONS**, closed by merged PR #82.
  EN/RU/ES gettext UI, one short configuration-aware /start, meaningful YouTube choices,
  E3 pre-binding and E4 evidence-based terminal cards. RU is owner LIVE-checked;
  EN/ES are automated-only. See [acceptance](PHASE8_UX_ACCEPTANCE.md).
- YouTube: normal video/Shorts; Video or Audio and available quality only when useful;
  direct download where no choice is needed. No normal user-facing video-only mode.
- Instagram: opt-in public Reels, public single-video /p/ and guarded video carousel
  selection. Photos are never delivered. Original source positions include photos;
  img_index instructions belong in that route, not /start. Ten-video ceiling retained.
- Ordinary TikTok: opt-in standard public video and guarded vm/vt short references;
  native public-page acquisition, no extra audio/quality screen. Availability depends
  on platform/network context. Narrow HOSTKEY success is owner-reported, not universal.
- Phase 9B bounded metadata isolation is implemented/merged/deployed. The old initial
  synchronous planning defect is fixed within the verified contract. LIVE callback
  concurrency responsiveness remains INCONCLUSIVE, not a new confirmed defect.
- **Phase 9C LOCAL ACCEPTED**: one unfinished cross-platform request per user,
  separate pending/work capacities, /cancel for waiting choices, bounded link replies,
  guarded writes/cleanup; fixed Instagram 25 MiB gates removed. Local owner 5/5 PASS.
- HOSTKEY cutover passed on 2026-10-28, and the later P9-R4 bot-only replacement passed on 2026-10-31 with yt-dlp 2026.10.26. VPS is the designated sole poller; MacBook bot/API remain stopped. See [P9-R4 deployment record](LOCAL_BOT_API.md#p9-r4-deployment-checkpoint--2026-10-31). The deployment test is not a Telegram LIVE download acceptance.

Repository defaults and deployed settings differ: flags default off, work capacity
four; the preserved HOSTKEY evidence has both platform flags on and work capacity one.
APP_ENV remains development to preserve the existing Instagram production guard;
physical production deployment does not justify silently changing it.

## Current boundaries
The intermittent YouTube metadata/snapshot issue has not been fixed. P9-R5f confirmed a synthetic offline conflict in the private diagnostic guard, which does not establish the original production failure. P9-R5g offline-only hardening is authorized, completion not yet reported. No production fix or external follow-up is authorized by this documentation update.


**Phase 9 remains OPEN**: load, restart/recovery, fault handling, rollback rehearsal,
large/long files and additional clients are not accepted by the small functional sample.
A historical playable 414.7 MB transfer and the Phase 9C >25 MiB Instagram acceptance
are not validated near-2 GB support. No queue, durable interaction recovery, distributed
lease database or external file-storage service is implemented.

TikTok Short Drama is **DEFERRED / SERVER RESOLVER BLOCKED / RESEARCH PRESERVED**.
The official browser supplies target-bound playback metadata, but independent server
retrieval and a complete permitted file are unverified. [Canonical research](research/TIKTOK_SHORT_DRAMA.md)
retains negative results, S1/S2 and reopening conditions; it does not block core work.

## Product strategy and future business model

Minimum actions, provider-specific capabilities, consistent language and truthful
status/delivery evidence. Unknown delivery must stay unknown; never retry media
because an acknowledgement was lost. Language follows Telegram User.language_code,
not a guaranteed client-interface language; no /language or preference database.

Membership of a Telegram channel/group is **not required** and enforcement is not
implemented. Membership gating, modular advertising, optional paid/free models and
other monetization choices remain Phase 10 design work, not approved current features.
Analytics remains a Phase 4 backlog: product/technical aggregates without viewing
history; no analytics database/service is selected. Advertising must stay outside providers.

See [ROADMAP](ROADMAP.md), [TASKS](TASKS.md), [architecture](ARCHITECTURE.md),
[testing](TESTING.md) and the [self-contained chat handoff](CHAT_HANDOFF_2026-10-29.md).
