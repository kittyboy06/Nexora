# NEXORA — Master Architecture and Antigravity Build Guide

**Document type:** Product and engineering architecture reference  
**Project:** NEXORA — Local Autonomous Intelligence  
**Target platform:** Windows 11 desktop, local-first  
**Architecture baseline:** Agent Fleet preferences confirmed in the Local AI Setup conversation  
**Repository status reference:** 6 November 2026

---

## 1. Purpose of this guide

This document describes the complete intended NEXORA application and gives Antigravity a phased path for building it in the existing repository at `D:\Projects\Works\Nexora`.

For the detailed file-per-phase and file-per-module implementation set, start with `Plans/README — Architecture Documentation Index.md`.

The repository already contains the Phase 0–3 backend foundation and real Windows tools. A Phase 4 model profile and routing foundation has also been started. This guide is a separate product-level architecture document. It does not replace the detailed Phase 0–3 specifications, and it does not authorize a rewrite of existing code.

### Instructions for Antigravity

1. Inspect the repository, current branch, current files, tests, and all `Plans/` specifications before editing anything.
2. Preserve working Phase 0–3 components and their API contracts. Extend the current modular FastAPI backend; do not start a second backend or create a duplicate executor.
3. Compare the repository with the phase status in this document. Treat status claims as a map to inspect, not as proof that a feature currently works.
4. Work only on the next incomplete phase or milestone. Read its phase plan, state assumptions, implement the smallest end-to-end increment, document it, and stop at its test gate.
5. Do not silently decide an open architecture question. Use the provisional defaults below for prototypes, label them provisional in documentation and configuration, and ask for a decision when a choice would create a difficult-to-reverse dependency.
6. Never claim that a test, Windows operation, Ollama model, GPU behavior, browser, MCP server, or end-to-end workflow was verified unless it was actually run and the evidence is recorded.

---

## 2. Product description

NEXORA is a local-first AI desktop assistant for Windows. A user gives it a goal in natural language. NEXORA chooses a suitable local model and specialist profile, plans the work, asks for confirmation when an action requires it, executes approved registered capabilities, checks the results, and reports what happened.

NEXORA is an **orchestration and controlled-execution application**, not a model with unrestricted access to the computer. Models propose classifications, plans, explanations, and recovery suggestions. Deterministic application code validates proposals, enforces limits, authorizes each action, executes capabilities, records an audit trail, and verifies outcomes.

The finished product is expected to provide:

- A native Windows dashboard for chat, task submission, progress, approvals, history, model profiles, skills, MCP connections, and settings.
- An optional always-on-top native companion window in a screen corner for task status, approvals, quick capture and pause/cancel controls.
- A dynamic Agent Fleet that creates a task-specific team of specialists when a task benefits from multiple roles.
- Local model discovery, specialist profiles, automatic routing, optional escalation, and manual profile/model selection.
- Selective Markdown skill loading and controlled discovery of skills, tools, MCP servers, and workflows from GitHub.
- A standards-based MCP client that can discover and inspect servers; installation and capability use remain permission-gated.
- Controlled filesystem, Windows application, terminal, browser, and future desktop-vision capabilities.
- A secure sandbox for generated tools, plus validation and human review before a generated capability can be retained.
- Persistent task records, tiered memory, audit events, result verification, and eventually scheduled tasks.

All capabilities are introduced incrementally. A listed future feature is not considered implemented until its phase acceptance criteria pass.

---

## 3. Target environment and operating assumptions

The original project specifications target Windows 11, Python 3.10+, FastAPI, Pydantic, Ollama, and a local Qwen model. The recorded reference machine is an AMD Ryzen 7 5700X, 16 GB RAM, and NVIDIA RTX 5050 with 8 GB VRAM. Antigravity must inspect the actual laptop before relying on these values; they are project planning inputs, not verified current hardware facts.

Design for a single-user local application first:

- The native Windows shell communicates with the backend locally. The backend binds to `127.0.0.1` by default; do not expose it to a LAN unless a later security design explicitly authorizes that.
- Ollama is the first model provider. NEXORA must remain usable and diagnosable when Ollama is offline.
- Start with one concurrent model generation and one active agent task, preserving current hardware guards. Relax limits only after measured tests.
- Keep user data, task state, audit records, skills, and configuration local unless a user explicitly connects an external service.
- Never require a hosted AI API for normal operation.
- Treat every model, extension, skill, MCP server, browser page, file, and tool result as potentially incorrect or adversarial input.

---

## 4. Architecture decisions and provisional defaults

### 4.1 Confirmed Agent Fleet preferences

| Area | Confirmed direction |
|---|---|
| Fleet composition | Dynamic, task-specific agents |
| Router | Hybrid: a small model routes first, with escalation when needed |
| Model selection | Automatic, with a manual override |
| Model inventory | Support multiple locally installed models |
| Specialist roles | Multiple specialist profiles may use one model, and profiles may use different models |
| Skills | Selectively inject relevant Markdown instructions from stored skills |
| Ecosystem discovery | Discover skills, tools, MCP servers, and workflows from GitHub |
| MCP | Universal standards-based client; discover and inspect servers |
| MCP installation | Require user approval before installation |
| Generated tools | Validate, then execute in a real sandbox |
| Research | Agents may share browser and internet research capabilities subject to central permissions |
| Governance | Centralize execution authorization, auditing, and verification |

