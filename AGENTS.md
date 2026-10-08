# AGENTS.md

## Purpose
This file defines the operating rules for AI agents working on the Social Video Downloader repository.

## Core rules
1. Prefer small, testable changes.
2. Keep the downloader core independent from Telegram transport.
3. Validate risky assumptions early with explicit Go/No-Go gates.
4. Do not introduce infrastructure without a demonstrated requirement.
5. Do not claim production readiness without the required checks.

## Git
- Keep main working.
- Use focused branches for non-trivial changes.
- Make atomic commits.
- Use Conventional Commit prefixes: feat, fix, refactor, test, docs, chore, build, ci, perf.
- Review the exact diff and changed-file list before every commit.
- Never rewrite published history unless explicitly requested.

## Security
Never commit tokens, API keys, passwords, cookies, session files, private keys, user media, user identifiers, personal contact data, .env files, or machine-specific private paths.
Use environment variables and .env.example for non-secret configuration documentation.

## AI discipline
Before changing architecture, document the reason.
Do not silently introduce frameworks, queues, databases, cloud services, paid APIs, analytics, tracking, or monetization.
Stop and request a decision when a security-sensitive or architectural requirement is ambiguous.

## Definition of done
A task is complete only when implementation, tests, documentation, security review, and Git state satisfy its acceptance criteria.
