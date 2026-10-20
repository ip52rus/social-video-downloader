# Security Policy

## Secrets
Secrets must be supplied through environment variables or an approved secret manager. Never commit tokens, API keys, passwords, private keys, session files, or cookies.

Telegram secrets and credentials include the bot token, `TELEGRAM_API_ID`, and
`TELEGRAM_API_HASH`. Compose files must reference them through environment
interpolation, not hardcoded values.

`.env` and `.env.*` files must remain untracked. `.env.example` may be tracked because it
contains only variable names and empty or non-secret example values.

## Personal data
Do not commit user IDs, email addresses, phone numbers, private usernames, downloaded media, logs containing personal data, or local paths exposing personal information.

## Runtime data
Downloaded media, temporary files, logs, and local databases are runtime data and must not be version-controlled.

Telegram Local Bot API Server working data, named volumes, downloaded media,
temporary download directories, generated audio/video artifacts, and Bot API runtime
state are runtime data and must not be committed.

## Telegram data
Treat Telegram identifiers, messages, usernames, submitted URLs, and media metadata as potentially sensitive runtime data. Do not place real user data into fixtures or documentation.

Keep the Local Bot API endpoint private by default. Do not publish an unauthenticated
Bot API endpoint to the public internet unless an explicit deployment design secures and
limits access.

## Docker build context

The Docker build context must not contain secrets. `.dockerignore` must exclude `.env`,
`.env.*`, virtual environments, caches, temporary directories, media artifacts, and local
runtime data while allowing `.env.example` to document required variables.

## Security gate
Before each release inspect changed files, review the Git diff, search for credential-like strings, confirm ignored runtime files, review dependency changes, and verify logs do not expose secrets or unnecessary personal data.

## Isolated native TikTok experiment

Phase 6C admits only a verified embed identity and constrained video-CDN names,
with public-IPv4 pinning, original TLS hostname verification and pre-connect
redirect checks. One publication owns a memory-only, scope-checked cookiejar;
browser/account cookies, persistent sessions, proxies and challenge solvers are
excluded. Signed locators and HTML are never logged. Owned process/workspace,
body-size and HTTP completeness controls are described in
[Phase 6C](PHASE6C_TIKTOK_NATIVE.md). These are experiment boundaries, not a
production sandbox or evidence of real platform reliability.
Benchmark continuation is only to another explicitly approved publication with a
fresh session, never a retry/fallback. All cases consume the original shared limits;
case cleanup failure stops further work. No benchmark live call is implicit.

Phase 6D reuses that engine without another HTTP implementation. TikTok delivery is
off by default, development/test only, and restricted to an explicit test-user
allowlist; an empty list denies everyone and production activation is rejected.
Native work runs outside the event loop in a supervised group. Cancellation waits
for executor completion before deleting its workspace. Upload has a separate timeout,
confirmed API response requirement and no automatic retry. Failed process cleanup
refuses success, blocks further TikTok work and quarantines owned files rather than
deleting under a potentially live worker. Filesystem cleanup failure also blocks work.
User messages contain fixed safe categories, without raw exceptions/locators or
diagnostic data. No CDN/cookie/header/dependency or production-registry expansion.
See [Phase 6D](PHASE6D_TIKTOK_TELEGRAM.md) for the separate live acceptance gate.

## Experimental Instagram provider

The first Reel provider uses only anonymous extraction: no supplied cookies, browser
sessions, credentials, authentication fallback or persistent yt-dlp cache. Only the
explicit Instagram Reel host/path allowlist reaches the pinned Instagram extractor.
Collections and redirects are rejected before media acquisition. Upstream locator URLs
are runtime data, not fixtures or logs; raw yt-dlp messages are suppressed. Acquisition
uses an isolated temporary workspace, a fixed internal filename and generated safe output
names. No titles or source IDs are interpolated into output paths; symlinks and extra
outputs are rejected. This provider is not registered in the default bot yet.