### 4.2 Provisional defaults (not newly locked decisions)

Use these defaults to keep implementation moving. Keep them replaceable and label them provisional in the relevant design docs:

- Provider-independent model interface, with Ollama as the first adapter.
- DAG-based task scheduling for dependencies between agent subtasks.
- Tiered memory: short-lived task context, durable user-approved facts, and searchable long-term records only after retention rules are designed.
- Isolated browser context by default. Use an existing signed-in browser session only when the user explicitly authorizes that session for a task.
- Generated capability retention only after validation, sandbox execution, review, and explicit acceptance.
- One active task and one active inference by default on the reference hardware.
- The current configured Qwen model remains a safe fallback until a separate lightweight router and specialist models are installed and configured.

### 4.3 Decisions that remain open

Do not silently lock these choices. Record a proposal, trade-offs, and the point at which a decision is needed:

- Frontend layout and whether it should run as a browser page, a packaged desktop shell, or both.
- SQLite adoption and migration strategy. Phase 2 currently persists task snapshots as atomic JSON; do not discard them without a migration plan.
- Which lightweight router, coding, research, reasoning, and vision models are best for the actual laptop.
- Model unloading, warm-cache policy, VRAM scheduling, quantization, and concurrency above one inference.
- How skills and GitHub sources are signed, pinned, updated, reviewed, and rolled back.
- MCP transport versions and supported transports, server packaging, credential storage, and per-tool approval UX.
- Concrete sandbox technology for generated tools on Windows and how it contains filesystem, network, process, and resource access.
- Browser automation provider, browser binary/profile management, and the precise approval policy for form submissions and downloads.
- Memory retention periods, user controls, deletion, sensitive-data exclusion, and whether embeddings/vector search are needed.
- Desktop UI automation technology, supported applications, screenshot retention, and accessibility approach.
- Scheduler timezone, startup behavior, missed-run handling, and approval flow for unattended jobs.

---

## 5. System architecture

### 5.1 Main components

| Component | Responsibility | Authority boundary |
|---|---|---|
| Native Windows shell | Chat, task controls, status, approval prompts, configuration, audit views, tray, companion window and native capture broker | Presents actions and decisions; never executes tools itself or bypasses backend governance |
| FastAPI application | Local HTTP API, WebSocket/event delivery, dependency wiring and lifecycle | Validates API contracts; does not bypass services |
| Model provider interface | Common model discovery and inference contract | No tool execution permission |
| Ollama adapter | Local model inventory, chat completion, timeout/error translation | Communicates only with configured Ollama endpoint |
| Model registry | Installed model inventory, profiles, specialties, prompts and availability | Registry selection does not grant capabilities |
| Hybrid router | Classifies task, selects a profile, escalates ambiguity, records reason | Produces a routing decision only |
| Fleet orchestrator | Creates agents, decomposes goals, builds DAG dependencies, assigns work and joins results | Cannot directly invoke operating-system tools |
| Agent runtime | Isolated specialist identity, model/profile, allowed skills, context and capability set | Receives only task-scoped capabilities and context |
| Skill manager | Finds, validates, versions and injects selected Markdown skills | Skill text is untrusted guidance; it is not executable permission |
| Capability discovery | Finds candidate skills/tools/MCP/workflows from approved GitHub sources | Discovery and inspection are read-only until approved |
| MCP manager | Connects to installed/approved MCP servers and exposes declared capabilities | Server install and capability use go through user and policy approval |
| Tool registry | Catalogues typed, schema-validated tools and metadata | No model-created tool is trusted just by registration |
| Permission manager | Applies central policy, risk classification, approvals, expiry and action binding | Sole authorization authority for side effects |
| Execution engine | Executes registered actions, enforces limits, classifies failures and records results | Executes only after validation and authorization |
| Generated-tool sandbox | Validates and runs generated tool code with resource/capability isolation | No direct host access; no retention before review |
| Browser/research service | Shared research session and web retrieval for agents | Central permission checks; isolated session by default |
| Memory manager | Task context and approved durable memories with retention controls | Sensitive content is excluded unless explicitly authorized |
| Audit and verification | Append-only action trace, evidence, approvals and postcondition checks | Model statements alone are not proof of success |
| Scheduler | Later phase for recurring/background work | Each run is a new governed task; approvals do not silently persist |

### 5.2 Main execution flow

