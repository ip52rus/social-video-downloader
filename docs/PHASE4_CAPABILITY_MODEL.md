# Phase 4 Capability Model

## Purpose

Phase 4 needs a minimal capability model for Telegram download UX. The model must use the
existing provider architecture rather than create a second independent capability system.

Core rule:

`minimum steps + provider-specific capabilities + consistent visual language`

The bot should show only meaningful choices for the current platform and content. If
there is no meaningful choice, Telegram should not add an extra screen.

## Existing Foundation

The current provider contract already has the primitives needed for Phase 4:

- `DownloadMode`
  - `VIDEO_WITH_AUDIO`
  - `VIDEO_ONLY`
  - `AUDIO_ONLY`
- `QualityOption`
- `MediaProvider.get_supported_modes(url)`
- `MediaProvider.get_available_qualities(url, mode)`
- `DownloadOptions`
- `DownloadService`

Phase 4 should add only a thin application/Telegram interpretation layer over these
existing primitives. It should not duplicate provider extraction logic, create a parallel
source of truth for platform capabilities, or add provider-owned product analytics.

## Architectural Distinction

### Provider Capabilities

Provider capabilities are factual technical capabilities for a specific URL/content item.

Provider responsibilities:

- detect whether the provider can handle the URL;
- report available `DownloadMode` values through `get_supported_modes(url)`;
- report selectable `QualityOption` values through `get_available_qualities(url, mode)`;
- reject unsupported modes or invalid quality IDs during `download()`;
- keep provider-specific extraction details inside the provider.

Providers should not decide which options are good product UX. For example, if YouTube can
technically provide `VIDEO_ONLY`, the provider should be free to report it. Hiding that
option from normal users is product policy, not provider capability.

### Product/UX Policy

Product/UX policy belongs in the application/Telegram layer. It maps technical
capabilities to user-facing choices and finally to `DownloadOptions`.

Policy responsibilities:

- decide whether a mode should be shown, hidden, or selected automatically;
- decide whether quality selection is useful for the current mode/content;
- define user-facing labels and button flow;
- avoid meaningless choices and extra screens;
- preserve automatic/best selection when no user decision is useful;
- record analytics about available, hidden, shown, and selected options.

This keeps providers factual and lets the product vary UX by platform, content type, and
evidence from real usage.

The Telegram handler should not contain provider-specific branching such as "if YouTube,
show these buttons; if Instagram, skip these buttons." Instead, handler code should call
application-layer policy/helpers that derive an interaction plan from provider
capabilities and product policy. The handler should render that plan and submit the final
`DownloadOptions`.

## Minimal Interpretation Model

The Phase 4 implementation can be designed around a transient application-layer view of
provider output. This is a design concept, not a required dataclass or database schema.

Provider input:

- platform/provider selected by `DownloadService`;
- normalized URL;
- supported modes from `get_supported_modes(url)`;
- qualities for relevant modes from `get_available_qualities(url, mode)`;
- metadata or content characteristics only where already available and useful.

Policy output:

- direct download with `DownloadOptions`, or
- one user choice screen, or
- a short sequence of meaningful choice screens.

Every final path must produce `DownloadOptions` for `DownloadService`.

Examples:

- direct video: `DownloadOptions(mode=VIDEO_WITH_AUDIO, quality_id=None)`;
- YouTube audio: `DownloadOptions(mode=AUDIO_ONLY, quality_id=None)`;
- YouTube video with selected quality tier: `DownloadOptions(mode=VIDEO_WITH_AUDIO, quality_id=<mapped provider quality ID>)`.

The interpretation layer may track hidden options and reasons for analytics, but hidden
technical capabilities should not become user-facing buttons.

## Application Choice Model

The next Phase 4 step should add a minimal application-level choice model between provider
capabilities and the future Telegram UI:

provider capabilities -> product policy -> transport rendering -> `DownloadOptions`

This model must be transient and immutable. It should not become a second provider
capability system, and it should not contain Telegram button text, callback-data formats,
FSM state, analytics storage, or provider/media-engine selection logic.

### Concrete models/API

Use existing primitives as the source of truth:

- technical modes come from `DownloadMode`;
- selectable technical qualities come from `QualityOption`;
- final execution options are `DownloadOptions`;
- Low / Medium / High video tier decisions come from `QualityTierPlan`.

Minimal concrete application API:

