# NEXORA — Phase 4 Design Specification
## Agent Fleet Foundation: Model Profiles and Hybrid Routing

**Document Type:** Technical Design Specification  
**Project:** NEXORA — Local Autonomous Intelligence  
**Phase:** 4 — Agent Fleet Foundation  
**Status:** Validated Design (Ready for Implementation Planning)  
**Date:** 6 November 2026  

---

## 1. Understanding Summary

* **What is being built:** Complete technical hardening, diagnostics integration, and verification for Phase 4 (Model Registry and Hybrid Routing). This attaches model routing decisions (`RouteSelection`) directly to `AgentTask`, introduces dynamic on-demand profile catalogue reloading, gracefully handles offline Ollama and missing models during planning, extends automated unit and integration test coverage, and documents profile management.
* **Why it exists:** NEXORA requires deterministic, transparent routing from user prompts to specialized local model profiles (coding, research, reasoning, general) with confident classification, model escalation, and heuristic fallback. Exposing this information on the task record is critical for user trust, auditability, and the upcoming Phase 5 native Windows dashboard.
* **Who it is for:** The NEXORA agent runtime, the future WinUI 3 desktop shell, and system administrators configuring local models.
* **Key constraints:**
  * Strict backward compatibility with existing task JSON snapshots in `data/tasks/`.
  * Zero regression against the existing Phase 0–3 test suite (all 76 tests must continue to pass).
  * Strict single-inference concurrency enforcement via `InferenceGuard`.
  * Central governance boundary: routing only selects planner profiles and models; it does not grant permissions or bypass executor safety controls.
* **Explicit non-goals:**
  * Multi-agent DAG parallel orchestration (Phase 6).
  * WinUI 3 desktop shell implementation (Phase 5).
  * Cloud/remote LLM provider integrations (NEXORA remains strictly local-first).

---

## 2. Assumptions & Risks

### Assumptions
1. **Model Defaults:** `data/model_profiles.json` defaults all profiles to `qwen3.5:9b` to work out-of-the-box on the baseline single-model configuration. Users can configure a smaller router model (e.g. `qwen2.5:1.5b` or `phi3:mini`) as `MODEL_ROUTER_MODEL`.
2. **Missing Router Model:** If `MODEL_ROUTER_MODEL` is absent from Ollama inventory, the router automatically attempts routing via `OLLAMA_MODEL` before falling back to keyword heuristics.
3. **Persistence:** Existing and future task records are persisted atomically as JSON in `data/tasks/<task_id>.json`. Older tasks without a `routing` key deserialize cleanly with `routing=None`.
4. **Single Inference:** All router classification calls and planner generation calls acquire the shared `InferenceGuard` semaphore.

### Key Risks & Mitigations
* **Risk: Task hangs if Ollama drops offline during planning.**
  * *Mitigation:* `AgentOrchestrator` catches connection exceptions during routing/planning and transitions the task to `TaskStatus.FAILED` with a clear message (`"Ollama is offline or unreachable"`), persisting the failed task state.
* **Risk: File drift if `data/model_profiles.json` is edited while backend is running.**
  * *Mitigation:* `ModelProfileRegistry.reload()` provides atomic in-memory catalogue refresh, triggered on-demand via `GET /api/ollama/profiles` or `POST /api/ollama/profiles/reload`.

---

## 3. Decision Log

| # | Decision | Alternatives Considered | Reason for Choice |
|---|---|---|---|
| 1 | Full Phase 4 completion scope | Minimal diagnostics only; live hardware testing only | Delivers a hardened, verifiable foundation before beginning Phase 5 native shell work. |
| 2 | Add optional `routing: RouteSelection \| None = None` to `AgentTask` | Embed in `TaskPlan`; write synthetic trace entry; generic metadata dict | Clean separation of concerns, 100% backward-compatible, captures routing even if plan generation fails. |
| 3 | Dynamic on-demand reload for `data/model_profiles.json` | Restart server only; file-system watcher daemon | Provides instantaneous updates without server downtime or file-watcher complexity. |
| 4 | Decompose planning into `route_task()` followed by `generate_plan_for_route()` | Return tuple `(TaskPlan, RouteSelection)` from monolithic method | Durably persists routing diagnostics in `AgentTask` immediately upon classification, before attempting plan LLM generation. |
| 5 | Expose reload trigger on `GET /api/ollama/profiles` and `POST /api/ollama/profiles/reload` | Query parameter only; backend restart only | Ergonomic for both automated UI refreshing and manual developer reloading. |
| 6 | Centralize task-level Ollama failure transitions in `AgentOrchestrator` | Let unhandled exceptions bubble to background worker | Guarantees tasks never stall in `PLANNING` or `PARSING` state if Ollama crashes or stops. |
| 7 | Create dedicated integration test suite `test_phase4_routing.py` | Unit tests only; live tests only | Validates full end-to-end task state machine, persistence, and error handling deterministically. |

---

## 4. Architectural Design & Component Details

### 4.1 Schema Enhancements (`backend/app/models/agent.py`)

