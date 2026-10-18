# Phase 5: Instagram single-video provider scope and evidence

## Agreed scope and decision

On 2026-10-16 the user approved the first implementation PR from main
`9148c81ccdf6b3d97c43b7ed20f23b5766925a50`, on a separate feature branch and checkout.
The decision is GO for an experimental anonymous provider of public individual Reels.
It is not acceptance of production reliability or permission to rebuild/restart the
running Compose stack. At that stage the PR had to remain draft pending a separate
merge decision.

The handoff reports previously completed Gates 1–3C. The available Gate 3C report
records one metadata-only extraction (`download=False, process=False`), with five video
entries in a `/p/` playlist, no downloaded media and no authentication. That establishes
only the reported metadata access/classification. Full Gates 1–3B reports were not
available in this implementation session; their detailed results are not reconstructed
or claimed as freshly verified. The user's explicit scope decision authorizes this
implementation without a new observation/waiting gate.

## PR 1 acceptance

These criteria record the original Reel-only PR. Its original mandatory-audio policy
is superseded by the approved silent-video decision below; other safety rules remain.
The approved current expansion is below.

- Implement `MediaProvider` without changing its contract or the one-file `DownloadedMedia`.
- Admit only individual `/reel/<id>/` paths on instagram.com, www.instagram.com or
  m.instagram.com; canonicalize to HTTPS/www and drop tracking queries/fragments.
- Reject `/p/` posts, Stories, profiles, collections (even one entry), redirect results,
  private/auth-gated metadata, DRM and unclassifiable or unsupported formats before
  media acquisition. Never enumerate a playlist or select its first entry.
- Start with direct HTTP(S) MP4 formats only. No DASH/HLS assembly, cookies, credentials,
  persistent extractor cache, new dependencies or application retry loop.
- Validate the effective protocol before acquisition using yt-dlp's protocol helper;
  reject manifest/fragment formats even with missing protocol or a misleading MP4 label.
  Signed direct MP4 URLs without a filename extension remain eligible when the extractor
  supplies the MP4 extension. Missing dimensions/codecs do not by themselves disqualify
  a direct MP4 candidate; explicit video/audio absence still does.
- Prefer metadata-confirmed H.264/AAC, then incomplete codec metadata without known
  incompatible codecs, then other admitted MP4 formats. Retain yt-dlp quality ordering
  within each class and select one format without acquisition-error fallback.
- Expose one normal video route and no selectable qualities. Reject audio-only,
  video-only and supplied quality IDs. Explicit injection into `DownloadService` must
  produce the existing `DIRECT_DOWNLOAD` plan without adding Telegram UI.
- Reuse fresh inspection data between planning and acquisition; expired data must be
  revalidated. Keep cache lifetime and size bounded.
- Return exactly one nonempty regular file in the caller's output directory. Clean the
  internal acquisition workspace on success/failure and reject symlinks/extra outputs.
  Keep source titles/IDs out of filesystem paths.
- Treat title/uploader/duration as optional extractor data. Unknown duration remains
  unknown; Telegram preparation/upload metadata use the existing ffprobe/FFmpeg helpers.
- Validate the contract, failure boundaries, service injection and transport preparation
  offline; run the existing suite, Ruff, diff and security review. Record results and
  remaining checks explicitly.

Only the `VIDEO_WITH_AUDIO` route is exposed. The installed Instagram extractor may
omit both dimensions and codecs on progressive MP4 data. Such direct candidates remain
eligible, with unknown codecs ranked below confirmed H.264/AAC; no streams or dimensions
are invented. Actual video/audio presence remains unverified until stream inspection.
Explicit audio-only formats remain rejected. Audio-free video is now admitted under
the later product decision below; actual streams still need inspection. Default Telegram
preparation still rejects silent files; the explicit optional-audio API below is tested offline.
The provider does not transcode, add audio or duplicate the transport pipeline.

## Verification and follow-up

