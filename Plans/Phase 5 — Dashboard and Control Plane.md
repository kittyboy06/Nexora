# NEXORA — Phase 5: Native Windows Shell and Control Plane

> The filename is retained for roadmap continuity. This phase specifies a native C#/.NET WinUI 3 Windows shell, not a web dashboard.

## Purpose

Build the first user-facing native Windows application for NEXORA. It must let the user understand the system, submit work, observe deterministic task progress, approve sensitive actions, choose model profiles, inspect evidence and use an optional corner companion. It is a control plane over the FastAPI backend, not an execution authority.

## Prerequisites

- Inspect and preserve all Phase 0–3 backend endpoints and tests.
- Verify Phase 4 profile routing before exposing profile selection in the UI.
- Read `Modules/01 — Governance, Permissions, Audit and Verification.md`, `Modules/09 — Native Control Plane and API Client.md`, and `Modules/11 — Native Windows Shell.md`.
- Do not begin work on browser control, MCP installation, generated tools, memory editing, desktop automation or scheduling in this phase.

## Product experience

On launch, the user should see whether the local backend and Ollama are available, which models and profiles can run, and whether a task needs attention. The main screen presents a natural-language goal field. A task detail view shows the selected profile, current state, steps, outputs, verification evidence, approval request, and failure/uncertainty reason in plain language.

The user can submit a task, choose automatic routing or a named profile, cancel a running task, approve/reject a sensitive action, and inspect historical task records. The user must never be led to believe approval is blanket authorization: approval views show the exact tool, arguments, reason, affected scope, and expiry.

## Scope

### Included

- C#/.NET WinUI 3 application in `desktop/`.
- Typed local API client for existing backend REST endpoints; preserve loopback FastAPI contracts.
- Dashboard status panel for shell/backend/Ollama/model availability and a backend supervisor.
- Chat/goal composer with automatic routing and manual profile override.
- Task list, task detail, step trace, outputs and error display.
- Approval inbox with approve/reject actions for an exact pending action.
- Model/profile availability view based on `/api/ollama/profiles`.
- Task cancellation and refresh/retry display states.
- Optional always-on-top corner companion with task status, quick capture, pause/cancel and open-dashboard controls.
- Native system tray, notifications and opt-in global hotkeys.
- Local settings screen for non-secret shell preferences only.
- Accessible loading, offline, error, empty and reconnect states.
- Responsive desktop-first layout and keyboard navigation.

### Excluded

- Authentication or network exposure beyond localhost.
- Secret editing/storage in shell settings.
- New execution paths or client-side permission checks.
- Electron, React or a browser-hosted frontend as the primary application.
- MCP installation, agent DAG controls, durable memory editing or scheduling screens.
- A claim of real-time streaming until backend event delivery exists and has been tested.

## User flows

### Submit a task

1. User writes a goal and may select `Automatic` or an installed specialist profile.
2. Native shell validates only basic required fields and calls the backend.
3. Backend creates the task; UI shows its server-assigned ID and initial state.
4. UI refreshes task status on a bounded polling interval. It stops polling terminal tasks or when navigating away.
5. The task page displays status transitions, selected profile/model when available, step execution evidence, and final report.

### Review approval

1. Polling discovers a task in `WAITING_APPROVAL`.
2. UI displays task goal, step description, tool, normalized arguments, risk, expiry and why approval is needed.
3. User approves or rejects one action. The client includes the exact approval ID supplied by backend.
4. Backend validates expiry and argument hash; UI renders accepted, rejected, expired, or invalidated result exactly as returned.
5. The UI never caches an approval as reusable.

### Diagnose unavailable local AI

1. Status panel distinguishes backend reachable from Ollama reachable and configured model available.
2. It shows actionable local guidance sourced from backend diagnostic fields.
3. It does not infer that a model is available merely because a profile is configured.

## Native shell architecture

```text
desktop/
├── Nexora.Desktop/           # WinUI 3 application
│   ├── Views/                # Dashboard, task, approval, profile and settings views
│   ├── ViewModels/           # Presentation state and commands
│   ├── Services/             # Backend client, supervisor, tray, notifications, settings
│   ├── Capture/              # Native capture broker and redaction handoff
│   ├── Interop/              # Narrow Win32/WinRT adapters
│   └── Models/               # Typed API and local UI models
└── Nexora.Desktop.Tests/     # Unit, contract and UI fixture tests
```

Use one controlled local API endpoint. Keep transport/error behavior in one C# client service. Make backend response models the source for C# contracts; do not hand-copy assumptions without a contract update. The shell starts and observes the local backend but never implements a second task executor.

## Backend additions allowed in this phase

Add only read-oriented or event-oriented endpoints needed by the UI, preserving existing contracts. Candidate additions are a versioned system-info endpoint, a structured task event endpoint, and pagination/filtering for historical tasks. For each addition, define Pydantic models, authorization behavior, error response, API tests, and native shell use before implementation.

Server-Sent Events or WebSockets are optional. Start with polling while the task volume is low. If events are added, define connection lifecycle, reconnect/backoff, event IDs, replay limitations, terminal cleanup, and behavior when the backend restarts.

## Security and privacy requirements

- Bind native shell/backend communication to localhost by default.
- Treat rendered tool output and model output as text; do not inject HTML from them.
- Do not log task content in third-party analytics; no third-party analytics in the local app.
- Do not store API credentials, approvals, or sensitive task data in local shell settings by default.
- Show sensitive tool arguments carefully: redaction from backend takes precedence, and client must not reconstruct/redact poorly.
- Every approval and task command must be sent to backend; no UI-only authorization state.

## Test plan

- Unit test API error normalization, status rendering, profile selection, terminal-state polling stop, approval expiry display and sanitized output rendering.
- Native UI test keyboard navigation, focus movement into approval dialog, disabled states during submit, and error recovery.
- Contract test create/list/get/cancel/approve against mocked FastAPI backend responses.
- Windows fixture test tray/companion behavior, always-on-top toggle, notifications and backend restart/offline handling.
- End-to-end local test: submit a mock task, observe state transition, approve a mocked sensitive step, see final result.
- Manually verify backend reconnect behavior and that no approval action is double-submitted.

## Acceptance criteria

- User can operate all existing agent task endpoints without a terminal.
- Native dashboard accurately distinguishes shell/backend/Ollama/model states.
- Task and approval screens are derived from backend data and correctly handle errors and expiry.
- Manual profile override is available only for profiles backend reports as available.
- Existing backend tests remain passing; native shell has a documented build/test/package path.
- The implementation report identifies which tests were run and whether a live Ollama task was actually verified.

## Implementation sequence

1. Scaffold the WinUI 3 shell and show a health/status window with mocked tests.
2. Add backend supervisor and typed client, then task create/list/detail views.
3. Add polling lifecycle and terminal/error states.
4. Add approval/rejection flow, task cancellation, tray and companion window.
5. Add profile status/manual selection and native capture-picker architecture.
6. Perform accessibility, Windows integration and packaging pass; update documentation.