1. The user submits a goal, optional constraints, and optional manual profile override.
2. The API validates the request and creates a persistent task record.
3. The hybrid router uses the configured small model and available profile metadata. If confidence is low or output is invalid, it escalates to the primary model when distinct; deterministic fallback and user clarification are used if ambiguity remains.
4. The planner or Fleet Orchestrator creates a concise plan. Multi-agent work is represented as a dependency DAG, not an unbounded chat among agents.
5. The orchestrator selects specialist profiles and injects only relevant, approved skill instructions and task context.
6. Python validates plan schema, dependencies, tool names, arguments, budgets, and task boundaries. Any invalid proposal is rejected or sent for bounded correction.
7. Immediately before each side effect, the Permission Manager computes risk from the operation and arguments, checks policy, and requests a task/action-scoped approval when required.
8. The execution engine invokes the registered tool or approved MCP capability. It enforces timeouts, resource limits, path boundaries, and retry classification.
9. The verifier checks the expected postcondition using independent evidence where possible (file state, process state, API result, browser state, etc.). It must distinguish success, failure, and uncertain outcomes.
10. Results and evidence return to the orchestrator. Failed steps may be retried only according to the tri-state retry policy; uncertain side effects are never blindly repeated.
11. NEXORA stores the task trace and audit events, updates the UI, and gives the user a concise report with completed actions, uncompleted work, and evidence.

### 5.3 Hard boundary

Models never directly execute Python, shell commands, filesystem operations, browser actions, or MCP calls. A model can request a registered capability by name and arguments. Deterministic code validates the request, authorizes it, executes it, and verifies the result. This rule applies equally to the planner, specialist agents, evaluator, and generated tools.

---

## 6. Core domain and task lifecycle

Preserve the Phase 2 state machine as the base contract:

`SUBMITTED → PARSING → PLANNING → EXECUTING → COMPLETED`

Additional states already represented include `WAITING_APPROVAL`, `APPROVED`, `REJECTED`, `EXPIRED`, `FAILED`, `CANCELLED`, and `INTERRUPTED`. The StateManager remains the only authority that changes task status. On startup, a task left active by a crash is marked `INTERRUPTED`; it is not automatically replayed because it may have completed a side effect before the process stopped.

Core records should evolve without breaking old task snapshots:

- **AgentTask:** original goal, user constraints, status, manual model-profile override, plan, agent/subtask links, trace, approvals, timestamps, outcome, and error summary.
- **TaskPlan:** validated goal and DAG steps.
- **PlanStep:** ID, description, dependencies, requested capability, typed arguments, risk, state, retries, owner agent, expected postcondition.
- **AgentProfile:** profile/model, role, specialties, system instructions, skills, capability allowlist, resource needs, enabled state, version.
- **Capability:** source, version, schema, permissions, risk rules, timeout/resource limits, verification method, trust state.
- **Approval:** user, task/agent/step, exact action and canonical argument hash, reason, expiration, decision, timestamp.
- **AuditEvent:** actor/model/profile, action, authorization decision, request hash, execution status, evidence references, timestamps. Never record credentials or secret values.
- **MemoryRecord:** content, provenance, category/tier, sensitivity, created/expiry times, and user consent state.

Model-generated output must be parsed into typed data and validated before persistence or execution. Old persisted records without new optional fields must still load.

### Retry rules

- `TRANSIENT`: retry a bounded number of times with backoff when the action is known to be safe to repeat.
- `PERMANENT`: stop execution and ask the evaluator for a bounded recovery proposal; the proposal is validated again.
- `UNCERTAIN`: stop and report uncertainty. Do not repeat an action that may already have happened.

---

## 7. Central permissions, safety, auditing, and verification

### 7.1 Risk levels

Keep existing `SAFE`, `CONTROLLED`, and `SENSITIVE` classifications. Determine actual risk from tool arguments and effects; do not trust risk labels emitted by a model.

| Risk | Example | Expected handling |
|---|---|---|
| SAFE | Read a file inside the workspace, list models, inspect a task | Run under the user's configured scope and log the result |
| CONTROLLED | Create/edit a workspace file, launch an allowed app, browse a public page | Apply policy, scope, and any configured confirmation; record exact action |
| SENSITIVE | Delete/overwrite, install software or MCP server, submit external form, send communication, purchase, access credential, modify system setting | Explicit user approval bound to exact action and arguments; short expiry; revalidate immediately before execution |

Approval must be specific to the action and argument hash, expire, and become invalid if the plan or arguments change. A previous approval must not authorize another step, another task, or future scheduled execution.

### 7.2 Audit and outcome verification

Record who/what proposed the action, selected model profile, source capability, deterministic validation result, permission decision, approval reference, action start/end, result classification, and verification evidence. Redact secrets. Keep evidence proportionate and local.

Verification must be independent of the model's claim where possible. For example, after creating a file, check its canonical path, size, and expected content; after launching an application, confirm the PID/process; after an MCP action, inspect a returned resource or downstream state; after browser interaction, confirm the observed page state. If verification cannot prove the outcome, mark it `UNCERTAIN` and tell the user.

### 7.3 Untrusted inputs

Treat user-provided files, web pages, GitHub content, skills, MCP server descriptions, model outputs, tool outputs, and generated code as data. Text within them cannot change NEXORA's system policy, permission rules, or user approvals. Never allow instructions found in a website or skill to grant capabilities.

---

