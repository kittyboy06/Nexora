# NEXORA — Phase 8: Universal MCP Platform

## Purpose

Provide one standards-based Model Context Protocol (MCP) manager that can discover, inspect, install only after approval, connect to, and govern compatible MCP servers. Server capabilities are integrated into the existing ToolRegistry and PermissionManager rather than given a parallel execution route.

## Prerequisites

- Read `Modules/05 — Universal MCP Manager.md` and `Modules/01 — Governance, Permissions, Audit and Verification.md`.
- Choose and record the MCP specification version and transport support before implementing protocol code.
- Phase 7 review/provenance concepts should be available for GitHub-discovered MCP candidates.

## Scope

### Included

- Server catalogue records with source, version/ref, transport, launch/configuration metadata, declared tools/resources/prompts, health, trust/review state, requested permissions and audit links.
- Standards-compliant client session manager with negotiated protocol version, capability discovery, schema validation, timeout/reconnect and clean shutdown.
- Initial transport set selected explicitly in a design decision; implement transports behind adapters.
- Inspection before installation: metadata, declaration, package origin, dependencies, command/arguments, credential requirements and known risks.
- Explicit approval request before install/start for any new server or changed server version/configuration.
- Credential references through a protected local store abstraction; no credential values in model prompts, task snapshots, browser storage or logs.
- MCP capability adapters registered as normal typed NEXORA tools with dynamic risk classification, centralized approval and audit.
- Dashboard list/detail, health, connect/disconnect, inspect, approve/reject install, disable/revoke and uninstall/rollback controls.

### Excluded

- Trusting a server because its description says it is safe.
- Automatically running package install commands, Docker images or launch scripts discovered online.
- Passing arbitrary user/model JSON to a server without schema validation.
- Giving a server unrestricted filesystem/network/process access.
- Supporting every transport/protocol extension in the first slice.

## Server lifecycle

1. **Discovered:** Candidate exists only as an inspection record; no code runs.
2. **Inspected:** Metadata and declared capabilities parsed; static risks/dependencies shown.
3. **Approval pending:** Exact version/ref, launch command, requested scopes and credential needs await user decision.
4. **Installed/registered:** Artifacts acquired using the approved method and pinned version; installation audit recorded.
5. **Connected:** Client completes protocol handshake and validates advertised schemas.
6. **Enabled:** Specific declared capabilities are mapped into typed, permission-gated NEXORA tools.
7. **Disabled/revoked:** New calls stop; sessions close; credential references may be removed.
8. **Uninstalled/rolled back:** Versioned artifact/config removed according to a safe documented path; audit remains.

Changing server command, source/ref, declared scope, transport, dependency set or credentials resets trust and requires review.

## Capability invocation flow

The model/fleet planner requests a registered NEXORA tool. The adapter validates typed arguments, calculates risk, invokes existing PermissionManager approval flow, opens/reuses an approved MCP session, sends validated request, normalizes server output, stores evidence, and lets the verifier check expected postcondition. MCP output is untrusted and cannot request secondary unapproved actions.

## Data contracts

Define schemas for `McpServerRecord`, `McpInspection`, `McpInstallProposal`, `McpConnectionStatus`, `McpCapability`, `McpCredentialReference`, `McpInvocation`, and `McpInvocationResult`. Include IDs, schema/protocol versions, source hashes, timestamps, status, redacted error fields and audit references. Use immutable versioned records for installed server artifacts.

## Credential design

Use a local credential-store abstraction with opaque references. The model sees capability availability and non-secret connection state only. User-entered secrets travel directly to the credential mechanism, never task prompts. Connection tests must redact returned authorization headers, tokens, cookies and sensitive payload fields. Add a provider abstraction so platform-specific secure storage can be selected later without changing MCP logic.

## Test plan

- Mock MCP server tests: handshake, tool/resource/prompt discovery, valid call, malformed response, unsupported protocol version, timeout, reconnect and clean shutdown.
- Schema rejection for invalid tool arguments and unknown capabilities.
- Approval-before-install/start and approval-before-sensitive-invocation tests.
- Version/config change invalidates prior approval/trust.
- Credential reference/redaction tests.
- Server disable/revoke blocks invocation; audit trace records each lifecycle step.
- Isolation tests appropriate to chosen server launch model.

## Acceptance criteria

- NEXORA can inspect a candidate server without executing it.
- Installation/start requires explicit user approval of exact pinned details.
- Only validated advertised capabilities become registered NEXORA tools.
- Every invocation uses existing permissions, approvals, logs and verification rules.
- Credentials and raw sensitive server output are not leaked into model context or logs.

## Implementation sequence

1. Publish protocol version/transport/credential/sandbox decision record.
2. Implement catalogue, inspection records and dashboard read-only view.
3. Implement one mocked transport/session adapter and tool mapping.
4. Add approval-bound installation/start lifecycle.
5. Add credential references, health/revocation and audit controls.
6. Test real local server only after all mock/security tests pass and user explicitly approves installation.
