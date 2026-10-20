# Phase 6E: isolated public-page metadata prototype

## Decision before implementation

Controlled Telegram attempts on PR #61 reached native metadata and received HTTP
429 on the embed endpoint, before media GET or upload. The response category does
not identify the rate-limit scope, duration or cause. No evidence establishes that
Telegram changes the native HTTP request or that another endpoint will succeed.

CLI and provider use the same packaged engine. Both derive the requested ID and
canonical Referer with `publication()`, remove benign tracking query/fragment and
request the exact `/embed/v2/<id>` route. `is_from_webapp` and `sender_device` are
not sent. Headers, scoped cookies, DNS/IP pinning, TLS, redirects and body budgets
are shared. The historical standalone implementation has the same transport.

Two inspected sources independently describe public video-page state:

- Installed [yt-dlp 2026.08.19 source](https://github.com/yt-dlp/yt-dlp/blob/2026.08.19/yt_dlp/extractor/tiktok.py),
  `TikTokIE._get_universal_data()` and
  `_extract_web_data_and_status()`: JSON script `__UNIVERSAL_DATA_FOR_REHYDRATION__`,
  then `__DEFAULT_SCOPE__/webapp.video-detail/itemInfo/itemStruct`.
- [Cobalt source at 2ac0436](https://github.com/imputnet/cobalt/blob/2ac0436f717d21c0719974e1c886c91d3c9597b9/api/src/processing/services/tiktok.js):
  the same state path and `video.playAddr`. This is schema research only;
  no AGPL code is copied or translated. The prototype is independently written.

yt-dlp also requests impersonation, generates randomized headers and may solve a
challenge/reload when state is missing. None of those behaviors is adopted.
Cobalt's cookie forwarding and synthetic `@i` URL are not adopted either.

## Narrow prototype

Add a separate parser and metadata-only session adapter, without changing the
embed engine, CLI, provider or Telegram handler. Reuse the existing HTTP transport
and all network/body limits; admit only the supplied publication's canonical page.
Require a single closed JSON script, unambiguous JSON and explicit matching source
ID before admitting a media locator. Initially support only `video.playAddr`
(string or bounded source list), with existing exact CDN admission. This does not
prove MP4 completeness, codecs, audio or availability.

No fallback, retry, alternate metadata destination, media GET, challenge, login,
header change or expanded CDN policy. No live entry point is provided at this gate.
Any future network experiment must run the adapter in the existing owned process
supervisor: the synchronous session's cooperative deadline/socket timeout alone is
not a hard bound on DNS or process lifetime. Real requests require separate approval.

## Evidence and limits

Synthetic real-HTTP-parser tests compare the actual outbound embed requests from
CLI and provider for plain, `is_from_webapp` and `sender_device` inputs. Host,
target and headers match exactly, including canonical Referer and identity encoding.
AST comparison against PR #60's successful standalone revision also finds identical
URL validation, Session, cookies, DNS/IP pinning, TLS and framing. This does not
reconstruct historical DNS/public IP or prove the server-side reason for HTTP 429.

The installed yt-dlp parser recognizes the same synthetic universal-state fixture.
Its mapper overwrites the output ID with the requested ID; the new parser instead
checks original `itemStruct.id` before examining candidate URLs. Missing/mismatched
identity, non-public status, photos, significant unknown photo layouts, duplicate
state/JSON/attributes and malformed/unknown HTML refuse safely. HTML remains in
memory, is not evaluated or logged, and error messages contain fixed categories.
Inert text/template/comment markers are not accepted as the JSON script.

The narrow `playAddr` support deliberately excludes bitrate/download selection,
`video.urls`, synthetic `@i` URLs, short links, playlists and additional API requests.
Missing `playAddr` refuses; no candidate is tried over the network. A returned
locator is not proof of an MP4, working CDN, codec or audible sound. Explicit
separate-audio evidence is preserved as a flag, not silently treated as silence.

The adapter changes only the metadata path for a separate explicit call. The
canonical host/path and optional trailing slash are admitted; redirects to another
publication, username/path, login, embed, private IP or external host stop before
another connection. Original headers and per-operation scoped memory-only cookies
remain unchanged; the jar is cleared on success/failure. Body/request caps and
HTTP 403/429 fail-fast behavior are inherited, with no retries or error-body read.

## Original metadata-only gate (completed separately)

Recommendation: **GO for one supervised metadata-only public-page experiment**,
not for fallback integration or claims of a 429 fix. Owner supplies one full public
video URL; request only its canonical page, no embed preflight/fallback, no media
GET, no account/challenge/impersonation/header tuning. Keep 180 seconds plus bounded
process cleanup, original metadata body/request/redirect budgets and cookie scope.
Stop on 429/403, forbidden redirect, missing state or ID mismatch, without retry.

Use the existing owned process supervision around this synchronous prototype;
there is intentionally no newly enabled CLI or bot route. Report only category,
HTTP status if available, counts/bytes and safe candidate fields. Do not emit the
resolved locator or HTML. A successful matching state would justify planning a
separate acquisition test, not immediate Telegram integration. Another 429, challenge
or missing JSON would leave page feasibility unproven; do not solve or bypass it.

Offline verification: **45 new focused cases PASS**; final full suite with inherited
external socket/DNS denial **1658 passed, 1 skipped**. Ruff lint/format, diff,
documentation and scope/security review pass. Original engine/CLI/provider/handler,
config example, dependencies and MIT notice are byte-identical to PR #61. CI's
pull-request base filter includes the parent feature branch for this separate
stacked Draft PR; jobs and permissions are unchanged. Exact-head publication CI
is checked before handoff. See [TESTING](TESTING.md).

## Authorized metadata-only result and next gate

The separate experiment on `4265328` returned HTTP 200, valid universal JSON,
matching original source ID and one admitted `playAddr`, with no separate-audio
flag. One metadata request read 405,981 bytes; no media request/acquisition occurred.
Supervised elapsed time was 2.632 seconds, exact counters and process/workspace
cleanup passed. This one response does not prove MP4 availability or a general
solution to HTTP 429.

[Phase 6F](PHASE6F_TIKTOK_PUBLIC_PAGE_MP4.md) prepares a separate explicit supervised
acquisition mode. `inspect_public_page()` retains its metadata-only restriction;
provider/Telegram do not acquire a page fallback. The subsequent separately
authorized Phase 6F MP4 test passed; Phase 6G prepares explicit provider selection
without fallback. See [Phase 6G](PHASE6G_TIKTOK_PUBLIC_PAGE_TELEGRAM.md) for the
still-open controlled real Telegram acceptance gate.
