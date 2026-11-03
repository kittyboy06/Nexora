# NEXORA — Phase 3: Real-World Tool Integration
## Technical Design Specification — Version 1.0

---

## 1. Executive Summary

This document specifies the architectural design for **Phase 3: Real-World Tool Integration** of NEXORA.

Phase 3 transitions NEXORA from simulated mock tools to controlled, real-world Windows 11 capabilities across three domains:
1. **Milestone 3A — Filesystem Intelligence**: Controlled filesystem operations strictly confined to a dedicated workspace jail (`data/workspace/`).
2. **Milestone 3B — Windows Application Control**: Native application discovery via `winreg` and Start Menu shortcuts, and safe process management.
3. **Milestone 3C — Terminal Intelligence**: Controlled command execution using tokenized argument arrays (`asyncio.create_subprocess_exec`) against a strict allowlist.
4. **Milestone 3D — Integration Testing**: Multi-step autonomous agent tasks combining filesystem, application, and terminal tools.

> **Security Rule**: NEXORA never executes unverified commands or unrestricted operations. All actions pass through strict path canonicalization, command allowlists, and the dynamic `PermissionManager` gatekeeper before execution.

---

## 2. Understanding Summary & Security Boundaries

* **Filesystem Containment**: All filesystem tools are confined to `data/workspace/`. All paths are canonicalized with `Path.resolve()`; traversal escapes or dangling symlinks raise `PathTraversalException`. Overwrite and delete require `SENSITIVE` human approval.
* **Application Control**: Discovered natively via Windows Registry (`winreg`) and Start Menu `.lnk` shortcut traversal. Process termination is restricted to user applications or NEXORA-launched PIDs; system processes (`explorer.exe`, `svchost.exe`, `csrss.exe`) are protected by a hard denylist.
* **Terminal Hardening**: Commands run via tokenized arrays using `asyncio.create_subprocess_exec` (strictly **no `shell=True`**) to prevent injection attacks. Execution is limited to a configurable allowlist (`python`, `pip`, `git`, `node`, `npm`, `pytest`, `systeminfo`, `whoami`, `ipconfig`) with execution timeouts and output masking.
* **Dynamic Permission Model**: Tools implement `get_risk_level(arguments: dict) -> RiskLevel` on `BaseTool` to dynamically classify operations:
  * `SAFE`: Read-only operations in the workspace (`file_read`, `file_list`, `terminal_get_system_info`).
  * `CONTROLLED`: Non-destructive state modifications (`file_create`, `file_edit`, `app_launch`).
  * `SENSITIVE`: Deletions, overwrites, package installations, app terminations (`file_delete`, `terminal_install_package`, `app_close`).
* **Progressive Milestone Strategy**:
  * Implement and test **3A** completely before starting **3B**.
  * Implement and test **3B** completely before starting **3C**.
  * Complete **3D** integration testing after all tools pass.
* **Explicit Non-Goals (Scope Restrictions)**:
  * No browser automation (Playwright).
  * No mouse or keyboard control.
  * No screenshot capture or visual interaction.
  * No persistent vector/SQL memory.
  * No background cron schedulers.
  * No frontend dashboard.

---

## 3. Assumptions

1. **Host Environment**: Running natively on Windows 11 with standard user privileges.
2. **Architecture Reusability**: All tools plug directly into the existing Phase 2 `BaseTool`, `ToolRegistry`, `PermissionManager`, `Executor`, `PlanValidator`, and `AgentOrchestrator` without rewriting core agent logic.
3. **Workspace Location**: Default workspace is `data/workspace/` inside the NEXORA project root, configurable via `.env`.
4. **Offline & Isolated Testing**: Unit tests use isolated temporary folders (`tmp_path`) for filesystem operations and mock process runners where appropriate.

---

## 4. Decision Log

| # | Topic | Decision | Alternatives Considered | Rationale |
|---|---|---|---|---|
| **D25** | Filesystem Boundary | Strict Workspace Jail confined to `data/workspace/`; path resolution rejecting escapes with `PathTraversalException` | Unrestricted filesystem access; Whitelisted system paths | Prevents unintended edits or deletions to host OS, user files, or system directories. |
| **D26** | Application Discovery & Control | Native Windows Registry (`winreg`) + Start Menu scan; PID-tracked process termination | PowerShell command scraping; Unrestricted `taskkill` | Avoids shell injection and prevents accidental termination of critical Windows system processes. |
| **D27** | Terminal Execution Safeguards | Tokenized argument arrays (`asyncio.create_subprocess_exec`) without shell interpolation + strict command allowlist | `shell=True` with regex sanitization; PowerShell AST parsing | Physically eliminates shell injection attacks while confining execution to pre-approved binaries. |
| **D28** | Dynamic Permission Model | `BaseTool.get_risk_level(arguments)` enables dynamic risk escalation based on arguments (e.g. overwriting/deleting is `SENSITIVE`) | Static tool risk levels; Centralized permission matrix | Accurately reflects operation danger without trusting the LLM's classification. |
| **D29** | Progressive Milestones | Strict sequential milestone gating: 3A (Filesystem) $\rightarrow$ 3B (Apps) $\rightarrow$ 3C (Terminal) $\rightarrow$ 3D (Integration) | Simultaneous bulk implementation; Flat single release | Guarantees security and unit-test stability of each subsystem before introducing the next. |
| **D30** | Subsystem Architecture | Dedicated service layer (`FilesystemService`, `AppService`, `TerminalService`) backing thin `BaseTool` adapters | Self-contained tool monoliths; Separate IPC daemon | Consolidates security checks in central testable services while keeping tool adapters lightweight. |

---

