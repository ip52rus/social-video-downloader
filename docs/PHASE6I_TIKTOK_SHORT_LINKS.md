# Phase 6I — TikTok short share links

## Decision before implementation

The domain router already recognizes TikTok subdomains. Only local reference
validation needs to expand before admission: no HTTP is allowed in URL intake or
capability planning. The existing TikTok handler reserves its process/user slot,
then its executor invokes the same supervised native worker.

Inside that worker, a separate narrow resolver reuses `native.Session.open` and
the pinned HTTPS transport. Only exact `vm.tiktok.com` and `vt.tiktok.com` hosts,
HTTPS and one ASCII alphanumeric path token (1–64 characters, optional trailing
slash) are accepted. Short-link query strings, fragments, credentials, ports and
encoded/extra path components are refused. No real short token is a test fixture.

The inherited transport validates every redirect before connecting, bounds headers,
closes each response/connection and sends its existing standard headers. Intermediate
targets can only be another admitted short link. The first target accepted by
`native.publication()` terminates short-link resolution **before fetching that page**;
the existing public-page path then fetches metadata once and verifies its source ID.
No other page type, external host, IP literal or media URL is a redirect destination.
Redirect bodies are not read or used; HTML/JavaScript redirects are unsupported.
Body counters therefore exclude unread redirect bodies, headers and TLS/network bytes.

DNS/public IPv4 admission, address pinning, TLS/SNI verification and scoped anonymous
memory-only cookies are inherited without broadening policy. Legitimately scoped
cookies from short redirects stay in this operation's jar for the canonical page;
cookiejar domain/path/secure rules govern any later sending. Nothing persists or
crosses users. The jar is cleared on success/error, including a resolution failure.

Resolution has a 20-second cooperative sub-deadline inside the existing hard
180-second worker deadline, not extra time. Inherited redirects allow at most three
short GET attempts/two redirect hops; cycles fail closed. All short requests consume
the original six metadata requests, with the existing metadata/media/body/workspace
budgets. No media retry, fallback, second candidate, header change or CDN expansion.

Only the internal public-page export path opts into short links. Existing embed,
benchmark and diagnostic CLI interfaces retain their admission rules. The provider
retains the admitted input reference in its local metadata descriptor; resolved
publication URLs/IDs and short tokens are not added to worker reports or logs.
Media acquisition/verification/export remains the existing implementation.

Cancellation covers resolution, acquisition and upload through the existing executor,
process-group termination/reap, caller workspace ownership and quarantine. Default
admission remains two operations per bot process, one per user, with no queue.

## Verification and next gate

**53 targeted short-link tests PASS**; full network-blocked offline suite:
**1769 passed, 1 skipped**, 227.63 s. The skipped case is the opt-in real YouTube
smoke. Ruff lint/format, diff-check, privacy/scope/security review and local-link
checks passed. Synthetic real-parser HTTP, generated MP4, fake Telegram and actual
supervised workers cover both share hosts, multiple redirects, cycles/budgets,
forbidden destinations, source mismatch, scoped cookies, report privacy, admission
before network, two concurrent short-link workers, and cancellation/hard timeout
while resolution is demonstrably active. Existing full-link, silent-video,
quarantine/repeated cancellation, embed/benchmark, YouTube and Instagram regressions
pass. External socket/DNS denial is inherited by Python workers.

