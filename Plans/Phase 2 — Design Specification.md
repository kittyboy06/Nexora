# NEXORA — Phase 2: Hybrid Autonomous Agent Engine
## Technical Design Specification — Version 1.0

---

## 1. Executive Summary

This document specifies the architectural and technical design for **Phase 2: Hybrid Autonomous Agent Engine** of the NEXORA local autonomous AI agent.

The core architectural paradigm is the **Hybrid Planning Architecture**:
* **Local LLM (`qwen3.5:9b` via Ollama)** is responsible strictly for cognitive tasks: goal understanding, generating structured task plans, selecting tools, evaluating execution logs, and formulating recovery suggestions.
* **Deterministic Python Engine** is the sole execution authority: validating plans, enforcing hard limits, evaluating permissions, managing state transitions, executing registered tools, managing retries, and recording atomic snapshots.

> **Non-Negotiable Rule**: NEXORA must never let Qwen directly execute actions or bypass the Python execution layer. **Qwen proposes; Python validates, authorizes, and executes.**

---

## 2. Understanding Summary & Hard Constraints

* **Planning Architecture**: Hybrid LLM reasoning + deterministic Python enforcement.
* **Task Lifecycle**: Asynchronous state machine managed by a dedicated `TaskManager` and `StateManager`.
* **State Machine States**: `SUBMITTED`, `PARSING`, `PLANNING`, `EXECUTING`, `WAITING_APPROVAL`, `APPROVED`, `REJECTED`, `EXPIRED`, `COMPLETED`, `FAILED`, `CANCELLED`, `INTERRUPTED`.
* **State Authority**: `StateManager` is the single authority for task state transitions, validated against an explicit transition map.
* **Plan Generation**: Ollama native `format: "json"` + 1 self-correction retry with Python validation feedback on syntax or schema errors.
* **Plan Validation**: `PlanValidator` enforces required fields, unique step IDs (1–10), registered tools, Pydantic argument schemas, acyclic dependencies, and execution limits.
* **Tool Strategy**: Central `ToolRegistry` hosting mock tools only (`mock_search`, `mock_summarize`, `mock_calculate`, `mock_file_read`). Zero real filesystem or network modifications.
* **Permission Tiers**: `SAFE` (auto-execute), `CONTROLLED` (policy-checked), `SENSITIVE` (always requires explicit human approval).
* **Action-Scoped Approvals**: Bound to `(task_id, step_id, approval_id, tool_name, argument_hash, expires_at)`. Modifying any argument invalidates previous approvals. Default 10-minute expiry.
* **Retry Protocol**: Tri-state classification distinguishing `TRANSIENT` (retried up to 2 times), `PERMANENT` (fails immediately to LLM recovery), and `UNCERTAIN` (never blindly retried).
* **Persistence & Recovery**: In-memory active state with atomic JSON snapshots to `data/tasks/{task_id}.json`. On startup, any uncompleted tasks from prior runs are marked `INTERRUPTED`.
* **Hardware & Concurrency**: Maximum 1 active task (via `asyncio.Lock` in `TaskManager`) and maximum 1 concurrent LLM generation (reusing Phase 1 `InferenceGuard`).
* **Explicit Non-Goals (Scope Restrictions)**:
  * No frontend interface.
  * No real desktop automation (mouse, keyboard, screenshot capture).
  * No browser automation (Playwright).
  * No unrestricted terminal or shell execution.
  * No persistent vector/SQL database memory.
  * No background cron schedulers.

---

## 3. Assumptions

1. **Phase 1 Integration**: Extends the existing FastAPI application, reusing the shared `httpx.AsyncClient`, `OllamaService`, `InferenceGuard`, logging, and unified `ErrorResponse` contracts without rewriting them.
2. **Environment**: Windows 11 on AMD Ryzen 7 5700X, 16 GB RAM, NVIDIA RTX 5050 (8 GB VRAM).
3. **Execution Safety**: Mock tools execute deterministically with simulated latency (50ms) and return structured simulated responses.
4. **Testing Offline**: 100% of unit tests pass offline using mock LLM responses and mock tools without requiring GPU inference.

---

## 4. Decision Log

