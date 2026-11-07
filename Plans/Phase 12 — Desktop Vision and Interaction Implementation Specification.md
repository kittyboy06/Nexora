# NEXORA — Phase 12: Desktop Vision and Interaction Implementation Specification

## 1. Executive Summary

Phase 12 establishes a bounded, verifiable, and secure Windows Desktop Vision and UI Interaction platform for NEXORA. Building upon the matured foundation of process launching, browser research, sandboxed code execution, and long-term memory, Phase 12 gives agents the ability to observe and interact with authorized desktop applications on Windows without opening arbitrary desktop access or creating security blind spots.

The system is governed by strict fail-closed security rules:
* **Strict HWND + Process Lock:** Actions are bound to a verified window `(HWND, PID, process_name, window_title)`. Any focus shift or foreground change aborts execution immediately as `UNCERTAIN` before input is sent.
* **Accessibility-First:** UI Automation patterns (`InvokePattern`, `ValuePattern`, `TogglePattern`) are executed directly wherever available, eliminating cursor drift and resolution dependencies. Bounded coordinate clicks serve only as a fallback strictly constrained within the target window client rect.
* **Shielded Windows & Password Redaction:** Credential managers (1Password, Bitwarden, KeePass), Windows Security, UAC prompts, and lock screens are completely blacklisted. Password fields in accessibility trees are masked, and screenshots visually black out sensitive controls.
* **Emergency Stop:** A thread-safe global cancellation controller accessible via REST API, a prominent WinUI 3 dashboard button, and a global keyboard shortcut immediately terminates in-flight actions.

---

## 2. Understanding Summary & Scope

### 2.1 What is Being Built
1. **Desktop Adapter Layer:** Abstract interface `DesktopAdapter` with `Win32DesktopAdapter` (native Win32/UIA) and `MockDesktopAdapter` (headless simulator for CI).
2. **Window Focus & Binding Guard:** Enforces `TargetWindowBinding` and shields sensitive system dialogs and password managers.
3. **Accessibility Inspection Service:** Recursively parses Windows UI Automation trees, extracting element identities, control types, bounding rects, and redaction metadata.
4. **Capture Broker:** Captures window-bounded screenshots, masks sensitive elements, downscales/compresses, computes SHA-256 hashes, and records evidence with a 24-hour TTL.
5. **Action Executor & Postcondition Verifier:** Executes typed actions (`FOCUS`, `INSPECT_TREE`, `CLICK_ELEMENT`, `TYPE_TEXT`, `SCROLL`, `WAIT_STATE`), performs pre- and post-action diffing, and halts if postconditions are unfulfilled.
6. **Emergency Stop Subsystem:** Thread-safe cancellation mechanism that releases synthetic inputs, cancels active actions, and marks tasks as cancelled.
7. **FastAPI Router:** Exposes `/api/desktop/*` endpoints for window discovery, tree inspection, capture, action dispatch, and emergency stop.
8. **WinUI 3 Desktop Control Plane:** Dedicated "Desktop Vision & UI" navigation pill with target window selector, live screenshot preview, element tree explorer, and global Emergency Stop button.

### 2.2 Explicit Non-Goals
* No always-on screen recording, passive surveillance, or background video streams.
* No keyloggers, global keyboard hooks, or raw clipboard monitoring.
* No autonomous interaction with credential dialogs, password managers, or elevated UAC prompts.
* No unconstrained global desktop coordinate clicks.
* No off-device transmission of full desktop frames by default.

---

## 3. Assumptions & Non-Functional Requirements

1. **Host Environment:** Standard Windows 10/11 desktop with standard DPI scaling.
2. **Headless CI Testing:** Full capability to test target binding, focus changes, element lookup, postcondition diffs, and emergency stop under Linux/Windows CI without real desktop windows via `MockDesktopAdapter`.
3. **Screenshot Storage & Expiry:** Stored in `data/quarantine/desktop/<task_id>/<image_hash>.jpg` with SHA-256 tracking and automated 24-hour purge.
4. **Performance Targets:**
   - Window discovery: $\le 100\text{ ms}$
   - Tree inspection (depth 4): $\le 300\text{ ms}$
   - Window-bounded capture: $\le 80\text{ ms}$
   - Emergency stop propagation: $\le 50\text{ ms}$

---

## 4. Decision Log