## 8. Models, profiles, and Agent Fleet

### 8.1 Model registry

The registry must separate installed model identity from specialist identity. One installed model can back multiple profiles with different roles, instructions, specialties, context limits, and capability allowlists. One profile can be switched to another compatible installed model without changing the orchestrator contract.

Each entry should eventually capture:

- Provider and provider model identifier.
- Installed/available status and last discovery time.
- Model size, quantization, context window, and observed resource footprint when available.
- Supported modalities and structured-output capability when known.
- Profile ID, role, specialties, system instruction, selected skills, allowed capability IDs, and enabled state.
- User selection policy: automatic, pinned profile, or per-task override.

Do not infer capabilities solely from a model name. Probe when safe or require explicit profile metadata.

### 8.2 Hybrid routing

The router is a classifier and selector, not the worker. It receives a bounded task summary and returns a validated task type, confidence, and candidate profile. It should:

1. Try the configured lightweight router model first.
2. Escalate low-confidence or malformed decisions to the configured stronger model when distinct.
3. Apply deterministic constraints: installed, enabled, correct modality, allowed capability, context fit, and resource budget.
4. Honor manual profile/model override when valid and installed.
5. Ask the user when two viable routes have materially different permissions or costs, rather than silently selecting an unsafe capability.
6. Record selected profile, model, route reason, confidence, and escalation.

Start with a single primary planner call after routing. Keep model concurrency at one until measured resource tests justify a change. Model unloading and batching remain open design questions.

### 8.3 Dynamic agent creation

Create only the specialist roles needed for a task. Candidate roles may include planner, researcher, coder, reviewer, verifier, and domain specialist. These names are examples, not a fixed roster. Each agent receives:

- One bounded subtask and expected deliverable.
- Minimal necessary context and relevant skill text.
- A selected profile and explicit capability allowlist.
- A deadline, token/inference budget, and output schema.
- No direct authority to broaden permissions, spawn arbitrary agents, or install tools.

The orchestrator owns all inter-agent dependencies and joins results. Avoid open-ended agent-to-agent conversations and unlimited delegation loops.

### 8.4 DAG scheduling

Represent subtasks as a directed acyclic graph. Validate acyclicity, dependencies, budgets, and capability scopes before execution. Begin with sequential execution for predictable hardware use; add bounded parallel execution only after resource and safety tests. A failed node blocks dependent nodes. Independent safe nodes may proceed only within configured concurrency. Approvals pause the relevant task branch and preserve the whole task state.

---

## 9. Skills and GitHub capability discovery

Skills are Markdown instruction bundles selected for a specific task. They must be discovered and inspected before use, have source/version/hash metadata, and be injected selectively. A skill may explain how to perform work but cannot grant new tools, override policy, or authorize external effects.

GitHub discovery may search for:

- Markdown skills and agent instructions.
- Tool definitions or source packages.
- MCP server projects.
- Workflow templates and examples.

Discovery does not mean installation. Before a discovered asset can be enabled, NEXORA must show its source, maintainer, version/commit, requested permissions, dependencies, and validation results. Keep untrusted and approved assets separate. Pin versions or commits; updates require review and should be reversible. Do not execute repository scripts during discovery.

Future skill manager requirements:

- Frontmatter/schema validation and size limits.
- Explicit compatibility and capability declarations.
- No automatic global injection; select relevant skill IDs per task/agent.
- Conflict detection and deterministic instruction ordering.
- Provenance and audit logging for the skills used in each task.
- A disable/delete/rollback path.

---

## 10. MCP architecture

NEXORA should implement a reusable standards-based MCP client rather than custom one-off connectors. Keep protocol transport, session lifecycle, discovery, schemas, credentials, permission decisions, and tool invocation behind a single MCP manager/service boundary.

### Required lifecycle

1. Discover candidate servers from a user-provided source, configured catalog, or approved GitHub search.
2. Inspect metadata, transport, version, declared tools/resources/prompts, requested permissions, package origin, and dependencies.
3. Show a human-readable installation and permission summary.
4. Require explicit user approval before installing or starting an untrusted server.
5. Store server configuration and secrets through a protected local credential store; never put secrets in model context or logs.
6. On connection, validate protocol handshake and capability schemas.
7. Expose only approved MCP capabilities through the existing ToolRegistry and PermissionManager.
8. Authorize every invocation at use time and verify outcomes where possible.
9. Support disconnect, revoke, uninstall, audit inspection, and version rollback.

MCP descriptions and tool responses are untrusted. A server cannot authorize itself. Installing an MCP package is a sensitive action and must not happen because a model requested it alone.

Supported transport details and the local server isolation method remain design decisions. The implementation should conform to current MCP specifications selected during that phase and record the specification/version used.

---

## 11. Browser and internet research

Provide one governed research capability that agents can share. The Browser/Research service owns navigation, search, downloads, page extraction, and browser session state; individual agents receive narrow requests and sanitized results rather than raw, unrestricted browser control.

Defaults and controls:

