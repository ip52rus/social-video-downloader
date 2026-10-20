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
The Draft PR requires successful exact committed-head GitHub CI before handoff;
its checks record the publication result. No real TikTok/Telegram request, polling,
Docker operation, media download, merge or deployment was performed.

A separately authorized **one short-link LIVE test** remains required. Only HTTP
redirects via exact vm/vt intermediates to a full www publication are supported;
other intermediate routes, query-bearing short links and HTML/JS navigation refuse.
The 20-second sub-deadline is cooperative: blocked DNS is ultimately bounded by the
existing hard 180-second process supervisor, not a separate DNS timer. Discovering a
canonical URL does not prove MP4 availability; existing 403/429 outcomes remain
possible. Merge and deployment need independent owner decisions after live evidence.
