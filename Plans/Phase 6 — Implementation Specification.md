# NEXORA — Phase 6: Dynamic Agent Fleet and DAG Implementation Specification

**Document Type:** Technical Architecture & Implementation Specification  
**Status:** Validated & Locked via Brainstorming Protocol  
**Date:** 7 November 2026  
**Target Platform:** Windows 11 Desktop (Local-First)  

---

## 1. Executive Summary

Phase 6 evolves NEXORA’s single-agent execution loop into a bounded, task-specific **Dynamic Agent Fleet** coordinated via a validated **Directed Acyclic Graph (DAG)**. 

Complex user goals are decomposed into isolated subtasks, assigned to curated specialist profiles (Planner, Researcher, Coder, Verifier), executed sequentially under strict local hardware guards (1 active inference at a time via `InferenceGuard`), and connected exclusively through immutable, schema-validated artifacts. Central Python backend services authoritatively govern permissions, state mutations, and tool execution.

---

## 2. Understanding Summary & Hard Constraints

* **Purpose:** Break complex multi-domain tasks into focused specialist roles with bounded contexts to eliminate hallucinations, prompt pollution, and context window overflow.
* **Non-Negotiable Model Boundary:** Models propose structured plans and subtask outputs; they cannot invoke tools directly, grant permissions, install tools, or spawn unrestricted children.
* **Strict Conservative Bounds:** Maximum **5 nodes per fleet**. Execution is strictly sequential to respect local 8 GB VRAM limits (RTX 5050 ceiling) and eliminate GPU semaphore contention.
* **Context Isolation:** A node receives *only* explicit upstream input artifacts by reference. It has zero access to parent conversation history, sibling reasoning, or irrelevant task data.
* **Fail-Fast Safety:** A permanent or uncertain failure halts the fleet immediately, marks downstream dependent nodes `BLOCKED`, preserves completed artifacts, and surfaces detailed diagnostics.
* **UI Transparency:** The WinUI 3 Control Plane visualizes fleet progression via an interactive stepper bar (`[Planner] → [Researcher] → [Coder] → [Verifier]`) with status badges and artifact inspection.

---

## 3. Assumptions & Operating Bounds

1. **Hardware & Concurrency:** Single-user local Windows 11 machine. Exactly 1 active fleet at a time, exactly 1 active model inference at a time.
2. **Specialist Catalog:** Standard verified roles (`planner`, `researcher`, `coder`, `reviewer_verifier`) with locked capability allowlists and per-node context/token ceilings.
3. **Backward Compatibility:** Simple 1-step tasks continue running through the existing fast path without regression or schema breaks to `AgentTask`.
4. **Interruption & Crash Safety:** Interrupted fleet tasks follow existing safety protocols: no unverified or uncertain side effects are replayed on restart.

---

## 4. Complete Decision Log

| # | Decision Area | Chosen Strategy | Alternatives Considered | Rationale |
|---|---|---|---|---|
| **1** | **Fleet Trigger Policy** | **Hybrid Automatic with User Override** | Always Fleet (1-node DAG), Explicit Opt-in Only | Seamless automation for multi-step goals while retaining manual control and zero overhead for direct simple tasks. |
| **2** | **Specialist Roles & Scopes** | **Curated Catalog with Scoped Customization** | Strict Static Catalog Only, Fully Dynamic Prompt Synthesis | Guarantees strict governance and pre-validated tool allowlists while allowing task-specific objective framing. |
| **3** | **Execution Concurrency** | **Strict Conservative Bounds (Max 5 nodes, sequential)** | Configurable Bounds (up to 10), Deep Decomposition | Protects local 8 GB GPU VRAM (RTX 5050) from OOM, eliminates semaphore contention, ensures deterministic auditability. |
| **4** | **Data & Context Flow** | **Explicit Typed Artifacts (Hashed & Schema-Validated)** | Filtered Markdown Summaries, Shared Blackboard State | Eliminates prompt pollution, enforces strict context budgets, and guarantees verifiable, immutable evidence records. |
| **5** | **Failure & Cancellation** | **Fail-Fast with Artifact Preservation** | Interactive Human Recovery, Best-Effort Partial Completion | Halts compromised execution immediately, marks dependents `BLOCKED`, protects system state, and preserves completed work. |
| **6** | **UI Representation** | **Hierarchical Fleet Stepper** | Tabbed Specialist View, Flat Unified Trace | Clear visual progression matching the DAG, intuitive status tracking, and seamless per-node artifact inspection. |
| **7** | **System Architecture** | **Native Modular Fleet Coordinator** | LangGraph Subgraphs, Linear Staged Pipeline | Zero heavy framework bloat, direct binding to existing `InferenceGuard` and `PermissionManager`, and 100% testable standard Python. |

