# Security Policy

## Secrets
Secrets must be supplied through environment variables or an approved secret manager. Never commit tokens, API keys, passwords, private keys, session files, or cookies.

## Personal data
Do not commit user IDs, email addresses, phone numbers, private usernames, downloaded media, logs containing personal data, or local paths exposing personal information.

## Runtime data
Downloaded media, temporary files, logs, and local databases are runtime data and must not be version-controlled.

## Telegram data
Treat Telegram identifiers, messages, usernames, submitted URLs, and media metadata as potentially sensitive runtime data. Do not place real user data into fixtures or documentation.

## Security gate
Before each release inspect changed files, review the Git diff, search for credential-like strings, confirm ignored runtime files, review dependency changes, and verify logs do not expose secrets or unnecessary personal data.
