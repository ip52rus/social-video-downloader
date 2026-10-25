# Phase 8 E5 UX acceptance

## Scope and evidence

Baseline: E4 merge [177f11e](https://github.com/ip52rus/social-video-downloader/commit/177f11ef7e8ad17a0993f7083b23ede15d2e7a70);
[post-merge CI #40178485535](https://github.com/ip52rus/social-video-downloader/actions/runs/40178485535)
SUCCESS. E5 reviews existing Telegram presentation offline, with targeted copy fixes.
Media policies, callback payloads, stores, deadlines, admission, workers and delivery
are unchanged. No Docker, polling, platform requests or device checks run in E5.

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
- E4 deployment checks and CI are separate from these human observations. E5 adds
  no LIVE evidence. No numerical callback latency is inferred.

## Remaining manual acceptance matrix

Plan only; a new LIVE operation requires an owner decision. Record actual Telegram
User.language_code where safely available, observed language and client name, without
publishing user identifiers or source URLs. A changed client setting alone is not
proof of the value sent by Telegram. No forced restart, induced send failure,
automatic repeat, mass matrix or universal client coverage is requested.

| Scope | Existing acceptance / remaining action |
|---|---|
| E4 greeting + YouTube sent card | Owner PASS above; do not repeat without a specific regression. |
| EN and ES UI / fallback | Remaining: /start, invalid text and unsupported link in existing clients. No media request. Existing resolver tests cover missing/unsupported codes; do not fabricate real updates. |
| Format → quality / pinned language | Remaining LIVE coverage not specified by E3/E4 report. If separately authorized, use one known interactive video; inspect translated step text and valid callback language. Terminal audio/video buttons can download and require explicit media authorization. |
| Instagram Item Selection | Historical all/one delivery PASS is retained. Remaining current localized labels/source-position display and stale/foreign instruction need bounded owner approval. No demand to repeat historical media delivery without a concrete reason. |
| TikTok | Existing functional delivery evidence remains historical. Current localized status/caption in one full or supported short-link case remains unverified; real acquisition/send needs separate approval. Do not test every language × URL type. |
| Old callbacks / client rendering | If an existing pre-restart card is available, one safe stale click may confirm localized refusal and no download. Do not restart production or use a valid terminal button merely to create this condition. Record the client actually used; other clients remain unverified. |
| Failure / partial / uncertain delivery | Offline evidence only; do not induce Telegram faults, interrupt owned workers or retry ambiguous delivery for acceptance. |

## Verification and disposition

79 new cases cover the two concrete gaps. Focused UI/localization/wheel:
**693 passed**. Full inherited socket/DNS-denied offline pytest:
**2737 passed, 1 skipped**. Ruff, PO/MO reproducibility, installed-wheel resources,
diff, 91 relative links/anchors, privacy and exact file-scope checks passed.
Exact-head CI is a separate Draft PR check; no merge or deployment is performed.

E5 implementation/offline readiness and final owner acceptance are separate.
Unqualified Phase 8 closure is BLOCKED by outstanding owner manual acceptance
of the scoped matrix (especially EN/ES and current Instagram/TikTok presentation).
This is an evidence gap, not a confirmed downloader regression or a requirement to
prove every platform/language/client combination. The owner may complete the bounded
checks or explicitly accept/defer remaining limits. No existing LIVE PASS is revoked.
Durable restart-card retirement remains a documented separate design question.