```python
class ChoicePlanState(StrEnum):
    DIRECT_DOWNLOAD = "direct_download"
    CHOOSE_MODE = "choose_mode"
    CHOOSE_QUALITY = "choose_quality"
    BLOCKED = "blocked"


class UserChoiceKind(StrEnum):
    VIDEO = "video"
    AUDIO = "audio"


@dataclass(frozen=True, slots=True)
class QualityChoice:
    tier: QualityTier
    quality: QualityOption
    final_options: DownloadOptions


@dataclass(frozen=True, slots=True)
class ModeChoice:
    kind: UserChoiceKind
    mode: DownloadMode
    final_options: DownloadOptions | None
    quality_choices: tuple[QualityChoice, ...] = ()


@dataclass(frozen=True, slots=True)
class ChoicePlan:
    state: ChoicePlanState
    technical_modes: tuple[DownloadMode, ...]
    hidden_modes: tuple[tuple[DownloadMode, str], ...]
    unavailable_choices: tuple[tuple[UserChoiceKind, str], ...]
    mode_choices: tuple[ModeChoice, ...] = ()
    quality_choices: tuple[QualityChoice, ...] = ()
    automatic_options: DownloadOptions | None = None
    blocked_reason: str | None = None
```

Invariants:

- `DIRECT_DOWNLOAD` means `automatic_options` is present and can be passed directly to
  `DownloadService.download()`.
- `CHOOSE_MODE` means `mode_choices` contains at least two user-facing choices. Selecting
  a `ModeChoice` either yields its concrete `final_options` or its concrete
  `quality_choices`.
- `CHOOSE_QUALITY` means the only useful mode is already implied and `quality_choices`
  contains at least two final choices.
- `BLOCKED` means no safe product path can produce `DownloadOptions`; `blocked_reason`
  explains why.
- Every terminal `ModeChoice`, `QualityChoice`, and automatic path carries concrete
  `DownloadOptions`. Telegram handlers must render and resolve these objects, not
  reinterpret provider capabilities.

`QualityChoice.final_options` must include the exact provider `quality_id` from the
underlying `QualityOption`. If tier collapse leaves exactly one distinct `QualityOption`,
the quality screen is skipped, but the automatic video path must still use
`DownloadOptions(mode=VIDEO_WITH_AUDIO, quality_id=<that exact quality_id>)`. It must not
be converted to `quality_id=None`, because that would ask the provider to choose a
possibly different automatic/best quality.

The same rule applies to any future automatic path created from a specific provider
option: preserve that provider option's identity in `DownloadOptions`.

Do not add a separate "platform capability" enum that mirrors `DownloadMode`. User-facing
semantics such as `video` and `audio` are product choices layered over `DownloadMode`, not
new provider facts.

`HiddenCapability` is not required for the first implementation. A simpler
`hidden_modes: tuple[tuple[DownloadMode, str], ...]` is enough for the known policy case of hiding
YouTube `VIDEO_ONLY`, and avoids a generic capability wrapper before hidden non-mode
capabilities exist. If future policy hides individual qualities, add a focused field for
hidden quality IDs rather than widening the provider capability model.

Conceptual API:

```python
class DownloadService:
    def create_choice_plan(self, url: str) -> ChoicePlan: ...
```

`DownloadService.create_choice_plan()` should reuse the same normalization, platform
detection, and provider selection path as `download()`. Internally it can delegate product
policy to a small pure helper, but handler code should not perform provider lookup itself.
This avoids duplicating URL/provider resolution while keeping `DownloadService.download()`
as the only execution path.

A separate planning service is only justified if provider lookup is first extracted into a
shared application component used by both services. Creating an independent planning
service with its own provider registry would duplicate routing logic and should be
avoided.

### Responsibilities

Provider responsibilities stay factual:

- report `get_supported_modes(url)`;
- report `get_available_qualities(url, mode)`;
- reject unsupported `DownloadOptions`;
- keep extraction, selector, codec, and container behavior inside the provider/media
  pipeline.

Application policy responsibilities:

- decide which technical modes are meaningful user-facing choices;
- hide technical modes that should not appear in normal UX;
- decide whether a quality screen is useful after a selected semantic mode;
- map quality tiers to existing provider `QualityOption` values;
- produce exact `DownloadOptions` for every final path;
- expose enough non-persistent facts for future analytics to know what was technically
  available, hidden, shown, and selected.

Transport responsibilities:

- render the `ChoicePlan` in Telegram;
- preserve user selection state between steps;
- pass the selected `DownloadOptions` back to `DownloadService.download()`;
- choose localized button text outside domain/provider models.

### Flow

Future handler flow:

1. Receive URL.
2. Call `DownloadService.create_choice_plan(url)`.
3. If the plan has no useful path, send an explicit unsupported/error response.
4. If `state` is `DIRECT_DOWNLOAD`, call `DownloadService.download(url, output_dir,
   plan.automatic_options)` immediately.
