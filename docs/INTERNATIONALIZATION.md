# Internationalization foundation (Phase 8 E1a)

## Scope and decision

Use aiogram I18n, GNU gettext and Babel instead of a custom translation engine or
plural rules. The foundation is inactive: bot.py, current messages/keyboards,
callback routing and media pipelines remain unchanged. Activation in E1b, editable
cards, manual language selection and command/profile publication require separate
authorization. No translation service, database or runtime API call is introduced.

## Locale lifecycle

Resolve the sender's optional Telegram language_code locally. Bounded ASCII tags
are parsed by Babel; regional tags select a supported base language (en/ru/es).
Missing, malformed, unsupported languages or tag shapes fall back to English.
This is not a universal BCP 47 parser or client-specific language detection.

RequestLocaleMiddleware is opt-in and not registered in the dispatcher. It uses
aiogram ContextVar contexts, restored after exceptions and cancellation. Callback
locale comes from callback.from_user, never callback.message.from_user.

Pending records have a keyword-only presentation locale, default en for existing
callers. Current handlers do not populate the user locale or render translations. Creation validates this resolved value. Binding, transitions, expiry and
consume retain their contracts. Future handlers must validate the pending record's
owner/chat/message/freshness before using its pinned locale. Invalid/stale/foreign
callbacks use the current sender locale. Locale does not enter ChoicePlan, callback
data, quality IDs, source identities or worker IPC. These are foundation contracts,
not integrated acceptance of translated user interactions.

## Catalogs and packaging

Package-local locales contain only infrastructure test strings in EN/RU/ES.
Translate before named substitution; use ngettext for counts. The compiler validates
plain named brace placeholders; attribute access, conversions and format specifications
are not part of this initial catalog contract. Do not translate
upstream titles or machine identifiers. Adding a language needs a catalog, registry
entry and tests, with no media logic change or preference storage.

Compile with `uv run python scripts/compile_translations.py`; verify without writes
with `uv run python scripts/compile_translations.py --check`. Version .mo files with
their .po sources. Compilation is deterministic; no build hook mutates source files.
The wheel must contain both formats. Test installation into an isolated target and
import outside the source tree: source-file presence alone is insufficient.
Existing Docker source-copy/package-install steps remain; no image build is claimed.

## Verification boundary

See [foundation verification](TESTING.md#phase-8-e1a-internationalization-foundation).
The full E1b text catalog, activation, manual overrides, profile metadata and LIVE
acceptance are outside E1a. Phase 9 reliability remains OPEN.