AST/source comparison confirms unchanged pinned transport, framing, acquisition,
media verification, exchange/reap ownership, native policy constants and public-page
parser. Domain routing, configuration, dependencies, CI and MIT notice are unchanged.
Implementation HEAD `b08f57d25e4c6ba0815a25c270495f59c17b3703` passed GitHub CI
[#39511176476](https://github.com/ip52rus/social-video-downloader/actions/runs/39511176476):
1769 passed / 1 skipped. The offline implementation stage performed no real
TikTok/Telegram request, polling, Docker operation, media download, merge or deployment.

## Owner-confirmed SHORT-LINK LIVE PASS

The separately authorized local Telegram test on that implementation HEAD processed
one new mobile-app share link on `vm.tiktok.com` through the existing dispatcher,
provider and supervised public-page worker. No real short token, publication identity,
user identity or media locator is retained in this evidence.

| Check | Measured result |
|---|---|
| Short-link HTTP redirect / final publication validation | PASS, HTTP 301 |
| Public-page metadata / source identity | PASS, HTTP 200 |
| Selected media | One candidate from `playAddr` |
| Media GET / Content-Length completeness | PASS, HTTP 200, complete 1,049,546-byte MP4 |
| Verified streams / codecs | One H.264 video stream, one AAC audio stream |
| Resolution / duration | 720×720, 14 seconds |
| Full FFmpeg decode / Telegram preparation | PASS, passthrough without transcoding |
| Telegram delivery | One sendVideo attempt; confirmed video Message in the correct chat |
| Owner playback, orientation and sound check | PASS |

Metadata: 2 HTTP attempts (one short redirect and one public page), 415,102 body bytes.
Media: 1 HTTP attempt, 1,049,546 bytes; one acquisition, `counts_exact=true`.
Redirect bodies were not read and are excluded from the byte counter, as are headers
and wire overhead. Native operation: 3.409 s. The 643.211 s controlled-runner lifetime
includes waiting for the owner's message and is not download/upload latency.
The file remained present through the successful Telegram API response; worker reap
completed before upload. Polling stopped, Bot API session closed, worker/FFmpeg and
private/caller workspace cleanup passed. Containers remained exited. No retry,
fallback, merge or deployment occurred.

With the owner's explicit permission, pre-existing updates were left untouched:
getUpdates used no offset/acknowledgement/deletion and only a new message containing
the approved reference was fed once through the existing dispatcher. Restart replay
prevention and ordinary polling queue acknowledgement were not validated by this test.

This closes the single-case `vm.tiktok.com` end-to-end gate. `vt.tiktok.com` has
offline coverage only, not a separate live test. A broader set of mobile links and
high-load reliability remain unverified. Earlier TikTok HTTP 429/403 outcomes are
historical limitations and have not been universally eliminated.

## Final documentation and review

The docs-only preparation repeated the full network-blocked offline suite:
**1769 passed, 1 skipped**, 219.88 s. The opt-in real YouTube case remained skipped;
the Python socket/DNS guard was inherited and checked in a child process. Ruff
lint/format, diff-check, privacy and local-link checks passed.

Final review against main `fc7868610efb7bebb66b7873273ff2a4cf939c99` found no new
code defect. Admission precedes network resolution; the existing transport, public-page
parser, policy constants, supervisor exchange/reap and handler ownership remain intact.
Full-link requests gain no extra HTTP; default two-per-process/one-per-user capacity,
quarantine, YouTube/Instagram routes, configuration, dependencies and MIT notice are
unchanged. Documentation alone records the live result; no new platform request,
polling, container start, merge or deployment is performed. Exact documentation-head
CI must pass before handoff; its result is recorded in PR #66 GitHub checks.

## Remaining limits and next decision

Only HTTP redirects via exact vm/vt intermediates to a full www publication are supported;
other intermediate routes, query-bearing short links and HTML/JS navigation refuse.
The 20-second sub-deadline is cooperative: blocked DNS is ultimately bounded by the
existing hard 180-second process supervisor, not a separate DNS timer. Discovering a
canonical URL does not prove MP4 availability; existing 403/429 outcomes remain
possible. At the final PR preparation stage, exact new-head CI, merge and deployment
were separate owner decisions; neither operation was authorized by that preparation.

## Subsequent merge and public deployment

PR #66 later merged at main `389258cee9cf966be531ae5d6d60b192a59bcdb2`, with
[post-merge CI #39517532808 SUCCESS](https://github.com/ip52rus/social-video-downloader/actions/runs/39517532808).
A separately authorized deployment preserved the previous image for rollback,
prepared the new bot image, completed Cloud-to-Local Bot API migration and started
the updated main bot with public TikTok true/2 and Instagram still enabled.

Stage D PUBLIC DEPLOYMENT ACCEPTED records one additional deployed `vm` short-link
scenario, followed by one Instagram Reel and one YouTube video. The owner confirmed
delivery, complete playback, orientation and sound for each. Workers and temporary
files were cleaned; both containers remained running without observed restart/OOM
or runtime errors. Detailed Stage D HTTP/byte/latency metrics were not measured.
This does not broaden evidence to `vt`, high load, all publications or universal
resolution of the earlier HTTP 429/403 outcomes.

Subsequent local configuration finalization persisted only TikTok true/2 in the
protected, ignored `.env`, preserving other settings and permissions. Resolved
Compose configuration was checked without TikTok shell overrides; no container
restart/recreation or new live request was performed. This documentation PR does
not change the deployed source or include local credentials. See
[deployment configuration](DEVELOPMENT.md#deployed-public-tiktok-configuration)
and [Stage D evidence](TESTING.md#public-deployment-stage-d-acceptance).
