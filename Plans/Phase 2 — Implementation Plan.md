# NEXORA — Phase 2: Implementation Plan
## Hybrid Autonomous Agent Engine

---

### Milestone-Based Execution Sequence

- [x] **Milestone 1: Pydantic Domain Models & Tool Registry**
  - Implemented `backend/app/models/agent.py`: `TaskStatus`, `StepStatus`, `RiskLevel`, `RetryClassification`, `ToolCall`, `PlanStep`, `TaskPlan`, `ActionApproval`, `StepResult`, `AgentTask`, and API request/response schemas.
  - Implemented `backend/app/tools/base.py`: Abstract `BaseTool` class with input schema validation and metadata.
  - Implemented `backend/app/tools/registry.py`: Central `ToolRegistry` with registration, lookup, and schema export.
  - Implemented `backend/app/tools/mock_tools/`: `mock_search`, `mock_summarize`, `mock_calculate`, and `mock_file_read`.

- [x] **Milestone 2: StateManager, Transition Map & Atomic Persistence**
  - Implemented `backend/app/agent/state_manager.py`:
    - Enforced explicit 12-state transition map.
    - Implemented atomic snapshot writing (`.tmp` $\rightarrow$ `.json` replace) to `data/tasks/{task_id}.json`.
    - Implemented startup restart recovery sweep marking uncompleted tasks as `INTERRUPTED`.
    - Implemented approval expiration evaluation.

- [x] **Milestone 3: Planner & PlanValidator**
  - Implemented `backend/app/agent/plan_validator.py`:
    - Validated required fields, unique step IDs (1–10), and registered tool names.
    - Validated tool arguments against Pydantic schemas.
    - Enforced acyclic dependencies (DFS cycle detection).
  - Implemented `backend/app/agent/planner.py`:
    - Built system prompt with tool registry definitions.
    - Queried `OllamaService` using `format: "json"` under Phase 1 `InferenceGuard`.
    - Implemented 1 self-correction retry injecting validation errors into prompt on failure.

- [x] **Milestone 4: PermissionManager & Executor**
  - Implemented `backend/app/permissions/manager.py`:
    - Classified tool risk tiers (`SAFE`, `CONTROLLED`, `SENSITIVE`).
    - Generated action-scoped `ActionApproval` with canonical SHA-256 argument hash and 10-minute expiry.
    - Verified approval decisions and detected argument tampering.
  - Implemented `backend/app/agent/executor.py`:
    - Ran step execution loop in dependency order.
    - Enforced pre-execution authorization check on every attempt.
    - Implemented tri-state retry handling (`TRANSIENT` $\le 2$, `PERMANENT`, `UNCERTAIN`).

- [x] **Milestone 5: ResultEvaluator, Orchestrator, TaskManager & API Wiring**
  - Implemented `backend/app/agent/result_evaluator.py`: Analyzed execution traces and prompted LLM for alternative steps on failure.
  - Implemented `backend/app/agent/orchestrator.py`: Coordinated full pipeline from request understanding to completion.
  - Implemented `backend/app/agent/task_manager.py`: Enforced max 1 active task via `asyncio.Lock` and delegated to FastAPI `BackgroundTasks`.
  - Implemented `backend/app/api/routes/agent.py`:
    - `POST /api/agent/tasks`: Create and start task.
    - `GET /api/agent/tasks`: List all tasks.
    - `GET /api/agent/tasks/{id}`: Inspect task status and trace.
    - `POST /api/agent/tasks/{id}/approve`: Submit human-in-the-loop approval decision.
    - `POST /api/agent/tasks/{id}/cancel`: Cancel active task.
  - Mounted router in `backend/app/main.py` and registered startup recovery in `lifespan`.

- [x] **Milestone 6: Comprehensive Test Suite & Live Verification**
  - Implemented unit test suites in `backend/tests/agent/`:
    - `test_models.py`
    - `test_tools.py`
    - `test_state_manager.py`
    - `test_plan_validator.py`
    - `test_permissions.py`
    - `test_executor.py`
    - `test_task_manager.py`
    - `test_api_agent.py`
  - Ran offline test suite: **43/43 tests passed in 1.90s**.
  - Ran live hardware verification with `qwen3.5:9b`: 2-step task planned, validated, executed, and completed with full execution trace.
  - Updated `backend/README.md`.
