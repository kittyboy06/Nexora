# Phase 5 — Build and Run Guide: Native Windows Shell and Control Plane

This document provides complete instructions for building, running, and verifying the **NEXORA Native Windows Control Plane** (`Nexora.Desktop`), built with **C# .NET 8 and WinUI 3 (Windows App SDK 1.5)**.

---

## 1. Architectural Overview

NEXORA adheres strictly to the **Authoritative Host / Presentation Client** pattern:

```
+-----------------------------------------------------------------------------------+
|                           NEXORA Control Plane (Desktop)                          |
|                                                                                   |
|  +-------------------------------------+  +------------------------------------+  |
|  |             MainWindow              |  |          CompanionWindow           |  |
|  | - TitleBar & Backend Status Pill    |  | - Corner always-on-top window      |  |
|  | - Task Composer (Prompt, Profiles)  |  | - Compact status & quick run       |  |
|  | - Plan Step Trace (ListView & Icons)|  | - Direct "Open Dashboard" launcher |  |
|  | - In-Window Modal Approval Dialog   |  +------------------------------------+  |
|  +-------------------------------------+                                          |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  |                           Nexora.Desktop.Services                          |  |
|  |  [NexoraApiClient]        [TaskPoller]         [BackendSupervisor]          |  |
|  |  (REST HTTP Client)      (Periodic Poller)    (Self-healing Process Spawn) |  |
|  |  [TrayIconService]                                                          |  |
|  |  (Win32 Notification Area Tray Icon & Context Menu)                         |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------|-----------------------------------------+
                                          | HTTP REST (Authoritative API)
                                          v
+-----------------------------------------------------------------------------------+
|                           Local Python / FastAPI Backend                          |
|                               (http://127.0.0.1:8000)                             |
|  - Authoritative Task State Manager & SQLite Persistence                          |
|  - Dynamic Model Registry & Hybrid LLM Routing (Fast Local / Smart Cloud)         |
|  - Two-Stage Plan Validation & Strict Schema Invariants                           |
|  - Human-in-the-Loop Dangerous Tool Permissions Policy Engine                     |
|  - Sandboxed Tool Execution (Terminal, Filesystem, Windows Shell, Ollama)         |
+-----------------------------------------------------------------------------------+
```

### Component Structure
* **`desktop/Nexora.Core`** (`net8.0`):
  * Domain models (`AgentTask`, `PlanStep`, `ActionApproval`, `RouteSelection`, `ModelProfileStatus`).
  * Typed API client (`INexoraApiClient`, `NexoraApiClient`, `NexoraApiException`).
  * Process supervisor (`IBackendSupervisor`, `BackendSupervisor`) for self-healing local FastAPI backend lifecycle.
  * Task polling engine (`ITaskPoller`, `TaskPoller`).
  * MVVM ViewModels (`MainViewModel`, `TaskComposerViewModel`, `TaskDetailViewModel`, `ApprovalDialogViewModel`) leveraging `CommunityToolkit.Mvvm`.
* **`desktop/Nexora.Desktop`** (`net8.0-windows10.0.19041.0`, WinUI 3 unpackaged):
  * Application entry and DI bootstrap (`App.xaml`, `App.xaml.cs`).
  * Fluent Windows 11 Main Window with Mica material backdrop (`MainWindow.xaml`, `MainWindow.xaml.cs`).
  * Always-on-top Corner Companion Window (`Views/CompanionWindow.xaml`, `CompanionWindow.xaml.cs`).
  * Win32 System Tray integration with context menu (`Services/TrayIconService.cs`).
  * Fluent UI Value Converters (`Converters/Converters.cs`).
* **`desktop/Nexora.Desktop.Tests`** (`net8.0`):
  * Fast unit tests for API Client, Poller, and Approval flows using xUnit and Moq.

---

## 2. Prerequisites

1. **Operating System:** Windows 10 (version 1809+ / build 17763+) or Windows 11.
2. **.NET 8 SDK:** .NET 8.0 SDK (version 8.0.400 or newer).
3. **Windows App Runtime:** Windows App SDK 1.5 runtime (automatically provisioned on modern Windows 11 or installable via `winget install Microsoft.WindowsAppRuntime.1.5`).
4. **Python Backend:** Python 3.12+ (or 3.14) with virtual environment located in `.venv` or in system path.

