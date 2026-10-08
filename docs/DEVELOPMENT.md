# Development Workflow

## Source of truth
GitHub is canonical. Before work, synchronize with main, inspect the working tree, and confirm there are no unrelated local changes.

## Branches
Use feature/name, fix/name, refactor/name, or docs/name for non-trivial work.

## Commits
Use Conventional Commit prefixes. One coherent change per commit.

## Pre-commit checklist
- Tests and checks pass.
- Diff reviewed.
- No secrets or personal data.
- No generated files or accidental media.
- Documentation updated when required.
- Commit message describes the actual change.

## Synchronization
After each commit verify the commit SHA and branch state, then keep the local and GitHub histories aligned.
