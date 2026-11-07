# Phase 8 — Universal MCP Platform Implementation Specification

## 1. Executive Summary & Understanding
* **System Purpose:** Provide a standards-compliant, secure Model Context Protocol (MCP) platform in NEXORA. Allows operators to discover, inspect, configure, approve, connect to, and govern external MCP servers without parallel execution routes or unmonitored host access.
* **Core Philosophy:** MCP servers are untrusted external integrations. Their advertised capabilities are dynamically mapped into typed, server-namespaced NEXORA `BaseTool` instances (`mcp__<server_id>__<tool_name>`) and governed centrally by `PermissionManager` and the execution audit trail.
* **Zero Secret Leakage:** Credentials and API keys are stored in an encrypted local vault, referenced opaquely (`ref:vault/<key>`), and injected into child processes strictly at spawn time.

---

## 2. Decision Log

| ID | Topic | Decision | Alternatives Considered | Rationale |
|---|---|---|---|---|
| **D1** | **Transport** | `stdio` subprocess pipes primary with modular `McpTransport` interface | Dual `stdio` + HTTP/SSE from day one; HTTP/SSE only | `stdio` is universal for local CLI MCP tools (SQLite, Git, Python, Node); modular interface enables SSE/HTTP in future without refactoring. |
| **D2** | **Credential Vault** | Encrypted local vault (`data/mcp/vault.bin`) with opaque references (`ref:vault/<key>`) | Plaintext JSON, host environment variables only | Guarantees machine-bound encryption; secrets never appear in prompts, task snapshots, UI, or logs. |
| **D3** | **Tool Mapping** | Server-namespaced tool IDs (`mcp__<server_id>__<tool_name>`) registered into `ToolRegistry` with risk gating | Generic proxy tool (`invoke_mcp_tool`), flat global names | Prevents naming collisions; treats MCP tools identically to native tools under `PermissionManager`. |
| **D4** | **Subprocess Lifecycle** | Lazy on-demand spawning with idle pool (10-minute auto-shutdown) and clean termination | Continuous daemon, ephemeral per-call | Eliminates cold-start latency on multi-step tasks while avoiding memory bloat and orphan processes. |
| **D5** | **UI Experience** | Dedicated "MCP Platform" navigation view in WinUI 3 with dual panels (Inventory & Inspector/Vault) | Settings dialog only, sub-tab in Skills | First-class operational control, clear visual approval queue, and rich schema viewing. |
| **D6** | **Architecture** | Decoupled Multi-Service Protocol Engine (`McpVaultService`, `McpServerRegistry`, `McpClientSession`, `McpCapabilityBridge`) | Monolithic MCP service, external sidecar daemon | Zero blast radius: process or protocol crashes are safely caught without destabilizing core backend services. |

---

## 3. Assumptions & Non-Functional Requirements
1. **Performance:** Subprocess JSON-RPC tool dispatch overhead $\le 20\text{ ms}$; JSON-RPC requests enforce a 30-second default execution timeout.
2. **Process Containment:** Subprocesses are launched with `shell=False` using tokenized arguments and explicit working directory bounds to prevent command injection.
3. **Approval Invalidation:** Modifying a server's command, arguments, or environment automatically revokes approval (`is_approved = False`), requiring operator review before launch.
4. **Reliability:** Process pipe crashes or protocol errors produce structured `McpToolError` exceptions classified as `TRANSIENT` or `PERMANENT`, never crashing the backend server.
5. **Redaction:** Tool results and error traces are filtered for sensitive tokens and authorization headers before logging.

---

## 4. Technical Architecture & Components

### 4.1 Directory Structure
```text
backend/app/mcp/
├── __init__.py
├── models.py           # Pydantic schemas (ServerRecord, ToolDefinition, VaultSecret, Invocation)
├── vault.py            # McpVaultService: encrypted key-value store & ref resolution
├── transport.py        # McpTransport abstract base & StdioTransport implementation
├── protocol.py         # JSON-RPC 2.0 framing, handshake, request/response dispatcher
├── session.py          # McpClientSession: connection pool, ping health, idle timer
├── registry.py         # McpServerRegistry: data/mcp/servers.json persistence & approval state
├── bridge.py           # McpCapabilityBridge: wraps advertised tools into BaseTool instances
└── router.py           # FastAPI endpoints (/api/mcp/*)

data/mcp/
├── servers.json        # Pinned server records, approval status, and command definitions
└── vault.bin           # Cryptographically encrypted credentials vault
```

### 4.2 Data Models (`backend/app/mcp/models.py`)
* `McpServerStatus`: `DISCOVERED`, `APPROVED`, `CONNECTED`, `STOPPED`, `ERROR`, `REVOKED`
* `McpServerConfig`: ID slug, display name, description, transport (`stdio`), command, args, env (with `ref:vault/<key>` values), working directory, approval and enabled flags.
* `McpToolDefinition`: Advertised tool name, description, JSON schema for input parameters, and assigned `RiskLevel`.
* `McpServerRecord`: Full record including status, advertised tools, negotiated protocol version, last connected timestamp, ping latency, and error details.
* `McpVaultItemSummary`: Key, description, created timestamp, and boolean presence (plaintext secret is never exposed).

