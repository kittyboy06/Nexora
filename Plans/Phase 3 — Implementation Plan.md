# NEXORA — Phase 3: Implementation Plan
## Real-World Tool Integration

---

### Progressive Milestone Sequence

- [x] **Milestone 3A: Filesystem Intelligence**
  - Implement `backend/app/core/exceptions.py`: Add `PathTraversalException`, `FileTooLargeException`, `FileAlreadyExistsException`.
  - Update `backend/app/core/config.py`: Add `WORKSPACE_DIR` (default: `data/workspace`) and `MAX_FILE_SIZE_BYTES` (default: 5 MB).
  - Implement `backend/app/services/filesystem_service.py`: Path resolution, workspace jail checking, file size checks, and safe I/O.
  - Upgrade `backend/app/tools/base.py`: Add `get_risk_level(arguments)` method.
  - Implement 9 filesystem tools in `backend/app/tools/filesystem/`:
    - `file_list.py`
    - `file_search.py`
    - `file_read.py`
    - `file_create.py`
    - `file_edit.py`
    - `file_rename.py`
    - `file_copy.py`
    - `file_move.py`
    - `file_delete.py`
  - Register filesystem tools in `ToolRegistry`.
  - Update `PermissionManager` to use `tool.get_risk_level(step.tool_call.arguments)`.
  - Implement unit test suite in `backend/tests/tools/test_filesystem.py`:
    - Test path traversal blocks (`../`, symlinks outside).
    - Test all 9 tools on isolated `tmp_path`.
    - Test overwrite protection and dynamic `SENSITIVE` escalation.
  - **Milestone Gate**: Run tests and verify 100% pass before proceeding to 3B.

- [x] **Milestone 3B: Windows Application Control**
  - Implement `backend/app/services/app_service.py`:
    - Registry scanning (`winreg`) for installed desktop apps.
    - Start Menu shortcut (`.lnk`) enumeration.
    - Process launcher and PID tracking (`_launched_pids`).
    - System process denylist protection.
  - Implement 6 application control tools in `backend/app/tools/windows/`:
    - `app_list_installed.py`
    - `app_find.py`
    - `app_launch.py`
    - `app_get_running.py`
    - `app_get_details.py`
    - `app_close.py`
  - Register application tools in `ToolRegistry`.
  - Implement unit test suite in `backend/tests/tools/test_windows.py`:
    - Test catalog discovery.
    - Test process launch and PID tracking.
    - Test rejection of system process termination (`explorer.exe`, etc.).
  - **Milestone Gate**: Run tests and verify 100% pass before proceeding to 3C.

- [x] **Milestone 3C: Terminal Intelligence**
  - Update `backend/app/core/config.py`: Add `ALLOWED_TERMINAL_COMMANDS`, `TERMINAL_TIMEOUT_SECONDS`, and `MAX_TERMINAL_OUTPUT_BYTES`.
  - Implement `backend/app/services/terminal_service.py`:
    - Subprocess execution via `asyncio.create_subprocess_exec` (strictly no `shell=True`).
    - Command allowlist verification.
    - Output capture (stdout/stderr) and truncation (50 KB).
    - Secret redaction.
  - Implement 5 terminal tools in `backend/app/tools/terminal/`:
    - `terminal_get_system_info.py`
    - `terminal_get_directory.py`
    - `terminal_run_allowlisted.py`
    - `terminal_run_script.py`
    - `terminal_install_package.py`
  - Register terminal tools in `ToolRegistry`.
  - Implement unit test suite in `backend/tests/tools/test_terminal.py`:
    - Test allowlist rejection.
    - Test tokenized execution and timeout abort.
    - Test package install approval requirement.
  - **Milestone Gate**: Run tests and verify 100% pass before proceeding to 3D.

- [x] **Milestone 3D: Autonomous Integration & Live Verification**
  - Implement integration test suite `backend/tests/integration/test_phase3_agent.py`:
    - Autonomous multi-step task: Filesystem creation $\rightarrow$ Terminal validation $\rightarrow$ Results summarization.
    - Approval verification on destructive/sensitive steps.
  - Run complete offline test suite (Phases 1, 2, and 3).
  - Run live hardware verification with `qwen3.5:9b`.
  - Update `backend/README.md`.