[TESTING.md](TESTING.md#experimental-instagram-reel-provider-2026-10-16) records offline
results, including real local yt-dlp processing and synthetic ffprobe preparation.
No real Instagram extraction/download or Telegram API request was run for this PR.
No dependency, Docker/Compose, default registry, handler or deployment changes are included.

PR #44 was subsequently merged. The first real provider smoke failed before acquisition:
13 returned formats, zero admitted, with incomplete video metadata in three formats;
the other ten rejection reasons were not verified. An offline regression using the
installed extractor's `video_versions` mapping confirmed and corrected the overly strict
dimension/codec evidence rule. This does not establish why every real format was rejected
or prove that the live Reel now downloads. See the follow-up evidence in TESTING.md.

PR #45 was subsequently merged. Its separately authorized repeat smoke on 2026-10-16
passed for one public Reel through the actual provider/service: 13 formats, 3 admitted,
10 rejected as manifest/fragment candidates, one extraction and one acquisition.
The actual file was MP4 H.264/AAC, 720x1280, 11.282041 seconds, 1,317,210 bytes;
preparation was passthrough, ffprobe and full FFmpeg decoding passed. There was no
Telegram upload. This resolves the observed admission failure for that case only.

## Approved expansion and current single-video-post stage

The user approved Reels, ordinary public single-video posts and future video-only
carousel downloads. Photos are NEVER downloaded or delivered. The single-video-post
stage covered `/p/<id>/` single-video posts, using the existing
provider and one-file `DownloadedMedia` contract. No second acquisition/preparation
pipeline, new dependencies or Telegram changes are introduced.

- Accept the same strict host allowlist and canonical HTTPS/www identity for `/reel/`
  and `/p/`; remove tracking queries/fragments without conflating the two path kinds.
- Decide content type from the extractor result, not the `/p/` path. Installed yt-dlp
  maps single-video products to video results; carousel products to playlists, including
  one-entry and mixed-media collections; photos have no admissible video formats and
  may raise an upstream no-video error. Test these mappings with synthetic responses.
- Reuse `_single_video()` to reject playlists, any `entries`, redirects, unclassified,
  inaccessible/private and DRM results before acquisition. Never recursively process
  entries or silently pick the first item. `noplaylist` is not a carousel-to-video conversion.
- Preserve direct HTTP(S) MP4 admission, manifest/fragment rejection, H.264/AAC priority,
  incomplete metadata support, bounded cache/snapshot reuse, safe filenames and cleanup.
- Expose only `VIDEO_WITH_AUDIO` / `DIRECT_DOWNLOAD`; no audio or quality menu. Reject
  unsupported modes and arbitrary quality IDs. Missing post titles use `Instagram Video`.
- Keep Instagram disabled in the default registry and leave Telegram handlers unchanged.

Real Reel smoke evidence predates this extension. Real `/p/` extraction/acquisition is
UNVERIFIED; offline tests do not establish current platform access or Telegram delivery.
Next: independent review and a separately authorized bounded real single-video-post smoke.
Telegram activation/deployment checks remain separately authorized work.

## Approved carousel scope and separate implementation stages

Carousel acquisition is approved VIDEO-ONLY scope, separate from single-file downloads in
this stage. Skip only positively classified photos; UNKNOWN or an unavailable selected
video blocks the operation. Preserve the original ordering of videos. One video uses one
Telegram message; 2–10 use a group; larger selections use sequential groups with a single
remainder sent individually. Never silently omit a selected video.
Multi-file acquisition uses the separate bounded operation described below, not the
single-file provider contract. Live routing remains a separate future integration;
the offline transport is described below. Photos and all collections still fail safely
through the single-file download path.

Stories, private-content access, authentication and additional formats require separate
scope decisions. Silent-video acquisition is included; optional-audio preparation is
implemented offline with explicit opt-in. A separate offline carousel transport now
builds ordered albums; routing activation and real-client validation remain unfinished. Phase 5 and production reliability remain open.

## Carousel inspection and selection — metadata only

The first carousel implementation adds a separate `InstagramCarouselService` entry point,
backed by `InstagramProvider.inspect_carousel`. The existing one-file `download` paths
still reject every collection, including one-entry playlists. No registry/handler changes,
media acquisition, Telegram album sending or new dependencies are included.

A per-instance `CarouselInstagramIE` reuses installed yt-dlp extraction and mapping, then
preserves immutable source evidence before it is discarded. Guarded count/order/ID checks
reject missing or changed mappings. No global monkeypatch, HTTP interception or duplicate
metadata extraction is introduced. Missing/malformed IDs are not synthesized; source
unavailability/DRM also survives the mapping. No raw responses enter plans or the cache.

VIDEO requires explicit video evidence, including `video_versions` even when its locator
is unusable (then the VIDEO is unsupported, never a PHOTO). PHOTO requires an explicit
photo marker or strictly integer `media_type=1`, plus usable image candidate structure
and no video conflict/malformed type metadata. Numeric type codes alone are insufficient.
Only successful numeric PHOTO classification adds `media_type_photo` evidence.
Unknown/conflicting evidence blocks the whole selection. Corrected PHOTO selection is
validated offline only; the live evidence and outstanding gate are recorded below.

Plans preserve canonical identity, original entry count, ordered positions/IDs, kinds,
evidence, admitted-format counts, selected video references, scope and READY/BLOCKED reason.
READY means only a valid metadata selection; actual streams, budgets and acquisition are
not validated. Every selected video needs at least one format admitted by the existing
MP4/H.264/AAC preference and manifest/fragment rejection policy. Nothing is truncated.
Facts use a separate bounded 180-second cache; expiry requires new inspection.

Query intent is examined before canonical cache use. At the original inspection stage,
unknown query parameters/fragments were ambiguous and only allowlisted tracking keys
could be discarded. The post-share follow-up below replaces that policy with the shared
Reel guard: reject known item selectors, strip non-selector share data. No frontend
index semantics or first-item fallback is implemented.

### Live metadata evidence — 2026-10-16, before this implementation

One public five-entry video carousel was inspected twice anonymously, once with
`img_index=3`. Both calls used `download=False, process=False`: six observed HTTP requests
in total, zero processing/acquisition. Every position had explicit `video_versions` and
three admitted direct MP4 candidates. Unique source IDs and original ordering survived.
`media_type=2` was present; `is_video` was absent; normal mapping discarded type fields.
The second URL reached the extractor with its query, but upstream requests were identical
and both returned the full five-entry playlist with the same ordered IDs. Bodies differed;
no selected-item behavior was established. CSRF-token warning was nonfatal.

This validates video metadata for that case, not this newly implemented adapter, actual
media streams, photos/mixed carousels, frontend index semantics or Telegram delivery.
At that gate the complete PHOTO/VIDEO/UNKNOWN result was INCONCLUSIVE; the installed-
extractor item-reference gate failed. The decision was CONDITIONAL GO for inspection planning.
Mixed/photo live evidence, item-specific semantics, acquisition/preparation and Telegram
validation remain separate gates. Phase 5 and production reliability remain open.


### Corroborated PHOTO follow-up — initial offline fix

After PR #47, two separately authorized one-shot anonymous metadata checks investigated
one real 20-entry publication without acquisition. The production adapter preserved all
20 positions and unique IDs, classified 17 entries as VIDEO and left positions 8, 9 and 18
UNKNOWN. Its plan was safely BLOCKED / unknown_item with no selected videos.

The source diagnostic found integer `media_type=1`, no `is_video`, an unrecognized
`__typename`, and coherent `image_versions2` with nonempty candidates at those three
positions. Video versions/codec/duration/manifest fields were absent. Representative
VIDEO entries had integer `media_type=2`, nonempty video versions/manifest and also image
versions. Image metadata alone therefore does not distinguish photos from videos.
The combination supports three PHOTO candidates for this observed schema; it does not
establish universal Instagram semantics or involve viewing/downloading those images.

The focused correction is confined to `_classify`: a strict integer photo type can
corroborate existing image evidence. Booleans, malformed markers, conflicting video
versions/codec/duration/manifest, `is_video=True` or `GraphVideo` cannot take this route.
Existing explicit photo markers still work. Source extraction, ID/order guards, cache,
URL policy and all download/transport contracts are unchanged.

Deterministic tests reproduce the source shape and a 20-item mixed plan: 17 VIDEO,
PHOTO at 8/9/18, READY with selected positions 1–7, 10–17, 19–20 and no acquisition.
This is an offline result, not a retest of the corrected adapter against Instagram.
That initial implementation left the live mixed-selection gate open; the subsequent
real validation below closes it for one publication. Item references, live Telegram
group validation and production reliability remain unfinished. Photos will never be acquired or delivered.


## Final mixed-carousel metadata gate — PASS, 2026-10-16

After PR #48, the production adapter/service at `1e08478646057326284ff410ea23f2ca312b4f2f`
passed one separately authorized anonymous metadata-only check: one extraction, three
observed metadata HTTP requests; 20 original entries, 17 VIDEO, PHOTO at 8/9/18, zero
UNKNOWN. The READY plan selected exactly 1–7, 10–17, 19–20 with issue=None, unique original
IDs and source/mapped/plan order checks PASS; every VIDEO had three admissible direct MP4
candidates. PHOTO evidence included integer media_type=1 and valid image structure without
video conflicts. No acquisition or Telegram requests occurred. Nonfatal warning:
CSRF_TOKEN_UNAVAILABLE. This validates one publication's classification, not downloadability
of its 17 videos or general platform reliability. The mixed-classification gate is closed.

## Bounded ordered video acquisition — deterministic implementation

A separate explicit async `InstagramCarouselAcquisition` now downloads a READY publication
plan into an immutable ordered collection without changing single-file contracts. It runs
in a short-lived POSIX process for hard network/probe deadline and cancellation handling.
One fresh extraction revalidates every source identity, position, classification and all
selected video formats before any child processing. Cached locators are never reused;
changes reject the operation without adopting a different selection. Only selected VIDEO
children are processed sequentially; photos and the parent playlist are never acquired.

Existing direct MP4 admission and H.264/AAC priority are reused. Unknown codecs remain
unknown until actual ffprobe; actual MP4 video is mandatory and audio is optional.
Every existing audio stream must have a valid codec. No conversion or
Telegram delivery is included. All videos must validate before a collection is returned.
Failure/cancellation kills the process group, removes all owned staged/published files and
preserves unrelated files. Success transfers generated output-file ownership to the caller;
exclusive hard links avoid large copies. Caller deletes successful files after use.

Defaults, configurable per service: 25 videos, 100 MiB/file, 500 MiB total actual response
bytes, 512 MiB temporary logical media bytes, 600 s operation deadline. No truncation,
size-based alternative download or retry. Response reads, not size headers alone, enforce
byte budgets; yt-dlp size checks and POSIX file limits are backstops. Exhausted unknown-size
streams fail closed. Filesystem overhead, process memory, concurrent-operation quotas and
crash recovery are outside these limits. These defaults are not production capacity claims.

The narrow real three-video acquisition gate passed (record below); larger collections
remain NOT VERIFIED. Telegram media-group transport is implemented offline below;
real delivery is NOT VERIFIED. Real item-reference selection remains blocked. Next:
independent transport review, separate routing activation and authorized real-client
validation. No deployment changes in this stage.


## Silent Instagram videos — approved policy, deterministic implementation

The user approved downloading MP4 videos with or without audio for public Reels,
single-video posts and selected carousel VIDEO entries. No new mode/menu is introduced:
the shared legacy VIDEO_WITH_AUDIO enum remains the normal Instagram route. Explicit
video absence, audio-only media, non-direct/unsupported protocols, manifest/fragment
metadata and DRM remain inadmissible. Incomplete codecs remain unknown, not proof of
video/audio. No artificial audio, retry, alternate acquisition or mandatory conversion.

A preceding separately authorized metadata-only diagnostic concerned one three-VIDEO
publication: boolean has_audio=False at all positions; three source video_versions each
preserved as structural direct MP4 candidates with acodec="none". Nine direct candidates
were rejected solely by the former explicit-audio-absence rule; 23 manifest-derived
candidates also had forbidden fragment markers. Mapped counts were 11/11/10 (32 total).
Source IDs/order were intact. One extraction and three metadata HTTP requests, zero
media acquisition. This justified a product-policy change, not a claim that those real
files contain valid silent video. The later bounded acquisition below verifies the
actual streams of those three files only.

Ranking retains compatibility-first selection: confirmed H.264/AAC, compatible/incomplete
metadata (now also H.264/unknown-video with explicit silence), then other MP4 codecs.
Within each group non-silent-or-unknown audio precedes explicit silence, then native
yt-dlp quality order applies. Unknown is never claimed to contain audio or to be silent.
Silent H.264 can intentionally beat less compatible VP9/AAC in another group. Equivalent
silent candidates retain native quality ordering. No fallback after download failure.

Carousel ffprobe requires actual MP4, recognized video codec and positive dimensions;
absent audio is allowed but invalid/unknown codecs on any present audio stream fail.
Local synthetic silent H.264 files are accepted without changing bytes. The existing
single-video file checks remain unchanged. Limits remain 25 videos, 100 MiB/file,
500 MiB total media, 512 MiB temporary logical media and 600 seconds. Identity/order
revalidation, all-or-nothing cleanup and caller output ownership are unchanged.

Telegram remains disabled for Instagram. Default preparation still requires audio;
explicit optional-audio preparation is implemented and tested locally below. Album
batching is now implemented offline; img_index selection, real Telegram playback and
production readiness are not claimed.


## First real silent three-video acquisition — PASS

A separately authorized one-shot experiment used production main
`055fced0bdf337a5b04132600cc803321db59c80` in an isolated existing-image runtime with
current source read-only and verified hashes. The three-entry READY publication had
VIDEO at 1/2/3, no PHOTO/UNKNOWN, three admitted direct MP4 candidates each, and valid
source/mapped identity and order. Planning plus fresh acquisition extraction made two
extractor calls, six observed metadata HTTP opens; three media requests succeeded.

All three actual files were silent MP4/H.264, 720x960, 5.041667 seconds each; sizes
613050, 738479 and 609669 bytes (1,961,198 total). ffprobe passed. Received-body hashes
matched final-file hashes: no remux/transcode/artificial audio. Acquisition took 6.90 s
under explicit limits 3 videos / 30 MiB per file / 75 MiB received / 90 MiB temporary /
180 s. Files, scripts and isolated runtime were removed; Compose was untouched and
Telegram calls were zero. This closes only the real three-video acquisition gate.
Larger carousels, broader availability and real Telegram playback remain NOT VERIFIED.

## Explicit optional-audio preparation — offline implementation

`prepare_telegram_video(path, runner=None, *, allow_silent=False)` keeps the existing
YouTube audio-required default. Explicit `allow_silent=True` accepts actual video without
audio: H.264 MP4 passes unchanged, compatible non-MP4 remuxes by stream copy, incompatible
video converts with the established H.264 settings. Existing audio is mapped and prepared
as AAC; absent audio is never mapped or synthesized. Actual output container/streams
are checked, including unchanged audio presence. Failed derivatives are removed and
pre-existing destinations preserved. Orientation and video-derived upload parameters
are covered by generated local FFmpeg/ffprobe fixtures, not real Telegram sends.

Future Instagram callers must opt in and own successful derivatives inside their request
workspace. PR #51 and its P2 ownership correction were independently reviewed and merged.
Routing remains disabled and client playback remains unverified; offline album delivery
is described below. No new Instagram extraction, acquisition or Telegram request
occurred in the optional-audio preparation stage.


## Offline ordered Telegram carousel delivery

An explicit reusable `TelegramCarouselDelivery` now consumes `DownloadedCarousel`, its
original selection plan, an approved caller workspace and an injected aiogram-compatible
sender. All selected files are prepared with `allow_silent=True` and probed before any
send. Only actual H.264 MP4 with optional AAC passes; no photo selection or new extraction
occurs. Source positions/IDs and all files are validated; no missing video is skipped.

One video is sent individually; 2–10 form one ordered album; larger selections use
sequential slices of ten with a final singleton sent individually. No captions expose
source metadata. Telegram failures/timeouts/malformed responses stop all later requests,
never retry, and return safe confirmed/uncertain progress via the error. Prior successful
albums cannot be rolled back as part of a transaction. Caller owns user communication.

Preparation uses private hard-link aliases and a killable POSIX child, preserving original
files. Defaults: 25 videos, 50,000,000 bytes/file and 200 MiB total upload; workspace logical
bytes 1 GiB (unique inodes, including originals/staging), 2048 entries; 180 s preparation,
120 s/send. Existing acquisition limits are unchanged. Remaining-byte OS output limits
and whole-preparation deadline prevent unbounded conversion. Filesystem overhead, global
memory/concurrency quotas and production capacity are not claimed. Private outputs are
removed on every normal completion/failure/cancellation; caller cleans original files.

This is offline transport implementation, not activation. PR #51 optional-audio/P2
preparation is merged. The only real carousel acquisition remains the three-video
1,961,198-byte case above; no new Instagram or Telegram calls occurred. Live albums,
client playback, larger-carousel reliability and broad availability remain NOT VERIFIED.
Independent review and separately authorized routing/client validation remain required.

## Historical Reel-only Telegram MVP (offline)

A narrow `InstagramReelHandler` connects only public `/reel/<id>/` URLs to the existing
InstagramProvider, DownloadedMedia, `prepare_telegram_video(..., allow_silent=True)`,
ffprobe upload metadata and aiogram sendVideo. No menus, carousel-shaped single results
or default-provider registration are introduced. Query intent is checked before stripping:
known item selectors (`img_index`, `media_id`, `item_id`, `carousel_index`, `index`,
`slide`) fail case-insensitively before extraction, including selector-shaped fragments
such as `#slide`, `#slide/2` and `#?img_index=2`. Ordinary share parameters (`psln`,
`utm_source`, unknown irrelevant keys or bare flags) and harmless fragments are accepted
and removed by the existing provider canonicalizer. Raw query strings never reach the
provider download call or yt-dlp. The 32-query-field bound and strict host/path/credential/
port validation remain. `/p/` and carousel integration and their separate conservative
query policy remain unchanged.

`INSTAGRAM_TELEGRAM_ENABLED` defaults to false and accepts only true/false. Settings
reject enabled+production. The planned controlled smoke uses the existing main bot;
current Compose explicitly sets `APP_ENV=development`, which is preserved. Dispatcher-local
injection owns one Reel handler/admission slot; fresh routers
avoid cross-dispatcher attachment. Existing YouTube callbacks/options are unchanged.
No live environment or dependencies were changed by the offline integration stage.

MVP guards: 25 MiB received media and final upload file, 20 s yt-dlp socket timeout,
180 s cooperative acquisition/preparation deadline, 120 s per send. The normal provider
still selects one direct MP4 and performs extraction once; no acquisition retry/fallback
is added. A scoped response reader caps media-body reads independently of Content-Length,
with yt-dlp max_filesize/progress checks as backstops. This is not a cap on HTTP/TLS
wire bytes or upstream buffering/metadata memory. Exact-cap unknown-length responses may
fail closed. Preparation uses existing runner injection with subprocess timeout and a
POSIX RLIMIT_FSIZE for FFmpeg outputs; exhaustion fails, never returns a deliberately
truncated conversion or attempts a fallback. No new process-management framework exists.

Cancellation signals the worker and waits for it to really finish before releasing the
slot or deleting its workspace. It does not terminate a network thread; DNS/native stalls
can exceed the cooperative deadline. There is no hard whole-request watchdog, global
quota, restart-proof deduplication or concurrent YouTube/Local Bot API storage budget.
An initial free-space check requires three file caps of headroom; it does not reserve
space against other processes. Per-file caps are not a physical disk quota. A send
error/timeout/unconfirmed response is never retried automatically.

After PR #54, a separately authorized deployment recreated only the existing bot and
enabled the flag in its protected environment. One canonical public Reel was delivered;
the user confirmed playback, orientation and sound. Temporary Reel files were cleaned,
polling remained healthy and the Local Bot API container was unchanged. Exact file size
and processing time were not captured. This closes only the one-Reel delivery/client
smoke, not `/p/`, albums, broad availability or production reliability.

The full share URL initially failed before acquisition because `psln` was outside the
old tracking allowlist. The share-link correction is verified offline using the exact
reported URL without network access; committed fixtures replace the opaque tracking
value with synthetic data. Synthetic provider/send tests confirm a canonical URL and
one send. PR #55 then merged at `0a87beeaa8acb302b74e980946778608856b13f6`
and was separately deployed. The user confirmed delivery, playback, orientation and
sound for the full Reel URL with `utm_source` and `psln`; file size/time were not
recorded. This closes that full-share-link smoke only, not `/p/`, albums or broad
Instagram reliability. The 25 MiB limit, cooperative deadlines, disabled-by-default
configuration and production guard remain. No new live test is part of PR #56.

## Opt-in /p/ Telegram integration — PR #56

The user authorized connecting the already merged single-post, carousel
acquisition and offline Telegram album components, **not** merging or restarting
the running bot without review. The branch
`feat/instagram-post-carousel-telegram` wires `/p/` to the existing
Instagram handler and the same disabled-by-default flag.

A single-video publication now requires positive source VIDEO evidence, coherent
source/mapped identity, public availability and admissible direct formats. The existing
adapter and `_single_video` validators make this decision; absent or conflicting
metadata does not establish support. Its existing single-file worker consumes that
same validated provider snapshot without another extraction. All BLOCKED results,
including UNSUPPORTED_CONTENT, stay blocked. A complete READY
carousel uses `InstagramCarouselAcquisition` and `TelegramCarouselDelivery`
in one owned operation; 2–10 videos form a Telegram album, and a singleton is
delivered as a video. The original PR #56 query policy accepted only allowlisted share
keys and rejected all fragments. The offline follow-up now uses the same reference
guard as Reels: non-selector query keys/bare flags and ordinary anchors are stripped,
while known selectors (including encoded/case variants and selector-shaped fragments)
remain BLOCKED before extraction. Malformed references and more than 32 query fields
are blocked. No raw query or fragment reaches the provider.
No PHOTO is sent; UNKNOWNs and unsupported selected videos block the whole
operation. Send uncertainty is reported without automatic retries. The per-
dispatcher slot prevents simultaneous Reel and carousel handling.

The source-shape correction validates `carousel_media` before yt-dlp can filter it:
only an absent field permits single-video classification. Present null/non-list values,
malformed members and nested collections give INVALID_METADATA without acquisition.
An empty list remains NO_VIDEOS. A valid source collection must remain a playlist with
the original count, identities and order; missing/dropped/reordered entries or a mapped
single result fail closed. Parent video_versions never override this source evidence.

Initial route limits are smaller than the reusable components' defaults:
10 selected videos, 25 MiB per acquired/uploaded file, 100 MiB media total,
130 MiB acquisition temporary budget, 400 MiB delivery workspace budget.
They are safety caps, not production throughput guarantees. Existing
`INSTAGRAM_TELEGRAM_ENABLED=false` default and the production guard remain.

The P2 correction shares the existing cooperative guard/event with initial metadata
requests. A common 300-second window starts before inspection and covers later stages;
single-file work keeps its 180-second cap from that start and sending keeps its
120-second cap within the original window. Acquisition receives remaining time;
preparation/upload cancellation preserves existing cleanup and uncertain-delivery
progress. No new request or media stage starts after a cooperative stop is observed.
A pending native/network call is not forcibly interrupted: ownership remains until
the worker finishes. No new process manager, product byte/count limit or dependency.

Before these corrections, network-forbidden routing and local FFmpeg/ffprobe suites
passed on GitHub Actions (1277 passed, 1 optional real YouTube test skipped), along with
Ruff lint and formatting. Independent review identified P1/P2/P3; the corrected diff
required another independent review. The previous real three-silent-video
acquisition still proves only files/ffprobe, not live album sending or client
playback. Final independent review passed on `219e1bfcc134e80be24bb8565f6dfc18dae77c21`;
PR #56 merged at `20d14441a2b7ea906ed2a0abc83679d25d9f2d32` and was separately
deployed only to bot. Source hashes and polling passed; Local Bot API was unchanged.
This does not close the live `/p/` or album gates.

After that deployment, the user reported the same reference-rejection response for
one single post and one carousel. Their URLs were not supplied: no exact parameter
combination or selector intent is inferred. The share-link correction reproduces the
old policy's rejection classes with synthetic offline URLs only. Corrected real
`/p/` delivery and Telegram album playback remain NOT VERIFIED; this fix is not deployed.
