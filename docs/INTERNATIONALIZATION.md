# Telegram internationalization (Phase 8 E1a / E1b / E2 / E3 / E4)

## Scope and decision

E1a introduced aiogram I18n, gettext/Babel and package-local EN/RU/ES catalogs,
merged in PR #75. E1b activated existing Telegram presentation in PR #76, merged at
08d726d; post-merge CI #40085827763 succeeded. Its offline evidence remains distinct
from deployment and LIVE acceptance. E2 is a separate presentation-only change.
A cached process-local I18n instance holds catalogs; aiogram ContextVars hold locale.
No custom plural engine, translation API, preference database or /language command.
No command/profile publication is introduced. E3's one additional publication edit
is explicitly budgeted below.

## Locale lifecycle and middleware

The existing nested Telegram router installs the standard I18n middleware on its
observers (excluding update). Message/callback sender language_code is normalized
locally, bounded to 64 ASCII characters and parsed by Babel. Supported regional
codes resolve to en/ru/es; missing, malformed, unsupported languages and unsupported
extensions fall back to English. This is not universal BCP 47 parsing or a promise
about a particular Telegram client. Never use callback.message.from_user as locale.

YouTube records the current request locale when creating pending choices. Only after
the existing successful transition/terminal consume does presentation enter the
pinned locale. Invalid indices, expired/unknown/foreign/wrong-chat/wrong-message and
racing invalid callbacks use the current sender context. No TTL, payload, option ID,
quality ID, callback routing or consume policy changes. E2 changes mode-to-quality
presentation in one editMessageText call: both the translated quality prompt and its
keyboard use the validated interaction locale.
Acknowledgement order, request count and pending-state mutation remain unchanged.

InstagramChoiceStore.resolve_selection() returns an immutable plan-plus-locale
result after the same lock-protected token/owner/chat/message/expiry/index checks.
resolve() remains a plan-only compatible adapter. The callback keeps its existing
validate → admission → acknowledge → consume → edit → acquisition sequence. Busy
choices remain pending; failed acknowledgement does not consume. No unsafe preliminary
lookup or additional consume is added. After validation, the original request locale
is used even if the sender later changes Telegram language. Restart makes choices stale.

Contexts restore after success, exceptions and repeated cancellation; concurrent
requests do not share mutable locale state. Source URLs/identities, upstream titles,
technical diagnostics, worker IPC and media selection are not translated.

## Catalogs and packaging

[Review matrix](TRANSLATIONS.md) retains the 68 E1b user-facing entries and adds
two E3 receipt strings and nine E4 entries. Catalogs now contain 81 entries,
including two infrastructure entries and retained historical copy. E4 uses one
trusted platforms placeholder in /start; plural rules remain unchanged. English
msgids are trusted application copy. Translate first, then substitute plain named
values. Counts use native gettext ngettext, including Russian plural forms.

The compiler requires nonempty, nonfuzzy translations, explicit python-brace-format
markers in PO source, and exact placeholder parity. Babel auto-adds format flags;
the explicit source check prevents missing markers from being silently accepted.
Attribute/index access, conversions and format specifications are not allowed.

Run `uv run python scripts/compile_translations.py`; verify without writes using
`uv run python scripts/compile_translations.py --check`. Version PO and MO together.
The wheel includes both formats; build/install tests import outside the checkout.
Adding languages requires catalogs, registry and tests, without changing media logic.

## Meaning and verification boundary

At E1b the disabled-platform /start branch was corrected, preserving enabled
branches and message counts. E4 supersedes that greeting with one message listing
only enabled platforms, without img_index instructions. Selection/error routes
retain their useful context-specific guidance. RU busy copy uses informal singular voice.
The review matrix records safety constraints: no automatic retry after uncertain
sending, partial delivery is not success, and item numbers are original source positions.

