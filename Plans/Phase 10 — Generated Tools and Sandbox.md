# NEXORA — Phase 10: Generated Tools and Sandbox

## Purpose

Allow NEXORA to propose a missing capability only when no approved tool solves the task, then validate and run that capability in a real isolated sandbox. This phase must prove containment before it enables useful generated code. A generated tool never runs in the FastAPI process or with ambient user permissions.

## Prerequisites

- Read `Modules/07 — Generated Tool Sandbox.md` and `Modules/01 — Governance, Permissions, Audit and Verification.md`.
- Select a Windows-capable sandbox approach in a written decision record. It must cover process isolation, filesystem boundary, network policy, resource limits, cleanup and known escape limitations.
- Existing executor/permission/audit contracts are passing.

## Scope

### Included

- Capability gap assessment that proves no approved tool or MCP capability is adequate.
- Typed generated-tool proposal: purpose, inputs/outputs, dependencies, requested filesystem/network/process capabilities, tests, verification method and source code.
- Static policy validation before execution: permitted language/runtime, import/dependency allowlist, no shell escape, no undeclared networking, no privileged APIs, no ambient secret access, bounded source/dependency size.
- Real sandbox runner with isolated disposable working directory, denied-by-default host/network access, CPU/memory/time/output/process limits, structured results and forced cleanup.
- Test generation/execution inside sandbox, including negative tests and expected postcondition checks.
- Review/approval record for enabling a validated version as a registered capability.
- Versioned registry, disable/revoke/remove/rollback, audit and retention controls.

### Excluded

- Running generated Python/JavaScript in backend process.
- Letting a model install arbitrary dependencies or use `pip`, `npm`, shell or Docker without an explicit reviewed sandbox policy.
- Retaining generated code after one successful run without review.
- Claiming a virtual environment alone is an adequate security sandbox.

## Lifecycle

1. Planner identifies a concrete capability gap and provides a typed specification.
2. Deterministic policy checks determine whether generation is allowed for the task.
3. Model produces proposal code and explicit manifest. Parse it without executing it.
4. Static validator rejects code/manifests that violate policy or request undeclared privileges.
5. User sees what the tool proposes to do and requested access. Sensitive generation/execution decisions require approval under central policy.
6. Sandbox runner creates a new disposable environment; mounts only task input/work directories; applies resource and network constraints.
7. Runner executes a known test set and a limited task trial. All outputs are captured/redacted and sandbox is destroyed.
8. Verifier evaluates observable result/evidence. Failure, timeout, crash or uncertainty never triggers an automatic host retry.
9. Human review decides whether the exact hashed version is a one-off result, a disabled draft, or an approved reusable capability.
10. Only an approved version can be represented in ToolRegistry, with normal schema/risk/permission rules.

## Sandbox design requirements

The decision record must state exactly what isolates the code, which host directories can be read/written, network default, process/account privileges, container/VM image origin, logging behavior, time/memory/CPU/pid quotas, cleanup strategy, escape-response plan and limits. If any required control cannot be enforced on the laptop, that action type must be refused rather than weakened silently.

Tool code sees explicit inputs and a working directory only. It does not receive database, task-store, browser profile, credentials, backend source tree, user home directory, registry, Windows application handles or internal API tokens. Tool output is treated as untrusted data.

## Data contracts

Define `GeneratedToolProposal`, `GeneratedToolManifest`, `SandboxPolicy`, `SandboxRun`, `SandboxEvidence`, `GeneratedToolReview`, and `GeneratedToolVersion`. Include immutable content hash, parent task, requested/approved scopes, runtime image version, resource limits, start/end timestamps, exit state, redacted logs, produced artifact hashes, verification result, reviewer and retention status.

## Test plan

- Static rejection: shell escape, dangerous imports, undeclared network, path traversal, oversized source, dependency confusion, malformed manifest.
- Sandbox containment: no access outside mount, no network when disabled, time/memory/output limits, child process cleanup, failure cleanup and repeated fresh environment.
- Capability lifecycle: proposal → review → sandbox run → rejected/approved → disabled/revoked/rollback.
- Approval hash/version binding and audit completeness.
- Adversarial escape attempts suitable to selected sandbox technology. Record limitations and do not describe this as a complete security guarantee.

## Acceptance criteria

- Generated code cannot reach the backend process, user files or network unless explicit sandbox policy exposes a narrow scope.
- Every run is disposable, resource-bounded and audit-recorded.
- Passing a test does not make code reusable without review/approval.
- A missing or failed sandbox is a safe blocker, not a reason to execute on host.

## Implementation sequence

1. Write sandbox technology decision and threat model.
2. Build manifest/schema and static validator with negative tests.
3. Implement no-network disposable sandbox runner and containment tests.
4. Add runner evidence, cleanup and dashboard review view.
5. Add controlled one-off generation flow.
6. Add reviewed registry retention and rollback only after evidence is solid.
