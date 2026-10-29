# Phase 8 E5 UX acceptance

## Later checkpoint — 2026-10-29

The accepted Phase 8 MVP and its original sample limits below remain unchanged;
[PR #82](https://github.com/ip52rus/social-video-downloader/pull/82) merged this acceptance.
Phase 9C later received local owner 5/5 acceptance, and HOSTKEY received a separate
technical cutover PASS. Owner now reports ordinary TikTok success on HOSTKEY;
references below to future VPS egress being untested describe the earlier acceptance
checkpoint, not the absence of this later narrow result. EN/ES LIVE, wider Instagram/
client coverage, load/recovery and visual post-restart cleanup remain unverified.
See the [updated evidence ledger](TESTING.md#checkpoint-2026-10-29); no repeat E5 LIVE
or broader reliability is inferred. Historical E5 catalog counts do not include the
later five Phase 9C entries (current total88 per locale).


Current owner disposition (2026-10-26): **PHASE 8 MVP — ACCEPTED WITH DOCUMENTED LIMITATIONS**.
Acceptance baseline: E5 plus TikTok diagnostics, main `b55a019b9943d75e7ed715f1b64cefc57f1e2dbc`.
This accepts the verified MVP; it does not establish universal platform reliability.

## Scope and evidence

E5 implementation-review baseline: E4 merge [177f11e](https://github.com/ip52rus/social-video-downloader/commit/177f11ef7e8ad17a0993f7083b23ede15d2e7a70);
[post-merge CI #40178485535](https://github.com/ip52rus/social-video-downloader/actions/runs/40178485535)
SUCCESS. E5 reviews existing Telegram presentation offline, with targeted copy fixes.
Media policies, callback payloads, stores, deadlines, admission, workers and delivery
are unchanged. No Docker, polling, platform requests or device checks ran during
that implementation/offline stage. Later deployment and owner LIVE evidence are
recorded separately below.

Evidence classes are separate: source review; deterministic dispatcher/fake-transport
tests; GitHub CI; prior deployment checks; owner-reported LIVE observations.
A synthetic store/dispatcher replacement is not a real process or device test.

## Targeted findings and decisions

1. The greeting lists available platforms, but invalid/unsupported-link guidance
   advertised all three even when disabled. The two error messages now reuse the
   greeting's presentation-only platform list, including existing TikTok user policy.
   URL normalization/validation and routing remain unchanged. Simpler link wording
   removes HTTP terminology without expanding supported inputs.
2. Instagram unknown/expired/foreign callbacks had a localized refusal but no next
   action. The validated-refusal branch now reuses the existing generic unavailable
   choice instruction to send the link again, without revealing another interaction
   or changing validation/consume. Malformed/disabled-handler refusals already had
   that instruction and are unchanged.
3. Existing tests covered refusal after store replacement, but not the subsequent
   fresh request and repeated submission through a fresh dispatcher. Added offline
   cases verify both paths, sender/pinned locales, no edits to unvalidated old cards
   and one delivery boundary call per intentional new selection.

These are the only runtime changes. Historical translation entries are retained;
two new placeholder-marked messages bring catalogs to 83 entries. No infrastructure,
automatic retry, new Telegram call or required user action is introduced.

## Journey review

| Journey | Actual behavior / user action | Source and offline evidence |
|---|---|---|
| First contact | One short /start; only available platforms; send a link. EN fallback uses Telegram User.language_code, not an inferred client language. | [intake](../src/social_video_downloader/handlers.py), test_telegram_localization start/flags matrix; test_telegram_i18n resolver/context cases |
| Invalid or unsupported link | One localized actionable refusal listing available platforms. Disabled recognized platform is explicitly refused. No extraction. | handle_text; test_ux_acceptance guidance cases and existing disabled-link tests |
| YouTube choices | Noninteractive receipt, confirmed binding, format prompt; quality prompt and keyboard edit together only when needed. Terminal selection consumes once and pins request language. | _publish_choices, _handle_mode_callback, _consume_and_download; test_youtube_status_cards, test_terminal_ux |
| YouTube direct | No extra confirmation or selection. Accepted-request receipt, existing download, then terminal edit of that card. | handle_text; existing direct, audio/video and exact-quality tests |
| YouTube waiting/outcome | Metadata has no new progress message; busy/unavailable is explicit. Receipt means accepted, not percentage/ETA. Positive media acknowledgement → sent; pre-upload/explicit rejection → failure; lost response/interruption → uncertain, no automatic retry. | _run_youtube_request and typed delivery result; test_terminal_ux, test_youtube_cancellation |
| Instagram Reel / single /p/ video | Direct path and existing starting notice; delivered media is the result. No extra success message or new confirmation. Unsupported selectors/limits remain explicit. | [Reels](../src/social_video_downloader/telegram_instagram.py), [posts](../src/social_video_downloader/telegram_instagram_posts.py); actual-pipeline localization tests |
| Instagram carousel | Whole-post video delivery remains automatic, source order and limits retained. Confirmed partial and uncertain sending keep distinct existing copy; photos are not silently delivered as video. | post handle / _send_carousel; test_telegram_localization post partial/error cases and delivery suite |
| Instagram Item Selection | Source position includes photos. All videos or only specified video; photo reference offers all videos only. Validated consume replaces old instruction/keyboard with receipt. | _offer_choice / handle_callback; test_instagram_item_selection, test_terminal_ux |
| TikTok | Full/supported short URL → existing direct path, busy/paused refusal or status then media; localized caption. No new choices or retries. | [TikTok](../src/social_video_downloader/telegram_tiktok.py); test_telegram_localization and TikTok handler suites |
| Repeated/foreign/stale callback | No repeat download; unavailable/expired instruction in current sender locale. Valid callback retains original request locale even after a language change. | both interaction stores; existing ownership/expiry/concurrency tests and new restart journey |
| New request after completion | A new submission may create a new independent choice; old tokens never revive. | test_ux_acceptance fresh/repeated request after simulated restart |

Different provider capabilities are intentional. Only YouTube has format/quality
steps. Instagram source-position selection and plural/partial-delivery copy remain
platform-specific. Captions containing source titles are upstream content, not
untranslated bot copy. img_index guidance remains only where a selector correction
is needed, not in onboarding. Busy does not mean queued.

Reel/TikTok starting notices and Instagram result messages retain their existing
lifecycle. Replacing them with owned editable cards would require a distinct
message-lifecycle design, not a safe text-only substitution. No cosmetic unification
changes worker cancellation, API call budgets or uncertain delivery.

## Restart and visual limits

Both pending stores are in-memory. A restart discards tokens, bound message IDs,
ownership and pinned locale. YouTube rejects an unknown token; Instagram rejects
it through the missing-handler or empty-store path. Both return a localized next
action in the current sender's locale and perform no media work. Existing expiry,
foreign, wrong-chat/message and one-shot checks remain authoritative.

A visible old keyboard can remain in Telegram. The current process cannot infer
its owner or safely retire an arbitrary card from untrusted callback data. E5 does
not edit those cards, recover operations, replay delivery or promise crash cleanup.
Even known-card edits are best-effort after a lost Telegram response.

Separate proposed UX design task: assess a minimal durable owner/chat/message
binding for authorized visual retirement, with retention/privacy/TTL rules and
crash/ambiguous-edit behavior. This is a proposal, not implemented persistence or
permission to add a database/background worker.

## Owner LIVE evidence ledger

- E3: owner reported LIVE PASS with E4 authorization. Case counts, clients,
  languages and precise observations were not supplied; do not infer coverage.
- E4: owner explicitly reported one short /start, correct available-platform list,
  a delivered YouTube video, and the final “✅ Файл отправлен.” card without old
  buttons. Record this as narrow owner LIVE PASS. Exact date, client, sample count,
  selection path, EN/ES, Instagram/TikTok, error/restart and latency coverage were
  not supplied.
- Historical Instagram Item Selection [accepted cases](TESTING.md#instagram-item-selection--live-acceptance-2026-10-22)
  remain valid historical delivery evidence. They do not establish the later
  EN/RU/ES interface or all client behavior. Existing results are not overwritten.
- E4 deployment checks and CI are separate from these human observations. The E5
  implementation/offline stage added no LIVE evidence. No numerical callback
  latency is inferred. Later observations follow; earlier results remain intact.

### Final MVP owner acceptance — 2026-10-26

| Scope | Owner-confirmed result and boundary |
|---|---|
| YouTube | PASS: link recognition, Video/Audio and quality selection, video delivery and a terminal request card after successful sending. This does not assert a new audio-file delivery test or numerical latency. |
| Instagram | PASS for the checked Reel: recognition, starting notice and successful video delivery. Earlier [post/carousel](TESTING.md#instagram-live-acceptance-2026-10-18) and Item Selection results above remain historical, not a fresh E5 matrix. |
| TikTok | PASS in the working network environment: the owner confirmed a successful video download after switching the VPN exit from Kazakhstan to the Netherlands. Earlier failures are retained in the [TikTok chronology](TESTING.md#subsequent-deployment-and-live-observations). |
| Common UX | PASS: /start lists available platforms; an unsupported link gives actionable guidance listing YouTube, Instagram and TikTok in the tested configuration. |
| Language | RU is LIVE-checked. EN/ES have automated coverage, with no separate manual Telegram language_code=en/es acceptance. The owner explicitly accepts this residual gap. |

The failed Kazakhstan-exit attempts and later Netherlands-exit success support
network-egress/IP dependence in these observations. The precise cause is not
proven: neither a defective original parser nor all Netherlands IPs being usable
is established. PR #81 diagnostics are retained. Actual IPs, submitted links and
response bodies are not published. Future VPS egress remains untested.

This is owner-reported LIVE evidence, not new agent-executed tests or general
load/recovery acceptance. Confirmed journeys require no repeat LIVE test without
a concrete regression. Client names and exact successful sample counts were not
supplied; do not infer coverage.

## Remaining manual acceptance matrix

Retained as the disposition of the original plan: the owner accepted the remaining
gaps below as limitations of the MVP. They do not block this scoped acceptance.
Any new LIVE operation still requires an owner decision. Record actual Telegram
User.language_code where safely available, observed language and client name, without
publishing user identifiers or source URLs. A changed client setting alone is not
proof of the value sent by Telegram. No forced restart, induced send failure,
automatic repeat, mass matrix or universal client coverage is requested.

| Scope | Existing acceptance / remaining action |
|---|---|
| Greeting + YouTube sent card | E4 and final owner PASS above; do not repeat without a specific regression. |
| EN and ES UI / fallback | Manual LIVE en/es remains unverified and explicitly accepted as a residual gap. Automated EN/RU/ES and missing/unsupported-code coverage is separate evidence. |
| Format → quality / pinned language | Final owner PASS covers selection. LIVE language-switching/pinned-locale behavior remains unverified; automated coverage is retained. No repeat of accepted downloads is required. |
| Instagram Item Selection | Historical all/one delivery PASS is retained. Current full carousel/item/client matrix was not repeated on E5 and remains a documented limit; the fresh Reel PASS does not expand it. |
| TikTok | Final owner PASS is limited to the working VPN exit and checked video. Network dependence, future VPS egress and broader publication/client/language coverage remain unverified. Earlier HTTP and missing-state failures are not erased. |
| Old callbacks / client rendering | In-memory state loss safely refuses old tokens, while visually stale keyboards can remain. No durable cleanup/recovery is implemented; other client combinations remain unverified. No forced restart is required for closure. |
| Failure / partial / uncertain delivery | Offline evidence only; do not induce Telegram faults, interrupt owned workers or retry ambiguous delivery for acceptance. |

## Verification and disposition

79 new cases cover the two concrete gaps. Focused UI/localization/wheel:
**693 passed**. Full inherited socket/DNS-denied offline pytest:
**2737 passed, 1 skipped**. Ruff, PO/MO reproducibility, installed-wheel resources,
diff, 91 relative links/anchors, privacy and exact file-scope checks passed.
At that implementation handoff, exact-head CI was a separate Draft PR check;
no merge or deployment was performed by that stage. E5 later merged in PR #80
at `082986e`; post-merge CI #40184267688 succeeded and a separately authorized
bot-only deployment followed. TikTok diagnostics later merged/deployed from
PR #81 at `b55a019`; post-merge CI #40231655683 succeeded. These are separate
from human LIVE acceptance and from this docs-only closure PR.

At the E5 implementation handoff, unqualified closure was BLOCKED pending owner
manual acceptance/disposition. On 2026-10-26 the owner accepted the scoped results
and explicitly accepted the remaining limitations: **PHASE 8 MVP — ACCEPTED WITH
DOCUMENTED LIMITATIONS**. Earlier failures and unverified checks are not relabelled
as successes. This is MVP acceptance, not universal reliability of all platforms.

Accepted limits: TikTok network dependence and untested future VPS IP; no separate
EN/ES LIVE acceptance; incomplete Instagram carousel/client combinations; no load,
failure-recovery or broad operational reliability acceptance; and visually stale
post-restart cards with no durable retirement/recovery. Phase 9 remains OPEN and
is not started by this closure. Durable restart-card retirement remains a separate
design question. No code, deployment or LIVE operation occurs in this docs-only PR.
