# AGENTS.md

## Purpose
This file defines the operating rules for AI agents working on the Social Video Downloader repository.

## Core rules
1. Prefer small, testable changes.
2. Keep the downloader core independent from Telegram transport.
3. Validate risky assumptions early with explicit Go/No-Go gates.
4. Do not introduce infrastructure without a demonstrated requirement.
5. Do not claim production readiness without the required checks.
6. Keep project documentation synchronized with verified implementation progress after every completed stage and before starting the next one.

## Documentation discipline
- Treat documentation as part of the deliverable, not optional follow-up work.
- After each completed stage, review and update `docs/TASKS.md` before moving to the next stage.
- Update `docs/ROADMAP.md` when phase status, scope, dependencies, acceptance gates, or the next planned step changes.
- Update architecture, testing, security, development, and product documents whenever the change makes their current statements inaccurate or incomplete.
- Mark a task complete only when its stated acceptance criteria have been verified. Record partial progress and outstanding checks explicitly.
- Distinguish unit tests, deterministic integration tests, real external-platform smoke tests, and end-to-end Telegram tests. Do not treat one category as proof that another has passed.
- Record relevant verification evidence, including test and quality-check results, and disclose important limits such as the number and type of external cases tested.
- Review documentation and code together in the same diff. Do not knowingly leave progress tracking stale after a stage is complete.
- If documentation cannot be updated or a check remains outstanding, state this explicitly and do not represent the stage as fully complete.

## Git
- Treat the local repository as the active development source of truth while work is in
  progress. GitHub is the synchronized remote history and checkpoint after a verified
  stage, not the place to infer uncommitted local state.
- Keep main working.
- All new project Git worktrees MUST be created in permanent storage, for example
  `~/PycharmProjects/social-video-downloader-worktrees/`. This applies to every future
  Codex task. NEVER create working worktrees in `/private/tmp`, `/tmp`, system temp
  directories, or any other automatically cleaned temporary location.
- Use focused branches for non-trivial changes.
- Make atomic commits.
- Use Conventional Commit prefixes: feat, fix, refactor, test, docs, chore, build, ci, perf.
- Review the exact diff and changed-file list before every commit.
- Commit only after implementation/config changes, documentation synchronization, tests and
  quality checks, and security review have been completed or explicitly documented.
- After pushing, verify the remote branch state and CI result.
- Never lose unrelated local work. Preserve unrelated local files and changes unless the
  user explicitly asks for a destructive operation.
- Never rewrite published history unless explicitly requested.
- AI agents must not independently run destructive Git operations such as reset, restore,
  checkout, clean, rebase, or force-push.

## Security
Never commit tokens, API keys, passwords, cookies, session files, private keys, user media, user identifiers, personal contact data, .env files, or machine-specific private paths.
Use environment variables and .env.example for non-secret configuration documentation.

## AI discipline
Before changing architecture, document the reason.
Do not silently introduce frameworks, queues, databases, cloud services, paid APIs, analytics, tracking, or monetization.
Stop and request a decision when a security-sensitive or architectural requirement is ambiguous.

## Definition of done
A task is complete only when implementation, tests, documentation, security review, and Git state satisfy its acceptance criteria. The relevant progress and roadmap documents must reflect the verified result before the next stage begins.
