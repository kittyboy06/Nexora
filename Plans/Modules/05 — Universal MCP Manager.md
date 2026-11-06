# Module 05 — Universal MCP Manager

## Responsibility

Provide a standards-based MCP client and server lifecycle manager. It treats MCP servers as untrusted integrations and maps their declared capabilities into normal NEXORA tools governed by the central permission system.

## Core entities

Server record, inspection, installation proposal, connection session, declared capability, credential reference, invocation and normalized result. Every entity has IDs, versions, timestamps, status, provenance and audit links. Protocol/transport choices are versioned decision records.

## Lifecycle and boundaries

Discover and inspect without execution. Approval is required before installation/start. Connect with handshake/schema validation. Enable only selected declared capabilities after mapping typed schemas and risk policy. Invocation enters ToolRegistry → PermissionManager → adapter → verifier. Disable/revoke stops new calls and closes sessions. Changes to source/ref/command/config/dependencies/scopes require reinspection and approval.

## Credentials

Use opaque local credential references. The MCP manager resolves secrets only at connection/invocation boundary. Models/logs/task snapshots/UI receive redacted state. Connection errors and server results require sensitive-field filtering.

## Reliability

Use session lifecycle, bounded timeouts, cancellation, reconnection policy and resource cleanup. Server output remains untrusted. A protocol/session failure is surfaced as a structured tool error and follows retry classification; never blindly repeat an uncertain external action.

## Tests

Mock handshake/discovery/invocation, malformed schemas, protocol mismatch, timeouts, disconnect, credentials redaction, install approval, change invalidation, revoke and permission enforcement.
