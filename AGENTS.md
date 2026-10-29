# AGENTS.md

## Purpose

This file defines the operating rules for AI agents working on the Social Video Downloader repository.

## Project authority and scope

- The human owner decides stage boundaries, product policy and authorization. ChatGPT
  supports analysis/planning; Codex executes the explicitly agreed task.
- Do not expand scope, turn hypotheses into facts, or start the next stage automatically.
- On a new safety/integrity blocker, stop affected work and report evidence and unknowns.
  Accepted deviations below are not new blockers while unchanged.

## Canonical documentation and reading order

1. `AGENTS.md` (this file).
2. `docs/PROJECT.md` (product and current scope).
3. `docs/ARCHITECTURE.md` (implemented boundaries).
4. `docs/ROADMAP.md` (stage order and open gates).
5. `docs/TASKS.md` (verified completion and backlog).
6. `docs/DEVELOPMENT.md` (workflow and historical engineering records).
7. `docs/TESTING.md` (offline/CI/deployment/owner LIVE evidence and limits).
8. `docs/SECURITY.md`.
9. `docs/LOCAL_BOT_API.md` (canonical deployment/operations, dated HOSTKEY record).
10. `docs/research/TIKTOK_SHORT_DRAMA.md` only for an explicitly authorized research task.
11. `docs/CHAT_HANDOFF_2026-10-29.md` (self-contained dated handoff; recheck drift).

Use code/configuration first, then reproducible tests/CI, Git/PR history, canonical
project docs, preserved reports, owner observations and explicitly marked hypotheses.
Dates and evidence categories matter. Historical documents do not authorize operations.

## Workflow approval gates

Implementation, external LIVE experiments, merge, deployment, production LIVE tests,
server-configuration changes and risky Git operations require separate owner scope.
Authorization already given in the session remains valid within that scope; do not
ask again merely because a checklist mentions approval. Passing tests/CI never grants
permission for another gate. Draft PR publication is not merge or deployment approval.

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

## Accepted worktree deviation (checkpoint 2026-10-29)

- Nineteen existing registrations report `prunable gitdir file points to non-existent
  location`. The owner accepts this unchanged deviation for research/documentation.
- Earlier temporary-worktree preservation incidents and private archives remain
  preserved; do not infer that all 19 entries share a cause or known incident.
- Never prune/remove/repair these registrations, run GC, or restore/clean historical
  directories without separate explicit authorization. Do not modify existing worktrees.
- Compare the main checkout HEAD/status and existing registrations before/after work.
  A deliberately authorized new permanent worktree is separate from those 19 entries.
- Stop for new missing files, altered existing registrations/count or unexpected main
  checkout changes. Main's checkpoint baseline is `f74dc6c933012b809d4e6dc33ed3f3bdadc39d34`;
  documentation branches must not move it. Historical untracked/ignored losses are UNKNOWN.

## Security

Never commit tokens, API keys, passwords, cookies, session files, private keys, user media, user identifiers, personal contact data, .env files, or machine-specific private paths.
Use environment variables and .env.example for non-secret configuration documentation.

Do not export browser sessions, credentials, signed media URLs, HAR or raw platform
responses into Git, reports, fixtures or logs. Sensitive query values previously seen
in chat are not reusable evidence or example values. Preserve transport URL/DNS/IP/
redirect guards, Phase 9C budgets, worker drain and cleanup/quarantine ownership.
Do not start a second production poller. HOSTKEY is the designated sole deployment;
MacBook containers are retained stopped for controlled rollback. Verify dated state
only when authorized; do not operate production during documentation work.
No uncontrolled downloads, account-cookie integration or automated access bypass.

## Deferred research

TikTok Short Drama is DEFERRED / SERVER RESOLVER BLOCKED / RESEARCH PRESERVED.
Read its canonical record before any future work; do not repeat exhausted PoCs or
resume LIVE/monitoring without a separate owner decision. It does not block the main
reliability roadmap. Only free self-hosted OSS with reviewed commercial-compatible
licensing is eligible; no paid API/SaaS, closed downloader or external download server.

## AI discipline

Before changing architecture, document the reason.
Do not silently introduce frameworks, queues, databases, cloud services, paid APIs, analytics, tracking, or monetization.
Stop and request a decision when a security-sensitive or architectural requirement is ambiguous.

## Definition of done

A task is complete only when implementation, tests, documentation, security review, and Git state satisfy its acceptance criteria. The relevant progress and roadmap documents must reflect the verified result before the next stage begins.
