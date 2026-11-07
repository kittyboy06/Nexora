# NEXORA Backup, Restore & Data Lifecycle Operations Guide

**Version:** 1.0.0  
**Target Platform:** Windows 10/11 (x64)  
**Applicability:** Production Deployments, CI/CD, and Development Environments

---

## 1. Storage Architecture Overview

NEXORA organizes all mutable runtime state, long-term memory, and task execution history under the root `data/` directory:

```
data/
├── memory/
│   └── nexora_memory.db          <-- Phase 11 Long-Term Memory (SQLite WAL)
├── scheduler/
│   └── nexora_scheduler.db       <-- Phase 13 Background Schedules & Runs (SQLite WAL)
├── tasks/
│   └── *.json                    <-- Phase 2/3 Task execution plans and traces
├── skills/                       <-- Phase 7 Installed local skill packages
├── mcp/                          <-- Phase 8 MCP server registry & secrets vault
├── workspace/                    <-- Sandboxed user directory for filesystem tasks
├── model_profiles.json           <-- Hardware inference calibration cache
├── logs/                         <-- Rotating run logs (excluded from backup)
└── quarantine/                   <-- Ephemeral 24h downloads (excluded from backup)
```

### 1.1. SQLite Write-Ahead Logging (WAL)
Both `nexora_memory.db` and `nexora_scheduler.db` operate in SQLite `WAL` mode (`PRAGMA journal_mode=WAL;`). In WAL mode, concurrent readers never block writers, and writes append to companion `-wal` and `-shm` files.

Before any backup or archive operation, NEXORA executes:
```sql
PRAGMA wal_checkpoint(TRUNCATE);
```
This forces all active WAL log pages to be cleanly committed into the main `.db` file and truncates the WAL file to zero bytes, ensuring a 100% consistent, self-contained single-file state suitable for cold or live backup.

---

## 2. Taking an Atomic Backup

Use the automated PowerShell backup script:

```powershell
# Create a timestamped backup in backups/
.\scripts\backup.ps1

# Or specify a custom output path:
.\scripts\backup.ps1 -BackupPath "D:\Backups\nexora-production-20261107.zip"
```

### What `backup.ps1` Does:
1. **Flushes WAL:** Executes `PRAGMA wal_checkpoint(TRUNCATE);` across all SQLite databases.
2. **Assembles Payload:** Collects `memory/`, `scheduler/`, `tasks/`, `skills/`, `mcp/`, `workspace/`, and `model_profiles.json`.
3. **Excludes Ephemeral Data:** Skips `logs/` (rotated separately) and `quarantine/` (auto-pruned after 24h).
4. **Attaches Manifest:** Embeds `backup_manifest.json` detailing timestamp, machine name, and item counts.
5. **Generates Checksum:** Computes a SHA-256 hash and writes it to `<backup-file>.sha256`.

---

## 3. Verifying Backup Soundness

Before deploying or applying a backup, you can test its health non-destructively:

```powershell
.\scripts\restore.ps1 -BackupPath "backups\nexora-backup-20261107_120000.zip" -VerifyOnly
```

### Verification Checks:
* Validates the archive against the companion `.sha256` checksum.
* Inspects `backup_manifest.json`.
* Extracts SQLite databases to a temporary sandbox and executes `PRAGMA integrity_check;`.
* Exits 0 on clean pass; does NOT alter `data/`.

---

## 4. Restoring From Backup

To restore data onto a machine:

```powershell
# Interactive restore (prompts before applying):
.\scripts\restore.ps1 -BackupPath "backups\nexora-backup-20261107_120000.zip"

# Automated / unattended restore:
.\scripts\restore.ps1 -BackupPath "backups\nexora-backup-20261107_120000.zip" -Force
```

### Rollback Protection:
`restore.ps1` automatically captures a temporary rollback snapshot of existing `data/` before copying new files. If any restored database fails its post-extraction integrity check, the restore automatically reverts back to the pre-restore state.

---

## 5. System Cleanup & Factory Reset

To purge test data or reset the workspace:

```powershell
# Mode 1: Data-Only Reset (Purges data/ directory; preserves code, git, .env)
.\scripts\uninstall-clean.ps1 -Mode DataOnly -Force

# Mode 2: Full Factory Reset (Purges data/, build artifacts, pycache, diagnostics)
.\scripts\uninstall-clean.ps1 -Mode FactoryReset -Force
```

---

## 6. Disaster Recovery Runbook

| Incident | Recovery Action |
| :--- | :--- |
| **Corrupted SQLite DB** | 1. Stop backend (`Ctrl+C`).<br/>2. Run `.\scripts\restore.ps1 -BackupPath <latest_backup.zip> -Force`.<br/>3. Restart backend. |
| **Laptop / Machine Migration** | 1. On source machine: `.\scripts\backup.ps1`.<br/>2. Copy `.zip` and `.sha256` to target machine.<br/>3. On target machine: `.\scripts\bootstrap.ps1`.<br/>4. Run `.\scripts\restore.ps1 -BackupPath <file.zip> -Force`. |
| **Accidental Task Deletion** | 1. Verify backup via `-VerifyOnly`.<br/>2. Extract required task JSONs from the backup zip into `data/tasks/`. |
