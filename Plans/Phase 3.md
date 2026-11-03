# NEXORA — PHASE 3
## Real-World Tool Integration

### 1. Project Context

NEXORA Phase 1 and Phase 2 have been implemented and verified.

Phase 1 provides:
- FastAPI backend.
- Ollama integration.
- Shared HTTP client.
- Inference concurrency protection.
- Centralized configuration and logging.

Phase 2 provides:
- Hybrid Agent Engine.
- Planning Engine.
- PlanValidator.
- ToolRegistry.
- PermissionManager.
- Executor.
- ResultEvaluator.
- TaskManager.
- Asynchronous task lifecycle.
- JSON task persistence.

The objective of Phase 3 is to replace simulated tool capabilities with carefully controlled real Windows operations.

Do not rewrite the existing Agent Engine.

### 2. Development Strategy

Implement Phase 3 progressively in four milestones:

3A. Filesystem Intelligence.
3B. Windows Application Control.
3C. Terminal Intelligence.
3D. Integration Testing.

Complete and test each milestone before starting the next.

### 3. Milestone 3A — Filesystem Intelligence

Implement real filesystem tools:

- file_list
- file_search
- file_read
- file_create
- file_edit
- file_rename
- file_copy
- file_move
- file_delete

Requirements:

1. Introduce a configurable NEXORA workspace directory.
2. Initially restrict all filesystem tools to this workspace.
3. Validate and resolve all requested paths.
4. Prevent directory traversal and symbolic-link escape.
5. Prevent silent overwrites.
6. Implement configurable file-size limits.
7. Require approval for destructive operations.
8. Log filesystem operations.
9. Provide structured errors.
10. Test every tool independently.

Do not provide unrestricted filesystem access.

### 4. Milestone 3B — Windows Application Control

Implement:

- app_list_installed
- app_find
- app_launch
- app_get_running
- app_get_details
- app_close

Requirements:

1. Use Windows-compatible application discovery.
2. Support common installed desktop applications.
3. Validate application paths before launching.
4. Avoid executing arbitrary commands as a substitute for application discovery.
5. Require permission for launching and closing applications according to configured policy.
6. Do not terminate arbitrary processes.
7. Do not implement mouse or keyboard interaction.
8. Test on Windows 11.

### 5. Milestone 3C — Terminal Intelligence

Implement controlled PowerShell capabilities.

Initial tools:

- terminal_get_system_info
- terminal_get_directory
- terminal_run_allowlisted
- terminal_run_script
- terminal_install_package

Requirements:

1. Use a dedicated execution service.
2. Do not allow direct shell execution by the LLM.
3. Validate commands and arguments in Python.
4. Introduce configurable command allowlists.
5. Require explicit approval for sensitive operations.
6. Never run with administrator privileges by default.
7. Apply execution timeouts.
8. Capture standard output and standard error.
9. Restrict script execution to approved workspace locations.
10. Never expose credentials or secrets in logs.
11. Prevent shell injection.
12. Do not permit unrestricted destructive system commands.

### 6. Permission Integration

All new tools must integrate with the existing PermissionManager.

Use:

SAFE:
Read-only operations within authorized boundaries.

CONTROLLED:
Operations that modify workspace contents or launch applications.

SENSITIVE:
Deletion, package installation, potentially destructive commands and system-level operations.

The actual risk level must be determined by the operation and its arguments, not simply trusted from the LLM-generated plan.

Every operation must pass permission validation immediately before execution.

Approval must remain bound to the exact action and validated arguments.

### 7. Tool Architecture

Every real tool must implement the existing BaseTool contract.

Use Pydantic argument schemas.

Register tools through the existing ToolRegistry.

Do not create a separate execution pathway.

Tool outputs must use structured, predictable response formats.

### 8. Integration Requirements

Reuse:
- Agent Orchestrator.
- Planner.
- PlanValidator.
- Executor.
- PermissionManager.
- ToolRegistry.
- StateManager.
- Existing error handling.
- Logging system.

Do not duplicate functionality already implemented.

### 9. Testing

Each milestone must include:

- Unit tests.
- Permission tests.
- Invalid argument tests.
- Failure handling tests.
- Path and security boundary tests where applicable.
- Integration tests with the existing Agent Engine.

Use isolated temporary directories for filesystem tests.

Mock external dependencies where appropriate.

Do not test destructive operations against real user data.

### 10. Development Boundaries

Do not implement:

- Browser automation.
- Mouse or keyboard control.
- Screenshot capture.
- Visual computer interaction.
- Persistent vector memory.
- Background scheduling.
- Frontend dashboard.

These belong to later phases.

### 11. Deliverables

Before coding, produce:

1. Phase 3 Design Specification.
2. Tool contracts and argument schemas.
3. Permission classification.
4. Security boundaries.
5. Updated project structure.
6. Testing strategy.
7. Milestone-based implementation plan.

Do not begin implementation until the design is reviewed.

After design approval, implement 3A first.

Do not begin 3B until 3A passes its tests.
Do not begin 3C until 3B passes its tests.