# NEXORA — Phase 11: Memory and Persistence

## Purpose

Provide useful continuity while keeping storage local, understandable, inspectable and removable. This phase evolves current atomic task snapshots into tiered memory and a deliberate persistence strategy; it must not quietly build a surveillance archive.

## Prerequisites

- Read `Modules/08 — Memory and Persistence.md` and `Modules/01 — Governance, Permissions, Audit and Verification.md`.
- Decide whether SQLite is needed, and write a migration/backup/rollback plan before replacing existing task JSON snapshots.
- Dashboard control plane must be capable of showing/editing/deleting memory records.

## Memory tiers

### Request context

Ephemeral user request, immediate constraints and conversation inputs. It is used to execute one task and discarded from durable storage unless explicitly selected by policy/consent.

### Task working memory

Bounded plan state, agent artifacts, tool outputs, evidence and execution trace required to complete/review a task. It inherits task retention rules and stores references/summary where full content is sensitive or large.

### Durable user memory

Explicitly approved preferences and facts such as preferred model selection or project conventions. Each record requires provenance, consent/creation reason, sensitivity level, editable value, expiry/retention and deletion state.

### Searchable archive

Optional retrieval over old task summaries/evidence. Introduce only after retention, indexing, embeddings, access boundaries, deletion propagation and storage cost are designed. Vector storage is optional; it is not a prerequisite for useful NEXORA memory.

## Scope

- Typed records for memory, provenance, sensitivity, retention, consent and lifecycle.
- Local storage abstraction that supports current JSON task history and a deliberate database migration if selected.
- Memory policy filtering before models receive retrieved content.
- User dashboard controls: view, search, approve, edit, delete, export, retention settings and per-record provenance.
- Per-task working-memory budgets and redaction/summarization rules.
- Backup/restore, integrity checks, migration and rollback procedure.
- Audit events for read, write, consent, update, export and deletion.

## Excluded

- Automatic storage of all conversations, page contents, screenshots or tool results forever.
- Durable storage of passwords, API keys, cookies, tokens, private credentials or raw sensitive form data.
- Cross-user sharing, cloud synchronization or training on user data.
- Embedding/vector database before a documented retrieval need exists.

## Retrieval flow

1. A planner/agent asks for a narrow memory category and task reason.
2. Memory policy checks agent role, sensitivity and task scope.
3. Service retrieves minimum necessary records, applies expiry/deletion/consent filters and redacts protected fields.
4. Returned context includes provenance and is marked as recalled data, not a system instruction.
5. Task audit records which memory IDs/version hashes were read, without copying sensitive values unnecessarily.

Models cannot self-promote a transient statement into durable memory. Proposed memory writes must meet deterministic policy, then use user approval where the configured rule requires it.

## Migration and data integrity

Existing Phase 2 task JSON remains supported until migration succeeds. If SQLite is adopted, version a schema migration, import records transactionally, retain verified backups, compare counts/hashes, and provide a rollback path. Never delete legacy snapshots before migration/restore verification. Database encryption, if selected, requires key management design and must not make the app unrecoverable without a documented backup procedure.

## Test plan

- Record schema, expiry, consent, sensitivity and deletion filtering.
- Ensure expired/deleted/unapproved records never reach model context.
- Provenance/audit completeness and user edit/delete/export behavior.
- Sensitive value exclusion and redaction tests.
- JSON-to-database migration, partial failure, duplicate import, backup/restore and rollback.
- Context size/budget tests and retrieval relevance with deterministic fixtures.

## Acceptance criteria

- Users can see, correct, export and delete what NEXORA retains.
- Durable storage has a reason, provenance, retention state and access policy.
- Old task persistence remains readable or has a tested reversible migration.
- Memory cannot bypass central permissions or become hidden model instructions.

## Implementation sequence

1. Define tier/record/policy schemas and dashboard mock view.
2. Add task working-memory references and retention controls.
3. Add durable user memory with explicit lifecycle/audit.
4. Decide/implement storage migration and backup only after tests.
5. Add narrow retrieval with policy filtering.
6. Evaluate searchable archive/vector retrieval as a separate decision.