5. If `state` is `CHOOSE_MODE`, render `plan.mode_choices`.
6. If the selected `ModeChoice.final_options` is present, download with it.
7. If the selected `ModeChoice.quality_choices` has multiple entries, render those quality
   choices.
8. If `state` is `CHOOSE_QUALITY`, render `plan.quality_choices` immediately because the
   mode is already implied.
9. Resolve the final user selection to the stored `DownloadOptions`.
10. Call the existing `DownloadService.download()` execution path.

No Telegram state machine is implemented by this model. The model only defines what the
state machine will need to render and resolve.

### YouTube example

If YouTube reports:

- `VIDEO_WITH_AUDIO`;
- `VIDEO_ONLY`;
- `AUDIO_ONLY`;
- classifiable video qualities for `VIDEO_WITH_AUDIO`;

application policy should produce:

- shown mode choices:
  - semantic `video`, technical `VIDEO_WITH_AUDIO`;
  - semantic `audio`, technical `AUDIO_ONLY`;
- hidden capability:
  - technical `VIDEO_ONLY`, reason `hidden_by_normal_youtube_policy`;
- audio final options:
  - `DownloadOptions(mode=AUDIO_ONLY, quality_id=None)`;
- video quality plan:
  - build `QualityTierPlan` from `get_available_qualities(url, VIDEO_WITH_AUDIO)`;
  - if one distinct tier remains, skip the quality screen and use that tier's
    exact `quality_id` in a concrete `DownloadOptions`;
  - if two or three distinct tiers remain, show only those tier choices;
  - final video options are
    `DownloadOptions(mode=VIDEO_WITH_AUDIO, quality_id=<tier quality_id>)`.

If no video quality can be classified, do not show fake Low / Medium / High choices. The
plan should record `(VIDEO, "safe_quality_mapping_unavailable")` in `unavailable_choices`
or, if no other useful path remains, `state=BLOCKED` with the same reason. Because
`quality_id=None` currently means provider automatic/best for YouTube and may exceed the
High approximately 1080-class product policy, an empty or unclassifiable `QualityTierPlan`
must not silently become
`DownloadOptions(mode=VIDEO_WITH_AUDIO, quality_id=None)` as normal High/default
behavior.

Later implementation may add a safe provider-level approximately 1080-class ceiling
fallback. Until that exists, the choice model must keep "safe tier mapping unavailable"
distinct from ordinary automatic provider selection.

### One-choice provider example

For a future provider/content item that reports only `VIDEO_WITH_AUDIO` and no meaningful
selectable quality:

- shown mode choices: none;
- hidden capabilities: none unless policy intentionally hides something;
- automatic options: `DownloadOptions(mode=VIDEO_WITH_AUDIO, quality_id=None)`;
- quality plan: none;
- handler behavior: start download immediately with no mode or quality screen.

This rule is provider-independent. Do not hard-code Instagram or TikTok branches before
their provider spikes prove what capabilities they expose.

This direct automatic path is different from the YouTube unclassifiable-quality case. The
future provider example has no meaningful selectable quality to preserve, so
`quality_id=None` is the provider's factual automatic path. YouTube with available but
unclassifiable qualities has selectable provider options that cannot yet be safely mapped
to product tiers, so treating `quality_id=None` as High would be misleading.

### Relationship to `DownloadOptions`

The choice model is only a planning layer. Every terminal choice must resolve to an exact
`DownloadOptions` instance:

- direct automatic video -> `DownloadOptions(mode=VIDEO_WITH_AUDIO, quality_id=None)`;
- YouTube audio -> `DownloadOptions(mode=AUDIO_ONLY, quality_id=None)`;
- YouTube video tier -> `DownloadOptions(mode=VIDEO_WITH_AUDIO,
  quality_id=<provider quality_id>)`.

The application model must preserve the underlying `QualityOption` or exact
provider-owned `quality_id`. It must not invent provider format identifiers, parse
quality labels as identity, or encode selector logic in product policy.

The handler's job is mechanical: render the choices already present in the plan and submit
the selected choice's stored `DownloadOptions`. It must not decide whether `VIDEO_ONLY` is
hidden, whether one quality should collapse, whether a quality screen is needed, or
whether `quality_id=None` is a safe default.

### Analytics boundary

The choice model may expose non-persistent planning facts useful for analytics:

- technically available modes and quality IDs;
- technically unavailable product choices inferred from absent modes;
- modes hidden by policy and stable reasons;
- user-facing mode choices shown;
- quality tiers shown;
- product choices unavailable because safe mapping is unavailable;
- final selected semantic choice and final `DownloadOptions`.

It must not implement analytics storage, retention, pseudonymous identifiers, event
delivery, or database schema. It must also avoid storing source URLs, titles, authors,
Telegram usernames, message text, or other unnecessary personal data in analytics events.

