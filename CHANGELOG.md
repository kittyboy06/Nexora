# NEXORA Changelog

All notable changes to the NEXORA platform are documented in this file.

---

## [1.0.0] - 2026-11-07

### Added
* **Phase 14 — Hardening and Release:**
  * System diagnostics engine and pre-flight doctor (`backend/app/cli/doctor.py`, `scripts/doctor.ps1`).
  * Sanitized diagnostic support bundle exporter (`scripts/export-diagnostics.ps1`).
  * High-entropy secret scrubbing for memory, logs, and trace JSONs (`MemorySecurityGate.scrub_secrets`).
  * 16-test adversarial security regression suite (`backend/tests/security/test_security_hardening.py`).
  * Supply chain security audit script (`scripts/security-audit.ps1`) and CycloneDX SBOM (`docs/SBOM.json`).
  * Automated 24-hour quarantine pruner (`backend/app/core/pruner.py`) and 10MB rotating file logger.
  * Atomic SQLite WAL backup (`scripts/backup.ps1`) with `PRAGMA wal_checkpoint(TRUNCATE)` and SHA-256 verification.
  * Safe data restoration (`scripts/restore.ps1`) with automatic rollback snapshots and SQLite integrity checks.
  * System clean and factory reset tool (`scripts/uninstall-clean.ps1`).
  * One-click onboarding script (`scripts/bootstrap.ps1`).
  * Tiered test runner (`scripts/run-all-tests.ps1`) and live Ollama smoke suite (`test_live_smoke.py`).
  * Complete documentation suite (`DEPLOYMENT_GUIDE.md`, `SECURITY_AUDIT.md`, `BACKUP_RECOVERY.md`, `TEST_MATRIX.md`).

* **Phase 13 — Scheduler and Background Work:**
  * Deterministic recurrence engine supporting cron expressions, intervals, and one-shot executions with `zoneinfo` across DST shifts.
  * Concurrency guard (`SKIP_BUSY`, `RETRY_GRACE`, 10-minute approval timeout, drift invalidation).
  * SQLite WAL scheduler store with atomic leases and idempotency keys.
  * Startup reconciliation sweep recovering interrupted tasks.
  * WinUI 3 7th navigation pill "Scheduler & Automation" with card views, creation modal, and run history drawer.

* **Phase 12 — Desktop Vision and Interaction Platform:**
  * Win32 UI Automation tree inspector and native coordinate mapper.
  * `WindowFocusGuard` preventing interactions with shielded processes (1Password, Bitwarden, KeePass, UAC).
  * Short-lived visual verification screenshots with automatic password blackout redaction.

* **Phase 11 — Long-Term Memory and Retrieval:**
  * SQLite FTS5 lexical full-text search combined with vector similarity search.
  * High-entropy secret scrubbing on memory creation and retrieval.
  * Operator review and memory revocation endpoints.

* **Phase 10 — Dynamic Tool Generation and Code Sandbox:**
  * Abstract Syntax Tree (AST) security validator blocking dangerous Python imports.
  * Win32 Job Object sandbox execution with strict memory (500 MB), process (max 4), and timeout (30s) quotas.
  * Dynamic generated tool registry with hot-reloading bridge.

* **Phase 9 — Browser and Internet Research:**
  * Privacy-preserving search and web fetch engine.
  * Anti-prompt injection XML evidence fencing (`<untrusted_web_evidence>`).
  * Quarantine download manager with SHA-256 validation.

* **Phase 8 — Universal Model Context Protocol (MCP) Platform:**
  * Standard stdio client supporting tool discovery, parameter schema generation, and execution.
  * Encrypted credential vault with Windows DPAPI protection.

* **Phase 7 — Dynamic Skill Loading and Catalog:**
  * Markdown skill parser with semantic versioning.
  * Dynamic GitHub discovery and installation.
  * Deterministic policy composer with role matching and XML container fencing.

* **Phase 6 — Multi-Agent Fleet:**
  * DAG-based dependency planner supporting sequential and branching execution.
  * Specialized agent roles (Researcher, Coder, Reviewer, Verifier).
  * Immutable SHA-256 artifact pipeline between fleet nodes.

* **Phase 5 — Native WinUI 3 Desktop Application:**
  * Modern Fluent UI application built on C# / .NET 8.
  * Task composer, live execution progress timeline, and human approval dialogs.
  * Always-on-top corner companion mode.

* **Phases 0–4 — Foundation & Core Autonomous Engine:**
  * FastAPI backend with strict localhost loopback binding (`127.0.0.1:8000`).
  * Ollama client with GPU concurrency guard (limit=1).
  * Deterministic task state machine, execution planner, and retry supervisor.
  * Sandboxed filesystem and tokenized terminal execution services.
  * Dual-model router and dynamic latency calibration profiler.
