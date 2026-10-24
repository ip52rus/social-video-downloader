# Telegram internationalization (Phase 8 E1a / E1b)

## Scope and decision

E1a introduced aiogram I18n, gettext/Babel and package-local EN/RU/ES catalogs,
merged in PR #75. E1b activates the foundation for existing Telegram presentation
in this feature branch; independent review, merge and deployment remain separate gates.
A cached process-local I18n instance holds catalogs; aiogram ContextVars hold locale.
No custom plural engine, translation API, preference database or /language command.
No command/profile publication or extra Bot API request is introduced.

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
quality ID, callback routing or consume policy changes. Mode-to-quality edits still
change only the keyboard: text synchronization belongs to E2.

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

[Review matrix](TRANSLATIONS.md) lists all 68 user-facing entries (66 singular and
two plural groups), plus the catalogs retain two infrastructure entries. English
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

The disabled-platform /start branch previously suggested unavailable platforms; its
copy now explicitly describes YouTube and disabled Instagram/TikTok. Enabled-platform
branches and message counts are preserved. RU busy copy uses informal singular voice.
The review matrix records safety constraints: no automatic retry after uncertain
sending, partial delivery is not success, and item numbers are original source positions.

[Offline verification](TESTING.md#phase-8-e1b-telegram-interface-localization) separates
synthetic dispatcher/transport checks from LIVE acceptance. No deployment is performed.
The YouTube publish-before-message-binding risk remains unchanged for E3. Editable
cards, new choice UX, terminal cards, manual preferences and E2–E5 require separate
owner authorization. Phase 9 reliability remains OPEN.
