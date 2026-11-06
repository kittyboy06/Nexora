# Module 04 — Skills and GitHub Discovery

## Responsibility

Manage local Markdown skills and candidate discovery from GitHub while preserving provenance, review and selective use. A skill is guidance text; it is never authority to execute, install, access credentials or alter system policy.

## Local catalogue

Store approved skill bundles under a stable ID/version layout with `SKILL.md`, validated manifest and provenance. Manifest includes source/ref/hash, compatible roles, declared capabilities, size, license/review status and lifecycle state. Pin imported sources. No content executes at import time.

## Selection and injection

Planner can propose IDs; manager filters by profile compatibility, approval, enabled state, user policy, declared capability constraints and context budget. Ordering is deterministic. Detect conflicts and fail closed or require review. Prompt marks injected content as untrusted guidance. Audit exact ID/version/hash, selection reason, injection order and task/agent.

## GitHub discovery

Discovery uses read-only metadata/file access. It produces a candidate inspection record, never installation. Capture repository URL, owner, ref/commit, license, files/manifest, dependency/install declarations, suspicious patterns and review decision. Private access requires a least-privilege credential reference outside prompts/logs. Source changes invalidate previous review.

## Tests

Manifest/size/hash/schema failures, disabled/rejected/mismatched selection, deterministic selection, prompt injection, GitHub pagination/rate limit/access failures, import rollback and no-execution guarantee.
