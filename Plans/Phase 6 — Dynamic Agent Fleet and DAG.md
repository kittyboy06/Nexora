# NEXORA — Phase 6: Dynamic Agent Fleet and DAG Orchestration

## Purpose

Evolve the current single planner/executor loop into a bounded fleet that creates only the specialist agents needed for a task. The Fleet Orchestrator decomposes work into a validated directed acyclic graph (DAG), assigns profiles and scoped capabilities, coordinates results, and preserves the existing deterministic execution authority.

## Prerequisites

- Phase 4 hybrid routing has a passing test suite and profile availability behavior.
- Phase 5 can display task progress or an equivalent task inspection path exists.
- Read `Modules/01 — Governance, Permissions, Audit and Verification.md`, `Modules/02 — Models, Profiles and Routing.md`, and `Modules/03 — Dynamic Agent Fleet and DAG Runtime.md`.

## Non-negotiable model boundary

An agent may return structured subtask proposals and outputs. It may not invoke a tool, grant a capability, install an MCP server, create an unrestricted child agent, mutate task state, or claim verification. The Fleet Orchestrator, PlanValidator, PermissionManager, Executor and StateManager retain those powers.

## Scope

### Included

- Agent profile schema: role, model profile, instructions, selected skills, context budget, capability allowlist, deadlines and output schema.
- Fleet plan schema with agent nodes, subtask nodes, dependencies, expected artifacts and failure policy.
- Deterministic DAG validator: unique IDs, acyclicity, allowed dependencies, budget limits, profile availability and capability scope.
- Agent factory that creates in-memory task-scoped runtime instances only.
- Coordinator that executes a sequential DAG first and stores each node result.
- Join/review steps that aggregate structured worker output into the parent task result.
- Bounded delegation: maximum depth, agent count, prompt/context size, plan attempts and time budget from configuration.
- Parent cancellation, failure propagation and approval pause behavior.
- Trace/audit fields for agent assignment, selection reason, skill IDs and output evidence.

### Excluded

- Parallel DAG execution until sequential correctness and hardware profiling pass.
- Persistent autonomous agents.
- Free-form multi-agent chat rooms or unrestricted agent messaging.
- Agent-created capabilities, browser/MCP execution, generated tools, memory retention or scheduled autonomous work.

## Fleet planning lifecycle

1. Router selects the primary planner profile.
2. Planner proposes a `FleetPlan` as validated JSON: nodes, dependencies, candidate profiles, outputs and required registered capabilities.
3. Python validates the fleet plan. It rejects cycles, unavailable profiles, empty or oversized nodes, unregistered capabilities, ambiguous dependencies and over-budget fleets.
4. Orchestrator creates isolated agent runtimes with minimum context and a fixed scope.
5. It executes ready nodes in deterministic order. Each node output is schema-checked before dependents can see it.
6. A node requiring a tool creates normal plan steps; existing permission/executor flow runs them. An approval pauses the branch/task safely.
7. Node failures use existing retry classification. `UNCERTAIN` failure blocks downstream work and surfaces to the user.
8. A join/reviewer node synthesizes only validated upstream artifacts. A verifier confirms expected postconditions for any side effect.
9. Parent task completes only when all required nodes and verification steps reach a terminal acceptable state.

## Domain contracts

Define typed Pydantic schemas before runtime code:

- `FleetPlan`: fleet ID, parent goal, nodes, limits, version.
- `FleetNode`: node ID, agent profile ID, objective, input artifact refs, dependencies, output schema, required capabilities, expected postcondition and state.
- `AgentRuntime`: runtime ID, parent task ID, node ID, profile ID, bounded context, capability IDs, budgets and lifecycle timestamps.
- `Artifact`: immutable structured output, producer, schema version, content hash, sensitivity label and evidence references.
- `FleetResult`: node outcomes, blocked nodes, final artifacts, verification status and human-readable summary.

Keep `AgentTask`, `TaskPlan`, `PlanStep` and current task snapshots backward-compatible. A simple task should still run through the original one-agent path or an equivalent one-node fleet path without changing external behavior.

## Scheduling and resource policy

Start with a ready-node queue that executes one node at a time. This matches the current one-task/one-inference guard and makes audit/recovery predictable. Record the actual schedule order. Add parallelism only after a separate design amendment specifies CPU, RAM, VRAM, process isolation, queue fairness, failure propagation and concurrency tests.

## Security and verification

- A node receives artifact references, not unrestricted parent history.
- Skills and capabilities are selected by policy and profile; agents cannot add them.
- Profile instructions are versioned and logged.
- Tool outputs become immutable evidence records once used by a dependent node.
- A reviewer model may critique a result but cannot mark it verified. Verification uses deterministic checks or a separately defined evidence rule.
- Parent task resume after restart follows existing interrupted-task safety; no fleet node is replayed automatically after an uncertain interruption.

## Test plan

- Valid sequential two-node and three-node DAGs.
- Reject cycles, missing dependencies, duplicate node IDs, over-depth delegation, unavailable profiles, invalid output schema, unregistered tools and capability escalation attempts.
- Ensure one node cannot read unrelated artifact/context.
- Verify cancellation, approval pause/resume, transient recovery, permanent failure and uncertain failure propagation.
- Assert exactly one inference at a time under existing guard.
- Snapshot/backward-compatibility tests for old `AgentTask` JSON.

## Acceptance criteria

- Dynamic specialist selection is observable in task/audit detail.
- Every agent has bounded context, capability scope and budget.
- Invalid fleet plans fail before any tool runs.
- Existing approval and executor pathway remains the only side-effect pathway.
- Sequential fleet workflows, dependency blocking and restart behavior pass tests.
- No code claims or enables parallel execution without measured validation.

## Implementation sequence

1. Add schemas and validator with unit tests only.
2. Add agent factory and sequential in-memory runtime with mock agents.
3. Persist fleet metadata and surface it in task detail.
4. Integrate one safe multi-node planning workflow with existing tools.
5. Add cancellation/retry/approval/restart tests.
6. Update Phase and module documents with actual test results.
