# NEXORA — Phase 5 Implementation Plan
## Native Windows Shell and Control Plane

**Document Type:** Phased Implementation Plan  
**Target:** Phase 5 (WinUI 3 Native Desktop Application)  
**Specification:** `Plans/Phase 5 — Design Specification.md`  
**Host Platform:** Windows 11 desktop  

---

## Proposed Execution Milestones

### Milestone 1: Host Environment & Solution Scaffolding
- [ ] **Task 1.1:** Install .NET 8 SDK on the Windows 11 host using `winget install Microsoft.DotNet.SDK.8` (or verify path).
- [ ] **Task 1.2:** Install Windows App SDK templates: `dotnet new install Microsoft.WindowsAppSDK.Templates`.
- [ ] **Task 1.3:** Scaffold solution in `desktop/Nexora.sln` with `desktop/Nexora.Desktop/` (WinUI 3 unpackaged project targeting `net8.0-windows10.0.19041.0`) and `desktop/Nexora.Desktop.Tests/` (xUnit test project).
- [ ] **Task 1.4:** Add NuGet package references: `Microsoft.WindowsAppSDK`, `CommunityToolkit.Mvvm`, `System.Net.Http.Json`.
- [ ] **Task 1.5:** Verify clean compilation via `dotnet build desktop/Nexora.sln`.

### Milestone 2: Typed C# Domain Models & API Client Service
- [ ] **Task 2.1:** Implement typed C# record models in `Nexora.Desktop/Models/` mirroring FastAPI schemas:
  - `TaskModels.cs`: `AgentTask`, `TaskPlan`, `PlanStep`, `ToolCall`, `StepResult`, `RouteSelection`, `TaskCreateRequest`, `TaskResponse`.
  - `ApprovalModels.cs`: `ActionApproval`, `ApprovalDecisionRequest`.
  - `StatusModels.cs`: `HealthResponse`, `OllamaStatusResponse`, `ModelProfileStatus`, `ModelProfileListResponse`.
- [ ] **Task 2.2:** Implement `NexoraApiException` and error translation from FastAPI `ErrorResponse`.
- [ ] **Task 2.3:** Implement `INexoraApiClient` and `NexoraApiClient` in `Nexora.Desktop/Services/` using `HttpClient` and `System.Net.Http.Json`.
- [ ] **Task 2.4:** Write unit tests in `Nexora.Desktop.Tests/NexoraApiClientTests.cs` using mock `HttpMessageHandler` to verify contract serialization, deserialization, and error handling.

### Milestone 3: Backend Process Supervisor & Task Poller
- [ ] **Task 3.1:** Implement `IBackendSupervisor` and `BackendSupervisor` in `Nexora.Desktop/Services/` to probe `GET /api/health`, spawn Python child process (`uvicorn`) if offline, wait for readiness, and ensure clean child termination on exit.
- [ ] **Task 3.2:** Implement `ITaskPoller` and `TaskPoller` in `Nexora.Desktop/Services/` to poll active tasks every 750ms, pause on `WAITING_APPROVAL`, and cleanly terminate on `COMPLETED`, `FAILED`, `CANCELLED`.
- [ ] **Task 3.3:** Write unit tests in `Nexora.Desktop.Tests/TaskPollerTests.cs` validating timer frequency, pause on approval, and terminal stop.

### Milestone 4: Core ViewModels & Presentation Logic
- [ ] **Task 4.1:** Implement `MainViewModel` managing connectivity state (`IsBackendOnline`, `IsOllamaOnline`, `ActiveModelName`, `ProfilesList`) and view navigation.
- [ ] **Task 4.2:** Implement `TaskComposerViewModel` with prompt text binding, specialist profile selection, and double-click guarded `SubmitTaskCommand`.
- [ ] **Task 4.3:** Implement `TaskDetailViewModel` with step trace, live status pills, routing diagnostics card, and cancel command.
- [ ] **Task 4.4:** Implement `ApprovalDialogViewModel` with exact tool name, parameter display, countdown timer, and approve/reject commands.

### Milestone 5: WinUI 3 Views & Main Dashboard Window (Stage 1 UX)
- [ ] **Task 5.1:** Build `MainWindow.xaml` with modern Windows 11 styling, top status banner, and navigation view.
- [ ] **Task 5.2:** Build `TaskComposerView.xaml` (goal input text box, profile combo box, submit button).
- [ ] **Task 5.3:** Build `TaskDetailView.xaml` (status badge, routing info card, plan step tree view, execution trace output viewer).
- [ ] **Task 5.4:** Build `ApprovalDialog.xaml` (modal dialog presenting exact action, argument hash, and countdown).
- [ ] **Task 5.5:** Wire dependency injection in `App.xaml.cs`.

### Milestone 6: System Tray & Always-On-Top Corner Companion Window (Stage 2 UX)
- [ ] **Task 6.1:** Implement `CompanionWindow.xaml` (compact, borderless, always-on-top window pinned to bottom-right screen corner with active task progress and pause/cancel).
- [ ] **Task 6.2:** Implement `TrayIconService` for Windows notification area tray icon and context menu.
- [ ] **Task 6.3:** Add opt-in global hotkey registration for quick companion toggle.

### Milestone 7: Integration Verification & Packaging Documentation
- [ ] **Task 7.1:** Verify end-to-end task run through WinUI 3 dashboard connected to local backend.
- [ ] **Task 7.2:** Verify approval modal popup and execution resumption.
- [ ] **Task 7.3:** Author `Plans/Phase 5 — Build and Run Guide.md` and update index.
