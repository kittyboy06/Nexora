# NEXORA — Phase 5 Design Specification
## Native Windows Shell and Control Plane

**Document Type:** Technical Design Specification  
**Project:** NEXORA — Local Autonomous Intelligence  
**Phase:** 5 — Native Windows Shell and Control Plane  
**Status:** Validated Design (Ready for Implementation Planning)  
**Date:** 6 November 2026  

---

## 1. Understanding Summary

* **What is being built:** A native Windows 11 desktop application (`NEXORA.exe`) written in C# using .NET 8 and WinUI 3 (Windows App SDK in unpackaged mode), located in `desktop/Nexora.Desktop/`.
* **Why it exists:** Provides a responsive, first-class native Windows user interface to interact with NEXORA: natural language task submission, live step-by-step progress observation, explicit human approval for sensitive actions, model/profile selection, and status diagnostics without requiring a command prompt or browser.
* **Who it is for:** Single-user local desktop operator on Windows 11.
* **Key constraints:**
  * **Strict loopback communication:** Binds strictly to `http://127.0.0.1:8000`; no external network exposure or telemetry.
  * **Zero execution authority in C#:** The WinUI 3 shell is strictly a control and presentation plane. All task planning, validation, permissions, tool execution, and verification remain 100% authoritative in the Python/FastAPI backend.
  * **Development packaging:** Unpackaged mode (`<WindowsPackageType>None</WindowsPackageType>`) for clean command-line compilation (`dotnet build` / `dotnet run`) without requiring self-signed test certificates.
  * **Supervised lifecycle:** Automatically detects an existing backend or launches `python -m uvicorn backend.app.main:app --port 8000` as a monitored child process with health checks.
  * **Polling synchronization:** 500ms–1000ms polling while a task is running, automatically stopping on terminal states (`COMPLETED`, `FAILED`, `CANCELLED`).
  * **Exact approvals:** Approval cards display the exact tool, parameters, risk level, expiry, and argument hash. Approvals are sent to the backend with exact approval IDs and are never cached.
* **Explicit non-goals:**
  * No Electron or browser-hosted web apps as the primary desktop interface.
  * No desktop automation or screen-capture implementation in this initial UI milestone (reserved for Phase 12).
  * No client-side secret storage.

---

## 2. Assumptions & Risks

### Assumptions
1. **Host Environment:** .NET 8 SDK will be installed on the machine via `winget install Microsoft.DotNet.SDK.8`.
2. **Framework & Tooling:** Windows App SDK (WinUI 3) configured in unpackaged mode with `CommunityToolkit.Mvvm` and `System.Net.Http.Json`.
3. **Phased Sequencing:**
   * **Stage 1:** Backend supervisor, typed API client, Status Panel, Task Composer, and Task Detail / Approval Dialog (Main Dashboard Window).
   * **Stage 2:** System Tray, native toast notifications, and Always-on-top Corner Companion Window.

### Key Risks & Mitigations
* **Risk: Backend child process remains orphaned on shell exit.**
  * *Mitigation:* `BackendSupervisor` hooks `App.Current.Exit` and process termination events to send SIGINT/SIGTERM or terminate the process tree cleanly.
* **Risk: UI thread stuttering or blocking during network polling.**
  * *Mitigation:* Pure `async/await` with `HttpClient` on background thread pool, dispatching UI state changes via WinUI's `DispatcherQueue`.
* **Risk: User accidentally submits duplicate tasks on multiple clicks.**
  * *Mitigation:* `TaskComposerViewModel.SubmitTaskCommand` disables the submit button immediately upon invocation via `IsBusy` guard.

---

## 3. Decision Log

| # | Decision | Alternatives Considered | Reason for Choice |
|---|---|---|---|
| 1 | Target native C# / .NET 8 WinUI 3 in unpackaged mode | Electron; React in WebView2; packaged MSIX | Adheres strictly to Module 11 mandate, eliminates Chromium memory overhead, and allows frictionless CLI builds (`dotnet build`). |
| 2 | Adopt MVVM with `BackendSupervisor` and typed HTTP client | Monolithic code-behind; WebSocket / Named Pipes reactive architecture | Clean separation of concerns, unit-testable viewmodels, adheres to the Phase 5 spec ("prefer polling initially"), and prepares services for companion window reuse. |
| 3 | Sequence Stage 1 (Main Dashboard + Approvals) before Stage 2 (Tray + Corner Companion) | Scaffold both windows simultaneously; companion-first | Minimizes initial surface area and delivers the core human-in-the-loop task experience first. |
| 4 | Automatic port 8000 detection with child process fallback in `BackendSupervisor` | Always launch new process; never launch (manual terminal only) | Supports both developer workflows (running backend in debugger) and end-user workflows (double-clicking `NEXORA.exe`). |
| 5 | Typed C# client mirroring backend response schemas with unified error handling | Dynamic JSON parsing; auto-generated OpenAPI client | C# 12 records provide compile-time safety and zero code-generation overhead while mapping 1:1 with Pydantic models. |
| 6 | State synchronization via dedicated `TaskPoller` with terminal state cutoffs | Continuous background timer; manual refresh button only | Polling at 750ms during active execution provides near-instantaneous feedback without overloading loopback HTTP, stopping automatically when terminal states are reached. |
| 7 | Dedicated, modal `ApprovalDialog` displaying complete canonical tool arguments and countdown timer | Generic yes/no prompt; inline checkbox | Enforces the security mandate: approvals must be exact, time-bounded, argument-verified, and impossible to grant blindly. |
| 8 | Mocked `HttpMessageHandler` unit test suite for C# (`desktop/Nexora.Desktop.Tests/`) | Only manual testing on Windows | Guarantees contract alignment with FastAPI backend responses, polling lifecycle verification, and error handling without requiring a running Ollama server during CI. |
| 9 | Stage 2 Companion Window reuses the existing viewmodels and services | Separate companion codebase or standalone tray process | Single unified process hosting two windows ensures zero state synchronization drift between dashboard and companion. |

