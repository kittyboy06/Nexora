# NEXORA — Hybrid Autonomous Agent Backend

NEXORA is a local-first autonomous AI computer agent engineered for Windows 11.

It combines **FastAPI**, **Pydantic v2**, and locally hosted **Ollama (`qwen3.5:9b`)** using a **Hybrid Planning Architecture**:
* **Local LLM (`qwen3.5:9b`)**: Cognitive reasoning, structured JSON task planning, tool selection, failure log evaluation.
* **Deterministic Python Engine**: Strict plan validation, execution limit enforcement, permission authorization, tri-state retries, state machine management, and atomic persistence.

> **Execution Rule**: NEXORA never allows the LLM to execute code or tools directly. **Qwen proposes; Python validates, authorizes, and executes.**

---

## 1. System Requirements

* **Operating System**: Windows 11
* **Python**: 3.10+ (tested on Python 3.13)
* **Local LLM Runtime**: [Ollama](https://ollama.ai) with `qwen3.5:9b` installed and running

---

## 2. Environment Setup (PowerShell)

### 2.1 Virtual Environment
From the workspace root (`NEXORA/`):

```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1
```

### 2.2 Install Dependencies
```powershell
pip install -r backend/requirements.txt
```

### 2.3 Configuration
Copy the configuration template:
```powershell
Copy-Item backend\.env.example backend\.env
```

Key configuration parameters (`backend/.env`):

| Variable | Default | Description |
|---|---|---|
| `HOST` | `127.0.0.1` | Bind address |
| `PORT` | `8000` | Port for the FastAPI server |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL of local Ollama daemon |
| `OLLAMA_MODEL` | `qwen3.5:9b` | Default reasoning model |
| `INFERENCE_CONCURRENCY_LIMIT` | `1` | Max concurrent model generations (GPU guard) |
| `INFERENCE_SEMAPHORE_TIMEOUT_SECONDS` | `5.0` | Max wait time before returning HTTP 503 `INFERENCE_BUSY` |
| `MAX_PLAN_STEPS` | `10` | Maximum steps permitted in a generated plan |
| `MAX_EXECUTION_ITERATIONS` | `15` | Maximum tool execution iterations per task |
| `MAX_RETRIES_PER_STEP` | `2` | Maximum transient retries per step |
| `APPROVAL_EXPIRATION_SECONDS` | `600.0` | Human approval window (10 minutes) |
| `AUTO_APPROVE_CONTROLLED` | `True` | Automatically permit CONTROLLED actions in sandbox |
| `WORKSPACE_DIR` | `data/workspace` | Designated sandboxed workspace directory |
| `MAX_FILE_SIZE_BYTES` | `5000000` | Maximum file read/write threshold (5 MB) |
| `ALLOWED_TERMINAL_COMMANDS` | `["python", ...]` | Allowlisted terminal command binaries |
| `TERMINAL_TIMEOUT_SECONDS` | `30.0` | Subprocess execution timeout |
| `MAX_TERMINAL_OUTPUT_BYTES` | `51200` | Output capture limit before truncation (50 KB) |
| `TASK_DATA_DIR` | `data/tasks` | Atomic task snapshot directory |

---

## 3. Running the Backend Server

Start the Uvicorn server:

```powershell
$env:PYTHONPATH="."
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Interactive OpenAPI Swagger documentation:  
👉 `http://127.0.0.1:8000/docs`

---

## 4. Running the Automated Test Suite

All tests execute completely offline without requiring Ollama or a GPU:

```powershell
$env:PYTHONPATH="."
python -m pytest backend/tests -v
```

---

## 5. API Endpoints

### 5.1 Diagnostics & Chat
* **`GET /api/health`**: Fast health check (independent of Ollama status).
* **`GET /api/ollama/status`**: Detailed reachability and model availability.
* **`GET /api/ollama/models`**: List installed local models.
* **`POST /api/chat`**: Stateless conversational completion.

### 5.2 Autonomous Agent Engine (Phase 2)
* **`POST /api/agent/tasks`**:
  Submit an autonomous user goal. Enforces maximum 1 active task limit.
  ```json
  { "prompt": "Calculate 25 * 4, then summarize the outcome." }
  ```
  Returns `201 Created` with task details and background execution ID.

* **`GET /api/agent/tasks`**:
  List all historical and active agent tasks.

* **`GET /api/agent/tasks/{task_id}`**:
  Inspect full task status, generated plan steps, and real-time execution trace.

* **`POST /api/agent/tasks/{task_id}/approve`**:
  Submit a human-in-the-loop authorization decision for steps in `WAITING_APPROVAL` status:
  ```json
  {
    "approval_id": "appr_a1b2c3d4",
    "approved": true
  }
  ```

* **`POST /api/agent/tasks/{task_id}/cancel`**:
  Cancel an active or paused task.

### 5.3 Real-World Tool Suite (Phase 3)

#### Filesystem Tools (`data/workspace/` Sandbox Jail)
* **`file_list`** (`SAFE`): List folder contents with size, type, and modification dates.
* **`file_search`** (`SAFE`): Recursive glob search within workspace.
* **`file_read`** (`SAFE`): Read text content with byte limits.
* **`file_create`** (`CONTROLLED` / `SENSITIVE` if overwrite): Create files with overwrite protection.
* **`file_edit`** (`CONTROLLED`): Target/replacement text substitution.
* **`file_rename`** (`CONTROLLED`): Safe file/directory renaming within workspace.
* **`file_copy`** (`CONTROLLED` / `SENSITIVE` if overwrite): File copy with overwrite protection.
* **`file_move`** (`CONTROLLED` / `SENSITIVE` if overwrite): File move with overwrite protection.
* **`file_delete`** (`SENSITIVE`): Delete files or directories (**Always requires human approval**).

#### Windows Application Control Tools
* **`app_list_installed`** (`SAFE`): Enumerate desktop applications via Registry and Start Menu.
* **`app_find`** (`SAFE`): Search applications by name, alias, publisher, or PATH binary.
* **`app_launch`** (`CONTROLLED`): Launch validated desktop `.exe` in detached mode with PID tracking.
* **`app_get_running`** (`SAFE`): List active processes with CPU, memory, and status.
* **`app_get_details`** (`SAFE`): Detailed runtime telemetry for a specific PID.
* **`app_close`** (`SENSITIVE`): Close a process (**Requires human approval; system processes strictly protected**).

#### Terminal Intelligence Tools
* **`terminal_get_system_info`** (`SAFE`): Host CPU, RAM, OS version, and uptime telemetry.
* **`terminal_get_directory`** (`SAFE`): Host CWD and designated workspace path.
* **`terminal_run_allowlisted`** (`CONTROLLED`): Execute allowlisted command (`python`, `pip`, `git`, `node`, `npm`, `pytest`, `systeminfo`, `whoami`, `ipconfig`).
* **`terminal_run_script`** (`CONTROLLED`): Run sandboxed Python script inside workspace.
* **`terminal_install_package`** (`SENSITIVE`): Install package via `pip` or `npm` (**Requires human approval**).

---

## 6. Architecture & Security Controls

* **State Machine**: 12 deterministic states (`SUBMITTED`, `PARSING`, `PLANNING`, `EXECUTING`, `WAITING_APPROVAL`, `APPROVED`, `REJECTED`, `EXPIRED`, `COMPLETED`, `FAILED`, `CANCELLED`, `INTERRUPTED`).
* **Action-Scoped Approvals**: Bound to `(task_id, step_id, tool_name, argument_hash, expires_at)` with 10-minute expiry. Tampering with plan arguments invalidates the token.
* **Tri-State Retry Protocol**:
  * `TRANSIENT`: Retries automatically up to 2 times with backoff.
  * `PERMANENT`: Aborts to LLM `ResultEvaluator` for re-planning or fails.
  * `UNCERTAIN`: **Never blindly retried** to avoid duplicate side effects.
* **Atomic Persistence & Restart Recovery**:
  * Snapshots written atomically (`.tmp` $\rightarrow$ `.json` rename).
  * On application boot, any previously active tasks are transitioned to `INTERRUPTED`.
* **Hardware Guards**:
  * Single active task lock (`TaskManager`).
  * Single LLM generation semaphore (`InferenceGuard`).
