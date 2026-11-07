# NEXORA v1.0.0 Release Notes

**Release Date:** November 7, 2026  
**Status:** General Availability (GA)  
**Target Platform:** Windows 10/11 (x64)

---

## 1. Executive Summary

We are proud to announce the **General Availability of NEXORA v1.0.0**, the local-first, fail-closed autonomous intelligence platform built specifically for Windows laptops and workstations.

NEXORA bridges the gap between probabilistic generative AI reasoning and deterministic, observable, and recoverable operating system actions. Over 14 intensive development phases, NEXORA has evolved from an initial async client into a complete end-to-end control plane featuring native WinUI 3 desktop interfaces, multi-agent fleet orchestration, universal MCP tool connectivity, isolated code sandboxing with Win32 Job Objects, hybrid long-term memory, and background scheduling.

---

## 2. Key Release Highlights

### 2.1. Native WinUI 3 Desktop Control Plane
* **7-Pill Navigation Dashboard:** Seamless switching between *Agent Tasks*, *Fleet Coordination*, *Skills & Plugins*, *Universal MCP*, *Research Lab*, *Desktop Vision*, and *Scheduler & Automation*.
* **Live Action Timeline & Approvals:** Step-by-step progress tracking with Tier 1/2 human approval dialogs for system-modifying operations.
* **Corner Companion:** Compact, always-on-top desktop overlay for ambient task monitoring.

### 2.2. Multi-Agent Fleet & Dynamic Extensibility
* **DAG-Based Task Coordination:** Multi-agent dependency graphs supporting sequential and branching execution across specialized roles.
* **Universal Model Context Protocol (MCP):** Connect external data sources and developer tools via stdio with an encrypted Windows DPAPI credential vault.
* **Dynamic Markdown Skills:** Discover, validate, and hot-reload skills from GitHub with semantic versioning and XML container boundary sanitization.

### 2.3. Safe & Isolated Execution Sandbox
* **Win32 Job Objects:** Hard system limits on dynamic code trials (500 MB RAM quota, 4 active processes max, 30s timeout, automatic cleanup on job close).
* **Workspace Jail:** Strict path canonicalization preventing file operations outside `data/workspace`.
* **WindowFocusGuard:** Desktop vision engine shielded from accessing or automating password managers (`1password.exe`, `bitwarden.exe`, `keepass.exe`) and UAC prompts (`consent.exe`).

### 2.4. Hardening, Data Lifecycle & Observability
* **Online SQLite WAL Backups:** Atomic truncation checkpoints (`PRAGMA wal_checkpoint(TRUNCATE)`) and automated rollback protection on restore.
* **Pre-Flight Diagnostics:** Automated health checks (`scripts/doctor.ps1`) and zero-secret support bundle exporter (`scripts/export-diagnostics.ps1`).
* **Automated Data Lifecycle:** 24-hour TTL quarantine pruner and 10MB rotating log sink.

---

## 3. Hardware Compatibility Matrix

| Hardware Tier | Processor | RAM | GPU / VRAM | Recommended Model | Max Concurrency |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Minimum** | Intel Core i5 (11th Gen) / AMD Ryzen 5 5600 | 16 GB | Integrated / CPU Only | `llama3.2:3b` / `qwen2.5:3b` | 1 |
| **Standard** | Intel Core i7 (12th/13th Gen) / AMD Ryzen 7 5800 | 16 GB | NVIDIA RTX 3050 (4 GB) | `qwen3.5:9b` (Q4) / `llama3.1:8b` | 1 |
| **Recommended** | Intel Core i7 (14th Gen) / AMD Ryzen 7 7800X+ | 32 GB | NVIDIA RTX 4060 / 4070 (8 GB+) | `qwen3.5:9b` (Q4_K_M) | 1–2 |
| **Workstation** | Intel Core i9 / AMD Ryzen 9 | 64 GB | NVIDIA RTX 4080 / 4090 (16 GB+) | `qwen3.5:14b` / `llama3.3:70b` (Q4) | 2–4 |

---

## 4. Supported Local Models (Ollama)

| Model Tag | Parameters | Quantization | Context Window | Best Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **`qwen3.5:9b`** *(Default)* | 9 Billion | Q4_K_M | 8,192 tokens | General planning, code generation, tool calling, and fleet synthesis. |
| **`llama3.1:8b`** | 8 Billion | Q4_K_M | 8,192 tokens | Autonomous multi-step tool execution and research summarization. |
| **`mistral:7b-instruct`** | 7 Billion | Q4_0 | 4,096 tokens | Fast low-latency routing and simple task plans. |
| **`qwen2.5-coder:7b`** | 7 Billion | Q4_K_M | 8,192 tokens | Dynamic sandbox tool creation and Python code synthesis. |

---

## 5. Verification & Quality Metrics

All release gates have been validated against our tiered test matrix:
* **Python Backend Unit & Security Tests:** **328 Passed**, 2 Skipped (Live Opt-in), **0 Failed**.
* **Desktop .NET Unit Tests:** **49 Passed**, **0 Failed**.
* **WinUI 3 Desktop Application:** Build succeeded with **0 Warnings, 0 Errors**.
* **Security Audit Gates:** **4/4 Passed** (Dependency integrity, 16 adversarial security tests, SBOM validation, loopback binding).