| # | Topic | Decision | Alternatives Considered | Rationale |
|---|---|---|---|---|
| **D11** | Hybrid Architecture Boundary | Strict Hybrid division: LLM proposes plans and evaluates failures; Python validates, authorizes, limits, and executes | End-to-end LLM tool execution; ReAct prompt loop with autonomous shell | Eliminates prompt injection/hallucinated execution risks; Python retains 100% control over execution. |
| **D12** | Task Lifecycle Execution | Asynchronous state machine via FastAPI `BackgroundTasks` and dedicated `TaskManager` | Synchronous HTTP blocking; Full Celery/Redis queue | Fits single-process local prototype without heavy external infrastructure dependencies. |
| **D13** | Task State Machine States | `SUBMITTED`, `PARSING`, `PLANNING`, `EXECUTING`, `WAITING_APPROVAL`, `APPROVED`, `REJECTED`, `EXPIRED`, `COMPLETED`, `FAILED`, `CANCELLED`, `INTERRUPTED` | Simplified 4-state model | Explicitly captures human-in-the-loop pauses, timeouts, and ungraceful process restarts. |
| **D14** | Task State Persistence | In-memory active state + atomic JSON snapshots to `data/tasks/{task_id}.json` | Pure in-memory (ephemeral); SQLite database | Combines in-memory execution speed with crash recovery without introducing database dependencies in Phase 2. |
| **D15** | Restart Recovery | On application startup, scan `data/tasks/` and mark any active/incomplete tasks as `INTERRUPTED` | Auto-resume uncompleted tasks; Delete interrupted tasks | Prevents dangerous repeated execution of uncertain actions without human review after a crash or restart. |
| **D16** | Human-in-the-Loop Approval | Action-scoped `approval_id` tied to `(task_id, step_id, approval_id, tool_name, argument_hash, expires_at)` with 10-minute expiry | Task-level blanket approval; Unbounded approval timeouts | Prevents reuse of approvals across different actions or after plans change. |
| **D17** | Concurrency Enforcement | 1 active task max (`asyncio.Lock` in `TaskManager`) + reuse Phase 1 `InferenceGuard` for LLM calls | Multiple concurrent tasks; Separate independent semaphores | Protects system memory and the 8 GB RTX 5050 from competing tasks and multi-request VRAM thrashing. |
| **D18** | Tooling Scope | Registry with mock tools only (`mock_search`, `mock_summarize`, `mock_calculate`, `mock_file_read`) | Real OS/CLI tools; Live web requests | Verifies agent loop, validation, and permissions safely without modifying user data. |
| **D19** | State Authority | `StateManager` is the sole authority for task state transitions, validated against a strict state machine map | Decentralized state mutations across executor/orchestrator | Guarantees deterministic state changes and prevents race conditions or illegal state jumps. |
| **D20** | Approval Binding | Approvals are strictly action-scoped, bound to `(task_id, step_id, approval_id, tool_name, argument_hash, expires_at)` | Task-level approval; Unhashed argument approval | Any plan or argument tampering immediately invalidates the approval token. |
| **D21** | Atomic Persistence | Task snapshots written atomically via temporary file rename (`.tmp` $\rightarrow$ `.json`); separate execution logs | In-place file overwrite; Ephemeral memory only | Prevents corrupted or partially written JSON snapshots during abrupt process termination. |
| **D22** | Restart Integrity | Startup sweep scans `data/tasks/` and transitions any unfinalized tasks to `INTERRUPTED` | Auto-resume uncompleted tasks; Delete interrupted tasks | Avoids blindly repeating uncertain actions without human review after a crash or restart. |
| **D23** | Tri-State Retry Protocol | Tool failures categorized as `TRANSIENT` (retry $\le 2$), `PERMANENT` (abort to LLM), or `UNCERTAIN` (never retry, prompt user) | Uniform retry for all errors; No retries | Prevents duplicate side effects for non-idempotent or ambiguous operations. |
| **D24** | Hardware Concurrency | Max 1 active task via `asyncio.Lock` in `TaskManager`, reusing Phase 1 `InferenceGuard` for LLM calls | Multiple concurrent tasks; Independent semaphores | Enforces strict hardware limits for system RAM and the 8 GB RTX 5050. |

---

## 5. Architectural Structure & Component Responsibilities

```text
backend/app/
├── core/
│   ├── config.py            # Centralized settings (execution limits, timeouts)
│   ├── exceptions.py        # Domain exceptions
│   ├── guard.py             # Phase 1: InferenceGuard (reused)
│   └── logging.py           # Structured dual-sink logging
├── models/
│   ├── common.py            # ErrorResponse, ErrorDetail
│   ├── health.py            # HealthCheckResponse
│   ├── ollama.py            # OllamaStatusResponse
│   ├── chat.py              # ChatRequest, ChatResponse
│   └── agent.py             # AgentTask, TaskPlan, PlanStep, ToolCall, StepResult, ActionApproval
├── tools/
│   ├── base.py              # BaseTool abstract class with Pydantic schema validation
│   ├── registry.py          # Central ToolRegistry singleton
│   └── mock_tools/          # mock_search, mock_summarize, mock_calculate, mock_file_read
├── permissions/
│   └── manager.py           # Evaluates SAFE/CONTROLLED/SENSITIVE, issues & verifies ActionApprovals
├── agent/
│   ├── task_manager.py      # Concurrency lock (1 active task), background task delegation
│   ├── state_manager.py     # Single authority for state machine transitions & atomic JSON persistence
│   ├── planner.py           # Formulates prompt, calls Ollama (format: "json"), handles 1 retry
│   ├── plan_validator.py    # Enforces limits, tool registration, schemas, and acyclic DAG
│   ├── executor.py          # Executes steps, enforces pre-execution permission gate, classifies retries
│   ├── result_evaluator.py  # Evaluates failure logs; queries LLM for alternative steps or abort
│   └── orchestrator.py      # High-level pipeline coordinator
└── api/routes/
    ├── health.py            # Phase 1: GET /api/health
    ├── ollama.py            # Phase 1: GET /api/ollama/*
    ├── chat.py              # Phase 1: POST /api/chat
    └── agent.py             # Phase 2: POST /api/agent/tasks, GET /api/agent/tasks/{id}, POST /api/agent/tasks/{id}/approve
```

