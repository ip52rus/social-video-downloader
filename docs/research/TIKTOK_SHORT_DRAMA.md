# TikTok Short Drama — canonical preserved research

Checkpoint: **2026-10-29**. Project source baseline:
`f74dc6c933012b809d4e6dc33ed3f3bdadc39d34` (PR #83).

## Status and reading rules

**DEFERRED / SERVER RESOLVER BLOCKED / RESEARCH PRESERVED**

The official desktop browser supplies populated playback metadata for the chosen
Short Drama episode. Independent retrieval of that source by our server Python
client has not been demonstrated. No isolated research download proved a complete
selected file. S2 concluded **NO-GO for another anonymous LIVE request on present
evidence**, not global technical impossibility. Main roadmap work is not blocked by
this research. No active monitoring, endpoint search, new implementation or LIVE is
authorized; reopening requires an owner decision after main priorities or new evidence.

Evidence hierarchy: source/guards, reproducible tests/CI, Git/PR, project docs,
preserved reports, owner observations, marked hypotheses. PASS_METADATA, parser PASS,
browser playback, full-file PASS, Telegram delivery and commercial permission are
separate claims. A source URL, correct duration or successful JSON is not a full-file PASS.
This record preserves conclusions directly; private local folders are supplementary,
not a dependency for a new agent. No personal session or signed media URL is included.

## Selected target and identity contract

Public example: <https://www.tiktok.com/shortdrama/episode/7698874781395096594/1>.
Owner-supplied series title: **Daddy's Little Treasure Hunter**; the title is context,
not an identity key or independently recovered current catalogue claim.

| Identity | Confirmed value |
|---|---|
| dramaID | `7698874781395096594` |
| explicit EpisodeNumber | `1` |
| item.id | `7698876141532237070` |
| video.id in populated Chrome response | `7698876141532237070` |
| author.uniqueId | `fatefultwistus` |
| API duration | `113` seconds |

Ordinary mapped publication: <https://www.tiktok.com/@fatefultwistus/video/7698876141532237070>.
That mapping was checked in episode metadata; it did not make the ordinary extractor
return playback. Never treat dramaID as aweme/item.id, infer episode from index/cursor,
select aweme_list[0] without ID comparison, or use desc=EP01 as binding proof.
Verify explicit dramaID → EpisodeNumber → item.id → video.id, author and conflicts.

## Experiment chronology

Dates below refer to the 2026-10-28 research series unless the later S1/S2 date is
stated. Numbered PoCs are separate authorizations, not reusable request allowances.
Source labels map to the availability/hash inventory at the end. No experiment was
rerun in D1. All observed negative results are retained.

| Stage / goal | Executed mechanism and result | Identity / outcome / stop | Repeat policy / source |
|---|---|---|---|
| Initial anonymous episode API (PoC 1 A) | One GET item_list, dramaID/cursor=0/count=1/aid=1988/language=en; HTTP 200, API 0, 9,106 B JSON | Exact drama/episode/item/author, duration 113; no admitted playback candidate. **PASS identity**, full episode UNKNOWN | Do not repeat same request. `poc/result.json`, allowlisted synthetic fixture |
| Ordinary URL (PoC 1 B) | One metadata GET; HTTP 200, 384,554 B HTML | Existing public-page parser refused metadata_schema; precise missing field not captured then. **FAIL this extraction**, overall PoC **INCONCLUSIVE**; media GET 0 | Ticket exhausted; `poc/result.json` |
| Schema diagnosis (PoC 2) | Offline branch audit then one new ordinary-page GET; synthetic matching trace; 38 diagnostic cases and 45 existing parser tests | **PASS diagnosis**: video.playAddr is empty string; parser makes [empty-string] and rejects metadata_schema. downloadAddr empty, bitrateInfo absent. No malformed lookup exception; no media address | Do not repeat as a schema-only fix. `schema/analysis.json`, diagnostic schema; full-access cause UNKNOWN |
| Public item detail (PoC 3) | One unsigned anonymous GET `/api/item/detail/`, 2 MiB cap | HTTP 200, JSON MIME category, **0 B body**, API status UNKNOWN; **FAIL source retrieval**, media 0 | Do not invent a required token from empty body. `item-detail/diagnostic-report.json` |
| Embed (PoC 4) | One GET embed/v2 for target | HTTP **429** before body/parser; **FAIL this attempt**, no conclusion about embed schema; media 0 | Stop/no retry or IP change. `embed/diagnostic-report.json` |
| Anonymous official browser (PoC 5) | One main document GET HTTP 200, 465,579 B; 24 intercepted attempts, only 1 sent; bootstrap scripts blocked by harness | **INCONCLUSIVE**: 21 scripts plus Fetch/Other blocked, no successful metadata API, media 0; 60 s stop. This was a research-stand limitation | Do not call it TikTok denial or repeat old broken harness. `browser-poc5/analysis.json` |
| tiktok-crawler practical test | Built reviewed Go source; guarded CLI made one episode GET (count=1, empty region/storeRegion); HTTP 200/API 0, 9,098 B | Exact target and 113 s; playAddr/bitrateInfo nil; DramaVideoData.IsPreview=true, IsFreeIntro/IsHighlight=false. **FAIL download**, stopped locally at missing configured msToken before signed fallback; no file/media GET | Cookie requirement is this code path, not proof mandatory account login. `oss/crawler-result.json` |
| MediaFlow module practical test | Guarded Python module, research-only count/max_episodes=1; drama detail GET then episode GET then ordinary metadata fallback (3 metadata GET total) | Episode exact, HTTP 200/API 0, 9,106 B; no playback, same IsPreview=true. Ordinary-video fallback failed; **FAIL download**, media 0 | Original default count30 was not what this run sent. No suitable license confirmed; no code adoption. `oss/mediaflow-result.json`, research patch |
| douk practical test | Actual CLI offline cookie gate; version 0.2.0 | **INCONCLUSIVE**: required cookie file absent, exit1; HTTP 0, child processes 0, no file. Static target discarded episode number | No login/imported session/browser run. `oss/douk-result.json` |
| TokKit.js offline review | Actual resolver functions with fake network; 14 synthetic checks | **PASS offline assessment only**: mobile OPTIONS feed, unsafe wrong-first-item/status/host/fallback assumptions exposed | Not a working episode source. `oss-review/offline-results.json` |
| TokKit mobile LIVE | Exactly one OPTIONS to first reviewed mobile feed gateway, no cookies/signature | HTTP 200/API 0, 323,525 B; aweme_list has **zero exact target IDs**. **FAIL**, stop exact_item_not_unique_or_missing, media 0 | No method change, alternate gateway, retry or first-item substitution. `tokkit-live/result.json` |
| Mobile aweme detail R&D | Source/offline review of szdc GET detail vs yt-dlp form POST multi/detail | **INCONCLUSIVE for LIVE**: szdc needs caller signURL/device context; yt-dlp needs configured app/install context; no permitted working context established | Not LIVE tested, no new API sweep. `mechanism/REPORT.md`, mobile-offline-result.json |
| TikTokHelper R&D | Reviewed actual item_list browser fetch, normalization and exact-ID enrichment; 9 synthetic checks | **PASS offline code behavior only**; same endpoint, credentials:include, browser resource parameters. Positional episode assignment unsafe; merge useful only with existing exact source | No userscript installed/session imported. `mechanism/REPORT.md`, helper-offline-result.json |
| yt-dlp R&D | Reviewed pinned extractor web/app schemas and actual mocked app function bodies | **PASS offline shape assessment**, Short Drama full file not verified; app extraction can choose first aweme; broad high-level fallback/cookie behavior unsuitable | No independent full target file or new mobile LIVE. `mechanism/REPORT.md` |
| ChatGPT Work DOM/MediaSource observations | Owner reports Work could read connected Chrome DOM but not Network/DevTools bodies; main blob player and separate MP4 tab observed | Correct DOM item ID, durations and CDN properties observed; **INCONCLUSIVE exact source match** | No raw Network capture available from Work; don't equate blob and direct MP4. Owner evidence below |
| Prepared network observer / manual auth windows | Playwright/Chromium observer initially accepted after **25 offline checks**; separate approved auth preparation windows | No successful target observation: Google OAuth initially blocked by guard, fixed offline; second owner mobile approval succeeded first step, email reported “too many attempts”, no code. **INCONCLUSIVE**, target navigations 0, no LIVE observation ticket consumed | Browser contexts closed; no account data saved. Auth HTTP status/count UNKNOWN; **no confirmed login HTTP429**. `network-prep/AUTH_PREPARATION_RESULT*.json` |
| Ordinary desktop Google Chrome | Owner disabled mobile emulation, page loaded, playback worked; DevTools response item_list HTTP200/API0 | Target item/video ID and filled playback; **PASS owner-observed metadata/playback**, no independent whole-file/source-match PASS | Mobile emulation correlated with loading trouble; causality not proved. No raw response/profile/signed URLs transferred |
| S1 (2026-10-29) | Architecture/security/OSS review plus isolated synthetic normalizer; **86 offline tests PASS, Ruff PASS**, HTTP/media 0 | **GO further narrow offline R&D**, server integration BLOCKED. No pipeline implementation | Preserve design below; do not replay previous LIVE. `s1/REPORT.md`, offline-result.json |
| S2 (2026-10-29) | Offline successful-request contract comparison; **15 checks PASS, Ruff PASS**, HTTP/media 0 | **NO-GO next anonymous LIVE on evidence**, login causally required UNKNOWN, standalone server source NOT CONFIRMED | No new ticket/probe. `s2/REPORT.md`, comparison.json |

The later saved network-prep offline-result.json contains **37 checks** plus four
loopback-only test requests, TikTok0/media0; this is a later preparation artifact,
not a change to the originally accepted 25-check gate or a successful target LIVE.
The first normalizer development run had one wrong expected refusal code (76 tests,
1 failure); its initial report was retained, then the new expectation was corrected
without weakening guards; final S1 is 86 PASS. S2 initially miscounted query names as
44; corrected to the supplied **42 unique names**, no data or outcome changed.

## Owner Chrome discovery

After disabling mobile emulation in ordinary authorized desktop Chrome, owner
observed successful `GET /api/drama/episode/item_list/`: HTTP200, statusCode0,
itemList24, totalEpisodeCount `"82"`, hasMore true, response cursor `"24"`.
Target was reported at itemList[0], desc `EP01`, privateItem=false,
isProhibited=false. Index/description are descriptive, never selection proofs.

Target video fields: exact video.id, nonempty playAddr/downloadAddr,
PlayAddrStruct present, PlayAddrStruct.DataSize=12704993, nonempty bitrateInfo
(including H.265 variants), codecType=h264, format=mp4, duration113,
width576, height1024, size12704993. Playback host family:
`v16-webapp-prime.tiktok.com`. **No complete address is preserved.**
This is positive official-client evidence, not proof anonymous Python can reproduce it.
Top-level H.264 does not establish that every bitrateInfo candidate is H.264 or that
an actual file contains the declared streams. Explicit preview/paid/DRM flags for the
new populated response were not provided; their values remain UNKNOWN.

## Separate v19 resource and MSE boundary

Earlier owner/Work observations: `v19-webapp-prime.tiktok.com`, MIME video/mp4,
HTTP206, total8610536 B. Ranges included `bytes 0-8610535/8610536` and
`bytes 1219938-8610535/8610536`; repeated Fetch requests of analogous resource size
were observed during playback. Main TikTok video used blob:, duration≈113.7 s,
DOM wrapper `xgwrapper-0-7698876141532237070`. Separate direct-HTTPS MP4 tab had
duration113.568798 s. **Exact source equality is UNKNOWN.** Neither duration
proximity nor byte/range observations bind v19 to the target or equate it to v16.
The blob/MediaSource pipeline was not mapped to an exact API playback URL in memory.

The user confirmed browser playback, but no research acquisition proved a complete
permitted selected MP4. Do not call a URL, 206, duration113 or an IsLimitedFree flag
independent proof of complete/free/DRM-clear content.

## S2 request comparison and safe parameter inventory

Both requests use GET on the same exact HTTPS host/path. Original anonymous query:
`dramaID=<target>`, `cursor=0`, `count=1`, `aid=1988`, `language=en`.
Crawler added empty region/storeRegion. Guarded MediaFlow used the same five fields.
All returned the target without playback. New Chrome supplied 42 names: the five
old names plus37. Known common value difference: count1→24; Chrome language value
UNKNOWN. New known ordinary values: app_name=tiktok_web, channel=tiktok_web,
device_platform=web_pc, coverFormat=2. Chrome user_is_login=true is an observed
claim, not an authentication credential or a causality test.

| Category | Complete parameter names |
|---|---|
| Selector/pagination | `dramaID`, `cursor`, `count` |
| Ordinary client configuration | `aid`, `app_name`, `channel`, `device_platform`, `coverFormat`, `app_language`, `browser_language`, `language`, `webcast_language`, `priority_region`, `region`, `storeRegion` |
| Browser/session context | `WebIdLastTime`, `browser_name`, `browser_online`, `browser_platform`, `browser_version`, `cookie_enabled`, `data_collection_enabled`, `device_id`, `focus_state`, `from_page`, `history_len`, `is_fullscreen`, `is_page_visible`, `odinId`, `os`, `referer`, `root_referer`, `screen_height`, `screen_width`, `tz_name`, `user_is_login` |
| Verification/potentially sensitive | `verifyFp`, `msToken`, `X-Bogus` |
| Exact semantics UNKNOWN | `clientABVersions`, `X-Dynosaur`, `X-Gnarly` |

Safe known values only: aid1988, app_name/channel tiktok_web,
device_platform web_pc, target dramaID, count24, cursor0, coverFormat2;
user_is_login=true is recorded as a boolean-state observation, not proposed replay.
Query wire values are strings; unprovided value types and actual Cookie/Authorization
headers are UNKNOWN. Do not infer request cursor/count from response pagination.

msToken is read from configured cookie by crawler before its signed item-detail
fallback; that local gate is not proof mandatory login for item_list. It may involve
visitor/session context, but anonymous sufficiency here is unverified. verifyFp,
odinId and device_id cannot be copied or replaced with invented registered context.
X-Dynosaur/X-Gnarly have no implementation in the inspected crawler/Helper snapshots;
their exact verification/signature role and necessity are UNKNOWN. Unknown parameters
are not mandatory merely because official Chrome sends them. user_is_login=true
cannot turn an anonymous request into an authorized request.

The anonymous and populated Chrome observations are not a controlled pair. Login,
visitor/session state, web client settings, User-Agent/device, region/IP/time and
request verification may differ. No single causal factor is established. S2 judged
the known count/client/cover differences insufficient to justify another anonymous
LIVE; it did not prove that those fields can never affect a response. Integration
remains blocked, not declared fundamentally impossible.

## OSS snapshots and reuse decisions

Pinned source versions, not assertions about latest upstream:

| Project | Reviewed commit | License / usable scope |
|---|---|---|
| hatienl0i2612/tiktok-crawler | `9af7eb1b2febd172fc7887d4fb53c57fa8b9c72a` | MIT; address-shape normalization and per-bitrate metadata; no successful complete target file |
| zimabx/TikTokHelper | `e90d233777df775dca7de3683ac2b66899fc408e` | MIT; exact-item fragment principle and source normalization, browser-context only |
| ewanQiu/douk | `8af159db5c28452357e27dd8cc2784cd5d1565f0` | LICENSE text is MIT (D1 read); old GitHub classifier was “other/NOASSERTION”, not absence of license; cookie gate untested LIVE |
| odion-cloud/Tokkit.js | `4cc37bf69d0f8521ba78e67b6e0809e7267b3d81` | MIT; tested OPTIONS feed failed exact target; do not reuse high-level unsafe fallback |
| szdc/tiktok-api | `ba0674bfce451ba359838e4810e45a0a7ce79f99` | MIT, archived snapshot; detail request shape only, supplied signer/device requirement not resolved |
| AMThant6/tiktok-downloader-that-works | `a1db6ab2578c14b4052dea5913c8b8a19c3d17fa` | MIT; account/browser-cookie workflow is not proof our full target works or server session is approved |
| yt-dlp/yt-dlp | `f264a6cbd1f630894da0f368df00f8aae50140e0` | Unlicense source; assess dependencies/bundles separately; schema patterns useful, no complete target proof |
| phallymakara/MediaFlow | `cfdbcc32ec3d5e978aefb9e74e2977d8675dad6c` | Suitable reuse license NOT CONFIRMED; research observation only, do not adopt code |

Useful narrowly reviewed concepts:

- crawler address unmarshalling for string/object UrlList aliases and variant sizes;
  normal episode result can avoid its signed fallback **if** the first API has media.
- Helper getAddressUrls/extractVideoSources/normalizeMediaItem and
  ItemDataProvider/mergeExactItemFragments. Merge only exact IDs, reject conflicting
  identity/source metadata instead of overwriting. These functions do not fetch a
  new server-side source when official browser data is absent.
- yt-dlp web playAddr/downloadAddr/bitrateInfo.PlayAddr.UrlList/DataSize parsing;
  caller-supplied ID or codec defaults are not independent identity/stream evidence.
- S1 explicitly adapts PlayAddrStruct without assuming every upstream supports it.

Do not transplant first-list-item selection, positional episode numbering, unbounded
series pagination, uncontrolled fallback/retry, cookie export, signing/challenge
bypass, broad host permissions, full browser wrappers, or whole-MP4 memory blobs.
Do not put Go/Node/browser services on the 2vCPU/4GiB VPS without demonstrated need.
Small MIT-derived functions require copyright/license notices. No upstream code was
integrated into production by S1/S2/D1; synthetic normalizer stays outside runtime.

## S1 proposed integration

**Architecture is feasible; source retrieval is blocked.** Existing ordinary TikTok
path remains independent. Proposed, not implemented:

1. Strict Short Drama URL selector after normal Phase9C admission.
2. A narrow metadata adapter inside the existing owned worker: exact endpoint,
   bounded allowlisted query contract, JSON MIME/size/schema checks. Current Session
   metadata accepts a fixed HTML path without arbitrary queries; it cannot be pointed
   at this JSON API unchanged.
3. Explicit exact drama/episode/item/video/author checks and tri-state access evidence.
   Never substitute another public item or ignore preview/paid/DRM contradictions.
4. Typed plan for an unambiguous H.264/MP4 candidate with its own dimensions/size,
   duration and source provenance. Do not inherit codec/size from a different bitrate.
   H.265/separate audio/HLS/DASH/unknown codec are not silently accepted.
5. Reuse native media_url + pinned DNS/public-IP/TLS/redirect checks and bounded
   Session.acquire; source only in worker memory, not logs/cache/IPC. No public
   arbitrary-CDN input or fake ordinary URL that triggers another failed extraction.
6. Existing supervisor/reap, ffprobe/full decode and passthrough verification;
   additional Short Drama expected duration/size/fullness evidence checks, not guessed
   tolerances. Release leases only after owned worker/delivery/cleanup is safe.
7. Existing Telegram Local API delivery and no-retry uncertain-send semantics.

v16/v19-webapp-prime hosts already match existing media admission. This does not
prove actual GET compatibility, token expiry, IP/cookie binding or content availability.
Current native downloader sends GET **without Range**, accepts media **200** and
rejects **206**. Browser 206 is not proof what a plain GET returns. Offline wire tests
also showed status200 with Content-Range is not separately rejected by the current
transport; do not call that complete range validation. Do not weaken framing/status
checks for compatibility. Actual media GET/codecs/audio/fullness were not tested S1.

S1 synthetic normalizer: exact identity, duplicate/malformed rejection, filled/empty
sources, own-size H.264/MP4 variants, ambiguity/access UNKNOWN refusal, URL/DNS guards
and fake-wire 200/206 behavior; **86 PASS, Ruff PASS, HTTP0/media0**. Filled fixtures
have synthetic clear access flags for policy tests only, not real response claims.
Metadata candidate can be summarized, but UNKNOWN access blocks acquisition DTO.
No real decoding/full-file PASS is inferred. TikTok native 25MiB/file, 50MiB total,
180s acquisition and 128MiB workspace remain; Phase9C only removed Instagram's old
platform-specific 25MiB gate. Main source is unchanged.

## Browser and authentication limits

Work DOM access lacked response-body Network capability; a separate direct MP4 tab
is not a proven source for the main MSE/blob player. Prepared Playwright observation
and login preparation were separate phases. The target-observation phase did not
start in the two manual-auth windows; no later automated target navigation was made.
Reported email “too many attempts” is not a captured HTTP429, CAPTCHA diagnosis,
known cooldown or proof of account cause. No automated login, personal Chrome-profile
access or session transfer is permitted. User's normal Chrome supplied later evidence.

Official authorized playback shows that some official context has a source. A
persistent service-account session is not technically or commercially approved;
expiry, verification, account blocking and credential risks remain. No evidence
shows login alone solves the server gap. Do not ask for personal cookies/secrets.

## Security, rights and commercial gates

Keep distinct: (1) official playback, (2) server source retrieval, (3) actual complete
file, (4) permission for automated access, (5) permission for commercial Telegram
redistribution. Only (1) and populated metadata are owner-observed. No license for
code grants TikTok content rights or platform permission. Current applicable TikTok
terms were not refreshed during offline S1/S2/D1; no legal/commercial GO is claimed.
Only free self-hosted OSS with compatible reviewed licensing is eligible. Paid API,
SaaS/freemium/credits, closed downloader and third-party download servers are excluded.
No DRM/paywall/CAPTCHA/access-control bypass or signature imitation.

Previously pasted sensitive query values must never be recovered from chat or copied
into Markdown, fixtures, logs, issue/PR, requests or examples. Retain names only;
known non-secret constants above are expressly allowlisted. No cookies, Authorization,
profiles, HAR, raw pages/API bodies or complete signed URLs are preserved here.

## Conditions to reopen

- [ ] Main roadmap reaches the appropriate priority, or owner approves a new evidence-led exception.
- [ ] A genuinely new permitted OSS mechanism or changed yt-dlp extractor addresses source retrieval.
- [ ] A documented approved API or reproducible server PoC exists for permitted full content.
- [ ] New evidence differs from S1/S2; state the exact hypothesis, identity/access gates and source.
- [ ] Review current license/terms/content rights and security/resource compatibility.
- [ ] Owner explicitly approves a bounded next stage, including any LIVE budget separately.

Do not start by rerunning the same anonymous GETs, extending exhausted tickets,
copying browser parameters/tokens, monitoring upstream actively, rotating IP or
inventing endpoints. S1's conditional next-request proposal was superseded by S2
NO-GO. No exact new LIVE contract is approved. If no new evidence, keep DEFERRED.

## Local source availability at D1

The following permanent directory basenames were found under the owner's private
research storage. Use the basename to locate a report locally if needed; never
publish private absolute machine paths. This Markdown preserves essential knowledge
without requiring those folders. Report hashes below establish provenance, not
independent replay of LIVE findings. Profiles, binary snapshots and private state
were not copied. Raw owner Chrome/Work captures: **SOURCE NOT AVAILABLE** as a local
raw artifact; the D1/S1/S2 owner statements are explicitly the evidence source.

| Label | Permanent directory basename / report | Availability / SHA-256 |
|---|---|---|
| poc | `social-video-downloader-shortdrama-poc-20261028T162157Z-0a5a0e9f/result.json` | AVAILABLE; `4e40b44f33fc2aeb1d593c0372190a87a3f9d33bd2f79862e4b066e15a740e34` |
| schema | `social-video-downloader-shortdrama-schema-poc2-20261028T164822Z-cdcac50d/analysis.json` | AVAILABLE; `756fe979d50ac989f3ffd7bc8165b6f542c1e8e7c42f03c7714e50c6a010f8b1` |
| item-detail | `social-video-downloader-item-detail-poc3-20261028T174108Z-3e9a4546/diagnostic-report.json` | AVAILABLE; `8db264e99bd8189ff6b0de8bfba84bbe5feb234df1a1aa358da0ed251ce6058c` |
| embed | `social-video-downloader-embed-poc4-20261028T175200Z-a41d81f2/diagnostic-report.json` | AVAILABLE; `ec485a041cd65ff1fa664b94a9e7e8a0ff8c32ac09dc0139383ebecc7cea981b` |
| browser-poc5 | `social-video-downloader-browser-poc5-20261028T180756Z-30cd674f/analysis.json` | AVAILABLE; `94b7e59d43cf06c6952366fb6bba478946187c20efb2d1f350c0e295b34b2bc5` |
| oss | `social-video-downloader-oss-shortdrama-20261028T184715Z-0d0e1fd2/REPORT.md` | AVAILABLE; `f98ad6504088af5214203c20ce3d33d3b518c67863ca9046f7a428957729ce1a` |
| oss-review | `social-video-downloader-shortdrama-oss-review-20261028T193555Z-d6cfc5f8/REPORT.md` | AVAILABLE; `faebe6fc937815f6af8f7160286ff500ceacd2b6c6456d1bc0fc1aeb22c497fe` |
| tokkit-live | `social-video-downloader-tokkit-live-poc1-20261028T195621Z-7870aaa7/result.json` | AVAILABLE; `379dd698a9c71eca2f68f7bcfbc151212c138b9084cec83cef0f2a6a5cd48bbe` |
| mechanism | `social-video-downloader-shortdrama-mechanism-review-20261028T210829Z-d0ba9647/REPORT.md` | AVAILABLE; `444c633a6e3fca4259820d4cad8c512fdc2306cd8cd107fdbf56be5347eabec3` |
| network-prep | `social-video-downloader-shortdrama-network-prep-20261028T220450Z-cbe08bbe/offline-result.json` | AVAILABLE; `3e82c2fcad6543db3319a8ce9346281219478d7b0992c6f0cc418f1836f9509d` |
| s1 | `social-video-downloader-shortdrama-s1-20261029T104459Z-cf20a287/REPORT.md` | AVAILABLE; `e3e49c725647c2c09acb1b46b43b49a3bc88c2f5cdeb5abf10f3d4b5f9d403fd` |
| s2 | `social-video-downloader-shortdrama-s2-20261029T112740Z-e674f6ed/REPORT.md` | AVAILABLE; `84f3429bae5181bc51140baf78c72c42dd7858e68f8c75cc4aea3e8b61d0347f` |

No real media was acquired in the isolated Short Drama research stages summarized
here. A series-wide global HTTP count is not reconstructed from incomplete early
R&D logs; per-experiment counts above are the preserved evidence. No new requests,
fixtures or source modifications were made in D1. See [handoff](../CHAT_HANDOFF_2026-10-29.md)
and [main roadmap](../ROADMAP.md) before deciding future work.