### Error/no-choice state

A no-choice plan is different from an automatic plan:

- automatic plan means one useful path exists and can immediately produce
  `DownloadOptions`;
- no-choice plan means no supported provider capability can produce a meaningful product
  path for this URL/content item.

Examples of no-choice states:

- provider supports the URL but reports no supported modes;
- only modes unsupported by current product policy are available;
- quality selection is required for the chosen product path but no classifiable or safe
  fallback mapping is available.

The first implementation should prefer explicit unsupported/error user messaging for
no-choice plans rather than silently downloading an unbounded automatic quality.

Normal "needs user choice" states are not errors and should not be represented with
exceptions. Use `ChoicePlanState.CHOOSE_MODE` or `ChoicePlanState.CHOOSE_QUALITY`.
Provider extraction failures and unsupported platform errors may still use existing domain
errors before a plan can be built.

### Unresolved decisions for implementation

- Whether `blocked_reason`, `hidden_modes` reasons, and `unavailable_choices` reasons
  should be free strings or small enums in the first code implementation.
- Whether the first implementation allows a safe automatic video fallback when YouTube
  quality metadata is insufficient, and what explicit evidence is required.
- How much of the future analytics event shape should be defined before Telegram UI work.
- Whether to extract a shared provider resolver later if planning grows beyond a single
  `DownloadService.create_choice_plan()` method.

## Telegram Interaction State Flow

Telegram should be a renderer and executor for `ChoicePlan`, not a second product-policy
engine. The handler must call `DownloadService.create_choice_plan(url)`, render the
choices already present in the plan, store only the temporary interaction context needed
for callbacks, and eventually call the existing download/delivery flow with the stored
`DownloadOptions`.

The Telegram layer must not:

- call provider capability methods directly;
- decide whether `VIDEO_ONLY` should be hidden;
- compute Low / Medium / High tiers;
- reinterpret `quality_id=None` as High, best, or fallback policy;
- parse `QualityOption.label` or provider format IDs;
- store Telegram labels, callback syntax, or message text in application models.

### State storage approach

Use a small dedicated in-memory pending-interaction store for the first implementation.

Reasons:

- the current project does not already use aiogram FSM/state storage;
- a dedicated store keeps callback resolution easy to test without Telegram transport;
- no Redis, database, queue, or persistence is justified for a short-lived interaction;
- in-memory state makes restart behavior explicit: pending buttons become stale and safe.

Aiogram FSM can be reconsidered later if broader multi-step bot flows need one shared
state mechanism. Redis or database-backed state belongs to a later reliability stage only
if measured deployment requirements justify persistence or multi-instance coordination.

### Pending interaction model

The Telegram adapter should create one pending interaction only when the plan requires a
button response: `CHOOSE_MODE` or `CHOOSE_QUALITY`.

Minimal transient state:

- `interaction_id`: short opaque random ID, for example 128 bits encoded with URL-safe
  characters;
- `owner_user_id`: Telegram user ID that created the interaction;
- `chat_id`: chat where the interaction was shown;
- `message_id`: bot message containing the buttons, recorded after send/edit where
  available;
- `url`: source URL needed later to call `DownloadService.download()`; storing the
  validated user-submitted URL is sufficient because the service normalizes again;
- `plan`: the immutable `ChoicePlan` returned by the application service;
- `created_at` and `expires_at`;
- `consumed`: boolean set atomically before starting a terminal download;
- optional `active_step`: `mode` or `quality`, useful for validating callback type;
- optional `selected_mode_index`: set only when a mode selection opens that
  `ModeChoice`'s quality choices, so later quality callbacks resolve against the exact
  stored `ModeChoice.quality_choices`.

The pending state may temporarily contain the URL because callback handling needs it for
download. The URL must not be placed in callback data, intentionally logged, emitted to
analytics, or persisted.

The store key is `interaction_id`. Ownership checks use `owner_user_id` and `chat_id`.
`message_id` is not a security boundary by itself, but it helps reject callbacks from a
different message if Telegram supplies it and helps clean up stale button messages.

### Callback payload

Callback data should be compact and opaque:

- mode selection: `dl:v1:<interaction_id>:m:<mode_index>`;
- quality selection: `dl:v1:<interaction_id>:q:<quality_index>`.

Rules:

- `interaction_id` is the only lookup key in callback data;
- callback data contains no source URL, title, author/channel, provider format ID, or
  Telegram label text;
- callback data must fit Telegram's 64-byte callback-data limit; with a 128-bit URL-safe
  interaction ID, payloads such as `dl:v1:<interaction_id>:m:<mode_index>` remain well
  below that limit;
