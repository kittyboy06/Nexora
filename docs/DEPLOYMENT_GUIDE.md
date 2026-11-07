# NEXORA Production Deployment & Operator Guide

**Version:** 1.0.0  
**Target Architecture:** Windows 10/11 (x64)  
**Applicability:** Clean Machine Onboarding, Local Production Deployments

---

## 1. System Requirements

### 1.1. Hardware Recommendations
| Component | Minimum | Recommended |
| :--- | :--- | :--- |
| **Operating System** | Windows 10 (Build 19041+) 64-bit | Windows 11 (23H2+ / 24H2) 64-bit |
| **Processor** | 6-core x86_64 CPU (Intel i5 11th Gen / AMD Ryzen 5 5600) | 8+ core x86_64 CPU (Intel i7 13th Gen+ / AMD Ryzen 7 7800X+) |
| **System Memory (RAM)** | 16 GB | 32 GB DDR5 |
| **GPU / Acceleration** | Integrated GPU (CPU inference fallback) | NVIDIA RTX 3060 / 4060 (8 GB+ VRAM) |
| **Storage** | 20 GB free space on NVMe SSD | 50 GB+ free space on PCIe 4.0 NVMe SSD |

### 1.2. Software Prerequisites
* **Python:** Version 3.14+ (64-bit). Ensure `python` and `pip` are on the system `PATH`.
* **.NET 8 SDK:** Version 8.0.x (x64). Ensure `dotnet` is installed.
* **Ollama for Windows:** Latest version running locally on `http://127.0.0.1:11434`.
* **Primary LLM Model:** `qwen3.5:9b` (or `llama3.1:8b`). Pull via `ollama pull qwen3.5:9b`.

---

## 2. One-Click Automated Setup

On a clean checkout of the repository, execute:

```powershell
# Open PowerShell as Administrator or standard developer user:
cd D:\Projects\Works\Nexora
.\scripts\bootstrap.ps1
```

The bootstrap script will automatically:
1. Verify Python 3.14+ runtime and .NET 8 SDK presence.
2. Provision all required runtime directory structures under `data/`.
3. Generate local `.env` configuration from `.env.example`.
4. Install all Python dependencies from `backend/requirements.txt`.
5. Restore NuGet dependencies and build the WinUI 3 Desktop solution.
6. Execute `scripts/doctor.ps1` to confirm system health.

---

## 3. Manual Step-by-Step Installation

If you prefer manual configuration:

### 3.1. Clone & Configure Environment
```powershell
git clone <repo-url> Nexora
cd Nexora
copy backend\.env.example .env
```

### 3.2. Install Python Dependencies
```powershell
python -m pip install -r backend/requirements.txt
```

### 3.3. Pull Ollama Model
```powershell
ollama pull qwen3.5:9b
```

### 3.4. Build WinUI 3 Desktop Application
```powershell
dotnet build desktop/Nexora.sln -c Debug -p:Platform=x64
```

---

## 4. Launching the System

NEXORA operates as a dual-tier architecture:

### 4.1. Start Backend Core Engine
```powershell
# Quick launch using the bundled launcher:
.\start_server.bat

# Or direct uvicorn command:
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
The backend initializes SQLite WAL databases, long-term memory, MCP servers, and starts listening on `http://127.0.0.1:8000`.

### 4.2. Start WinUI 3 Desktop Application
In a separate terminal or shortcut:
```powershell
dotnet run --project desktop/Nexora.Desktop/Nexora.Desktop.csproj
```
The desktop host connects via loopback IPC to `http://127.0.0.1:8000` and displays the modern 7-pill control plane:
1. **Agent Tasks** (Task Composer, Live Step Progress, Human Approvals)
2. **Fleet Coordination** (Multi-agent DAG graphs and role status)
3. **Skills & Plugins** (Installed catalog & GitHub discovery)
4. **Universal MCP** (Server connections & encrypted vault)
5. **Research Lab** (Web evidence citations & quarantine)
6. **Desktop Vision** (UI automation, window focus & screen shield)
7. **Scheduler & Automation** (Recurring schedules & cron triggers)

---

## 5. Verification & Pre-Flight Checks

Before deploying to production, run the pre-flight diagnostics:

```powershell
# Run environment diagnostics doctor:
.\scripts\doctor.ps1

# Run full hermetic test gate (must pass 100%):
.\scripts\run-all-tests.ps1

# Run security hardening audit:
.\scripts\security-audit.ps1
```

---

## 6. Troubleshooting & Diagnostics

### 6.1. Exporting a Support Bundle
If you encounter unexpected errors or need assistance, export a sanitized diagnostic bundle:
```powershell
.\scripts\export-diagnostics.ps1
```
This produces `diagnostics/nexora-diagnostics-TIMESTAMP.zip` containing system metrics, recent scrubbed logs, and component status. **All secrets and sensitive credentials are automatically redacted.**

### 6.2. Common Issues
* **Port 8000 Conflict:** If port 8000 is occupied by another application, set `PORT=8001` in `.env` and configure the desktop host endpoint.
* **Ollama Model Missing:** If `doctor.ps1` warns of a missing model, run `ollama pull qwen3.5:9b` or update `OLLAMA_MODEL` in `.env`.
* **SQLite File Lock on Windows:** Ensure no third-party database viewers have exclusive locks on `nexora_memory.db` or `nexora_scheduler.db`.
