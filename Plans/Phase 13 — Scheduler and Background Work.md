# NEXORA — Phase 13: Scheduler and Background Work

## Purpose

Enable user-created recurring or delayed tasks without weakening permissions or duplicating side effects. Each schedule invocation becomes a governed NEXORA task with its own audit record and fresh policy evaluation.

## Prerequisites

- Read `Modules/10 — Desktop Interaction and Scheduler.md` and `Modules/01 — Governance, Permissions, Audit and Verification.md`.
- Decide scheduler library/runtime, persistent storage, timezone behavior, missed-run policy, startup recovery and notification approach.
- Task interruption and approval behavior from existing phases must be verified.

## Scope

- Persistent schedule record with task template, enabled state, timezone, recurrence, next/last run, missed-run policy, concurrency policy, owner, retention and notification preference.
- Dashboard create/edit/pause/resume/delete/inspect controls with human-readable next-run preview.
- Scheduler service that creates ordinary `AgentTask` instances under existing TaskManager/permissions/audit flow.
- Per-run budget, model/concurrency/queue policy and duplicate-run prevention.
- Run history and clear status for skipped, blocked, waiting approval, completed, failed, cancelled and interrupted runs.
- Restart reconciliation that avoids duplicate or silent replay of uncertain runs.

## Excluded

- A task-level approval acting as permanent authorization for future sensitive actions.
- Hidden continuous monitoring or arbitrary autonomous loops.
- Running more tasks than current hardware guards allow.
- Scheduling from text alone without a user-confirmed schedule record.

## Approval rule

Scheduling a sensitive capability does not grant permission for every future execution. For every run, central policy recalculates risk and prompts for fresh exact approval when required. Safe/controlled operations may run according to explicit user policy, but any changed plan, model profile, capability version, target scope or task template invalidates prior schedule assumptions and pauses/reviews the schedule.

## Time and restart semantics

Store timezone explicitly, defaulting to the user's chosen local zone. Define whether missed runs are skipped, run once on startup, or require user review; default to skip/notify for actions with side effects. Store idempotency/run keys. If the process stops during a run, preserve existing `INTERRUPTED` safety semantics and do not auto-replay an uncertain action. Prevent overlapping instances unless a future safe concurrency policy allows them.

## Test plan

- Clock-controlled tests for one-time, recurring, paused, edited, disabled and deleted schedules.
- Timezone/DST boundaries, clock jump, missed run and restart tests.
- Duplicate-run/overlap prevention and task capacity limits.
- Sensitive approval on every run; changed template/capability invalidation.
- Notifications/status/audit history and cancellation tests.

## Acceptance criteria

- Users can understand exactly when a schedule will run and what it can do.
- Every invocation enters normal task/permission/audit flow.
- No sensitive action runs merely because a similar earlier run was approved.
- Restart, missed-run and timezone behavior are predictable and tested.

## Implementation sequence

1. Decision record and schedule schemas with clock-based unit tests.
2. Persist/display schedule CRUD without executing tasks.
3. Add safe one-time task dispatch and run history.
4. Add recurrence/timezone/missed-run behavior.
5. Add approval/resume/notification behavior.
6. Run opt-in local schedule test and document evidence.
