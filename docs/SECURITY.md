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
