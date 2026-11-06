# Module 03 — Dynamic Agent Fleet and DAG Runtime

## Responsibility

Create bounded task-specific specialist runtimes, validate their dependency DAG and coordinate their structured results. It owns agent lifecycle and artifact flow, while state changes, side effects and permissions remain owned by existing central services.

## Rules

Each agent has one bounded objective, one profile, minimum required context, fixed skill/capability set, maximum inference/token/time budget and output schema. It may propose work but cannot mutate global policy, execute tools directly, grant capabilities, install components or create unlimited children. The orchestrator owns dependencies, scheduling, cancellation, error propagation and joins.

## DAG validation

Require unique node IDs, a single parent task, acyclic dependency graph, present dependencies, bounded node/delegation count, installed enabled profiles, capability compatibility, output schemas and budget sums. Reject any node that depends on unknown/unverified artifact or requests an unregistered capability. Store deterministic topological order for reproducibility.

## Artifact contract

Artifacts are immutable: producer, input refs, schema version, content hash, sensitivity, evidence refs and status. Dependents receive only artifact references/content allowed by policy. A model-written summary is an artifact, not proof. Verification evidence is separate.

## Execution policy

Start sequentially. Execute a ready node, validate its output, record artifact, then unblock dependents. A failed/uncertain node blocks required descendants. Approval pauses work safely. Cancellation reaches queued/running node boundaries. On restart, follow existing interrupted-task behavior and never replay uncertain side effects.

## Tests

Cover valid DAGs, cycles, missing node/profile, budget exhaustion, context isolation, artifact tampering, cancellation, approval pause, retry propagation, restart snapshots and inference guard behavior.