### 4.3 Encrypted Vault Service (`backend/app/mcp/vault.py`)
* Encrypts and decrypts `data/mcp/vault.bin` using Fernet with PBKDF2HMAC machine-derived key.
* `resolve_environment(env_config)` parses all `ref:vault/<key>` values into plaintext environment variables strictly in-memory at process spawn time.

### 4.4 Subprocess Protocol Engine (`transport.py`, `protocol.py`, `session.py`)
* `StdioTransport`: Non-shell subprocess execution with async stdin/stdout pipe streaming and stderr logging.
* `Protocol Handshake`: `initialize` (protocol version `2024-11-05`), `notifications/initialized`, `tools/list`, and `ping`.
* `McpClientSession`: Manages connection state, timeout enforcement, idle timer (10 mins), and clean process termination.

### 4.5 ToolRegistry Bridge (`backend/app/mcp/bridge.py`)
* Maps each advertised tool to a typed `BaseTool` subclass named `mcp__<server_id>__<tool_name>`.
* Bridges execution to the active `McpClientSession` while routing through `PermissionManager` risk checks.

---

## 5. API Specification (`/api/mcp`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/mcp/servers` | List all configured MCP servers with status and tool counts |
| `GET` | `/api/mcp/servers/{id}` | Get full server record, advertised tools, and schemas |
| `POST` | `/api/mcp/servers` | Register a new MCP server configuration (status: `DISCOVERED`) |
| `PUT` | `/api/mcp/servers/{id}` | Update server config (resets approval status if command/args/env changed) |
| `POST` | `/api/mcp/servers/{id}/approve` | Approve server launch configuration |
| `POST` | `/api/mcp/servers/{id}/connect` | Start/connect to approved server, complete handshake, discover tools |
| `POST` | `/api/mcp/servers/{id}/disconnect` | Disconnect and terminate server subprocess |
| `POST` | `/api/mcp/servers/{id}/ping` | Ping server via JSON-RPC and measure roundtrip latency |
| `DELETE` | `/api/mcp/servers/{id}` | Disconnect and remove server configuration |
| `GET` | `/api/mcp/vault` | List all opaque vault secret summaries |
| `POST` | `/api/mcp/vault` | Set or update a secret value in the encrypted vault |
| `DELETE` | `/api/mcp/vault/{key}` | Remove a secret from the vault |

---

## 6. Implementation Milestones

* **Milestone 1: Domain Models & Encrypted Vault Service**
  * Create `models.py`, `vault.py`.
  * Unit tests for encryption, machine-bound key derivation, reference resolution, and error handling (`test_mcp_vault.py`).
* **Milestone 2: JSON-RPC Framing & Stdio Transport**
  * Create `transport.py`, `protocol.py`.
  * Unit tests for message serialization, line framing, handshake negotiation, and error frames (`test_mcp_protocol.py`).
* **Milestone 3: Session Manager & Server Registry**
  * Create `session.py`, `registry.py`.
  * Unit tests for connection pooling, idle timer shutdown, approval state reset, and recovery (`test_mcp_session.py`).
* **Milestone 4: ToolRegistry Capability Bridge**
  * Create `bridge.py` dynamically mapping MCP tools to `BaseTool` instances.
  * Wire bridge with `ToolRegistry` and `PermissionManager`.
  * Unit tests for namespacing, risk classification, and execution forwarding (`test_mcp_bridge.py`).
* **Milestone 5: FastAPI Router & Main Wiring**
  * Create `router.py` for all `/api/mcp/*` routes.
  * Register router and wire services into `backend/app/main.py`.
  * Integration tests for all endpoints (`test_mcp_api.py`).
* **Milestone 6: WinUI 3 Desktop Control Plane**
  * Add "MCP Platform" navigation item to `desktop/Nexora.Desktop/MainWindow.xaml`.
  * Create `McpViewModel.cs` managing server inventory, inspector tabs, and vault secrets.
  * Wire API client methods in `NexoraApiClient.cs`.
  * Desktop unit tests (`McpViewModelTests.cs`).
* **Milestone 7: Verification & Mock Reference Server**
  * Create a reference mock MCP server (e.g. echo/math tool).
  * Run complete backend test suite and desktop tests.
  * Verify full run within an agent task.

---

## 7. Test Strategy & Acceptance Criteria
* **Isolated Testing:** Protocol, session, and bridge tests use mock transports without requiring live external processes in CI.
* **Security & Secret Verification:** Assert that plaintext secrets never appear in server configs, API responses, logs, or agent prompts.
* **Approval Gates:** Assert that an unapproved server cannot be connected or executed under any circumstances.
* **Zero Regression:** All existing 143 backend tests and 17 desktop tests continue to pass.