[E1b verification](TESTING.md#phase-8-e1b-telegram-interface-localization) and
[E2 verification](TESTING.md#phase-8-e2-youtube-choice-ux) separate synthetic
dispatcher/transport checks from LIVE acceptance. E2 performs no deployment.
E2 did not fix the YouTube publish-before-message-binding risk or implement status
cards. E3 addresses publication and durable request receipts as specified below;
E3 excluded terminal cleanup, which E4 adds below. A failed or ambiguous
quality edit retains the transitioned state: no automatic retry or download is added;
a repeated old mode callback can render the same quality step while still valid.
E4 is authorized below; E5 and manual preferences require separate authorization. Phase 9 reliability remains OPEN.

## E3 publication and status-card decision

Reason: sending an interactive keyboard before storing its message ID leaves a
callback race. E3 sends a noninteractive, localized receipt first. Only a confirmed
message response permits binding the pending interaction; a subsequent
edit publishes the prompt and keyboard together. Store validation independently
rejects unbound callbacks and missing or mismatched message IDs.

The initial receipt includes recovery guidance if buttons never appear. The TTL
starts at the original creation time, before the send. A failed or ambiguous initial
send removes the unbound interaction. An ambiguous edit retains the bound interaction because Telegram may have applied it; there is no automatic
retry. A visible keyboard can still be used, subject to the unchanged TTL.

After terminal consume, the same message becomes a durable download-request
receipt, replacing keyboard removal with one text-and-keyboard edit. Direct
downloads use the same copy in their existing single status message. This records
acceptance, not ongoing worker activity or delivery confirmation; it therefore
remains truthful after success, failure or cancellation. No new metadata progress
message, percentage, ETA or inferred FFmpeg stage is introduced. E4 still owns
terminal outcome cards and comprehensive stale-message cleanup. Live progress
would require a separately approved UI lifecycle; E3 does not add it implicitly.

Budget: interactive publication adds exactly one editMessageText to its existing
sendMessage. Mode-to-quality remains one acknowledgement plus one edit. Terminal
selection remains one acknowledgement plus one edit; direct download message
count is unchanged. Telegram edit failures are sanitized and do not retry media.

## E4 terminal presentation decision

Reason: a request receipt is not a delivery result, and an obsolete selection prompt
should not remain after consume. E4 adds a minimal typed YouTube delivery result
in the Telegram layer: delivered, failed or uncertain, plus trusted localized copy.
The wrapper edits the same card once after completion. It neither retries media
nor infers delivery from a successful status edit. A positive media response is
required for success; lost responses and cancellation do not prove non-delivery.
A confirmed media acknowledgement remains authoritative if later cleanup fails.

A per-interaction presentation lock sequences YouTube edits only, including initial
keyboard publication. Mode callbacks revalidate inside this lock after acknowledgement,
so a consumed request cannot be locally repainted as a live choice. No store lock
is held across network I/O; media work runs outside the presentation lock. Callback
payloads, TTL, ownership, one-shot consume, admission and worker deadlines are unchanged.
Remote application after an ambiguous API response cannot be absolutely ordered;
UI remains best-effort, without automatic retry or background repair tasks.

The existing Instagram selection edit changes text as well as removing the keyboard
after the same consume point and within its existing timeout. Carousel acquisition,
partial/uncertain delivery and quarantine remain unchanged. Invalid/foreign/expired
callbacks cannot edit a card whose ownership has not been validated. TikTok and Reel
flows have no selection keyboard to retire; their downloader paths are unchanged.

/start becomes one localized message listing only currently enabled platforms,
including the existing TikTok per-user allows check. Language selection, pinned
callback locales and English fallback remain those of E1b.

### Terminal evidence and failure handling

A media response containing the requested video/audio confirms delivery. No media
field, network/server failure, upload timeout or interruption leaves delivery uncertain;
there is no automatic retry. Explicit negative acknowledgements (bad request,
forbidden/unauthorized, rate limit or oversized file) and pre-upload failures produce
localized failure copy. Source titles and upload parameters remain unchanged.
A cleanup error after positive acknowledgement still produces a sent result with a
finishing-error notice, without encouraging a duplicate download.

Cancellation propagates after the existing workspace worker drain. The wrapper then
attempts one interrupted/uncertain edit. Further cancellation or notification error
cannot replace that cancellation or abandon a worker. A failed terminal edit is
logged by safe category, without a fallback send or repair task; the neutral receipt
or previous keyboard may remain. UI success never proves media success. A process
crash cannot promise a terminal edit.

The presentation lock lives with the immutable interaction copies, excluded from
equality/repr. It sequences that card only; media runs outside the UI lock and the
store's threading lock is never held across await. Existing Telegram request timeouts
still apply: a stuck edit can delay that request's next UI step, without blocking the
event loop or another card. No resource limits/timeouts are reconfigured. A remote
late application after an ambiguous response cannot justify automatic retry.

Budget: /start always sends one message. Healthy direct and interactive YouTube
flows add one terminal edit compared with E3, without a separate success message.
Pre-upload errors use the same card instead of an additional error send. The
accepted-request and terminal-result edits are distinct planned states; neither is
automatically retried. Instagram keeps its one post-consume edit and 10-second cap;
a known publisher bind failure may add one cleanup edit within the existing operation
window. Partial/uncertain carousel delivery copy remains unchanged. Invalid foreign/
expired/unknown callbacks receive their existing toast and cannot erase another
user's valid prompt.