- `mode_index` indexes `plan.mode_choices`;
- `quality_index` indexes either `plan.mode_choices[selected_mode_index].quality_choices`
  or `plan.quality_choices`, depending on the current step;
- indices are validated against the stored plan before any download starts;
- callback payload parsing errors are treated as invalid callbacks, not domain errors.

The handler may map choices to user-facing labels while rendering:

- `UserChoiceKind.VIDEO` -> `🎬 Видео`;
- `UserChoiceKind.AUDIO` -> `🎵 Аудио`;
- `QualityTier.LOW` -> `Низкое`;
- `QualityTier.MEDIUM` -> `Среднее`;
- `QualityTier.HIGH` -> `Высокое`.

These labels belong only to Telegram presentation code.

### Ownership and stale behavior

Callback handling must validate:

- payload parses as the expected version and action type;
- `interaction_id` exists;
- pending interaction has not expired;
- `consumed` is false;
- callback user ID equals `owner_user_id`;
- callback chat ID equals `chat_id`;
- optional callback message ID matches `message_id` when available;
- selected index exists for the stored step.

Safe behavior:

- invalid callback payload: answer callback with a short generic error and do not
  download;
- unknown interaction: tell the user the selection is no longer available and ask them to
  send the link again;
- expired interaction: delete the pending state lazily, tell the user to send the link
  again, and do not download;
- callback from another user: answer callback privately that the buttons belong to
  another user and do not download;
- already consumed interaction: answer that the request is already being processed and do
  not start another download;
- download error after valid selection: use the existing safe download-error handling.

Do not expose internal `blocked_reason`, provider errors, callback parse details, or debug
state to the user.

### Multiple interactions and replacement

When a user sends a new URL while older buttons still exist, the simplest safe behavior is
to keep the old pending interaction until it expires or is consumed. Each callback remains
bound to its own `interaction_id`, user, and chat, so older buttons cannot resolve to a
newer URL.

The first implementation may optionally expire existing pending interactions for the same
`owner_user_id` and `chat_id` when a new URL creates a new pending interaction. This is a
UX cleanup choice, not a correctness requirement. If replacement is implemented, old
buttons should produce the normal stale/expired response.

### TTL and cleanup

Use a short interaction TTL, for example 15 minutes.

Cleanup rules:

- terminal callback selection: set `consumed=True` atomically, remove the pending entry
  before or immediately after starting the download task;
- expired access: remove the pending entry lazily and report stale interaction;
- optional replacement: remove prior pending entries for the same user/chat;
- bot restart: in-memory store is empty, so existing buttons become unknown/stale.

No background cleanup worker is required initially. Lazy expiration on lookup and on new
interaction creation is enough for a single-process MVP. Production recovery and
multi-instance coordination remain Phase 9 concerns.

### Double-click and concurrency

A terminal callback must atomically consume the pending interaction before starting the
download. A second click on the same terminal choice should see `consumed=True` or a
missing interaction and must not start another download.

For a non-terminal mode callback that opens a quality screen, the interaction remains
pending and moves to the quality step. If the user clicks the same mode twice quickly, the
handler should either edit/show the same quality choices idempotently or answer that the
interaction is already on the quality step. It must not create multiple independent
pending entries for the same original plan.

Single-process locking around the in-memory store is sufficient for this stage. Do not
design distributed locks or cross-process coordination now.

### Flow details

`DIRECT_DOWNLOAD`:

1. Handler receives URL.
2. Handler calls `create_choice_plan(url)`.
3. Handler calls existing download/delivery flow immediately with
   `plan.automatic_options`.
4. No pending interaction is created.

`CHOOSE_MODE`:

1. Handler receives URL and creates a plan.
2. Handler creates a pending interaction with the plan and source URL.
3. Handler renders one button per `plan.mode_choices`.
4. Audio terminal choice resolves directly to its stored `ModeChoice.final_options`.
5. Video terminal choice resolves directly to its stored `ModeChoice.final_options`.
6. Video with `ModeChoice.quality_choices` records the selected mode index, moves the
   same pending interaction to the quality step, and renders only those stored quality
   choices.
7. Handler never computes tiers or mode policy during callback processing.

`CHOOSE_QUALITY`:

1. Handler receives URL and creates a plan.
2. Handler creates a pending interaction with `plan.quality_choices`.
3. Handler renders only meaningful `QualityChoice` values already present in the plan.
4. Callback resolves by index to the exact stored `QualityChoice.final_options`.

`BLOCKED`:

1. Handler receives URL and creates a plan.
2. Handler sends a concise user-facing message that no safe download option is available.
3. Handler does not create pending interaction state and does not start download.

### Current application API sufficiency