* **D1:** Adopted Python-native Win32/UIA Adapter architecture over out-of-process worker to minimize IPC overhead and ensure seamless mocking in headless CI.
* **D2:** Strict HWND + Process Lock (Fail-Closed) enforced: any focus shift or unexpected foreground window aborts actions as `UNCERTAIN`.
* **D3:** Accessibility-first targeting via UI Automation patterns, with bounded bounding-box clicks strictly constrained within the target window rect.
* **D4:** Shielded process blacklist (credential managers, UAC) with password masking and 24h screenshot quarantine auto-purge.
* **D5:** Two-tier action sensitivity: inspection/capture is `SAFE`; mutating actions require Operator Approval with WinUI 3 Emergency Stop.
* **D6:** Window targeting requires explicit `(HWND, PID, process_name, window_title)` binding; foreground mismatch fails closed as `UNCERTAIN`.
* **D7:** Hardcoded blacklist blocks all credential managers, UAC prompts, and lock screens from window discovery, capture, and interaction.
* **D8:** UI Automation patterns prioritized over mouse movement to eliminate cursor drift and multi-monitor scaling issues.
* **D9:** Elements with `is_password == True` are automatically masked in accessibility inspection responses and audit logs.
* **D10:** Coordinate clicks require strict relative offsets bounded inside the target window client rect; unconstrained desktop coordinates are rejected.
* **D11:** Window capture strictly bounded to target HWND client rect; password/secure elements visually blacked out before storage.
* **D12:** Screenshots stored in `data/quarantine/desktop/` with SHA-256 indexing and automatic 24-hour retention expiry.
* **D13:** Pre- and post-action verification required for all mutating actions; unfulfilled postconditions or focus drops result in `UNCERTAIN` task stop.
* **D14:** Global Emergency Stop accessible via API, WinUI 3 dashboard button, and `Ctrl + Alt + Pause/Break` hotkey.
* **D15:** WinUI 3 adds 6th navigation view for desktop inspection, window binding, and live screenshot verification.

---

## 5. Architectural Design & Component Specifications

### 5.1 Architecture Diagram

```mermaid
graph TD
    Agent[Agent / Planner] -->|Propose Action| Policy[DesktopPolicyEnforcer]
    Policy -->|Sensitivity Check| Approvals{Requires Operator Approval?}
    Approvals -->|Yes| Gate[Operator Approval Gate]
    Gate -->|Approved| Guard[WindowFocusGuard & Shield]
    Approvals -->|No (Read-Only)| Guard
    Guard -->|Verify HWND/PID/Title| Adapter[DesktopAdapter Interface]
    Adapter -->|Win32 / UIA / Mock| OS[Windows OS / Target Window]
    Guard -->|Pre-Action Capture| Broker[CaptureBroker]
    Broker -->|Redact Passwords| Quaran[Task Quarantine Store]
    Guard -->|Execute Action| Adapter
    Guard -->|Post-Action Capture| Broker
    Guard -->|Verify Postcondition| Verifier[PostconditionVerifier]
    Verifier -->|Check State| Result[Action Result: OK / UNCERTAIN]
    EStop[EmergencyStopManager] -->|Abort Signal| Guard
```

### 5.2 Domain Models (`backend/app/desktop/models.py`)

* `TargetWindowBinding`:
  ```python
  class TargetWindowBinding(BaseModel):
      hwnd: int
      pid: int
      process_name: str
      window_title: str
      bounds: tuple[int, int, int, int]  # x, y, width, height
      is_shielded: bool = False
  ```
* `UIElementNode`:
  ```python
  class UIElementNode(BaseModel):
      element_id: str
      automation_id: str
      name: str
      control_type: str
      bounding_rect: tuple[int, int, int, int]
      is_enabled: bool = True
      is_password: bool = False
      supported_patterns: list[str] = []
      children: list["UIElementNode"] = []
  ```
* `DesktopActionRequest` & `DesktopActionResult`:
  ```python
  class DesktopActionType(str, Enum):
      FOCUS = "focus"
      INSPECT_TREE = "inspect_tree"
      CLICK = "click"
      TYPE_TEXT = "type_text"
      SCROLL = "scroll"
      WAIT = "wait"

  class DesktopActionRequest(BaseModel):
      binding: TargetWindowBinding
      action_type: DesktopActionType
      target_element_id: Optional[str] = None
      relative_coords: Optional[tuple[int, int]] = None
      text_input: Optional[str] = None
      scroll_amount: Optional[int] = None
      expected_postcondition: Optional[str] = None

  class DesktopActionResult(BaseModel):
      action_id: str
      status: str  # SUCCESS, UNCERTAIN, FAILED, CANCELLED
      pre_action_screenshot_id: Optional[str] = None
      post_action_screenshot_id: Optional[str] = None
      message: str
      verification_ok: bool
  ```

