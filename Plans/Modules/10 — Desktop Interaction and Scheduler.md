# Module 10 — Desktop Interaction and Scheduler

## Responsibility

Define two late-stage controlled capabilities: Windows visual/UI interaction and time-based task dispatch. Both must enter existing permission/task/audit/verification pathways.

## Desktop interaction rules

Use accessibility APIs before coordinate clicking. Bind every observation/action to a positively identified authorized window/process. Captures are user-scoped, redacted/expired evidence; no always-on recording or keylogging. Model proposes a bounded action/expected postcondition; service validates target and current focus, permission approves it, executor acts once, verifier re-observes. Focus mismatch or ambiguous result stops execution as uncertain. External side effects require sensitive approval.

## Scheduler rules

Schedules contain task template, timezone, recurrence, next/last run, missed-run policy, concurrency, owner and notification policy. Each dispatch creates a normal AgentTask and recomputes permissions. Prior approval never authorizes a future sensitive side effect. Changed task/capability/profile/template invalidates the schedule for review. Restart does not replay uncertain runs; prevent overlaps/duplicate run keys.

## Tests

Desktop fixture tests cover target identity, focus change, redaction, cancellation/emergency stop and postcondition. Scheduler clock tests cover recurrence, timezone/DST, missed/restart behavior, approval per run, overlap and task capacity.