The current `ChoicePlan` API is sufficient for the first Telegram interaction
implementation:

- `ModeChoice.final_options` identifies terminal mode choices;
- `ModeChoice.quality_choices` identifies the next quality step after mode selection;
- `ChoicePlan.quality_choices` supports an immediately implied quality-selection state;
- every `QualityChoice.final_options` already contains the exact `DownloadOptions`;
- `ChoicePlan.automatic_options` supports direct download;
- `ChoicePlan.blocked_reason` and `unavailable_choices` support safe blocked messaging and
  later analytics facts.

No application-model extension is required before implementing Telegram handlers. If
later Telegram code needs stable non-index identifiers for choices, add display-layer
tokens in the pending store rather than changing provider or domain models.

### Telegram interaction implementation sequence

1. Add an in-memory pending-interaction store with TTL, ownership checks, and atomic
   consume.
2. Add callback-data parsing/building helpers for versioned mode and quality callbacks.
3. Update URL intake to call `DownloadService.create_choice_plan(url)`.
4. Route `DIRECT_DOWNLOAD` to the existing download/delivery flow.
5. Render mode buttons for `CHOOSE_MODE`.
6. Render quality buttons for `CHOOSE_QUALITY` and mode-selected quality steps.
7. Resolve callbacks to stored `DownloadOptions` and call existing download/delivery.
8. Add deterministic tests for direct, mode, quality, blocked, stale, expired,
   wrong-owner, consumed, and double-click paths.

### Telegram interaction non-goals

This design does not implement:

- Telegram buttons, handlers, callbacks, or FSM;
- Redis/database-backed interaction state;
- analytics events, storage, or retention policy;
- progress UI;
- cancellation;
- persistent recovery after bot restart;
- multi-instance coordination;
- monetization or access control.

## YouTube Policy

YouTube can technically expose:

- `VIDEO_WITH_AUDIO`;
- `VIDEO_ONLY`;
- `AUDIO_ONLY`;
- multiple video and audio qualities.

Normal user-facing Phase 4 UX:

1. Show `🎬 Видео` when `VIDEO_WITH_AUDIO` is available.
2. Show `🎵 Аудио` when `AUDIO_ONLY` is available.
3. Do not expose `VIDEO_ONLY` as a normal user option.
4. After `🎬 Видео`, offer:
   - `Низкое`
   - `Среднее`
   - `Высокое`
5. After `🎵 Аудио`, start download without an audio quality screen unless later evidence
   justifies that extra step.

If only one meaningful option is available for a particular YouTube item, the UX may skip
unnecessary choice screens and proceed with the best supported default.

## YouTube Quality Semantics

Phase 4 uses three user-facing quality tiers for YouTube video:

| Tier | Button label | Target class | Product intent |
| --- | --- | --- | --- |
| Low | `Низкое` | approximately 480-class | Lower bandwidth/resolution |
| Medium | `Среднее` | approximately 720-class | Balanced Telegram-friendly quality |
| High | `Высокое` | approximately 1080-class | Best reasonable Telegram-oriented quality |

High must not mean unlimited maximum/original quality and must not automatically select
1440p, 2160p, or 4320p when a 1080-class option exists. Do not introduce a `Maximum`
button in Phase 4.

### Orientation-independent metric

Do not classify YouTube quality only by `height`. A landscape 1920x1080 format and a
portrait 1080x1920 format should both be treated as roughly 1080-class.

Recommended metric for ordinary video:

`quality_resolution = min(width, height)`

Examples:

| Format dimensions | `quality_resolution` | Class |
| --- | ---: | --- |
| 854x480 | 480 | 480-class |
| 1280x720 | 720 | 720-class |
| 1920x1080 | 1080 | 1080-class |
| 1080x1920 | 1080 | 1080-class |
| 720x1280 | 720 | 720-class |
| 1080x1080 | 1080 | 1080-class |

This metric handles landscape, portrait, and square video with one simple rule. It also
avoids treating portrait 1080x1920 as a 1920-class or 4K-like option.

### `QualityOption` shape

`QualityOption` stores `height`, optional `width`, and optional `bitrate_kbps`. Keeping
both dimensions lets the application/UX policy layer perform orientation-independent
YouTube tier mapping while provider-specific quality IDs remain opaque.

Implemented foundation:

- `QualityOption.width: int | None = None` is available and validated like `height`;
- the YouTube provider preserves width and height from yt-dlp format metadata in video
  quality options where those dimensions are available;
- compute `quality_resolution = min(width, height)` when both are available;
- keep provider-specific `quality_id` values opaque to application/Telegram code.

The download selector behavior remains height-based inside the YouTube provider; the
application mapping only selects an existing provider `quality_id`.