### 5.3 Shielded Process Filter & Window Focus Guard (`backend/app/desktop/guard.py`)

* **Shielded Process List:**
  ```python
  SHIELDED_PROCESSES = {
      "1password.exe", "bitwarden.exe", "keepass.exe", "keepassxc.exe",
      "credentialuibroker.exe", "sechealthui.exe", "lockapp.exe", "consent.exe"
  }
  ```
* **Focus Check:** Validates `adapter.get_foreground_window() == binding.hwnd`. Throws `FocusLostException` on mismatch.
* **Title Check:** Validates `binding.window_title in adapter.get_window_text(binding.hwnd)`.

### 5.4 Capture Broker & Visual Redactor (`backend/app/desktop/capture.py`)

* Captures client rect of `binding.hwnd`.
* Queries UI Automation tree for all nodes where `is_password is True`.
* Overlays black rectangles on all sensitive coordinate regions.
* Saves to `data/quarantine/desktop/<task_id>/<hash>.jpg` with 24h expiration timestamp.

### 5.5 Desktop Action Executor & Verifier (`backend/app/desktop/executor.py`)

* Manages single-action execution pipeline.
* Settle delay: default 250ms after input before postcondition capture.
* Checks postconditions (e.g., target element text changed, window closed, new element visible).
* Stops task as `UNCERTAIN` if focus changes, target window closes unexpectedly, or postcondition check fails.

### 5.6 Emergency Stop Controller (`backend/app/desktop/emergency.py`)

* Atomic thread-safe flag `is_active: bool`.
* Methods:
  - `trigger_emergency_stop(reason: str)`: Halts all pending execution loops, clears queued actions, logs critical audit event.
  - `reset()`: Resets flag with operator authorization.
  - `check_stopped()`: Raises `EmergencyStopActiveException` if active.

### 5.7 Core Desktop Tools (`backend/app/desktop/tools.py`)

Registered with `ToolRegistry`:
1. `desktop_list_windows`: Lists open windows, excluding shielded processes (`RiskLevel.SAFE`).
2. `desktop_inspect_tree`: Inspects accessibility tree of bound window (`RiskLevel.SAFE`).
3. `desktop_capture_window`: Captures bounded, redacted window screenshot (`RiskLevel.SAFE`).
4. `desktop_execute_action`: Dispatches mutating action (click, type, scroll) (`RiskLevel.SENSITIVE_MODERATE`, requires operator confirmation).
5. `desktop_emergency_stop`: Instantly halts all automation (`RiskLevel.SAFE`).

### 5.8 FastAPI Endpoints (`backend/app/desktop/router.py`)

* `GET /api/desktop/windows`
* `POST /api/desktop/bind`
* `GET /api/desktop/tree`
* `POST /api/desktop/capture`
* `POST /api/desktop/actions`
* `POST /api/desktop/emergency-stop`
* `GET /api/desktop/evidence`

### 5.9 WinUI 3 Desktop Control Plane (`desktop/Nexora.Desktop`)

* New View: `DesktopVisionView.xaml` / `DesktopVisionViewModel.cs`.
* Window picker dropdown with real-time refresh.
* Live observation canvas showing the latest redacted screenshot.
* Element Explorer tree displaying UIA elements.
* Large red "EMERGENCY STOP" button in main top bar.
* Global keyboard shortcut listener for `Ctrl+Alt+Pause/Break`.

---

## 6. Implementation Sequence & Milestones

* **Milestone 1:** Domain models, `DesktopAdapter` interface, `Win32DesktopAdapter`, and `MockDesktopAdapter`.
* **Milestone 2:** `WindowFocusGuard`, shielded process blacklist, and window discovery.
* **Milestone 3:** `CaptureBroker`, password masking/redaction, and task quarantine evidence store.
* **Milestone 4:** Accessibility tree traversal, typed action executor, and postcondition verifier.
* **Milestone 5:** `EmergencyStopManager` and core tools registration (`desktop_*`).
* **Milestone 6:** FastAPI router, supervisor lifespan integration, and REST endpoints.
* **Milestone 7:** WinUI 3 Desktop Control Plane (UI, models, API client, ViewModel, and view).
* **Milestone 8:** End-to-end integration tests, regression verification, and documentation.
