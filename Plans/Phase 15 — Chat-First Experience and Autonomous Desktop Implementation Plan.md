# NEXORA Phase 15 — Chat-First Experience and Autonomous Desktop Implementation Plan

## Status

**Implementation plan only. Do not treat checkboxes as completed until code, tests, and live validation provide evidence.**

## Delivery Strategy

Deliver Phase 15 as small vertical slices. Each slice must preserve the existing native WinUI 3 + FastAPI architecture and leave an auditable, working route through the central permission service. Do not start autonomous desktop work before the session, stop, focus-guard, and evidence controls are complete.

## Workstream 0 — Baseline and Contracts

### Objectives

- Establish a truthful Phase 15 baseline.
- Define durable contracts before UI wiring.
- Prevent breaking Phase 0–14 records or endpoints.

### Tasks

- [ ] Run and record the current backend, desktop, security, and packaging checks before Phase 15 work.
- [ ] Add a Phase 15 architecture decision record for chat persistence, conversation retention, and cancellation behavior.
- [ ] Add versioned Pydantic/C# DTOs for `Conversation`, `ConversationMessage`, `ConversationWorkItem`, and `ConversationEvent`.
- [ ] Define status transitions and idempotency rules for every work-item type.
- [ ] Define a redaction contract: chat transcript, screenshot references, MCP manifests, errors, and tool output must use the existing secret-scrubbing boundary before display or persistence.
- [ ] Add migration/recovery tests for old task JSON files and new conversation/work-item files.

### Exit criteria

- Contract tests prove serialization compatibility in Python and C#.
- A missing/corrupt Phase 15 record fails safely without affecting Phase 2 task recovery.

## Workstream 1 — Chat-First Landing Vertical Slice

### Objectives

Create a useful local chat landing screen without operational side effects.

### Backend tasks

- [ ] Add durable conversation storage under the local data root, separate from task state.
- [ ] Add APIs: create/list/get conversation, append message, cancel generation, and stream/gather local-model response.
- [ ] Reuse the provider-independent Ollama-first model interface and existing inference guard.
- [ ] Store model/profile/routing metadata with each assistant response.
- [ ] Implement answer-only mode; it must never create an agent task.

### WinUI tasks

- [ ] Make Chat the default selected navigation destination.
- [ ] Build conversation list, message transcript, composer, send/cancel/retry controls, and profile override selector.
- [ ] Render safe Markdown as text/approved formatting only; do not render active HTML or execute links automatically.
- [ ] Show offline/Ollama-unavailable states without losing the operator draft.

### Tests

- [ ] Backend: conversation persistence, message ordering, cancellation, routing metadata, unavailable-model failure.
- [ ] Desktop: default navigation, composer command state, streaming state, retry/cancel behavior.
- [ ] Integration: one ordinary question receives a chat response and creates no `AgentTask`.

### Exit criteria

- A user can open the app, ask a general question, receive a local answer, and reopen the conversation after restart.

## Workstream 2 — Intent Routing and Work Cards

### Objectives

Connect chat to existing modules through durable, visible handoffs.

### Tasks

- [ ] Implement deterministic intent proposal using structured local-model output plus fallback rules.
- [ ] Add Auto route and explicit modes: Answer only, Create task, Research, Skill import, MCP onboarding, Desktop Vision, Schedule.
- [ ] Add `ConversationWorkItem` creation and event recording.
- [ ] Adapt existing TaskManager submission to accept source conversation/message IDs without changing its authorization behavior.
- [ ] Add work-card UI with destination, summary, routing, status, approval state, and navigation link.
- [ ] Send module lifecycle events back to the conversation through a central event publisher.
- [ ] Ensure duplicate retries cannot create duplicate tasks or schedules.

### Tests

- [ ] Auto route creates a task only for a structured actionable intent.
- [ ] Explicit Answer only overrides classifier output.
- [ ] Work cards remain linked after process restart.
- [ ] Approval, completion, cancellation, and failure generate one ordered chat event each.

### Exit criteria

- One chat request can create and monitor a normal agent task end-to-end without duplicating task state.

## Workstream 3 — Skill Import and GitHub Preview

### Objectives

Provide safe, operator-controlled skill acquisition.

### Tasks

- [ ] Define an `ImportedSkillCandidate` lifecycle separate from installed skill bundles.
- [ ] Implement folder picker and an Explorer “Open Skills Folder” command through a constrained desktop command broker.
- [ ] Implement paste-based draft validation.
- [ ] Add a folder scanner that restricts paths to the chosen root and validates `manifest.json` + `SKILL.md` sizes, encoding, IDs, versions, and hash.
- [ ] Add GitHub README retrieval, selected-ref resolution, source file hashes, and sanitized Markdown rendering.
- [ ] Add review screen: provenance, ref, hashes, manifest, instructions, README, and declared target roles.
- [ ] Install candidates disabled by default; require explicit enablement before selective skill injection.
- [ ] Document import conflict handling and rollback.

### Tests

- [ ] Reject traversal/symlink escape, malformed manifests, oversized files, and duplicate version collisions.
- [ ] Verify a repository preview renders README but does not install or execute content.
- [ ] Verify import defaults to disabled and is excluded from prompt injection until enabled.

### Exit criteria

- The operator can safely import a local or GitHub-discovered skill and inspect all source content before enabling it.

## Workstream 4 — MCP Onboarding Wizard

### Objectives

Make MCP setup understandable while retaining immutable approval and central authorization.

### Tasks

