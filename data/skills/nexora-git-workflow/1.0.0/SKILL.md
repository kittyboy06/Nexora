# NEXORA Git Conventional Workflow

## 1. Branch Strategy
- Keep feature branches short-lived and scoped to a single milestone or feature.
- Name branches using category prefixes: feat/<name>, fix/<name>, chore/<name>, refactor/<name>.

## 2. Conventional Commit Standards
All commits must strictly follow the Conventional Commits 1.0.0 format:
- feat: add new capability or user-facing feature
- fix: resolve a bug or failure
- refactor: code restructure with no behavior change
- test: add or update unit and integration test suites
- docs: update documentation or architecture plans

## 3. Hygiene & Safety Rules
- Never use force push (git push -f) on shared or default branches.
- Always run git status and verify staged changes before executing git commit.
- Keep commit diffs minimal and atomic.
