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

The current `QualityOption` stores `height` and optional `bitrate_kbps`, but not `width`.
That is not enough for orientation-independent YouTube tier mapping at the
application/UX policy layer.

Recommended minimal model change for implementation:

- add optional `width: int | None` to `QualityOption`;
- keep existing `height: int | None`;
- compute `quality_resolution = min(width, height)` when both are available;
- keep provider-specific `quality_id` values opaque to application/Telegram code.

The YouTube provider already reads both `width` and `height` from yt-dlp format metadata
while building quality labels. Phase 4 should preserve both dimensions in `QualityOption`
instead of discarding `width`.

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

- change the provider interface before there is an implementation need;
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
- implement product code, tests, or Telegram UI in this documentation stage.

## Implementation Sequence

Recommended Phase 4 implementation order:

1. Define the application-layer capability interpretation helper against the existing
   provider contract.
2. Preserve width and height in `QualityOption` or otherwise expose both dimensions to
   application policy.
3. Define Telegram interaction/state flow from the helper output.
4. Implement Low/Medium/High mapping rules for YouTube video.
5. Define privacy-conscious analytics events, including available, hidden, shown, and
   selected option states.
6. Design and implement analytics abstraction/storage only after the event model is
   accepted.
7. Implement YouTube Video/Audio UX.
8. Implement YouTube video quality choice.
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
- Telegram state transitions are specified;
- analytics events are defined with privacy limits;
- direct-download behavior for providers with no meaningful choices is specified;
- tests are planned for provider capability combinations and product policy decisions.