Add the optional `routing` field to `AgentTask`:

```python
class AgentTask(BaseModel):
    task_id: str = Field(..., description="Unique task identifier")
    prompt: str = Field(..., description="Original user prompt or instruction")
    model_profile_id: str | None = Field(default=None, description="Optional specialist profile override")
    status: TaskStatus = Field(default=TaskStatus.SUBMITTED, description="Current task lifecycle status")
    routing: RouteSelection | None = Field(
        default=None,
        description="Hybrid routing decision, profile, model, and escalation metadata"
    )
    plan: TaskPlan | None = Field(default=None, description="Validated task plan")
    execution_trace: list[StepResult] = Field(default_factory=list, description="Ordered step execution results")
    pending_approval: ActionApproval | None = Field(default=None, description="Pending approval token if paused")
    iterations_used: int = Field(default=0, le=15, description="Count of tool executions attempted")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = Field(default=None, description="Completion timestamp")
    error_message: str | None = Field(default=None, description="Detailed explanation if task failed")
```

### 4.2 State Manager Extension (`backend/app/agent/state_manager.py`)

Add atomic routing recording:

```python
async def record_routing(self, task_id: str, routing: RouteSelection) -> AgentTask:
    task = await self.get_task(task_id)
    task.routing = routing
    task.updated_at = datetime.now(timezone.utc)
    self._save_task(task)
    return task
```

### 4.3 Planner Refactoring (`backend/app/agent/planner.py`)

Decompose the planning workflow:
1. `async def route_task(self, prompt: str, profile_override: str | None = None) -> RouteSelection`:  
   Calls `self.model_router.route(prompt, profile_override=profile_override)`.
2. `async def generate_plan_for_route(self, prompt: str, selection: RouteSelection) -> TaskPlan`:  
   Retrieves profile instructions, formats prompt, acquires `InferenceGuard`, requests structured plan from `selection.model`, and validates with `PlanValidator`.
3. `async def generate_plan(self, prompt: str, profile_override: str | None = None) -> TaskPlan`:  
   Backward-compatible helper that executes `route_task` followed by `generate_plan_for_route`.

### 4.4 Orchestrator Execution Flow (`backend/app/agent/orchestrator.py`)

```python
# 1. Parsing & Planning
if task.status == TaskStatus.SUBMITTED:
    try:
        await self.state_manager.transition_state(task_id, TaskStatus.PARSING)
        await asyncio.sleep(0.01)

        await self.state_manager.transition_state(task_id, TaskStatus.PLANNING)
        
        # Route first and record diagnostics immediately
        selection = await self.planner.route_task(task.prompt, profile_override=task.model_profile_id)
        task = await self.state_manager.record_routing(task_id, selection)
        
        # Generate plan for the routed profile
        plan = await self.planner.generate_plan_for_route(task.prompt, selection)
        task = await self.state_manager.update_plan(task_id, plan)
        task = await self.state_manager.transition_state(task_id, TaskStatus.EXECUTING)
    except Exception as exc:
        logger.error("Planning failed for task %s: %s", task_id, exc)
        await self.state_manager.transition_state(task_id, TaskStatus.FAILED, error_message=str(exc))
        return
```

### 4.5 Model Profile Registry Reloading (`backend/app/services/model_registry.py`)

Add atomic reload capability:

```python
def reload(self) -> ModelProfileCatalogue:
    """Reloads the profile catalogue from disk and swaps references atomically."""
    new_catalogue = self._load()
    if not any(p.enabled and p.model == self.settings.OLLAMA_MODEL for p in new_catalogue.profiles):
        # Guarantee default primary fallback
        ...
    self.catalogue = new_catalogue
    logger.info("Reloaded %d model profiles from %s", len(self.catalogue.profiles), self.path)
    return self.catalogue
```

Update `backend/app/api/routes/ollama.py`:
* `GET /api/ollama/profiles`: reloads on request or accepts `?reload=true`.
* `POST /api/ollama/profiles/reload`: explicit reload endpoint.

---

## 5. Verification & Testing Plan

1. **Unit Tests (`backend/tests/test_model_registry.py`):**
   * Confident classification routing to specialist.
   * Low-confidence escalation from small router to distinct primary model.
   * Fallback to keyword heuristics on non-JSON response.
   * Manual override skipping classifier.
   * Missing model raising `ModelNotFoundException`.
   * Catalogue dynamic reload updating in-memory profiles.
2. **State Manager Unit Tests (`backend/tests/agent/test_state_manager.py`):**
   * `record_routing` updates task and saves to disk.
   * Backward compatibility loading task JSON without `routing`.
3. **Integration Tests (`backend/tests/integration/test_phase4_routing.py`):**
   * Full task lifecycle asserting `task.routing` is populated and visible via API.
   * Offline Ollama during planning transitions task to `FAILED` with descriptive error and preserved record.
   * `InferenceGuard` lock acquisition verification during routing and planning.
4. **Regression Gate:**
   * All 76 baseline tests must pass.