### Missing or partial metadata

Selection policy should degrade predictably:

- If both `width` and `height` are present, use `min(width, height)`.
- If only `height` is present, use `height` as a legacy fallback and mark the mapping as
  lower confidence because portrait content can be over-classified.
- If only `width` is present, use `width` as a lower-confidence fallback.
- If neither dimension is present, treat the option as unclassified for tier mapping.
- If no classifiable video quality options remain, do not show a fake Low/Medium/High
  choice.
- Prefer a safe product default consistent with the High / approximately 1080-class
  policy when the provider can enforce that ceiling reliably.
- Only if the provider cannot reliably apply a 1080-class ceiling because metadata is
  insufficient may it fall back to provider automatic/best behavior.
- That fallback is exceptional and must not redefine High as unlimited maximum/original
  quality.
- Future analytics/diagnostics should distinguish this fallback from normal High
  selection.

Do not parse dimensions from labels as a primary strategy. Labels are user-facing text,
not a stable capability contract.

### Tier selection algorithm

Use a deterministic ceiling-first policy for each target tier.

For each tier target `T`:

1. Build candidate video qualities with a classifiable `quality_resolution`.
2. Prefer the highest candidate where `quality_resolution <= T`.
3. If no candidate is at or below `T`, choose the lowest candidate above `T`.
4. If multiple candidates have the same `quality_resolution`, prefer the provider's
   existing ordering or selector-specific quality ID; do not duplicate codec/bitrate
   scoring in product policy.
5. After mapping tiers, collapse duplicate results:
   - never display multiple quality buttons that resolve to the same underlying
     `QualityOption`;
   - collapse duplicate mappings before presenting UX;
   - if only one distinct useful quality remains, skip the quality screen entirely;
   - if two distinct mappings remain, show only those meaningful choices rather than
     three misleading buttons.

If multiple tiers resolve to the same underlying provider `QualityOption`, keep the tier
whose target is semantically closest to the actual `quality_resolution`. For example, if
both Low and Medium would resolve to a 720-class option, keep Medium and do not show a
duplicate Low button for the same provider quality. The implemented application helper
uses a deterministic tie-break when a quality is exactly between two tier targets: prefer
the tier whose target is not below the actual quality resolution, then fall back to fixed
Low / Medium / High order.

This policy intentionally prefers `highest available <= target` rather than nearest
available. It respects the user's bandwidth/resolution intent: Medium should not jump to
1080-class merely because 1080 is numerically close to 720 when a lower suitable option
exists.

### Edge cases

Exact target missing:

- choose the highest available class below the target;
- if none is below, choose the lowest available class above the target.

All variants above target:

- choose the lowest available class above the target;
- for High, this is the only case where an above-1080 option may be selected
  automatically, and it should choose the lowest such option rather than maximum/original.

All variants below target:

- choose the highest available class below the target;
- High may resolve to 720-class or lower when no better format exists.

Unusual aspect ratios:

- use `min(width, height)` for ordinary video, including square and vertical formats;
- do not add aspect-ratio-specific policy until real cases show the simple metric is
  misleading.

Insufficient metadata:

- if individual qualities are missing dimensions, exclude them from tier mapping unless a
  legacy one-dimension fallback is available;
- if the provider cannot expose dimensions reliably, skip the quality screen and use
  automatic/best provider selection.

### Interaction with provider format selection

Quality tiers express resolution intent, not complete format scoring. Product policy
should map Low/Medium/High to a target class and selected provider `quality_id`; the
YouTube provider should remain responsible for choosing the best Telegram-friendly format
inside that intent using existing provider logic.

Do not duplicate codec ranking, estimated-size scoring, bitrate scoring, or adaptive
network logic in the product policy layer without evidence. H.264/AAC preference and
container/media assembly remain provider/media-preparation responsibilities.

Estimated file size and bitrate can be recorded for analytics where available, but they
should not drive Phase 4 quality-tier selection. File-size policy belongs to future
Production Reliability and large-file limit work.

## Instagram And TikTok Policy

Do not hard-code future Instagram or TikTok capabilities before their provider spikes.

Expected UX principle:

- if a provider/content item offers only normal video and no meaningful quality
  alternatives, start the download directly;
- do not show audio-only steps by default;
- do not show a quality-selection screen unless the provider proves useful selectable
  variants;
- map meaningful future format/quality choices into the shared `DownloadOptions` model
  only when real provider evidence supports it.

The same rule applies to later platforms: provider/content capabilities first, then
product policy.

## Analytics Implications

Analytics should improve UX and technical decisions without storing users' viewing
history.

Track aggregate or pseudonymous events for:

