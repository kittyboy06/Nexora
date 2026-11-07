# NEXORA — Phase 11: Memory and Persistence Implementation Specification

## 1. Executive Summary & Purpose

Phase 11 implements a local, transparent, and tiered **Memory and Persistence Platform** for NEXORA. It evolves atomic task snapshots into a structured memory hierarchy—enabling long-term agent recall of user preferences, coding conventions, and project facts across sessions without quietly building a surveillance archive or retaining credentials.

---

## 2. Core Constraints & Guarantees

1. **Zero Secret Persistence:** Deterministic regex pre-write screening automatically blocks API keys, access tokens, passwords, bearer tokens, or private keys before any database write.
2. **Context Poisoning Defense:** Recalled memories injected into model prompts are strictly demarcated in `<recalled_memory>` tags and tagged as untrusted historical context. They can never override system instructions, tool security levels, or permission gates.
3. **Two-Stage Write Lifecycle:** Models cannot self-promote transient statements into durable memory. New memories undergo policy validation; sensitive facts stage as `PENDING_APPROVAL` and require explicit human operator confirmation.
4. **Hybrid Storage & Legacy Protection:** Legacy task JSON snapshots (`data/tasks/<task_id>.json`) remain untouched as the primary execution state store. SQLite (`data/memory/nexora_memory.db` in WAL mode) is used additively for durable records, FTS5 full-text search, and audit trails.
5. **Operator Primacy & Right to Forget:** Operators can inspect every stored fact, trace its provenance (originating task ID and justification), edit its value, change its TTL, export memories (JSON/CSV), or physically wipe records permanently.

---

## 3. Decision Log

| ID | Decision | Alternatives Considered | Rationale |
| :--- | :--- | :--- | :--- |
| **D1** | Hybrid persistence: Atomic JSON for task snapshots + Embedded SQLite (WAL) for durable records and audit | Pure JSON files; Full SQLite migration of all tasks | Preserves zero-risk backward compatibility for existing task execution while unlocking ACID transactions and fast relational queries for durable memory. |
| **D2** | SQLite FTS5 virtual table for lexical BM25 search | ChromaDB / Vector DB; Inverted in-memory index | FTS5 is built directly into Python's `sqlite3`, provides sub-millisecond search without external daemon overhead, VRAM contention, or embedding generation latency. |
| **D3** | Strict 4-Tier Memory Segregation (Request, Working, Durable, Archive) | Flat transcript log; Unbounded context window | Prevents memory pollution, minimizes context token consumption, and ensures ephemeral prompts are never permanently archived without consent. |
| **D4** | Pre-write regex secret scrubber | Post-hoc redaction; Relying on LLM sanitization | Deterministic screening at the Python layer guarantees credentials, passwords, and tokens never touch the database or disk. |
| **D5** | Two-stage proposal lifecycle (`PENDING_APPROVAL` gate) | Unrestricted agent writing; Manual-only user authoring | Allows agents to discover useful preferences autonomously while requiring human review for project facts or sensitive configurations. |
| **D6** | Dual delivery: Upfront planning context block + On-demand `memory_query` tool | Upfront prompt only; Tool-only querying | Gives the planner instant high-level preference awareness while allowing fleet subagents to perform targeted fact lookups during execution. |
| **D7** | Explicit `<recalled_memory>` tagging with disclaimer | Raw text injection into system prompt | Prevents recalled user data from hijacking model role identity or overriding tool permission boundaries (anti-prompt-injection). |
| **D8** | Preserved raw JSON task history with additive FTS5 indexing | Converting past tasks to SQLite tables | Completely avoids risky data migrations or breaking changes to Phase 2–10 task workflows. |
| **D9** | SQLite online backup API (`sqlite3_backup`) with `PRAGMA integrity_check` | File copy; Export-only | Allows zero-downtime, consistent point-in-time database snapshots and automated rollback on failure. |
| **D10** | Complete WinUI 3 management plane ("Memory & Persistence" tab) | CLI-only memory inspection; Read-only viewing | Operators maintain absolute oversight to view, approve, edit, revoke, delete, and export all retained intelligence. |

---

## 4. Architecture & Module Design

