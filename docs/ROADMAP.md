# Roadmap

## Phase 0 - Foundation — done
GitHub repository, documentation, security baseline, Git workflow, test strategy, and AI-agent rules.
Gate: governance files exist, contain no secrets or personal data, and the repository history is reviewable.

## Phase 1 - Downloader Core — done
Transport-independent URL validation, provider detection, provider interface, download result model, temporary workspace, safe filenames, errors, logging, and tests.
Gate: core behavior is independently testable without Telegram.

## Phase 2 - YouTube Provider — done
The YouTube provider is implemented in the provider architecture. Real regular-video downloads succeeded in all three output modes, a live matrix passed for combined MP4, selected-quality video-only, and two audio containers, and Shorts smoke tests plus deterministic error-boundary/format-layout tests are recorded.
Evidence and limits are documented in TASKS.md and TESTING.md. Live matrix coverage is one regular public URL, not proof of broad reliability.

## Phase 3 - Telegram Functional MVP — done
The functional Telegram MVP is complete for the supported YouTube flow. It includes:

- Telegram bot entry point and aiogram polling setup;
- `/start`;
- text URL intake and supported-platform recognition;
- YouTube detection and download orchestration;
- transport-independent `DownloadService`;
- Telegram video delivery;
- Local Bot API integration;
- Telegram-compatible media preparation;
- H.264/AAC preference;
- compatible MP4 passthrough;
- verified stream-copy remux for compatible non-MP4 H.264/AAC input;
- transcode fallback for incompatible or failed remux output;
- rotation-aware width, height, and duration upload parameters;
- real Telegram delivery evidence through the Local Bot API Server;
- Dockerized yt-dlp with pinned Deno runtime for YouTube JavaScript challenge solving;
- containerized metadata/simulation evidence for the Deno-enabled runtime.

Gate: a core user can submit a supported YouTube URL and receive downloaded media in Telegram through the implemented flow.

This phase closure does not mean production readiness. It does not close restart/recovery, upload/network failure recovery, cloud/local operational rehearsal, larger-file limit work, repeatable E2E/deployment procedure, monitoring, resource limits, or broader reliability checks. Those are tracked in Phase 9, Production Reliability.

Instagram and TikTok remain recognition-only by default. Instagram has a separate explicit Telegram opt-in with narrow owner-confirmed Reel, single-post and three-video-album evidence; see Phase 5 below. The default downloader registry remains YouTube-only.

## Phase 4 - Download UX and YouTube Options
Expose useful provider/content capabilities through a polished Telegram interaction flow.
The primary capability design is [Phase 4 Capability Model](PHASE4_CAPABILITY_MODEL.md).

Core UX rule: minimum steps + provider-specific capabilities + consistent visual language.
The bot must not force identical options on every provider or add an extra click when
there is no meaningful choice.