---

## 4. Architecture & Component Details

### 4.1 Solution Layout (`desktop/`)

```text
desktop/
├── Nexora.sln
├── Nexora.Desktop/
│   ├── Nexora.Desktop.csproj       # net8.0-windows10.0.19041.0, WindowsPackageType=None
│   ├── App.xaml / App.xaml.cs       # App entry & DI container setup
│   ├── MainWindow.xaml (.cs)        # Main Shell Navigation & Window chrome
│   ├── Models/                      # C# records mirroring FastAPI Pydantic models
│   │   ├── TaskModels.cs           # AgentTask, TaskPlan, StepResult, RouteSelection
│   │   ├── ApprovalModels.cs       # ActionApproval, ApprovalDecisionRequest
│   │   └── StatusModels.cs         # SystemStatus, ModelProfileStatus
│   ├── Services/
│   │   ├── IBackendSupervisor.cs   # Spawns & monitors uvicorn child process
│   │   ├── INexoraApiClient.cs     # Typed REST client (HttpClient + System.Net.Http.Json)
│   │   └── ITaskPoller.cs          # Active task polling timer with cancellation
│   ├── ViewModels/                 # CommunityToolkit.Mvvm ViewModels
│   │   ├── MainViewModel.cs        # Status aggregation & view navigation
│   │   ├── TaskComposerViewModel.cs# Prompt composer & profile selector
│   │   ├── TaskDetailViewModel.cs  # Live execution trace & step progress
│   │   └── ApprovalDialogViewModel.cs # Exact action review and authorization
│   └── Views/
│       ├── DashboardView.xaml
│       ├── TaskComposerView.xaml
│       ├── TaskDetailView.xaml
│       └── Controls/ApprovalCard.xaml
└── Nexora.Desktop.Tests/           # Unit tests with xUnit and Moq
    ├── NexoraApiClientTests.cs
    ├── TaskPollerTests.cs
    └── ApprovalViewModelTests.cs
```

### 4.2 Backend Supervisor Lifecycle

1. Probes `GET http://127.0.0.1:8000/api/health`.
2. If responsive, reuses the existing running instance.
3. If unreachable, launches:
   ```cmd
   python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
   ```
   with redirected output and hidden window in the project root.
4. Polls readiness for up to 10 seconds (250ms intervals).
5. On shell exit, terminates the child process cleanly.

### 4.3 Typed API Client Contracts

The C# models in `Models/` map directly to FastAPI schemas:
* `AgentTask`: `TaskId`, `Prompt`, `ModelProfileId`, `Status`, `Routing`, `Plan`, `ExecutionTrace`, `PendingApproval`, `ErrorMessage`.
* `RouteSelection`: `ProfileId`, `Model`, `TaskKind`, `Reason`, `Escalated`.
* `ActionApproval`: `ApprovalId`, `TaskId`, `StepId`, `ToolName`, `ArgumentHash`, `ExpiresAt`.

### 4.4 Task Polling Lifecycle

* Poller activates upon task submission or task selection.
* Interval: 750ms while `Status` is `SUBMITTED`, `PARSING`, `PLANNING`, `EXECUTING`.
* If `Status == WAITING_APPROVAL`, poller pauses and triggers `ApprovalDialog`.
* If `Status` is terminal (`COMPLETED`, `FAILED`, `CANCELLED`), poller stops immediately.

---

## 5. Verification & Testing Strategy

1. **C# Unit Tests (`Nexora.Desktop.Tests`):**
   * Mock HTTP handler verifies REST contracts, query parameters, and error status code translation.
   * `TaskPoller` unit tests verify timer lifecycle and cancellation upon terminal status.
   * `ApprovalDialogViewModel` tests ensure argument hashes and exact IDs are passed without mutation.
2. **End-to-End Integration:**
   * WinUI 3 shell connects to local FastAPI backend on localhost.
   * Submits a test task, observes step updates, handles approval popup, and inspects verified result.
