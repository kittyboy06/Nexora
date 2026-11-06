# NEXORA — PHASE 4
## Agent Fleet Foundation: Model Profiles and Hybrid Routing

### Preserve the existing phases

Phases 0–3 remain the foundation: FastAPI, Ollama integration, deterministic planning and validation, task lifecycle, centralized inference limits, tool permissions, approvals, and real Windows tools. This milestone extends the existing planner boundary. It does not replace the executor or create a second tool path.

### Implemented milestone

- Ollama remains the first inference provider behind the existing service boundary.
- `data/model_profiles.json` defines multiple specialist profiles and allows multiple profiles to reference one installed model.
- The live Ollama inventory determines which configured profiles can be selected.
- A configurable router model classifies each agent goal. Low-confidence or malformed routing responses are escalated to the primary model when it is a distinct model, then a deterministic keyword fallback is used.
- The planner accepts a manual `model_profile_id` override on task submission. Automatic selection remains the default.
- Specialist instructions are injected into the existing planning prompt. The resulting plan still passes through the existing PlanValidator, permissions, and Executor.
- `GET /api/ollama/profiles` reports configured profiles and local installation availability.

### Provisional defaults

The shipped catalogue keeps every profile on the currently configured Qwen model so the project remains operable with its existing setup. `MODEL_ROUTER_MODEL` also defaults to that model. Point it at an installed small model and update specialist entries in `data/model_profiles.json` to enable multi-model routing. These values are starting defaults, not additional locked architecture decisions.

Other provisional decisions carried forward: provider-independent model interface with Ollama first; DAG scheduling; tiered memory; isolated browser sessions unless an existing session is explicitly authorized; and capability retention only after validation and review.

### Central governance boundary

Model routing only chooses the planner profile. It does not grant capabilities. Tool execution continues through the central permission manager, approval checks, plan validation, audit logging, and deterministic executor. Future generated tools must be validated and run in a real sandbox. MCP servers may be discovered and inspected, with user approval required before installation. Shared browser and internet research remain subject to central permissions.

### Remaining design and implementation decisions

- Persisted profile editing API and validation workflow.
- Provider adapter contract beyond the current Ollama service.
- Model capability/resource metadata and runtime load scheduling.
- Specialist selection for evaluator and dynamically created agents.
- DAG fleet scheduling and dependency-aware parallelism.
- Tiered memory implementation and retention rules.
- Selective Markdown skill discovery/injection and GitHub discovery controls.
- Universal MCP transport coverage, credential handling, and approval UX.
- Sandboxed generated-tool lifecycle, audit records, and review process.
- Shared browser research permissions and isolated-session implementation.

### Later validation

The code includes focused routing tests, but they have not been run in this continuation. Later checks should cover the project test suite, live Ollama inventory, routing with a lightweight local model, model switching, profile overrides, and the existing Phase 2/3 integration workflows on the laptop.