---

## 5. System Architecture & Component Design

### 5.1 Subsystem Layout (`backend/app/agent/fleet/`)

```
backend/app/agent/fleet/
├── __init__.py
├── models.py          # FleetPlan, FleetNode, Artifact, FleetResult, FleetNodeState
├── validator.py       # DAGValidator (Kahn's topological sort, cycle & capability checks)
├── catalog.py         # Curated specialist profiles (Planner, Researcher, Coder, Verifier)
├── runtime.py         # AgentRuntime & AgentRuntimeFactory (scoped context & tool proxy)
└── coordinator.py     # FleetCoordinator (sequential scheduler, failure router, joiner)
```

### 5.2 Domain Models (`models.py`)

* **`FleetNodeState` (str, Enum):**
  * `QUEUED`, `READY`, `RUNNING`, `WAITING_APPROVAL`, `COMPLETED`, `BLOCKED`, `FAILED`, `CANCELLED`.
* **`Artifact` (BaseModel):**
  * `artifact_id`: UUID string.
  * `node_id`: Producing node identifier.
  * `producer_role`: Role of producer (e.g., `"researcher"`).
  * `schema_version`: e.g. `"1.0"`.
  * `content`: Structured dictionary / payload.
  * `content_hash`: SHA-256 hex digest of canonical JSON serialization.
  * `evidence_refs`: Optional list of tool execution or file references.
  * `created_at`: UTC timestamp string.
* **`FleetNode` (BaseModel):**
  * `node_id`: Unique identifier (e.g., `"research_codebase"`).
  * `role`: Key in specialist catalog (e.g., `"researcher"`).
  * `objective`: Scoped natural language directive.
  * `dependencies`: List of parent `node_id` strings required before this node can run.
  * `input_artifact_refs`: List of `artifact_id`s consumed by this node.
  * `capability_allowlist`: List of authorized tool names.
  * `token_budget`: Maximum token allotment (e.g., `2048`).
  * `state`: `FleetNodeState` (default `QUEUED`).
  * `result_artifact_id`: Optional string pointing to output artifact.
  * `error`: Optional error detail string.
* **`FleetPlan` (BaseModel):**
  * `fleet_id`: UUID string.
  * `parent_task_id`: Linked parent `AgentTask` ID.
  * `goal`: Overarching user goal.
  * `nodes`: Dict of `node_id` to `FleetNode`.
  * `max_nodes`: Integer limit (default: 5, hard ceiling: 5).
  * `version`: Schema version `"1.0"`.
* **`FleetResult` (BaseModel):**
  * `fleet_id`: Linked fleet ID.
  * `node_outcomes`: Dict mapping `node_id` to terminal `FleetNodeState`.
  * `artifacts`: List of generated `Artifact` objects.
  * `summary`: Synthesized final narrative summary.
  * `is_verified`: Boolean indicating audit/verification status.

### 5.3 Deterministic DAG Validator (`validator.py`)

Before any execution occurs, `DAGValidator.validate(fleet_plan, tool_registry)` enforces:
1. **Node Count:** Enforces $1 \le \text{len}(nodes) \le 5$.
2. **Referential Integrity:** Ensures every dependency declared in `node.dependencies` exists in `fleet_plan.nodes`.
3. **Cycle Detection & Topological Ordering:**
   * Uses Kahn’s algorithm (in-degree resolution).
   * If the number of sorted nodes does not equal the total node count, raises `DAGCycleDetectedError`.
   * Returns a deterministic linear topological order for execution.
4. **Capability Containment:** Ensures every capability in `node.capability_allowlist` exists in the specialist profile's locked list and is registered in the backend `ToolRegistry`.

### 5.4 Curated Specialist Catalog (`catalog.py`)

Pre-configured profiles in `SpecialistCatalog`:

| Role ID | Display Name | Purpose | Capability Allowlist | Default Budget |
| :--- | :--- | :--- | :--- | :--- |
| `planner` | Fleet Planner | Decomposes goals into `FleetPlan` DAGs | `[]` (Pure reasoning) | 2048 tokens |
| `researcher` | Code/System Researcher | Inspects repository, files, and system state | `["list_directory", "read_file", "search_files"]` | 2048 tokens |
| `coder` | Software Engineer | Implements code changes and runs build commands | `["read_file", "write_file", "execute_command"]` | 4096 tokens |
| `auditor_verifier` | Quality & Security Verifier | Validates postconditions, tests, and syntax | `["read_file", "execute_command"]` (Verification commands only) | 2048 tokens |

