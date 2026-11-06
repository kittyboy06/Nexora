# NEXORA — Phase 7: Skills and GitHub Discovery

## Purpose

Introduce a controlled way to store, inspect, select and inject Markdown skills into a task-specific agent. Add read-only discovery of candidate skills, tools, MCP servers and workflow templates from GitHub. This phase establishes provenance and review, not automatic installation or execution.

## Prerequisites

- Phase 6 agent/profile contracts are stable enough to attach a selected skill set.
- Read `Modules/04 — Skills and GitHub Discovery.md` and `Modules/01 — Governance, Permissions, Audit and Verification.md`.
- Decide the minimum local directory format for skill storage and metadata before code is written.

## Scope

### Included

- Local Markdown skill catalogue with typed frontmatter/manifest, content hash, source, version/commit, author/maintainer metadata, status and compatibility data.
- Skills inspection API/UI: list, read, validate, enable/disable and view provenance.
- Deterministic relevance selector that produces candidate skill IDs for a task/profile; selection can be model-assisted but policy validates final set.
- Bounded selective injection: only approved, enabled skills that fit context/budget are included in a particular agent prompt.
- Per-task audit of exact skill version/hash and injection order.
- GitHub discovery adapters that query/read candidate repositories without running their code.
- Review queue for discovered assets: source URL, commit/ref, license, files, manifests, dependencies, declared permissions and risk summary.
- Pin, accept, reject, disable and rollback workflow for local approved skill records.

### Excluded

- Automatic installation of packages, MCP servers, tool code or workflow scripts.
- Treating any Markdown file as executable authority.
- Global injection of all installed skills.
- Automatic updates from GitHub.
- Running repository test scripts or reading secrets from GitHub issues/actions.

## Skill format

Use a predictable local skill bundle. Proposed minimum structure:

```text
data/skills/<skill-id>/<version>/
├── SKILL.md            # Human-readable instruction content
├── manifest.json       # Parsed, validated metadata
└── provenance.json     # Source/ref/hash/review history
```

The manifest must include: unique ID; display name; semantic/local version; description; compatible profile roles; allowed task categories; declared required capability IDs; instruction size; source type; source URL/ref; content hash; reviewer; approval state; created/updated dates. Reject missing IDs, duplicate IDs, invalid hashes, oversized content, unsupported capability requests and unknown fields unless a versioned schema permits them.

## Injection policy

1. A router/planner may propose relevant skill IDs based on task metadata.
2. `SkillManager` filters proposals by enabled/reviewed state, profile compatibility, policy, declared capabilities, sensitivity and token budget.
3. The manager orders skills deterministically and records why each was selected.
4. The agent prompt labels skill content as untrusted operational guidance that cannot alter execution policy or permissions.
5. Conflicting instructions are detected; a conflict fails closed or asks for user/maintainer resolution rather than choosing silently.
6. The task audit stores the resolved skill manifest/hash, not merely the human-readable ID.

No skill text can create a tool, install an MCP server, access credentials, bypass confirmation, or change system instructions.

## GitHub discovery workflow

1. User or task requests a discovery search within configured public/private source scope.
2. Discovery service uses GitHub APIs or an approved read-only transport to collect candidate metadata and selected files.
3. It never clones/runs untrusted repositories as part of discovery.
4. It extracts manifests/readmes, license and dependency declarations into a normalized inspection record.
5. Static analysis checks for missing provenance, suspicious install commands, policy conflict, large binaries and incompatible formats.
6. User reviews an explicit proposal. Accepting a Markdown skill imports a pinned copy with provenance. Accepting tools/MCP/workflows only creates a later installation proposal; it does not install them.

Private GitHub access, token storage and allowed organizations are separate user-controlled configuration decisions. Tokens must remain outside prompts/logs and be scoped read-only where possible.

## API and UI requirements

Candidate endpoints: skills list/detail, validate/import local skill, enable/disable, discovery search, discovery result detail, accept/reject candidate and usage history. All mutating actions need a user-visible confirmation path and audit event. Do not expose raw untrusted Markdown in a way that executes HTML or scripts in the dashboard.

## Test plan

- Manifest schema and path validation; duplicate/version conflicts; content hash verification; oversized file rejection.
- Selector relevance, profile mismatch, disabled/rejected skill exclusion, deterministic order and context-budget truncation/rejection.
- Prompt-injection examples that try to override permissions; assert only text is passed and no policy changes occur.
- Mock GitHub API discovery with pagination, rate limits, inaccessible repository, malicious readme, unsupported license and changed commit.
- Import/disable/rollback/audit tests; no network or repository command execution in discovery tests.

## Acceptance criteria

- Only approved, compatible, pinned skills can be injected.
- Every task identifies injected skill versions/hashes and selection reasons.
- GitHub discovery creates inspection records only; it cannot install or execute discovered assets.
- Dashboard lets the user inspect, enable, disable and rollback skills.
- Existing task execution behavior is unchanged when no skill is selected.

## Implementation sequence

1. Define manifest/Pydantic schemas and local storage layout.
2. Implement local catalog, validation, import and audit with tests.
3. Implement policy-based selector and planner/agent integration.
4. Build dashboard inspection/management view.
5. Add read-only GitHub discovery and review records using mocks.
6. Document configuration, source scope and live test evidence.