```
backend/app/memory/
├── __init__.py
├── models.py               # Domain models: MemoryRecord, MemoryProposal, MemoryAuditEntry, MemoryPolicy
├── database.py             # SQLite connection manager, WAL configuration, FTS5 table setup, migrations
├── security.py             # Secret scrubber regexes, sensitivity evaluator, and version hash generator
├── store.py                # CRUD repository for durable memory and audit logging
├── backup.py               # SQLite online backup, integrity verification, and rollback manager
├── retrieval.py            # Bounded prompt formatter, token budgeter, and FTS5 search engine
├── tools.py                # Core 'memory_query' BaseTool for runtime agent recall
├── service.py              # MemoryService orchestrating proposal lifecycle, recall, and governance
└── router.py               # FastAPI endpoints for /api/memory/*
```

---

## 5. Domain Models & SQLite Schema

### SQLite Schema (`data/memory/nexora_memory.db`)

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS durable_memory (
    id TEXT PRIMARY KEY,
    key TEXT NOT NULL,
    category TEXT NOT NULL,                -- 'user_preference', 'project_fact', 'system_constraint'
    value TEXT NOT NULL,
    sensitivity TEXT NOT NULL,             -- 'LOW', 'MEDIUM', 'HIGH'
    status TEXT NOT NULL,                  -- 'ACTIVE', 'PENDING_APPROVAL', 'EXPIRED', 'REVOKED'
    provenance_task_id TEXT,
    provenance_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT,                       -- NULL for indefinite retention
    version_hash TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    id UNINDEXED,
    key,
    category,
    value,
    content='durable_memory',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS memory_ai AFTER INSERT ON durable_memory BEGIN
    INSERT INTO memory_fts(rowid, id, key, category, value) VALUES (new.rowid, new.id, new.key, new.category, new.value);
END;

CREATE TRIGGER IF NOT EXISTS memory_ad AFTER DELETE ON durable_memory BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, id, key, category, value) VALUES('delete', old.rowid, old.id, old.key, old.category, old.value);
END;

CREATE TRIGGER IF NOT EXISTS memory_au AFTER UPDATE ON durable_memory BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, id, key, category, value) VALUES('delete', old.rowid, old.id, old.key, old.category, old.value);
    INSERT INTO memory_fts(rowid, id, key, category, value) VALUES (new.rowid, new.id, new.key, new.category, new.value);
END;

CREATE TABLE IF NOT EXISTS memory_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id TEXT NOT NULL,
    action TEXT NOT NULL,                  -- 'PROPOSE', 'APPROVE', 'UPDATE', 'RECALL', 'REVOKE', 'DELETE'
    actor TEXT NOT NULL,                   -- 'agent', 'operator', 'policy_engine'
    task_id TEXT,
    details TEXT,
    timestamp TEXT NOT NULL
);
```

---

## 6. Implementation Milestones

* **Milestone 1: Domain Models, SQLite Database Manager & Migrations**
  * `models.py`, `database.py`, tables creation, FTS5 virtual tables, WAL mode, unit tests in `test_memory_db.py`.
* **Milestone 2: Security Gate, Secret Scrubber & Memory Store**
  * `security.py`, `store.py`, pre-write regex screening, version hash validation, audit logging, unit tests in `test_memory_store.py`.
* **Milestone 3: Backup, Integrity & Rollback Service**
  * `backup.py`, SQLite online backup, `PRAGMA integrity_check`, restore/rollback verification, unit tests in `test_memory_backup.py`.
* **Milestone 4: Memory Retrieval Engine, Prompt Context Budgeter & `memory_query` Tool**
  * `retrieval.py`, `tools.py`, token budgeting (1,000 token limit), XML formatting with anti-poisoning disclaimers, unit tests in `test_memory_retrieval.py`.
* **Milestone 5: Memory Orchestration Service, FastAPI Router & Main Wiring**
  * `service.py`, `router.py`, wiring in `backend/app/main.py`, integration tests in `test_memory_api.py`.
* **Milestone 6: WinUI 3 Desktop Control Plane**
  * `MemoryModels.cs`, `INexoraApiClient.cs`, `NexoraApiClient.cs`, `MemoryViewModel.cs`, 5th navigation tab in `MainWindow.xaml`, unit tests in `Nexora.Desktop.Tests/MemoryViewModelTests.cs`.
* **Milestone 7: Verification & End-to-End Testing**
  * End-to-end integration test `test_memory_e2e.py`, full backend regression pass (226+ tests), full desktop regression pass (31+ tests).