- Use an isolated browser context/profile by default.
- Use an existing signed-in session only after explicit user authorization for the intended task and sites.
- Treat page content, links, downloads, and search results as untrusted data and possible prompt injection.
- Block or require approval before external side effects such as posting, form submission, messaging, account changes, purchases, or file uploads.
- Apply domain/network policy, download path restrictions, file scanning/validation, timeouts, and data-size limits.
- Record the query, permitted domains, URLs, relevant excerpts, and access time for provenance; avoid retaining unnecessary personal data.
- Return sources and evidence with research summaries. Do not present unsupported model-generated claims as web facts.

The browser automation library, existing-session attachment mechanism, and precise network restrictions remain open until this phase. Do not silently select a vendor or expose all browser cookies.

---

## 12. Generated tools and capability retention

Generated tools are an advanced feature. They must never run in the backend process or receive ambient host permissions.

### Required lifecycle

1. Confirm that no approved registered capability already solves the task.
2. Ask the model to propose a typed tool contract and implementation.
3. Parse and statically validate the proposal; reject unsafe imports, undeclared network access, path escapes, shell escape, and undeclared capabilities.
4. Show requested filesystem, network, process, and resource permissions.
5. Execute tests and a limited trial in a real OS/process/container sandbox with denied-by-default host access, time/resource limits, and disposable storage.
6. Review outputs and security findings. A sandbox test pass alone does not approve production use.
7. Require human approval before enabling the capability outside the test harness.
8. Keep the tool versioned, scoped, auditable, disableable, and removable.
9. Retain as a reusable capability only after validation and review; retention remains provisional until the user chooses the review policy.

The exact Windows sandbox technology is unresolved. Antigravity must first propose viable isolation options and their limits. If a real sandbox is unavailable, generated code must not be executed as a fallback in the host process.

---

## 13. Memory and persistence

Memory must be layered and user-controllable:

1. **Request context:** current user request and constraints; discarded after task completion unless explicitly retained.
2. **Task working memory:** plan, subtask results, evidence, and bounded notes needed to resume within the task.
3. **Durable user memory:** user-approved preferences and facts, with provenance, edit/delete controls, and retention rules.
4. **Searchable archive:** optional longer-term task/evidence retrieval only after privacy and retention design.

Do not store passwords, API tokens, sensitive page contents, or private file contents in durable memory by default. Provide inspect/export/delete controls and explain what is stored. Begin with the existing atomic task JSON persistence; evaluate SQLite for searchable structured state with a migration and backup plan. Vector search is optional, not a phase prerequisite.

---

## 14. Existing project structure and intended growth

Preserve and extend the existing project. The current repository is already organized around a Python backend with `app/api`, `agent`, `core`, `models`, `permissions`, `services`, and `tools`, plus backend tests, task/workspace/log data, and `Plans/` documents.

The intended long-term structure may grow toward:

```text
Nexora/
├── backend/
│   ├── app/
│   │   ├── api/              # REST and WebSocket routes
│   │   ├── agent/            # Planner, orchestrator, DAG, runtime, verifier
│   │   ├── core/             # Config, lifecycle, errors, logging, limits
│   │   ├── models/           # API and domain schemas
│   │   ├── permissions/      # Central policy and approval lifecycle
│   │   ├── services/         # Model providers, registry, skills, MCP, browser, memory
│   │   ├── tools/            # Typed registered capabilities/adapters
│   │   ├── sandbox/          # Generated-tool sandbox adapter and controls
│   │   ├── scheduler/        # Later phase only
│   │   └── main.py
│   ├── tests/                # Unit, integration, security, and Windows tests
│   └── requirements.txt
├── desktop/                  # C# WinUI 3 native shell, tray, companion and capture broker
├── data/
│   ├── tasks/                # Existing task snapshots until migration is decided
│   ├── workspace/            # Filesystem and generated-tool work area
│   ├── skills/               # Versioned local skills
│   ├── audit/                # Local audit records
│   ├── memory/               # Only after memory policy is approved
│   └── logs/
├── Plans/                    # Phase specifications and implementation plans
└── README.md
```

This is a target map, not an instruction to create every directory now. Add a subsystem when its phase begins. Keep secrets and `.env` files out of version control.

---

## 15. API and UI capability map

Keep existing routes backward-compatible. Add routes as needed for the dashboard, using validated Pydantic request and response models and the shared error format.

| Area | Existing/base routes | Future native shell needs |
|---|---|---|
| Health/model | `/api/health`, `/api/ollama/status`, `/api/ollama/models`, `/api/ollama/profiles` | Provider/model diagnostics, profile selection and configuration |
| Chat | `POST /api/chat` | Conversation/session history and streaming, if selected |
| Tasks | `/api/agent/tasks`, task detail, approve, cancel | Live event stream, subtask/agent view, retry/continue controls |
| Skills | Not implemented as a full manager | List, inspect, enable/disable, source/version, task injection trace |
| MCP | Not implemented as a universal manager | Discover, inspect, approval, connect/disconnect, permissions, audit |
| Permissions | Existing task approval API | Policy editor, pending approvals, revocation, audit evidence |
| Memory | Not implemented | View, approve, edit, export, delete and retention settings |
| Schedule | Not implemented | Create/pause/edit recurring tasks with per-run authorization |

