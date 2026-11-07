# NEXORA — Phase 4 Implementation Plan
## Agent Fleet Foundation: Model Profiles and Hybrid Routing

**Document Type:** Phased Implementation Plan  
**Target:** Phase 4 Completion & Verification  
**Specification:** `Plans/Phase 4 — Design Specification.md`  
**Test Status:** 84/84 passing (100% clean test suite)  

---

## Execution Milestones

### Milestone 1: Domain Models & State Management
- [x] **Task 1.1:** Add optional `routing: RouteSelection | None = Field(default=None)` to [`AgentTask`](backend/app/models/agent.py).
- [x] **Task 1.2:** Add `record_routing(self, task_id: str, routing: RouteSelection) -> AgentTask` in [`StateManager`](backend/app/agent/state_manager.py).
- [x] **Task 1.3:** Add unit tests in `backend/tests/agent/test_state_manager.py` verifying `record_routing` updates the model, touches `updated_at`, saves atomically, and old task JSONs deserialize without errors.

### Milestone 2: Dynamic Profile Reloading & API Endpoints
- [x] **Task 2.1:** Implement `reload(self) -> ModelProfileCatalogue` in [`ModelProfileRegistry`](backend/app/services/model_registry.py).
- [x] **Task 2.2:** Add `POST /api/ollama/profiles/reload` in [`backend/app/api/routes/ollama.py`](backend/app/api/routes/ollama.py) and ensure `GET /api/ollama/profiles` supports fresh reloading.
- [x] **Task 2.3:** Add unit tests in `backend/tests/test_model_registry.py` validating that modifying `data/model_profiles.json` and calling `reload()` updates in-memory profiles without restart.

### Milestone 3: Orchestrator & Planner Lifecycle Refactoring
- [x] **Task 3.1:** In [`Planner`](backend/app/agent/planner.py), implement `route_task(prompt, profile_override)` and `generate_plan_for_route(prompt, selection)`. Preserve `generate_plan(...)` as a backward-compatible wrapper.
- [x] **Task 3.2:** In [`AgentOrchestrator`](backend/app/agent/orchestrator.py), update `run_task` to execute `route_task` -> `record_routing` -> `generate_plan_for_route`.
- [x] **Task 3.3:** In [`AgentOrchestrator`](backend/app/agent/orchestrator.py), add structured exception catching for Ollama connection/timeout errors during planning, transitioning the task to `TaskStatus.FAILED` with a diagnostic error message while preserving the persisted snapshot.

### Milestone 4: Comprehensive Integration Tests & Verification
- [x] **Task 4.1:** Create `backend/tests/integration/test_phase4_routing.py` testing:
  - End-to-end task execution with automatic routing populating `task.routing`.
  - Router escalation from low-confidence router model to distinct primary model.
  - Keyword fallback routing when router outputs invalid format.
  - Manual `model_profile_id` override skipping classification.
  - Offline Ollama transitioning task to `TaskStatus.FAILED` with preserved disk snapshot.
  - `InferenceGuard` semaphore acquisition during both routing and planning.
- [x] **Task 4.2:** Run full test suite (`pytest backend/tests`) to ensure all 76 baseline tests + all new Phase 4 tests pass (84/84 passed).

### Milestone 5: Documentation & Configuration Guide
- [x] **Task 5.1:** Author user/developer documentation in `Plans/Phase 4 — Model Profiles Guide.md` explaining how to configure specialist profiles in `data/model_profiles.json`, configure small router models, and trigger reloads.
- [x] **Task 5.2:** Update `Plans/README — Architecture Documentation Index.md` to reflect Phase 4 completion.