---

## 6. State Machine & Transition Matrix

`StateManager` strictly enforces this state transition map. Any transition not declared below raises `InvalidStateTransitionException`:

```
SUBMITTED ────────► PARSING ────────► PLANNING ────────► EXECUTING ────────► COMPLETED
   │                   │                 │                   │
   ├───────────────────┴─────────────────┴───────────────────┼─────────────► FAILED
   │                                                         │
   │                                                         ▼
   │                                                 WAITING_APPROVAL
   │                                                         │
   │                                            ┌────────────┼────────────┐
   │                                            ▼            ▼            ▼
   │                                         APPROVED     REJECTED     EXPIRED
   │                                            │            │            │
   │                                            ▼            ▼            ▼
   │                                        EXECUTING      FAILED       FAILED
   │
   ├─ (Explicit Cancel) ───────────────────────────────────────────────────► CANCELLED
   │
   └─ (Startup Sweep) ──[Any uncompleted task on restart]─────────────────► INTERRUPTED
```

| Source State | Target State | Trigger / Guard Condition |
|---|---|---|
| `SUBMITTED` | `PARSING` | `TaskManager` enqueues and starts processing the task |
| `SUBMITTED` | `CANCELLED` | User requests cancellation |
| `PARSING` | `PLANNING` | User objective successfully validated and structured |
| `PARSING` | `FAILED` | Intent is malformed or violates system constraints |
| `PARSING` | `CANCELLED` | User requests cancellation |
| `PLANNING` | `EXECUTING` | `PlanValidator` confirms valid, authorized `TaskPlan` |
| `PLANNING` | `FAILED` | Model produces invalid plan after 2 attempts |
| `PLANNING` | `CANCELLED` | User requests cancellation |
| `EXECUTING` | `WAITING_APPROVAL` | Step requires `SENSITIVE` or policy-blocked `CONTROLLED` permission |
| `EXECUTING` | `COMPLETED` | All plan steps executed successfully |
| `EXECUTING` | `FAILED` | Unrecoverable error, timeout exceeded, or iteration limit reached |
| `EXECUTING` | `CANCELLED` | User requests cancellation |
| `WAITING_APPROVAL` | `APPROVED` | Valid user approval token submitted within 10-minute window |
| `WAITING_APPROVAL` | `REJECTED` | User explicitly denies execution |
| `WAITING_APPROVAL` | `EXPIRED` | 10-minute approval window expires without decision |
| `WAITING_APPROVAL` | `CANCELLED` | User requests cancellation |
| `APPROVED` | `EXECUTING` | `Executor` resumes step execution |
| `APPROVED` | `CANCELLED` | User requests cancellation |
| `REJECTED` | `FAILED` | Step cannot proceed without authorization |
| `EXPIRED` | `FAILED` | Step execution aborted due to expired approval |
| *Active State* | `INTERRUPTED` | Detected during FastAPI startup recovery sweep |

---

## 7. Action-Scoped Approval Lifecycle

Approvals are strictly bound to the exact tool call and its arguments:

1. **Generation**: When `Executor` hits a `SENSITIVE` tool:
   - `PermissionManager.create_approval(...)` generates an `approval_id`.
   - Computes canonical SHA-256 `argument_hash`:
     ```python
     canonical_json = json.dumps(step.tool_call.arguments, sort_keys=True)
     argument_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
     ```
   - Sets `expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)`.
   - `StateManager` updates task to `WAITING_APPROVAL` with `pending_approval`.
2. **Decision & Invalidation**:
   - On `POST /api/agent/tasks/{id}/approve`:
     - If `now() > expires_at`: Mark approval `EXPIRED` $\rightarrow$ task transitions to `FAILED`.
     - Recompute current step argument hash. If it does not match `argument_hash` (e.g. plan changed), reject decision with HTTP 409 `APPROVAL_INVALIDATED`.
     - If rejected: Transition task to `REJECTED` $\rightarrow$ `FAILED`.
     - If approved: Transition task to `APPROVED` $\rightarrow$ `EXECUTING`.