The dashboard must make it clear what is running, which model/agent/capability is active, what is awaiting approval, what changed, and how NEXORA verified the outcome. Avoid hiding implementation details unless they help the user make a decision.

---

## 16. Phase roadmap and completion gates

Phase status below reflects the repository and documents inspected on the status date. Antigravity must inspect and verify each item before relying on it.

### Phase 0 — Product and technical foundation (documented)

**Purpose:** Define NEXORA as an independent local Windows agent and set the initial technology, scope, project structure, security principles, and future capabilities.

**Core contracts:** Python/FastAPI backend; C#/.NET WinUI 3 native shell target; local Ollama; SQLite considered in original target spec; modular services; centralized permissions; incremental delivery. The initial phase explicitly excludes desktop control, browser automation, long-term memory, and scheduling.

**Gate:** Product scope and security boundaries are documented; phase-specific tasks and target environment are understood.

### Phase 1 — Core backend foundation (implemented; verify in repository)

**Purpose:** Reliable local backend and Ollama bridge.

**Components:** FastAPI lifecycle, configuration, logging, shared HTTP client, Ollama service, model/status endpoints, chat endpoint, unified errors, inference semaphore, offline tests.

**Gate:** Offline tests pass with mocked Ollama; health remains available while Ollama is offline; error and concurrency behavior are validated; live Ollama smoke test is separately recorded.

### Phase 2 — Hybrid autonomous agent engine (implemented; preserve)

**Purpose:** Let an LLM propose structured plans while Python retains all execution authority.

**Components:** Pydantic task/plan/tool schemas, ToolRegistry, Planner, PlanValidator, StateManager, atomic JSON persistence and restart recovery, PermissionManager, Executor, ResultEvaluator, Orchestrator, TaskManager, task and approval APIs.

**Hard limits:** Existing defaults include maximum 10 plan steps, 15 execution iterations, 2 retries per step, 1 active task, 1 concurrent inference, 2 planning attempts, and bounded execution duration. Read actual settings before changing them.

**Gate:** Plan schemas and dependency validation; approvals bound to exact actions and expiring; uncertain actions never blindly retried; restart recovery marks unfinished tasks interrupted; tests cover state transitions, permissions, retries, limits and end-to-end workflows.

### Phase 3 — Real-world controlled tools (implemented; preserve)

**3A Filesystem:** Real file list/search/read/create/edit/rename/copy/move/delete in `data/workspace`, canonical path enforcement, symlink/traversal protection, size limits, overwrite safeguards, approval for destructive work.

**3B Windows applications:** Registry/Start Menu discovery, application search, validated launch, process inspection, protected process denylist, bounded close behavior.

**3C Terminal:** Tokenized process launch without shell interpolation, command allowlist, workspace-bounded scripts, timeouts, output limits, secret redaction, approval for sensitive package installation.

**3D Integration:** Agent workflows using registered tools, approval and resumption, offline tests, separate live Windows verification.

**Gate:** All tool actions pass through `BaseTool`/ToolRegistry, argument validation, dynamic risk classification, central permission check, audit and result verification. Do not replace these tools with an alternate execution path.

### Phase 4 — Model registry and hybrid routing (started; verify and complete)

**Purpose:** Add the model/profile foundation without changing the executor.

**Current work to inspect:** `data/model_profiles.json`; model provider protocol; profile schemas and registry; routing service; `MODEL_ROUTER_MODEL`, confidence threshold and profile file configuration; `GET /api/ollama/profiles`; optional task `model_profile_id`; planner routing; focused routing tests. In the preceding work these tests were authored but not run, so Antigravity must verify the current code and test state.

**Complete this phase by:**

- Confirming installed inventory and profile availability are accurate and fail clearly.
- Testing a confident small-model route, escalation to a distinct primary model, deterministic fallback, multiple profiles sharing one model, manual override, missing model, and offline Ollama.
- Recording the selected profile/model and route reason in task diagnostics/audit.
- Confirming all routing and planning inference uses the central `InferenceGuard`.
- Preserving old task snapshots and existing chat behavior.
- Documenting how to add/switch profiles and when the backend must reload configuration.

**Gate:** Focused routing tests and all existing tests pass; profile route is visible; a live local model route is verified when available; no Phase 0–3 regression is accepted.

### Phase 5 — Native Windows shell and user control plane (future)

**Purpose:** Provide a native Windows interface for controlling NEXORA and reviewing its activity.

**Deliverables:** C#/.NET WinUI 3 shell; main dashboard; optional always-on-top corner companion; task/chat view; task progress and step trace; approval queue with exact action details; model/profile display and override; error/uncertain status; audit/evidence panel; tray, native notifications and opt-in hotkeys; settings and connection health; accessible keyboard-first UI; backend API client with typed contracts; native screen/window capture broker.