---

## 3. Building the Solution

### Build the Full Desktop Solution (.NET)
Open PowerShell and run:
```powershell
dotnet build desktop/Nexora.sln -p:Platform=x64
```
*Expected Output:*
```
Build succeeded.
    0 Warning(s)
    0 Error(s)
```

### Build Individual Projects
```powershell
# Core Library
dotnet build desktop/Nexora.Core/Nexora.Core.csproj

# WinUI 3 Desktop App
dotnet build desktop/Nexora.Desktop/Nexora.Desktop.csproj -p:Platform=x64

# Unit Tests
dotnet build desktop/Nexora.Desktop.Tests/Nexora.Desktop.Tests.csproj
```

---

## 4. Running the Tests

### C# Unit Tests (Desktop & Core)
```powershell
dotnet test desktop/Nexora.Desktop.Tests/Nexora.Desktop.Tests.csproj
```
*Result:* 8/8 tests pass in < 200ms covering:
* `GetHealthAsync_ReturnsParsedHealth`
* `CreateTaskAsync_SendsRequestAndReturnsTask`
* `DecideApprovalAsync_SendsExactApprovalPayload`
* `CancelTaskAsync_CallsCancelEndpoint`
* `TaskPoller_FiresUpdatedAndStopsOnTerminalState`
* `TaskPoller_FiresApprovalRequiredOnWaitingApproval`
* `ApproveCommand_CallsDecideApprovalWithTrue`
* `RejectCommand_CallsDecideApprovalWithFalse`

### Python Backend Tests (Phase 0 — Phase 4)
```powershell
$env:PYTHONPATH="."
pytest backend/tests
```
*Result:* 84/84 tests pass in < 15s verifying zero regressions across API, orchestrator, tools, permissions, validator, and hybrid routing.

---

## 5. Running the Application

### Option A: Run via .NET CLI (Recommended for Development)
```powershell
dotnet run --project desktop/Nexora.Desktop/Nexora.Desktop.csproj -p:Platform=x64
```

### Option B: Run Executable Directly
After building:
```powershell
& "desktop\Nexora.Desktop\bin\x64\Debug\net8.0-windows10.0.19041.0\Nexora.Desktop.exe"
```

### Automated Backend Supervisor Behavior
When `Nexora.Desktop.exe` launches:
1. `BackendSupervisor` sends a `GET /api/health` request to `http://127.0.0.1:8000`.
2. If the FastAPI backend is already running, the status pill updates to **Connected** immediately.
3. If the backend is offline, `BackendSupervisor` automatically launches `python -m uvicorn backend.app.main:app --port 8000` as a supervised child process and polls until healthy.
4. When `ExitApplication` is called from the System Tray or window close, the supervisor terminates child backend processes cleanly.

---

## 6. Control Plane Verification Walkthrough

1. **Connect & Status Verification:**
   * Observe the top header bar: **Connected** pill displays green.
   * "Ollama Model" displays the configured local model (e.g. `llama3.2:latest` or `qwen2.5-coder:7b`).
2. **Submit a Task:**
   * Type in the Composer: `Inspect the current project structure and list top-level directories.`
   * Click **Submit Task**.
   * Observe transition from `SUBMITTED` -> `ROUTING` -> `PLANNING` -> `EXECUTING`.
   * Expand the **Routing Diagnostic** card to view selected profile, route (`fast_local` vs `smart_cloud`), and reasoning.
   * Watch the step trace update in real time with checkmarks as steps succeed.
3. **Human-in-the-Loop Modal Approval:**
   * Submit a task that triggers dangerous tool execution (e.g. `Delete file temp.txt` or `Run script deploy.ps1`).
   * Task enters `WAITING_APPROVAL`.
   * The modal overlay appears displaying tool name, step ID, argument hash, and parameters.
   * Click **Approve (Execute)** to authorize or **Reject** to abort.
4. **Stage 2 Companion & Tray Navigation:**
   * Minimize the main window.
   * Right-click the NEXORA icon in the Windows Notification Area (System Tray) to inspect the context menu:
     * Click **Show Companion** to open the corner floating window.
     * Click **Open Dashboard** to restore the main window.
