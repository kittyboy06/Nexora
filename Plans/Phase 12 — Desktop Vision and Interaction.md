# NEXORA — Phase 12: Desktop Vision and Interaction

## Purpose

Add bounded Windows visual understanding and UI interaction after browser, permissions, verification and dashboard controls are mature. This is a high-impact capability: it must require explicit scope, visible feedback and strong stop controls.

## Prerequisites

- Read `Modules/10 — Desktop Interaction and Scheduler.md` and `Modules/01 — Governance, Permissions, Audit and Verification.md`.
- Write a Windows automation/vision technology decision covering accessibility APIs, screenshot service, target-window binding, input control, privacy and emergency stop.
- Browser interactions and approval UX should be stable first.

## Scope

- Capture broker that can obtain a user-authorized window or screen image with redaction, size limits and short-lived retention.
- Vision profile routing for approved images and structured visual observation output.
- Window discovery/selection and target binding by process/window identity, not uncontrolled coordinates.
- Accessibility-first read/action adapters where supported; constrained mouse/keyboard actions only when necessary.
- Typed desktop actions: focus known window, inspect tree, click approved target, type bounded text, scroll bounded region, wait for observable state.
- Action preview and confirmation where policy requires it; immediate cancellation/emergency stop; post-action verification screenshot/accessibility query.
- Audit records linking target, screenshot hash/redaction status, action, approval, result and verification.

## Excluded

- Always-on screen recording, covert capture, keylogging, broad clipboard capture or background visual monitoring.
- Reading arbitrary protected/password fields.
- Unbounded coordinate clicks, actions on an unknown foreground window or using vision output as unquestioned authority.
- Sending screenshots/content to external services by default.

## Permissions and privacy

Capturing a screen/window and interacting with desktop UI are controlled actions; operations that can send data, delete/overwrite, submit forms, change settings, make purchases or operate a signed-in account are sensitive. Bind approval to a target window/app and exact action intent. Require fresh approval if focus/app identity changes unexpectedly.

Screenshots are sensitive task evidence. Store only if required for verification/audit, use redaction/expiry, expose user controls, and never persist them in durable memory by default. Do not capture credential dialogs or password managers; detect likely sensitive windows and fail closed.

## Action lifecycle

1. Agent proposes typed action with target application/window and expected postcondition.
2. Deterministic service resolves target and checks policy/allowlist.
3. User approval is requested when required; UI presents target and intent.
4. Capture/accessibility service obtains fresh observation and confirms target identity.
5. Executor performs one bounded action.
6. Service re-observes target and verifies postcondition. Unexpected focus, missing target or ambiguous result becomes `UNCERTAIN` and stops the plan.

## Test plan

- Mock adapters for window identity, target mismatch, focus change, timeout, cancellation, screenshot redaction and action verification.
- Windows test application fixtures for basic accessibility paths; no tests against personal apps/accounts.
- Approval and sensitivity escalation tests.
- Screenshots retention/deletion tests and forbidden sensitive-window behavior.
- Emergency-stop test proves queued actions cannot continue after cancellation.

## Acceptance criteria

- NEXORA acts only on authorized, positively identified target windows.
- Each visual/UI action has a bounded intent, evidence and postcondition check.
- Sensitive screen data is minimized, redacted and retained only by policy.
- Focus ambiguity prevents action rather than guessing.

## Implementation sequence

1. Decide accessibility/capture/automation stack and privacy model.
2. Build window identity and observation-only service.
3. Add screenshot handling/redaction/expiry and dashboard preview.
4. Add one safe accessibility-based action with verification.
5. Add constrained input/vision actions after mock and fixture tests.
6. Add emergency-stop and complete Windows live validation.