**Constraints:** Do not add Electron or a browser-hosted frontend as the primary app. Do not put secrets in shell settings/storage. The shell is not the permission authority; backend checks remain mandatory. Preserve existing local FastAPI contracts initially; evaluate named pipes only in a separate decision. Prefer polling initially if it satisfies responsiveness; choose SSE/WebSockets only after connection lifecycle and reconnection behavior are specified.

**Gate:** Create, inspect, cancel, approve/reject, and follow a task entirely through the native UI; API errors and offline models render clearly; backend remains authoritative; native shell tests cover key controls, window behavior and backend supervision.

### Phase 6 — Dynamic Agent Fleet and DAG orchestration (future)

**Purpose:** Create task-specific specialist agents instead of a fixed collection.

**Deliverables:** Task classifier output schema; bounded decomposition; validated dependency DAG; dynamic agent factory/lifecycle; per-agent model profile, skills, context, capability allowlist, budget and deadlines; coordinator/join logic; failure propagation; cancellation and approval pause/resume across subtasks; task trace showing agent assignment and outputs.

**Constraints:** No unlimited delegation. Agents cannot grant permissions, create arbitrary subagents, or communicate without coordinator limits. Sequential DAG execution is the initial default; parallelism requires measured CPU/RAM/VRAM and task-isolation tests.

**Gate:** DAG cycles and invalid dependencies rejected; budgets enforced; failures block dependent nodes safely; cancellation and approvals work; all agent outputs are schema-checked and verifiable; task and inference concurrency remain bounded.

### Phase 7 — Skill manager and GitHub discovery (future)

**Purpose:** Add selective Markdown skill injection and controlled external discovery.

**Deliverables:** Local skill metadata/versioning; discovery and inspection UX; Markdown parsing and size limits; task relevance selection; explicit per-agent injection; provenance and hashes; GitHub discovery adapters for skills/tools/MCP/workflows; review, pin, update, disable and rollback flow.

**Constraints:** Discovery is read-only. Never execute installation scripts during discovery. Skills cannot grant permissions or supersede system policy. Unreviewed content is clearly marked untrusted.

**Gate:** Unit tests for parsing, conflicts, injection selection, source integrity, malicious instruction text and rollback; audit reports exact skill versions injected into each agent.

### Phase 8 — Universal MCP client and server lifecycle (future)

**Purpose:** Connect to compatible MCP servers through a standards-based, vendor-independent manager.

**Deliverables:** Protocol/transport layer; discovery; handshake/version handling; tools/resources/prompts catalog; schema validation; server health; per-server enable/disable; credential handling; capability mapping into ToolRegistry; human-readable inspection and approval UX; audit and uninstall/rollback.

**Constraints:** Discover and inspect without installation. Installation requires user approval. Every MCP invocation is separately authorized. Server-provided descriptions/results are untrusted. Do not expose credentials to models or logs. The exact supported transports and Windows isolation design must be recorded before implementation.

**Gate:** Fake-server protocol tests, malformed schema tests, timeout/reconnect tests, permission isolation tests, credential-redaction tests, and approval-before-install integration tests pass.

### Phase 9 — Shared browser and internet research (future)

**Purpose:** Allow agents to research with shared, governed browser access.

**Deliverables:** Browser service, isolated context manager, search/navigation/page extraction, agent request queue, source/evidence capture, download controls, domain policy, session cleanup, status in dashboard.

**Constraints:** Isolated browser by default. Existing user sessions only when explicitly authorized. Browser content is untrusted. Require explicit approval for external side effects and sensitive downloads/uploads. Do not let agents share cookies or unrestricted browser control.

**Gate:** Tests for prompt injection in pages, domain restrictions, download location/content, session isolation, approval requirements, browser crashes and evidence capture. Live site tests must be opt-in and must not submit real forms without approval.

### Phase 10 — Generated tools and sandbox (future)

**Purpose:** Let NEXORA propose missing tools while containing and reviewing them.

**Deliverables:** Tool contract generator, static checks, dependency policy, actual Windows sandbox adapter, isolated test runner, denied-by-default permissions, CPU/memory/time/output limits, capability review screen, versioned registry, disable/remove/rollback, verified acceptance tests.

**Constraints:** Never execute generated code inside the backend process or with ambient user permissions. Never silently keep a generated capability. If an adequate sandbox is unavailable, disable execution and report the blocker instead of using a weaker fallback.

**Gate:** Adversarial breakout attempts and filesystem/network/process/resource containment tests; approval and audit tests; reproducible tool versions; result verification; human review before persistence.

### Phase 11 — Tiered memory and persistence evolution (future)

**Purpose:** Support safe task continuation and user-approved durable recall.

**Deliverables:** Task working memory; durable preference/fact records with provenance; retention/expiry; user inspect/edit/delete/export controls; sensitive-data exclusions; backup/restore; optional search index after evaluation; migration strategy if moving from task JSON to SQLite.

**Gate:** Persistence/restart tests, permission tests, deletion and expiry tests, migration/rollback tests, no-secret-retention tests, and user-visible memory controls.

