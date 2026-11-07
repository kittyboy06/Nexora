# NEXORA Test Verification & Capability Matrix

**Version:** 1.0.0  
**Status:** Released & Validated  
**Verification Target:** Windows 10/11 (x64), Python 3.14+, .NET 8 SDK

---

## 1. Test Tier Classification

NEXORA organizes all automated validation into four distinct execution tiers:

```
┌────────────────────────────────────────────────────────────────────────┐
│ Tier 1: Hermetic Offline Gate (Default, <= 60s, 0 network, 0 GPU)     │
│   • 300+ Backend Pytest Units & Mocks                                  │
│   • 49 Desktop C# Unit Tests (xUnit + Moq)                             │
│   • 16 Adversarial Security Hardening Tests                            │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼─────────────────────────────────────┐
│ Tier 2: Windows Fixture Verification                                   │
│   • Win32 Job Object Quotas (Memory, Timeouts, ActiveProcessLimit)     │
│   • SQLite WAL Checkpoints & NTFS Permissions                          │
│   • WindowFocusGuard & UI Shielding Filter                             │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼─────────────────────────────────────┐
│ Tier 3: Opt-In Live Local Smoke (-IncludeLive)                         │
│   • Live Ollama Daemon Connectivity (127.0.0.1:11434)                  │
│   • Model Inference & Parameter Validation                             │
│   • WinUI 3 Frontend Build & Runtime Launch Readiness                  │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼─────────────────────────────────────┐
│ Tier 4: Explicitly Prohibited & Fail-Closed Behaviors                  │
│   • Non-allowlisted terminal binaries (format, reg, cmd, certutil)     │
│   • Shielded credential windows (1Password, Bitwarden, UAC)            │
│   • Public network binding (0.0.0.0)                                   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Phase 0–14 Capability Matrix

| Phase | Capability | Tier | Test Suite Path | Offline Duration |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 0** | Workspace Scaffolding & Virtualenv | Tier 1 | `backend/tests/` | $<0.1\text{ s}$ |
| **Phase 1** | Ollama Async Client & Concurrency Guard | Tier 1 | `backend/tests/test_ollama_service.py`<br/>`backend/tests/test_guard.py` | $<1.0\text{ s}$ |
| **Phase 2** | Autonomous Planner, State & Permissions | Tier 1 | `backend/tests/agent/` | $<2.5\text{ s}$ |
| **Phase 3** | Filesystem, Terminal & Windows App Tools | Tier 1 | `backend/tests/tools/`<br/>`backend/tests/services/` | $<3.0\text{ s}$ |
| **Phase 4** | Dual-Model Router & Profiler | Tier 1 | `backend/tests/test_model_router.py` | $<1.5\text{ s}$ |
| **Phase 5** | WinUI 3 Modern Desktop Client | Tier 1 | `desktop/Nexora.Desktop.Tests/` | $<2.5\text{ s}$ |
| **Phase 6** | Multi-Agent Fleet Coordinator & Subagents | Tier 1 | `backend/tests/agent/fleet/` | $<2.0\text{ s}$ |
| **Phase 7** | Dynamic Skill Loading & Discovery | Tier 1 | `backend/tests/skills/` | $<1.5\text{ s}$ |
| **Phase 8** | Model Context Protocol (MCP) Client | Tier 1 | `backend/tests/mcp/` | $<2.0\text{ s}$ |
| **Phase 9** | Browser Research, Sanitizer & Quarantine | Tier 1 | `backend/tests/research/` | $<2.0\text{ s}$ |
| **Phase 10** | Dynamic Code Sandbox & Job Objects | Tier 2 | `backend/tests/sandbox/` | $<3.0\text{ s}$ |
| **Phase 11** | Hybrid Long-Term Memory (FTS5 + Vector) | Tier 1 | `backend/tests/memory/` | $<3.5\text{ s}$ |
| **Phase 12** | Desktop Vision & UI Automation Guard | Tier 2 | `backend/tests/desktop/` | $<2.5\text{ s}$ |
| **Phase 13** | Background Scheduler & SQLite Store | Tier 1 | `backend/tests/scheduler/` | $<2.0\text{ s}$ |
| **Phase 14** | Pre-Flight Diagnostics (`doctor.ps1`) | Tier 2 | `backend/tests/test_doctor.py` | $<4.5\text{ s}$ |
| **Phase 14** | Sanitized Support Exporter (`export-diagnostics.ps1`)| Tier 1 | `backend/tests/test_support_bundle.py` | $<4.5\text{ s}$ |
| **Phase 14** | Adversarial Hardening Suite | Tier 1 | `backend/tests/security/test_security_hardening.py` | $<0.5\text{ s}$ |
| **Phase 14** | Log Rotation & Quarantine Pruner | Tier 1 | `backend/tests/test_pruner.py` | $<0.5\text{ s}$ |
| **Phase 14** | Backup, Restore & Reset Validation | Tier 2 | `scripts/backup.ps1`<br/>`scripts/restore.ps1 -VerifyOnly` | $<5.0\text{ s}$ |
| **Phase 14** | Live Ollama Integration Smoke | Tier 3 | `backend/tests/integration/test_live_smoke.py` | Opt-in (Live) |

---

## 3. Running Verification Suites

### 3.1. Complete Hermetic Offline Gate (Standard)
```powershell
.\scripts\run-all-tests.ps1
```
Executes all Python backend tests + all .NET desktop tests + WinUI 3 build. Requires zero internet connectivity and zero running GPU/Ollama instances. Must complete within $60\text{ s}$.

### 3.2. Live Local Smoke Verification
```powershell
.\scripts\run-all-tests.ps1 -IncludeLive
```
Runs the standard offline test gate plus live connectivity and single-token inference verification against the local Ollama instance on `127.0.0.1:11434`.

### 3.3. Security & Hardening Audit
```powershell
.\scripts\security-audit.ps1
```
Audits dependency integrity via `pip check`, verifies all 16 adversarial security regression tests, validates `docs/SBOM.json`, and asserts localhost-only loopback binding.
