# TikTok native refusal diagnostics

## Reason and boundary

The provider intentionally maps several native refusal codes to one safe domain
error. Ordinary bot logs therefore cannot distinguish missing embedded state,
schema refusal, identity mismatch and publication unavailability. The existing
native report contains useful counters but is discarded at the verified-file export
boundary. Reading it does not require another HTTP request.

Use one additional WARNING event per failed native export, through a dedicated exact
logger and allowlisted schema accepted by the existing private logging sink. Do not
expand the general operation-event schema. Successful exports add no event. Existing
operation events and user messages remain unchanged. This is observability only,
not a TikTok availability fix or permission for a LIVE request.

## Wire contract

Event: `platform=tiktok`, `event=native_refusal`. `reason` is a fixed native code,
`http_error` for an allowlisted numeric HTTP refusal, or `unknown`. `stage` records
where execution stopped: admission, short_link, metadata_fetch, metadata_parse,
media_acquire, media_verify, cleanup, or unknown. Parsing includes identity,
availability and media-address admission; schema refusal does not prove a platform
schema change. HTTP refusal does not establish its remote cause.

Optional integers: `metadata_http_status` (100–599, last response in the current
metadata session), `metadata_bytes` (0–4194304), `metadata_requests` and
`media_requests` (0–6). Bytes count body bytes consumed, not network traffic.
Short-link counts include redirects. No short-link response is inferred as the final
page status. `counts_exact=false` means counters are unknown (`null`), not zero.
Worker interruption, IPC loss, export/cleanup overrides or missing reports may leave
stage, HTTP status and counters unknown. No exception text is serialized. Every
field is rebuilt and checked again at the output sink; extra fields are discarded.

No URLs, IDs, bodies, headers, cookies, locators, arbitrary exception strings or
per-user correlation are included. Concurrent failures cannot be reliably matched
to individual requests. At most one diagnostic is emitted per failed export, with
no per-request HTTP logging, retry, fallback, new await or deadline extension.

## Evidence and limits

The five owner-reported failures on 2026-10-25 had the existing domain category
`metadata_unavailable` before MP4 acquisition/preparation/upload. Their original
native refusal codes remain UNKNOWN and cannot be reconstructed by this change.
Historical successful public-page and short-link LIVE cases remain narrow evidence;
see [public MVP](PHASE6H_TIKTOK_PUBLIC_MVP.md) and
[short links](PHASE6I_TIKTOK_SHORT_LINKS.md).

A separately authorized future single LIVE attempt could expose the fixed refusal
code, observed stage and available bounded counters/status. It would not prove a
remote anti-bot cause, universal availability or the cause of the five old failures.
Offline verification results are recorded in [TESTING](TESTING.md).