---

## 8. Tri-State Retry Protocol

Tool execution outcomes are classified into three distinct categories:

1. **`TRANSIENT`** (Simulated network timeout, temporary mock resource lock):
   - Python retries the step automatically up to `max_retries_per_step` (2).
   - Increments `retries_attempted`.
2. **`PERMANENT`** (Invalid argument schema, missing mock key, unsupported operation):
   - Never retried blindly.
   - Escalates immediately to `ResultEvaluator`:
     - If iterations remain ($\le 15$), prompts LLM for a revised step or recovery plan.
     - If recovery impossible or iterations exhausted, fails the task.
3. **`UNCERTAIN`** (Connection dropped mid-execution, unverified partial state):
   - **Never automatically retried.**
   - Halts step execution immediately with `UNCERTAIN` outcome to prevent dangerous duplicate side effects.

---

## 9. Atomic Persistence & Restart Recovery

### 9.1 Atomic Persistence
`StateManager` ensures zero data corruption on abrupt shutdown:
```python
task_file = data_dir / f"{task.task_id}.json"
tmp_file = data_dir / f"{task.task_id}.json.tmp"

tmp_file.write_text(task.model_dump_json(indent=2), encoding="utf-8")
tmp_file.replace(task_file)  # Atomic rename on Windows NT and POSIX
```

### 9.2 Restart Recovery Sweep
During application startup in `lifespan`:
1. `StateManager.recover_on_startup()` inspects all JSON files in `data/tasks/`.
2. Any task found with an active status (`SUBMITTED`, `PARSING`, `PLANNING`, `EXECUTING`, `WAITING_APPROVAL`, `APPROVED`) is transitioned to `INTERRUPTED`.
3. Records: *"Task interrupted by application restart. Uncertain operations not resumed."*
4. Writes atomic snapshot to disk.

---

## 10. Execution Limits Specification

| Parameter | Default | Enforced By | Description |
|---|---|---|---|
| `MAX_PLAN_STEPS` | `10` | `PlanValidator` | Maximum steps permitted in a single plan |
| `MAX_EXECUTION_ITERATIONS` | `15` | `Orchestrator` | Maximum total tool execution attempts per task |
| `MAX_RETRIES_PER_STEP` | `2` | `Executor` | Maximum retries for `TRANSIENT` errors |
| `MAX_CONCURRENT_TASKS` | `1` | `TaskManager` | Maximum simultaneous active agent tasks |
| `MAX_CONCURRENT_LLM` | `1` | `InferenceGuard` | Maximum concurrent LLM generation calls |
| `MAX_PLANNING_ATTEMPTS` | `2` | `Planner` | Maximum planning retries on validation failure |
| `MAX_EXECUTION_DURATION_SECONDS` | `300.0` | `Orchestrator` | Overall task execution timeout threshold |
| `APPROVAL_EXPIRATION_SECONDS` | `600.0` | `PermissionManager` | Approval window (10 minutes) |

---

## 11. Initial Mock Tools Catalog

All tools inherit from `BaseTool` and validate inputs via Pydantic:

1. **`mock_search`** (`RiskLevel.SAFE`):
   - Args: `query: str`, `max_results: int = 3`
   - Returns simulated web search snippets.
2. **`mock_summarize`** (`RiskLevel.SAFE`):
   - Args: `text: str`, `max_words: int = 50`
   - Returns a structured extractive/mock summary.
3. **`mock_calculate`** (`RiskLevel.SAFE`):
   - Args: `expression: str`
   - Evaluates safe mathematical expressions deterministically.
4. **`mock_file_read`** (`RiskLevel.CONTROLLED` / `SENSITIVE`):
   - Args: `filepath: str`
   - Returns simulated file contents without reading host filesystem.

---

## 12. Testing & Verification Strategy

All unit tests execute offline without requiring GPU or active Ollama:
* **`test_plan_validator.py`**: Validates schema compliance, step limits, unknown tools, argument errors, and cyclic dependencies.
* **`test_state_manager.py`**: Verifies valid vs invalid transitions, atomic file persistence, and startup recovery sweep (`INTERRUPTED`).
* **`test_permissions.py`**: Tests risk tier routing, action-scoped approvals, argument modification invalidation, and 10-minute expiry (`EXPIRED` $\rightarrow$ `FAILED`).
* **`test_executor.py`**: Verifies `TRANSIENT` retry recovery, `PERMANENT` escalation, and `UNCERTAIN` abortion.
* **`test_task_manager.py`**: Verifies max 1 active task (returns 503 `TASK_RUNNER_BUSY` when saturated) and `InferenceGuard` reuse.
* **`test_orchestrator.py`**: End-to-end multi-step task execution, approval pauses, and error recovery.
