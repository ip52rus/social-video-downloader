# Development Workflow

## Source of truth
GitHub is canonical. Before work, synchronize with main, inspect the working tree, and confirm there are no unrelated local changes. Preserve unrelated local files and never overwrite them as part of routine project work.

## Stage workflow
1. Read the relevant roadmap, task decomposition, architecture, testing guidance, and applicable agent rules before implementation.
2. Confirm the current stage, its acceptance criteria, dependencies, and outstanding checks. Do not skip an unmet roadmap gate without explicitly documenting the reason and obtaining a decision where needed.
3. Make a small, focused change on an appropriate branch.
4. Run the relevant tests and quality checks. Perform external-platform or end-to-end checks when required by the acceptance criteria.
5. Review implementation results and distinguish verified behavior from assumptions and untested cases.
6. Update `docs/TASKS.md` after every completed stage and before starting the next stage. Update `docs/ROADMAP.md` when phase status, gates, dependencies, scope, or the next step changes. Update any other document made inaccurate by the change.
7. Review the complete diff, changed-file list, test results, documentation consistency, and security implications.
8. Only then commit the coherent change, using a Conventional Commit message.

## Documentation requirements
- Documentation updates are part of the stage's definition of done.
- A task may be marked complete only when its acceptance criteria have evidence supporting completion.
- Keep partial work unchecked and describe the checks still outstanding.
- Identify the type and scope of verification: unit tests, deterministic integration tests, real external-platform tests, or Telegram end-to-end tests.
- For external-platform tests, record the scope of the evidence and distinguish application regressions from platform changes or transient network failures.
- Do not claim broad reliability based on one successful URL or one happy-path test.
- If a stage is not complete, preserve its in-progress status and state the remaining acceptance criteria.
- Do not defer routine documentation synchronization to an unspecified future cleanup task.

## Branches
Use `feature/name`, `fix/name`, `refactor/name`, or `docs/name` for non-trivial work.

## Commits
Use Conventional Commit prefixes. One coherent change per commit.

## Pre-commit checklist
- Relevant tests and checks pass, or outstanding failures are explicitly documented.
- Diff and changed-file list reviewed.
- No secrets or personal data.
- No generated files or accidental media.
- `docs/TASKS.md` and `docs/ROADMAP.md` accurately reflect the verified progress.
- Other affected documentation is updated.
- Commit message describes the actual change.

## Synchronization
After each commit verify the commit SHA and branch state, then keep the local and GitHub histories aligned. Do not overwrite unrelated local work while synchronizing.