### Phase 12 — Desktop vision and UI automation (future, gated)

**Purpose:** Add visual understanding and bounded desktop interaction only after explicit design and security review.

**Deliverables:** Capture broker, allowed-window/screen selection, redaction, short-lived screenshots, vision-profile routing, UI action planner, preview/confirm controls, coordinate/action bounds, post-action screenshot verification, cancellation and privacy controls.

**Constraints:** No always-on screen capture. No hidden observation. No credentials or sensitive screens sent to models by default. Mouse/keyboard interaction requires explicit scope and appropriate confirmation. Accessibility APIs should be evaluated before coordinate automation.

**Gate:** Windows-specific tests for target-window restriction, secret redaction, approval, correct postcondition, unexpected focus changes, and emergency stop.

### Phase 13 — Scheduled and background tasks (future)

**Purpose:** Run user-defined recurring jobs under the same governance model.

**Deliverables:** Schedule records, timezone-aware recurrence, pause/edit/delete, missed-run policy, run history, notifications, resource limits, and per-run permission checks.

**Constraints:** A previous approval cannot authorize future runs. Sensitive scheduled actions must pause for fresh approval. Startup behavior and timezone remain explicit user settings.

**Gate:** Timezone/DST tests, missed schedule behavior, restart recovery, cancellation, approval expiry, duplicate-run prevention, and audit completeness.

### Phase 14 — Full-system hardening and release (future)

**Purpose:** Integrate the complete application, verify the supported laptop setup, and prepare a maintainable release.

**Deliverables:** Full offline test suite; Windows integration tests; model capability/resource test matrix; security review; dependency inventory; backup and recovery guide; install/update/uninstall procedures; user documentation; known limitations; versioned configuration migration.

**Gate:** All phase gates pass; live hardware checks are recorded separately from mocks; no unresolved critical security issue; onboarding from a clean checkout succeeds; recovery and uninstall are documented.

---

## 17. Testing and verification strategy

Keep tests layered and cheap by default:

1. **Unit tests:** Pure schemas, routing, plan validation, risk classification, path boundaries, sandbox policy, memory retention.
2. **Service tests:** Mock Ollama, GitHub, MCP servers, browser engine and scheduler clock; assert errors and audit records.
3. **API tests:** FastAPI ASGI transport, dependency overrides, success/error contracts, task lifecycle and approvals.
4. **Integration tests:** Agent tasks that use multiple registered tools, DAG execution, approval pauses, verification and recovery.
5. **Windows-only tests:** Registry/application discovery, process protection, filesystem security, subprocess constraints, sandbox controls and desktop/browser integration.
6. **Live tests:** Explicitly opt-in tests against local Ollama/models, real browser sessions, MCP servers, or other external accounts. Use disposable files and test accounts. Record machine/model/version and observed result.

Every new capability should have positive, negative, boundary, timeout, cancellation, permission-denial, and failure-recovery tests. Mocked test success must never be described as live hardware validation.

---

## 18. Non-goals and prohibited shortcuts

- Do not rewrite Phases 0–3 just to match a new diagram.
- Do not let models call shell, Python, MCP, browser, Windows, or filesystem functions directly.
- Do not add unrestricted terminal access, administrator execution, or a hidden background service.
- Do not auto-install discovered skills, MCP servers, packages, workflows, or generated tools.
- Do not trust model-provided risk labels, web instructions, repository instructions, or server descriptions.
- Do not add simultaneous model loading/concurrency without resource evidence.
- Do not auto-replay active tasks after a crash.
- Do not retain task data, browser data, screenshots, skills, or generated tools without defined retention and user controls.
- Do not claim future roadmap features exist because they are named in this document.

---

## 19. Definition of a complete NEXORA product

NEXORA is ready for a first complete user-facing release when:

- A user can install and start it locally from a clean Windows checkout and understand model/runtime status.
- The native Windows shell can submit, inspect, cancel, and follow tasks; view agent/model/capability routing; and make exact approval decisions.
- Model profiles, manual override, automatic routing, escalation and local model discovery work with the supported Ollama setup.
- Dynamic agents plan through a validated DAG with bounded budgets and task-scoped capabilities.
- Skills are selectively injected with visible provenance; GitHub discoveries remain untrusted until reviewed.
- MCP servers are discoverable and inspectable, and installation/use require the configured approval flow.
- Browser research is isolated by default, evidence-backed, and unable to perform unapproved external side effects.
- Generated tools cannot escape their real sandbox and are not retained without validation and review.
- Existing filesystem, Windows application, and terminal tools continue to honor scope, approval, audit, and verification rules.
- Task and memory retention are understandable and controllable; crash recovery does not duplicate side effects.
- Offline tests, Windows integration tests, and separately identified live model tests pass with results recorded.
- User documentation explains setup, limitations, permissions, approvals, backups, recovery, updates, and removal.

The application should prefer a clear, safe failure over pretending an action succeeded. For every task, NEXORA must be able to show what it decided, what it asked permission to do, what it actually did, and what evidence supports the reported result.