### 5.5 Isolated Agent Runtime (`runtime.py`)

* Created ephemerally by `AgentRuntimeFactory.create_runtime(node, input_artifacts)`.
* **Context Construction:** System prompt consists strictly of `Role Definition + Subtask Objective + Formatted Input Artifact Payloads`. Parent conversation and unrelated scratchpads are omitted.
* **Tool Proxy:** Exposes only tools present in `node.capability_allowlist`. Tool calls outside the allowlist are rejected immediately at the proxy.

### 5.6 Fleet Coordinator (`coordinator.py`)

* Receives validated `FleetPlan`.
* Maintains a topological ready-queue:
  1. Identifies nodes whose dependencies have reached `COMPLETED`.
  2. Transitions ready node from `QUEUED` → `RUNNING`.
  3. Acquires `InferenceGuard` (1 active inference lock).
  4. Runs step proposals through `PlanValidator`, `PermissionManager`, and `Executor`.
  5. If an approval is required, marks node `WAITING_APPROVAL` and pauses fleet safely.
  6. On successful step completion, packages output into an immutable `Artifact` with SHA-256 hash.
  7. Transitions node to `COMPLETED`, evaluates dependents, and unblocks the next node.
* **Failure Handling:**
  * Transient errors retry up to 2 times.
  * Permanent or uncertain errors mark the active node `FAILED`, immediately transition all downstream dependent nodes to `BLOCKED`, halt further execution, and return preserved artifacts.
* **Cancellation:** User cancellation terminates active processes cleanly and marks queued nodes `CANCELLED`.

---

## 6. WinUI 3 Desktop Control Plane Integration

1. **`FleetNodeViewModel.cs` (`Nexora.Core`):**
   * Exposes `NodeId`, `Role`, `State`, `StatusBadgeBrush`, `IsActive`, and `ArtifactSummaries`.
2. **`MainWindow.xaml` Stepper Bar:**
   * Embedded in the Task Details panel header.
   * Renders the DAG nodes horizontally with modern WinUI 3 badges (Checkmark for Completed, Blue Spinner for Running, Red Slash for Blocked).
   * Clicking a node filters the live step trace below and opens an artifact drawer.
3. **Task Composer Mode Switcher:**
   * Adds a subtle segmented selector: `[Auto Fleet (Default) | Single Agent]`.
4. **Companion Window:**
   * Surfaces active specialist and progress indicator (e.g., `Coder (Node 3/4)`).

---

## 7. Testing & Verification Matrix

| Suite | File | Test Cases |
|---|---|---|
| **Models** | `test_fleet_models.py` | Schema validation, SHA-256 hashing, immutability, serialization. |
| **DAG Validator** | `test_dag_validator.py` | Topological sort, 2-node/3-node cycles, self-loops, missing dependencies, $>5$ nodes, unregistered capabilities. |
| **Catalog** | `test_fleet_catalog.py` | Profile lookups, capability containment, context budgets. |
| **Runtime** | `test_fleet_runtime.py` | Zero memory bleed, tool proxy enforcement, token limit injection. |
| **Coordinator** | `test_fleet_coordinator.py` | Topological dispatch, `InferenceGuard` locking, approval pause/resume, fail-fast downstream blocking, cancellation. |
| **Backward Compatibility** | `test_backward_compat.py` | Verifies existing single-agent tasks and snapshots run identically. |
| **Desktop Tests** | `FleetViewModelTests.cs` | ViewModel state mapping, badge styling, artifact binding. |

---

## 8. Implementation Sequence

1. **Step 1:** Implement `models.py` and `validator.py` with 100% unit test coverage (`test_fleet_models.py`, `test_dag_validator.py`).
2. **Step 2:** Implement `catalog.py` and `runtime.py` with mock specialist tests (`test_fleet_catalog.py`, `test_fleet_runtime.py`).
3. **Step 3:** Implement `coordinator.py` with sequential topological execution and failure blocking (`test_fleet_coordinator.py`).
4. **Step 4:** Integrate `FleetCoordinator` into `AgentOrchestrator` and `StateManager`.
5. **Step 5:** Extend WinUI 3 Desktop Control Plane (`FleetNodeViewModel`, `MainWindow.xaml` Stepper Bar).
6. **Step 6:** End-to-end multi-node integration test run and verification report.
