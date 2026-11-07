# NEXORA v1.0 Security Audit & Threat Model

**Document Version:** 1.0.0  
**Classification:** Public Engineering Specification  
**System Under Evaluation:** NEXORA Autonomous Intelligence Platform on Windows  
**Audit Scope:** Core Backend (FastAPI / Python 3.14+), WinUI 3 Desktop Host (.NET 8), Sandbox Job Objects, SQLite WAL Storage Engine.

---

## 1. Executive Summary

NEXORA is designed from the ground up as a **fail-closed, local-first autonomous intelligence platform** running on modern Windows laptops. Unlike cloud-dependent AI agents that transmit telemetry, embeddings, and workspace contents to third-party endpoints, NEXORA operates strictly within the host boundary using local Ollama model instances, an isolated SQLite WAL persistence engine, and OS-enforced process sandboxing.

The primary security objective is to prevent untrusted inputs (malicious web pages, untrusted prompt injections, hostile skill definitions, or adversarial tools) from breaking out of containment, elevating privileges, accessing credentials, or executing arbitrary system commands.

---

## 2. Threat Modeling (STRIDE Analysis)

| STRIDE Category | Potential Attack Vector | NEXORA Mitigation & Security Control | Verification Test |
| :--- | :--- | :--- | :--- |
| **Spoofing** | Attacker impersonates local WinUI 3 frontend or spoofed external web client. | The backend binds exclusively to `127.0.0.1` (loopback). CORS middleware rejects arbitrary cross-origin requests, only permitting designated localhost ports. | `test_server_defaults_to_localhost_loopback`<br/>`test_cors_configuration_rejects_arbitrary_origins` |
| **Tampering** | Malicious code modifies application binaries, core database rows, or memory records. | SQLite WAL mode with atomic file transactions, cryptographic SHA-256 backup verification, and strict workspace root path sandboxing. | `test_filesystem_service_blocks_path_traversal`<br/>`scripts/restore.ps1 -Verify` |
| **Repudiation** | An autonomous agent performs an unauthorized destructive action without audit trail. | Tier 1/2 human-in-the-loop approval gates for system-modifying tools. Immutable run histories, step action logs, and secret-scrubbed diagnostic trails. | `test_support_bundle_secret_scrubbing`<br/>`backend/tests/agent/` |
| **Information Disclosure** | API tokens, private keys, database passwords, or screen captures leak into logs or export bundles. | Real-time regex and entropy secret scrubbing (`MemorySecurityGate.scrub_secrets`, `TerminalService.redact_secrets`). Automated support bundle scrubber strips prompts and quarantine images. | `test_secret_scrubbing_removes_sensitive_tokens`<br/>`test_terminal_service_secret_masking` |
| **Denial of Service** | Long-running subprocess consumes infinite CPU/RAM, forks fork bombs, or exhausts GPU memory. | Windows Win32 Job Objects with `ActiveProcessLimit=4`, `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, 500 MB memory cap, 30s execution timeouts, and an asynchronous `InferenceGuard` semaphore (limit=1). | `backend/tests/sandbox/test_job_object.py`<br/>`backend/tests/test_guard.py` |
| **Elevation of Privilege** | Agent uses `runas`, `sudo`, `cmd.exe /c`, or UI automation to click UAC prompts or password vaults. | Tokenized `asyncio.create_subprocess_exec` (no `shell=True`), strict `ALLOWED_TERMINAL_COMMANDS` whitelist, and `WindowFocusGuard` shielding `1password.exe`, `bitwarden.exe`, `consent.exe`, and `credentialuibroker.exe`. | `test_terminal_blocks_privilege_elevation`<br/>`test_window_focus_guard_rejects_binding_shielded_window` |

---

## 3. Trust Boundaries & Architecture

```
                  [ Untrusted Internet / Web Pages ]
                                 │
                                 ▼ (Phase 9 Sanitizer & XML Fencing)
                      <untrusted_web_evidence>
                                 │
                                 ▼
                     ┌──────────────────────┐
                     │   Ollama Local LLM   │ (No direct system access)
                     └──────────┬───────────┘
                                │ JSON Tool Calls
                                ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ NEXORA Host Security Perimeter (FastAPI @ 127.0.0.1:8000)              │
 │                                                                        │
 │  ┌──────────────────────┐   ┌────────────────────────────────────────┐ │
 │  │ Permission Gate      │   │ WindowFocusGuard                       │ │
 │  │ (Human Operator Sign)│   │ (Shields 1Password, Bitwarden, UAC)    │ │
 │  └──────────┬───────────┘   └────────────────────────────────────────┘ │
 │             │                                                          │
 │             ▼                                                          │
 │  ┌──────────────────────────────────────────────────────────────────┐  │
 │  │ Isolated Execution Engines                                       │  │
 │  │  • FilesystemService: Chrooted inside `data/workspace`           │  │
 │  │  • TerminalService: Whitelisted commands only (dir, echo, git...)│  │
 │  │  • Win32 Job Object: Hard memory, process & time quotas          │  │
 │  │  • Secret Scrubber: Redacts tokens before logging or persistence │  │
 │  └──────────────────────────────────────────────────────────────────┘  │
 └────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Key Security Invariants

### 4.1. Loopback-Only Network Binding
The backend server configuration (`Settings.HOST`) defaults strictly to `127.0.0.1`. Under no circumstance is the backend bound to `0.0.0.0` or made accessible over public network adapters without an explicit reverse proxy.

### 4.2. XML Boundary Fencing for Untrusted Content
External web content scraped or retrieved via browser research is never fed raw to the LLM. It is stripped of closing container tags (`</untrusted_web_evidence>`, `<system>`, `<antigravity>`, `<USER_REQUEST>`) and enclosed within sanitized XML boundaries to prevent prompt breakout attacks.

### 4.3. UI Automation Shielding
The desktop automation engine cannot inspect or send mouse/keyboard events to windows matching shielded processes (`1password.exe`, `bitwarden.exe`, `keepass.exe`, `consent.exe`, `credentialuibroker.exe`, `taskmgr.exe`) or window titles matching security keywords ("Windows Security", "Credential Manager", "User Account Control", "Master Password").

### 4.4. Secret Redaction at Rest and in Transit
Diagnostic bundles generated via `scripts/export-diagnostics.ps1` pass all logs, configuration values, and state entries through `MemorySecurityGate.scrub_secrets`. Secret keys, GitHub tokens, Bearer tokens, and RSA/EC private keys are replaced with `[REDACTED_SECRET]` before archive creation.

---

## 5. Security Regression Verification

NEXORA includes an automated adversarial security regression test suite located at:
`backend/tests/security/test_security_hardening.py`

This suite can be executed offline in $<1\text{ s}$ via:
```powershell
python -m pytest backend/tests/security/test_security_hardening.py -v
```

All 16 adversarial tests must pass before any production build or release artifact is signed.