Functional scope ACCEPTED on 2026-10-15 against main
`ced1200bf2a81a1bb63c200e6441e8458d0af0df`, using the existing Compose bot and Local Bot
API. Real Telegram validation confirmed the playlist-context watch URL, Video/Audio
choices, landscape Medium 936x720, portrait Medium 720x1280 and High 1080x1920, playable
image/sound, M4A playback/duration, callback protection and distinct-URL isolation.
Earlier Local Bot API validation also delivered a file above 50 MB. Evidence and its
limits are recorded in [TESTING.md](TESTING.md#phase-4-functional-acceptance-2026-10-15).

The application choice model, inline interaction state, safe quality mapping and media
delivery are accepted within that tested functional scope. This is not exhaustive format
coverage, acceptance of all original backlog items, or production readiness.

Remaining work retains the existing phase definitions:

- unchecked analytics design/implementation/validation items remain in Phase 4 TASKS.md;
  no analytics implementation or storage choice is implied by functional acceptance;
- copy, obsolete choice prompts, loading/progress and interaction polish remain Phase 8;
- HTTP 403 recovery, metadata/event-loop responsiveness, network/restart recovery and
  monitoring remain Phase 9, which is open;
- later usage evidence may justify simplifying options; no product policy changes here.

Target YouTube UX:

- first choice: `🎬 Видео` or `🎵 Аудио`;
- after Video: `Низкое`, `Среднее`, `Высокое`;
- Audio starts without additional quality selection unless later evidence justifies it;
- video-without-audio is not exposed as a normal user option.

Target Instagram UX:

- normally download video directly;
- no audio-only option by default;
- no quality-selection step unless a future provider proves useful selectable variants.

Target TikTok UX:

- direct video download by default;
- no unnecessary audio or quality screen.

For future platforms, UX derives from provider/content capabilities rather than a fixed
global options flow. Do not hard-code Instagram, TikTok, or other future-provider
capabilities before the provider spike proves what each platform/content type can
actually offer.

YouTube quality semantics:

- Low means lower bandwidth/resolution;
- Medium means approximately 720p class;
- High means approximately 1080p class or best reasonable Telegram-oriented quality;
- High must not mean unlimited 4K/8K automatically;
- final resolution selection should gracefully use the nearest useful available format.

Analytics should improve UX and technical decisions without collecting users' viewing
history. Track product and technical statistics, not source URLs, video titles,
channel/author names, Telegram usernames, message text, or unnecessary personal data.
Use pseudonymous or anonymous user identity sufficient for aggregate usage statistics.
Analytics must distinguish `option unavailable` from `option available but not selected`.
It should also distinguish technically available options hidden by product policy from
options shown to the user.

The current provider architecture already exposes modes and quality options. This phase
should connect those capabilities to Telegram UX, add only the capability modeling needed
for product choices, and avoid redesigning provider internals or creating a second
capability source of truth without evidence.

## Phase 5 - Instagram Provider — in progress

Item Selection is implemented offline for one unambiguous `img_index=N` on a public
`/p/` carousel. Metadata/parent/full-manifest inspection precedes two choices: all
videos in source order, or the VIDEO at original position N (photos count toward
positions). A selected PHOTO offers only all videos; out-of-range/unknown intent
refuses. Ordinary `/p/` remains automatic and Reels retain their path. Explicit
PUBLICATION (whole publication) and SINGLE_VIDEO scopes share the existing worker,
private IPC, full fresh manifest/parent check, preparation and Telegram confirmation.
Opaque choices bind user/chat/message, expire after 15 minutes, consume once and
retain a busy/failed-ack choice. No Instagram slot is held while waiting for choice.
Cleanup uncertainty quarantines owned directories and blocks new Instagram work.
No new network policy, dependency, retry, quality mode or polling is introduced.
See [Item Selection evidence](TESTING.md#instagram-item-selection-offline) and
[URL/interaction rules](DEVELOPMENT.md#instagram-item-selection).
LIVE single-item acquisition/delivery and deployment remain separate unverified gates.

The parent-identity follow-up strengthens the existing whole-carousel contract:
observed product PK is validated before upstream mapping, converted to shortcode
and bound to the canonical requested publication; an optional response `code` must
agree. Immutable inspection/selection and the private worker IPC retain that
identity. The worker rechecks it and the complete ordered child manifest before
any media GET. Missing/conflicting evidence refuses instead of using the input URL
or upstream fallback ID. At that stage single-item scope and selection buttons
remained future work; the later Item Selection stage is recorded above. This is
offline contract verification only, not universal Instagram response
compatibility or a new live/deployment acceptance. See
[parent identity tests](TESTING.md#instagram-parent-identity-contract-offline).

On 2026-10-16 the user initially authorized implementation after the previously conducted Gates
1–3C, limited to anonymous public individual Reels. The cached Gate 3C report confirms
metadata extraction/classification of one five-item `/p/` playlist only; the carousel is
out of scope and that report does not prove media acquisition or Telegram delivery.
Full Gates 1–3B reports were not available in the handoff used for this PR. The GO is an
explicit development scope decision, not a broad reliability verdict.

Merged PR #44 implements the `MediaProvider` contract, direct MP4 Reel acquisition, rejection
boundaries, explicit `DownloadService` injection and deterministic validation. It leaves
the default registry and Telegram activation unchanged.

The first real provider smoke failed before acquisition on incomplete metadata. After
PR #45, a separately authorized repeat passed for one public Reel on 2026-10-16:
13 formats, 3 admitted, one extraction and acquisition; MP4 H.264/AAC, 720x1280,
11.282041 seconds, 1,317,210 bytes, preparation passthrough and ffprobe/full decode PASS.
No Telegram upload was performed; this is not broad reliability evidence.

The user subsequently approved a broader Phase 5 scope: public Reels, ordinary public
single-video posts, and video-only selection from carousels. Photos are NEVER downloaded
or delivered. Single-video `/p/` results reuse the provider with offline validation.
The first carousel stage now provides guarded metadata inspection and immutable whole-
publication selection plans only. UNKNOWN, unavailable/unsupported videos and unreliable
identities block selection; only confirmed PHOTO entries can be excluded. Item-reference
URLs remain blocked. Bounded ordered acquisition is implemented separately with deterministic
validation and one bounded real three-video smoke; larger collections and Telegram
integration remain unverified.
Eventual video delivery uses ordered Telegram groups, splitting more than 10 videos;
a single remainder uses one video message. Never silently omit a selected video.

At that provider-only stage, real single-video `/p/` and Telegram delivery required
separate gates. Subsequent routing and narrow live acceptance are recorded below;
the default downloader registry remains YouTube-only.
PR #47 inspection and PR #48 PHOTO correction were independently reviewed and merged.
The final authorized metadata gate passed on one real 20-entry mixed publication:
17 VIDEO, 3 PHOTO (8/9/18), zero UNKNOWN, READY with ordered unique IDs and three direct
MP4 candidates per VIDEO. One extraction/three observed HTTP requests, zero acquisition.
The mixed-classification gate is closed for that case only.
PR #49 bounded acquisition was independently reviewed and merged. The user subsequently
approved silent video across Reels, single posts and carousel VIDEO entries. Admission,
compatibility ranking and actual carousel stream validation now allow optional audio;
no synthetic audio or conversion is added. Direct MP4/protocol/manifest/DRM guards and
resource limits remain. PR #50 was independently reviewed and merged. A separately
authorized production smoke then passed on one three-video carousel: 3/3 silent
H.264 MP4 files, 720x960, 1,961,198 bytes total, exact order, ffprobe PASS, no conversion
or Telegram calls. Only that small real-acquisition gate is closed.
PR #51 merged explicit optional-audio preparation and atomic derivative ownership;
existing callers keep the audio-required default. A separate reusable carousel
transport now has offline coverage for preparation-before-upload, ordered batches,
bounded resources and safe partial progress. No handlers/default routing were enabled.
PR #52 transport was independently reviewed and merged. A narrow Reel-only Telegram
integration is now implemented offline behind `INSTAGRAM_TELEGRAM_ENABLED=false`;
PRs #53/#54 are merged. The separately authorized bot-only deployment and one canonical
Reel delivery smoke passed; the user confirmed playback, orientation and sound.
The initial shared URL failed on the irrelevant `psln` query key. PR #55 subsequently
merged at `0a87beeaa8acb302b74e980946778608856b13f6` and was separately deployed.
The user confirmed full-share-link delivery, playback, orientation and sound;
size/time were not recorded. This is narrow Reel evidence, not `/p/`/album reliability.
That earlier fix stripped ordinary queries/harmless fragments, retained known item-selector
rejection and left carousel policy unchanged. No restart, environment change or live request is
part of that share-link implementation. Compose defaults false; APP_ENV=development
and the production guard remain unchanged. Larger-carousel acquisition and broad
reliability remain unverified; later narrow `/p/`/album acceptance is recorded below. Item-specific semantics remain
blocked pending separate validation; the installed extractor ignores `img_index`.
No running-stack rebuild/restart is authorized by this stage.
Merged PR #56 (`feat/instagram-post-carousel-telegram`) connects
public `/p/` URLs to positively inspected post/provider single-video download or existing
carousel inspection/acquisition and Telegram album transport, without changing the
YouTube flow or the production-only Settings guard. The route shares the current
Reel admission slot. Initial bounded carousel scope is at most 10 videos, 25 MiB
per source/upload file and 100 MiB total; oversize/unknown selections are blocked,
not truncated. The share-link follow-up aligns `/p/` query/fragment admission with Reels:
strip non-selector share data and block known encoded/case-varied item selectors before
extraction. Malformed references and the 32-field bound remain. PR #56 passed independent
review, merged at `20d14441a2b7ea906ed2a0abc83679d25d9f2d32` and was separately
deployed only to bot, with source/polling verification and unchanged Local Bot API.
The external three-video acquisition gate is not
proof of Telegram album playback. Before review corrections, GitHub Actions lint, formatting and offline/FFmpeg integration tests passed
(1277 passed, one optional external YouTube test skipped) before any real
album smoke. PR #57 subsequently passed independent review, merged at
`13da14d6f1ea9378d776543c94b22b7b716630d3`, passed post-merge CI #39151964361
and was separately deployed only to bot.
On 2026-10-18 the owner confirmed one full-link single-video `/p/` delivery with normal
playback and one previously rejected full-link three-video carousel arriving as one
ordered, playable, silent album. Single-post processing was subjectively sufficiently
fast; exact time was not measured. Only these two real user acceptance cases are closed.
Other publication shapes, mixed-media delivery, clients/devices, larger/multi-batch
albums, file-size boundaries, recovery, load and production capacity remain open.
See [the evidence and limits](TESTING.md#instagram-live-acceptance-2026-10-18).
Review corrections remove the UNSUPPORTED_CONTENT-to-single fallback: only explicit
available VIDEO evidence and coherent identity seed the single-file snapshot, and no
second extraction can override a block. Initial inspection uses the existing guard/event
and a shared operation deadline; slot/workspace ownership survives cancellation until
worker completion. Those corrections passed independent review before merge; the
share-link follow-up also passed review before the narrow live acceptance above.
The source-shape follow-up rejects present malformed carousel fields before
mapping and requires complete source-to-playlist count/identity/order preservation.
It added no downloader or metadata model; another independent review was required after
offline verification. That PR review/merge/deployment subsequently completed as recorded
above. The user's two initial post-deployment refusals
do not identify the exact URL parameters because the links were not supplied.
See [the scope and acceptance record](PHASE5_INSTAGRAM_REELS.md).

The general gated sequence remains:

Order:

1. technical spike;
2. real-world reliability assessment;
3. explicit Go/No-Go;
4. provider implementation only if viable;
5. deterministic and external validation;
6. integration into the common Telegram UX.

Where Instagram exposes meaningful format or quality choices, map them into the shared download-options model.

## Phase 6 - TikTok Provider
The previous yt-dlp harness remains in unmerged Draft PR #59 and is discontinued:
the final series stopped on unrecognized metadata HTML before any media GET.
Phase 6C prepares a separate native public-video CLI from main, using tt-dlp's
embed-state approach under MIT attribution. Offline synthetic HTTP/local-media
checks establish implementation boundaries only. The first authorized native run
stopped on A's `unsupported_photo` before media GET; B was not run. A small offline
patch now distinguishes empty photo placeholders from populated/unknown structures.
The authorized retest obtained A's complete MP4 with actual video/audio streams,
decode and passthrough; B resolved metadata but media returned HTTP 403. The reason
is unknown. Safe diagnostics now report candidate origin, CDN family, query/cookie
presence, actual statuses, counters and measured codec names without new requests.
The authorized B-only diagnostic retest again returned media 403 (`urls`, EU CDN
family, query present, no cookies sent); B remains unverified and the cause unknown.
The separately authorized four-new-publication benchmark passed 4/4: complete MP4,
actual H.264/AAC streams, full decode and passthrough preparation, with exact bounded
counters and cleanup. This small sample does not establish general platform reliability.
The owner then authorized Phase 6D offline integration in a new stacked branch:
one reusable native engine, standard-video/silent-capable provider and a default-off
Telegram handler restricted to configured test users in development/test. The native
CLI/benchmark, original limits and working YouTube/Instagram paths are preserved.
Controlled owner-authorized Telegram attempts subsequently started and stopped
correctly but received embed metadata HTTP 429 before any media GET/upload. Those
attempts did not verify delivery. Phase 6E confirms equivalent CLI/provider
HTTP and adds a separate public-page universal-state parser/session adapter.
Its separately authorized metadata-only test obtained HTTP 200, a matching source
ID and one admitted `playAddr` (1 request / 405,981 bytes); no media GET occurred.
Phase 6F's explicit `--public-page` mode then passed one separately authorized native
MP4 test: complete 571,013-byte H.264/AAC file, original ID, full decode, passthrough
and cleanup in 5.506 s. It used one metadata request and one media GET (200), without
Telegram upload. Phase 6G adds explicit public-page selection in the existing
TikTokProvider and verified caller-workspace export to the unchanged handler.
No embed fallback, retry, network policy change or new handler is introduced. The
offline checks and exact-head CI passed. The subsequent separately authorized
Phase 6G Telegram test passed for one short public video: matching ID, complete
571,013-byte MP4, full decode and passthrough, one confirmed video Message, owner
confirmation of normal playback/orientation/sound and process/file cleanup.
The operation used one metadata request, one media GET (200), one acquisition and
one sendVideo attempt, without retry or fallback; handler/delivery took 5.432 s.
This closes only the controlled single-case end-to-end gate. PRs #60–64 were then
sequentially merged at main `fe59c1d`, with successful final CI (1696 passed / 1 skipped).
Phase 6H implements public opt-in access: TikTok remains off by default, but when
enabled admits any Telegram user and permits production configuration. Bounded local
capacity defaults to two operations per bot process and one per user, retaining worker,
upload and cleanup ownership. Instagram restrictions remain unchanged. Offline checks
passed (356 focused; full 1716 passed / 1 skipped, Ruff/diff/security), and implementation
HEAD `6665b90` passed exact-head CI #39469733288.

The separately authorized **PUBLIC TIKTOK LIVE PASS** confirms one second-account
full-link scenario without a personal allowlist: public-page metadata/source ID, one
HTTP 200 media acquisition, complete 565,847-byte H.264/AAC MP4, FFmpeg decode and
passthrough preparation, one confirmed Telegram video Message, and owner-confirmed
playback/orientation/sound. Polling/session, worker and file cleanup passed; Docker
remained exited. No retries, fallback, merge or deployment were performed. The approved
queued update was read without acknowledgement/deletion; future restart replay
prevention was not tested.

Final documentation-only preparation and PR review passed, including another full
network-blocked offline run (1716 passed / 1 skipped, 186.73 s), Ruff/diff/privacy
checks and 30 internal links/anchors. Source/configuration/dependencies/CI are unchanged
by that update. Documentation-head CI passed; PR #65 then merged at main `fc78686`
with successful post-merge CI. Deployment was not performed. The full-link success
does not validate scalability or general TikTok reliability; earlier 429/403 remain
historical limitations, not universally resolved outcomes.

Phase 6I prepares exact vm/vt HTTPS short share links using the same native transport
and owned worker. Local intake remains network-free; resolution starts after user/
process admission and consumes the original metadata request budget and deadline.
Only verified full-video destinations reach the existing public-page parser and one
media acquisition. No fallback, retry, CDN/header/cookie-policy expansion or second
HTTP client is introduced. Offline verification passed: 53 targeted tests, full
1769 passed / 1 skipped, Ruff/diff/privacy/security/link checks. Implementation HEAD
`b08f57d` passed CI #39511176476. The separately authorized SHORT-LINK LIVE test then
passed for one new mobile-app `vm.tiktok.com` link: HTTP 301 redirect, valid full
publication/source ID, public page 200, one `playAddr`, one complete 1,049,546-byte
MP4 (200), H.264/AAC, full decode and passthrough, one confirmed Telegram video and
owner playback/orientation/sound confirmation. Metadata 2 attempts / 415,102 bytes,
media 1 attempt, one acquisition, exact counters; native operation 3.409 s.
Polling/session, worker/FFmpeg and workspace cleanup passed; containers stayed exited,
without retry, fallback, merge or deployment. Old updates were preserved without
acknowledgement by owner permission; restart replay prevention was not tested.
Live coverage is one `vm` link; `vt` remains offline-only, and broader mobile-link
coverage/high-load stability are unverified. Earlier 429/403 are not universally
resolved. Final docs-only review found no new defect; full network-blocked pytest
again passed (1769 passed / 1 skipped, 219.88 s), with Ruff/diff/privacy/link checks.
PR #66 subsequently merged at main `389258cee9cf966be531ae5d6d60b192a59bcdb2`;
post-merge [CI #39517532808](https://github.com/ip52rus/social-video-downloader/actions/runs/39517532808)
passed. Separately authorized deployment prepared a new bot image with the old image
retained for rollback, completed Cloud-to-Local Bot API migration, and started the
existing bot with public TikTok enabled (capacity two) and Instagram still enabled.
The Local API container and volume were preserved.

Stage D **PUBLIC DEPLOYMENT ACCEPTED** covers three sequential owner-triggered cases:
one TikTok short link, one Instagram Reel and one YouTube video. Each was delivered;
the owner confirmed full playback, orientation and sound. Worker/file cleanup passed,
with no restart/OOM/runtime errors observed. Both services were left running.
Subsequent local configuration finalization persisted TikTok true/2 in the protected,
ignored `.env`; Compose resolves those values without shell overrides. That step
made no runtime/code change and did not restart or redeploy either container.

Next gates are the documentation PR's exact-head CI and independent merge decision;
broader mobile-link coverage, high-load and recovery validation remain open. Three
deployed smoke cases do not establish general reliability; `vt` is still offline-only
and historical 429/403 are not universally resolved. See
[Phase 6C](PHASE6C_TIKTOK_NATIVE.md), [Phase 6D](PHASE6D_TIKTOK_TELEGRAM.md),
[Phase 6E](PHASE6E_TIKTOK_PUBLIC_PAGE.md), [Phase 6F](PHASE6F_TIKTOK_PUBLIC_PAGE_MP4.md),
[Phase 6G](PHASE6G_TIKTOK_PUBLIC_PAGE_TELEGRAM.md),
[Phase 6H](PHASE6H_TIKTOK_PUBLIC_MVP.md) and [Phase 6I](PHASE6I_TIKTOK_SHORT_LINKS.md).

Use the same gated process as Instagram:

1. technical spike;
2. real-world reliability assessment;
3. explicit Go/No-Go;
4. provider implementation only if viable;
5. deterministic and external validation;
6. Telegram UX integration.

## Phase 7 - Additional Social Platforms
Evaluate other popular services one by one. Do not promise universal platform support.

Candidates should be selected later based on:

- user demand;
- technical feasibility;
- legal and platform restrictions;
- extraction reliability;
- maintenance burden.

Each platform requires its own technical spike and Go/No-Go gate before implementation. Do not hard-code a long unsupported platform list into product claims.

## Phase 8 - Unified Product UX
Polish the complete downloader experience after multiple providers exist.

Include:

- consistent Telegram UI;
- inline keyboards;
- provider-independent mode and quality presentation;
- all bot messages, including removing or updating obsolete video/audio choice prompts
  after selection when their inline buttons disappear;
- loading and waiting messages;
- success messages;
- unsupported-content messages;
- retry and error states;
- provider-specific exceptions only where necessary;
- consistent naming and button copy;
- final interaction-flow review.

Goal: the bot should feel like one coherent service rather than several provider integrations.

## Phase 9 - Production Reliability
Complete the operational and reliability work that is intentionally not part of the functional MVP gate.

Status: OPEN. Phase 4 functional acceptance does not satisfy this reliability gate.

Phase 9A adds minimal safe standard-library events after a read-only deployed
baseline audit: fixed platform/event/phase/category, monotonic observed duration,
service lifecycle and typed polling errors, without user identifiers, arbitrary
exception strings or probe dumps. Existing downloader/network/lifecycle behavior
is retained. Offline checks and separate exact-head Draft PR CI/review are required;
no container or environment change/deployment is included. The running image's
legacy verbose logs remain unchanged until a separately approved rollout.

Next is Phase 9B's offline measurement of slow synchronous YouTube metadata blocking
the event loop, with a concurrent ticker/callback and explicit bounded ownership/
cancellation acceptance criteria before any architecture change. Phase 9A events
are not a heartbeat, load test, per-user trace, availability metric, proof of worker
reap or HTTP-request counter. Broader recovery/load/reliability gates remain open.
See [operational contract](DEVELOPMENT.md#phase-9a-operational-baseline-and-safe-events)
and [offline evidence](TESTING.md#phase-9a-safe-operational-events-offline).

Include:

- bot restart and recovery;
- Local Bot API restart and recovery;
- temporary network/API failure behavior;
- intermittent YouTube HTTP 403 diagnosis and a narrowly bounded recovery strategy,
  with explicit limits and no duplicate downloads/uploads;
- upload failures;
- repeatable deployment and E2E procedure;
- resource observations;
- disk and temporary-file cleanup behavior;
- concurrency and load assessment;
- remove synchronous metadata extraction/planning from the async event loop and verify
  that slow inspection does not block other Telegram callbacks;
- rate limits when justified;
- queues and workers only if measured workload requires them;
- monitoring and observability;
- deployment automation where justified;
- backup and recovery procedures where relevant;
- large-file behavior and actual limits;
- strategy for files exceeding Telegram Bot API delivery limits.

For media above Telegram delivery limits, the current design direction is a possible external temporary object-storage/download-link fallback. Do not implement or commit to S3, R2, or any storage provider until this phase has a demonstrated requirement and design decision. Do not claim support for files above 2 GB.

## Phase 10 - Monetization and Access Control
Access restrictions and monetization are deferred until the project has a useful, working multi-platform downloader product worth monetizing.

Investigate and design:

- Telegram community membership gate;
- advertising gateway;
- optional paid/free models if desired later;
- other monetization mechanisms;
- access restrictions required by the chosen model.

Current product decision: membership is not required during core product development. Advertising must remain modular and must not be coupled into provider implementations.
