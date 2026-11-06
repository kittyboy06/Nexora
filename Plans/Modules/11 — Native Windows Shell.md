# Module 11 — Native Windows Shell

## Decision

NEXORA's primary user application is a native Windows desktop app, not Electron and not a browser-hosted React application. Use **C# with .NET 8+ and WinUI 3 through the Windows App SDK** for the shell. Retain the existing Python/FastAPI backend as a local AI, task orchestration and governed-execution service.

```text
NEXORA.exe — WinUI 3 native shell
  ├── Main dashboard window
  ├── Always-on-top companion window
  ├── System tray, native notifications and global hotkeys
  ├── Native capture and desktop-observation broker
  └── Local API client / backend supervisor

NEXORA Backend — Python/FastAPI child process
  ├── Models, routing, Agent Fleet, state and persistence
  ├── Permission, audit, verification and tool registry
  └── Local Ollama and future MCP/browser/sandbox services
```

The shell owns Windows-only experience and carefully scoped OS integration. The backend remains the sole authority for task state, permissions, tool requests, approvals, audits and verification. This preserves the working Phase 0–3 backend without copying security-sensitive execution logic into C#.

## Lifecycle and transport

The shell starts the packaged/selected backend as a child process, waits for bounded health confirmation, and shows a native diagnostic if Python, backend or Ollama is unavailable. Preserve the existing loopback FastAPI API for the first shell release so the shell is a new client rather than a backend rewrite. Bind only to loopback. Add a launch-scoped secret or Windows-user ownership check before privileged local routes; select/document the exact method in implementation design. A named-pipe transport is a later option, not an initial prerequisite.

The shell owns the backend it launches, avoids duplicate instances, requests graceful shutdown on exit, and never silently restarts a task with uncertain side effects. Close-to-tray behavior must be an explicit user preference.

## Windows experience

The main WinUI window is the dashboard. A small companion window can live in a screen corner, showing task state, model activity, approval needed, quick capture, pause/cancel and open-dashboard actions. It is borderless/repositionable, DPI/multi-monitor aware and has compact/expanded modes.

Always-on-top is user-controlled and applies only to the companion. Use the Windows topmost window mechanism through a narrow native interop service; provide a visible toggle and temporarily demote it when a capture picker or approval requires focus. System tray controls, native notifications and global hotkeys are opt-in, conflict-checked, scoped to show/hide/open/pause/cancel actions, and never become keyboard logging.

## Native capture and desktop interaction

The shell is the only component allowed to reach Windows capture and UI automation APIs. It uses the system capture picker so the user chooses one display or window and sees OS capture indication. It sends only bounded, redacted artifacts/structured observations to the backend after central task permission approves the capture.

Default capture is a single selected target, with short-lived frames and no persistence unless evidence policy allows it. Capture artifacts include task ID, target identity, timestamp, dimensions, hash, redaction and retention state. The backend/models never receive a desktop handle or raw unrestricted desktop access.

Use Windows UI Automation for accessible element inspection before mouse/keyboard coordinates. The model proposes a bounded action; backend validates and authorizes it; shell verifies target identity/focus; native adapter performs one action; shell re-observes; backend records verification. A focus mismatch or ambiguous result stops as uncertain.

## Packaging and test requirements

Choose a Windows-native packaging/installer approach in a separate decision record. It must include native shell, compatible backend assets, environment checks, update/migration, repair, uninstall and user-data preservation.

Test C# shell state, backend supervision, companion settings, hotkey conflicts and capture flow; mocked FastAPI contract; Windows fixture behavior for tray/DPI/window identity; picker cancellation/support/redaction/cleanup; UI Automation focus/cancellation; and clean-install/package smoke tests.

## Acceptance criteria

- `NEXORA.exe` has a native WinUI 3 dashboard and optional companion with no Electron/Chromium.
- It connects to local backend predictably and never bypasses backend permissions/audits.
- Tray, always-on-top and hotkeys are opt-in and controllable.
- Capture is visibly user-selected, permission-gated, redacted/short-lived by default and audit-linked.
- Native UI interaction is target-verified and bounded.