## 5. Architectural Structure & Directory Layout

```text
backend/app/
├── services/
│   ├── ollama_service.py       # Phase 1: Local LLM service
│   ├── filesystem_service.py   # Phase 3A: Workspace path jail & file operations
│   ├── app_service.py          # Phase 3B: Windows registry scan & process supervisor
│   └── terminal_service.py     # Phase 3C: Tokenized subprocess runner & allowlist
├── tools/
│   ├── base.py                 # Enhanced BaseTool with dynamic get_risk_level()
│   ├── registry.py             # Central ToolRegistry
│   ├── mock_tools/             # Phase 2: Mock tools
│   ├── filesystem/             # Phase 3A: 9 filesystem tools
│   ├── windows/                # Phase 3B: 6 Windows application control tools
│   └── terminal/               # Phase 3C: 5 controlled terminal tools
├── permissions/
│   └── manager.py              # Evaluates dynamic effective risk before execution
└── core/
    ├── config.py               # Workspace path, file limits, command allowlists
    └── exceptions.py           # PathTraversalException, CommandNotAllowedException, etc.
```

---

## 6. Milestone Specifications

### 6.1 Milestone 3A: Filesystem Intelligence

* **Service**: `FilesystemService` enforces:
  - Canonical path resolution against `workspace_root`.
  - Rejection of path traversal (`../`) and symlink escapes outside the jail.
  - File size threshold (default 5 MB).
  - Prevention of silent overwrites.

* **Tools (`tools/filesystem/`)**:
  1. `file_list` (`SAFE`): List directory entries with size, is_dir, and timestamps.
  2. `file_search` (`SAFE`): Recursive glob search within workspace.
  3. `file_read` (`SAFE`): Read text file contents with byte limit.
  4. `file_create` (`CONTROLLED` / `SENSITIVE` if overwrite): Create file.
  5. `file_edit` (`CONTROLLED`): Replace substring block in existing file.
  6. `file_rename` (`CONTROLLED`): Rename file or directory within workspace.
  7. `file_copy` (`CONTROLLED` / `SENSITIVE` if overwrite): Copy file within workspace.
  8. `file_move` (`CONTROLLED` / `SENSITIVE` if overwrite): Move file within workspace.
  9. `file_delete` (`SENSITIVE`): Delete file or directory (**Always requires approval**).

### 6.2 Milestone 3B: Windows Application Control

* **Service**: `AppService` enforces:
  - Application discovery via Windows Registry (`HKLM` / `HKCU` Uninstall keys) and Start Menu `.lnk` targets.
  - Verification that the target executable exists and is an `.exe`.
  - PID tracking for processes launched by NEXORA.
  - Denylist protection for core Windows system processes (`explorer.exe`, `svchost.exe`, `csrss.exe`, etc.).

* **Tools (`tools/windows/`)**:
  1. `app_list_installed` (`SAFE`): List discovered applications.
  2. `app_find` (`SAFE`): Search application catalog by name or keyword.
  3. `app_launch` (`CONTROLLED`): Launch verified desktop application; records PID.
  4. `app_get_running` (`SAFE`): List active non-system processes (PID, Name, Memory).
  5. `app_get_details` (`SAFE`): Status, CPU/RAM usage, and uptime by PID.
  6. `app_close` (`SENSITIVE`): Gracefully close application (**Requires approval**).

### 6.3 Milestone 3C: Terminal Intelligence

* **Service**: `TerminalService` enforces:
  - Tokenized subprocess execution via `asyncio.create_subprocess_exec` (strictly no `shell=True`).
  - Command allowlist verification: `python`, `pip`, `git`, `node`, `npm`, `pytest`, `systeminfo`, `whoami`, `ipconfig`.
  - Blocking administrative elevation (`runas`).
  - Execution timeout (default 30.0s) and stdout/stderr truncation (50 KB).
  - Secret masking in output logs.

* **Tools (`tools/terminal/`)**:
  1. `terminal_get_system_info` (`SAFE`): Host CPU, RAM, OS version, and uptime.
  2. `terminal_get_directory` (`SAFE`): Current working directory and workspace path.
  3. `terminal_run_allowlisted` (`CONTROLLED`): Execute an allowlisted binary in workspace.
  4. `terminal_run_script` (`CONTROLLED`): Execute a Python script inside the workspace.
  5. `terminal_install_package` (`SENSITIVE`): Install library via `pip` or `npm` (**Requires approval**).

---

## 7. Dynamic Permission Integration

In `PermissionManager.evaluate_permission(step, task)`:
1. Lookup registered tool from `ToolRegistry`.
2. Compute `effective_risk = tool.get_risk_level(step.tool_call.arguments)`.
3. Overwrite `step.risk_level = effective_risk`.
4. If `effective_risk == SENSITIVE`:
   - Computes SHA-256 argument hash and generates `ActionApproval` with 10-minute expiry.
   - Transitions task state to `WAITING_APPROVAL`.
5. If `SAFE` / `CONTROLLED` (with auto-policy): allows execution immediately.

---

## 8. Progressive Milestone Plan

* **Milestone 3A**: Filesystem Intelligence $\rightarrow$ Implement service & 9 tools $\rightarrow$ Pass all 3A tests.
* **Milestone 3B**: Windows Application Control $\rightarrow$ Implement service & 6 tools $\rightarrow$ Pass all 3B tests.
* **Milestone 3C**: Terminal Intelligence $\rightarrow$ Implement service & 5 tools $\rightarrow$ Pass all 3C tests.
* **Milestone 3D**: Integration & Live Verification $\rightarrow$ Autonomous multi-tool workflows $\rightarrow$ Live hardware test.