- platform;
- video/audio selection;
- quality selection;
- option availability;
- options unavailable for the content/provider;
- options hidden by product policy;
- options shown but not selected;
- options selected;
- short-form vs regular/long-form content where detectable;
- duration, file-size, and resolution buckets;
- success/failure categories;
- passthrough/remux/transcode;
- download, preparation, upload, and total timing;
- aggregate user usage such as total, unique, and returning users.

Do not store:

- source URLs;
- video titles;
- authors or channels;
- Telegram usernames;
- message text;
- unnecessary personal data.

Providers must not own product analytics logic. Providers may expose factual technical
capabilities; the Telegram/application flow emits analytics events based on product
policy and user choices.

Analytics storage is not implemented in this design stage. SQLite or another storage
choice requires a separate implementation design and evidence that it is sufficient. Do
not introduce Mixpanel, Amplitude, ClickHouse, Kafka, Redis, external analytics SaaS, or
other infrastructure during this documentation stage.

## Non-goals

Phase 4 capability design does not:

- create a second capability system independent from `DownloadMode`, `QualityOption`, and
  provider capability methods;
- move product analytics into providers;
- hard-code Instagram, TikTok, or future-platform capabilities before provider spikes;
- expose YouTube `VIDEO_ONLY` as a normal user option;
- define High quality as unlimited 4K/8K;
- introduce a Maximum/original-quality button;
- rank formats by bitrate, estimated size, codec, or network conditions in product
  policy;
- implement analytics storage, database tables, queues, or external analytics services;
- implement Telegram UI in the application choice-model or interaction-design stages.

## Implementation Progress

Implemented and covered by deterministic tests:

- `QualityOption.width` model support and validation;
- YouTube video quality options preserve extracted width and height metadata;
- transport-independent Low / Medium / High mapping in the application services layer;
- immutable `ChoicePlan`, `ModeChoice`, and `QualityChoice` application models;
- `DownloadService.create_choice_plan(url)` using the existing provider
  normalization/selection path;
- direct-download, mode-selection, quality-selection, and blocked plan states with
  concrete `DownloadOptions` for every terminal path;
- orientation-independent resolution classification for landscape, portrait, and square
  video;
- deterministic handling for missing exact targets, all-below/all-above cases,
  one-dimension fallback, unclassifiable options, duplicate tier collapse, and input
  ordering;
- deterministic planning for hidden `VIDEO_ONLY`, audio direct options, legitimate
  single-path automatic provider behavior, and unsafe unclassifiable video qualities.
- Telegram interaction state-flow design for rendering `ChoicePlan`, pending callback
  state, ownership checks, stale handling, TTL, and double-click safety.

Not implemented yet:

- Telegram buttons/state for Video/Audio or quality selection;
- pending-interaction store and callback handlers;
- analytics events or storage;
- file-size prediction, bitrate scoring, 4K/Maximum policy, or provider-specific
  branching in handlers.

## Implementation Sequence

Recommended Phase 4 implementation order:

1. Implement `DownloadService.create_choice_plan()` and immutable application choice
   models against the existing provider contract.
2. Reuse the implemented Low/Medium/High `QualityTierPlan` foundation for video quality
   decisions.
3. Define Telegram interaction/state flow from the choice-plan output.
4. Implement the pending-interaction store and callback-data helpers.
5. Implement YouTube Video/Audio UX from `ChoicePlan`.
6. Implement YouTube video quality choice from `QualityTierPlan`.
7. Define privacy-conscious analytics events, including available, hidden, shown, and
   selected option states.
8. Design and implement analytics abstraction/storage only after the event model is
   accepted.
9. Validate provider capability combinations, policy decisions, UX flow, and analytics
   events.
10. Use real usage evidence later to remove or simplify choices that users do not need.

## Unresolved Decisions

Before implementation, decide:

- how to handle content where `VIDEO_WITH_AUDIO` is unavailable but `VIDEO_ONLY` and
  `AUDIO_ONLY` exist separately;
- how much metadata can be used for short/regular/long classification without storing
  viewing history;
- whether initial analytics storage should be SQLite or another local mechanism;
- how long pseudonymous analytics identifiers should be retained;
- which UX events are required for the first implementation and which can wait.

## Phase 4 Acceptance Notes

Phase 4 should be considered ready for implementation only after:

- the capability interpretation layer is designed against the existing provider contract;
- YouTube Low/Medium/High mapping rules are defined;
- the Low/Medium/High foundation is implemented and verified in the application layer;
- the application choice-model foundation is implemented and verified without Telegram UI;
- Telegram state transitions are specified;
- analytics events are defined with privacy limits;
- direct-download behavior for providers with no meaningful choices is specified;
- tests are planned for provider capability combinations and product policy decisions.