- [ ] Add candidate records for manual, repository-assisted, and chat-assisted sources.
- [ ] Add repository inspector restricted to documentation/config retrieval; do not run package installs or server commands.
- [ ] Extract a proposed command/arguments only as a draft, annotated with source file and line/reference.
- [ ] Fingerprint the reviewed launch manifest: executable, arguments, directory, environment key names, and source ref.
- [ ] Make approval bind to that fingerprint and revoke approval on any change.
- [ ] Add bounded test connection: launch, initialize, tools/list, optional ping, shutdown.
- [ ] Classify all newly discovered tools as Sensitive by default.
- [ ] Require a separate approval to call any test tool; only allow explicitly designated non-mutating tools in test mode.
- [ ] Surface lifecycle, errors, advertised tools, and audit references in chat and the MCP page.

### Tests

- [ ] Repository URL produces an unapproved draft, never a process launch.
- [ ] Launch-manifest modification invalidates approval.
- [ ] Test connection discovers tools but invokes none.
- [ ] Unclassified tool call waits for approval even when controlled auto-approval is enabled.

### Exit criteria

- An MCP can be configured and tested without allowing README text, a repository, or a discovered tool to bypass approval.

## Workstream 5 — Desktop Vision Session Foundation

### Objectives

Establish the safety envelope required before autonomous action.

### Tasks

- [ ] Define durable `DesktopSession` and `DesktopAction` models with task/chat links.
- [ ] Add explicit session start dialog with target, duration, action budget, capture policy, and allowed categories.
- [ ] Add session state: Draft, AwaitingApproval, Active, Paused, WaitingApproval, Completed, Failed, Stopped, Expired.
- [ ] Bind every capture, inspect, and interaction to an active session and target window identity.
- [ ] Implement global emergency stop from the task page, companion, and chat. It must revoke queued actions.
- [ ] Extend `WindowFocusGuard` checks to every loop iteration and immediately before execution.
- [ ] Record screenshot/UI-tree evidence by reference in quarantine; enforce retention and redaction policy.
- [ ] Add desktop panel status: target, capture indicator, action count, timer, pause/resume, stop, and last verification.

### Tests

- [ ] No capture/action occurs without an active session.
- [ ] Focus change, protected process, UAC, or ambiguous target pauses/fails closed.
- [ ] Stop revokes an in-flight/queued next action safely.
- [ ] Sensitive interaction transitions to existing approval state with immutable arguments.

### Exit criteria

- A session can safely start, show its state, pause, stop, and persist audit evidence, without autonomous looping yet.

## Workstream 6 — Bounded Autonomous Desktop Loop

### Objectives

Enable complete safe-window desktop tasks under the session contract.

### Tasks

- [ ] Implement loop controller: capture → inspect → plan next action → policy/focus check → authorize → execute → verify.
- [ ] Define explicit confidence thresholds and retry limits for vision/UI target selection.
- [ ] Enforce duration and action budgets server-side, not only in the UI.
- [ ] Keep automation to one approved target window by default; focus/window identity change pauses session.
- [ ] Classify text input, file selection, download, external submit, clipboard, login, and destructive controls as Sensitive.
- [ ] Add deterministic postcondition validators for common actions (window state, selected element, visible success/error cue).
- [ ] Publish concise action/verification events to the task timeline and originating chat.
- [ ] Run live validation only on an approved non-sensitive fixture application.

### Tests

- [ ] Unit tests for budget, timeout, confidence, target mismatch, retry, and emergency-stop transitions.
- [ ] Integration tests with a fixture UI for a successful safe workflow.
- [ ] Live opt-in tests for capture and UI Automation, clearly separated from hermetic tests.
- [ ] Security regressions for protected windows, password-like fields, and cross-window handoff.

### Exit criteria

- NEXORA completes a documented safe fixture workflow autonomously, creates verification evidence, and stops safely under every termination condition.

## Workstream 7 — Release, Documentation, and Migration

### Tasks

- [ ] Update README, release notes, architecture index, API guide, and privacy/security documentation.
- [ ] Add migration notes for existing users and an explicit rollback path for conversation/work-item data.
- [ ] Update backup/restore inclusion and redaction rules for Phase 15 data.
- [ ] Update doctor and test-matrix scripts with offline vs live classifications.
- [ ] Verify native deployment includes all desktop and backend assets needed for the Phase 15 features.
- [ ] Perform a final audit of API contracts, authorization paths, runtime-data exclusion, package contents, and UI navigation.

## Required Decision Checkpoints

Do not silently choose these during implementation:

1. Conversation retention duration and delete/export UX.
2. Whether chat supports file attachments in 1.2 or text/links only.
3. Exact trusted GitHub sources or whether all repositories remain user-selected.
4. Whether an MCP repository installer is ever supported; Phase 15 default is **no automatic install**.
5. Which MCP test tools can be treated as non-mutating.
6. Exact emergency-stop keyboard shortcut.
7. Whether continuous screen capture is allowed at all, and its retention period.
8. Approved fixture applications for live Desktop Vision validation.

## Overall Definition of Done

- Chat is the stable landing experience and drives existing modules through auditable work items.
- Skills and MCP onboarding are review-first and never execute imported/repository content automatically.
- GitHub previews visibly include sanitized README content and immutable provenance.
- Desktop Vision autonomy is bounded to approved sessions, target windows, budgets, evidence, and the existing central authorization system.
- All new backend and desktop tests pass; live browser/MCP/desktop checks are reported separately from hermetic tests.
- Documentation accurately identifies provisional defaults and unverified live behavior.
