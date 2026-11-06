# Module 01 — Governance, Permissions, Audit and Verification

## Responsibility

This module is the central authority for whether NEXORA may perform a side effect, how that decision is recorded, and how it determines whether an outcome occurred. It is shared by every tool, MCP adapter, browser action, generated tool, desktop action and scheduled task.

## Invariants

- Models propose; deterministic code authorizes and executes.
- Every side effect passes through one PermissionManager immediately before execution.
- Risk is calculated from action plus typed arguments, never trusted from a model label.
- Approval binds exact task/step/action/argument hash and expires.
- Audit writes record decisions and evidence; secret values are redacted before persistence.
- Verification distinguishes success, failure and uncertainty. Uncertain operations are never blindly retried.

## Contracts

`CapabilityDescriptor` defines ID, version, input/output schema, risk resolver, permission scopes, timeout, resource limits, verification contract and provenance. `AuthorizationRequest` contains task/agent/step/capability, normalized args, computed risk, reason and target scope. `ApprovalRecord` includes a canonical argument hash, user decision, expiry and invalidation reason. `AuditEvent` records proposal, validation, authorization, execution, result and verification with correlation IDs. `VerificationResult` is `VERIFIED`, `FAILED`, or `UNCERTAIN` with evidence references.

## Authorization flow

Validate capability ID and Pydantic arguments; normalize/canonicalize arguments; calculate risk; validate task/profile/capability scope; check policy; create approval if required; revalidate hashes/expiry immediately before execution; execute through registered adapter; record result; verify postcondition; classify retry. A new target, changed arguments, changed capability version, changed server/session or changed schedule template must cause fresh authorization.

## Redaction and audit retention

Capability descriptors identify sensitive argument/result fields. Redact before model context, logs, browser UI and long-term audit. Store enough hashed/referenced evidence to investigate events without copying secrets. Audit should be append-only at the service interface; corrections are separate events, never silent mutation.

## Tests

Test every capability type for risk escalation, argument normalization/hash stability, approval expiry/invalidation, denial, cancellation, redaction, audit ordering, verification outcome and uncertain retry blocking. Treat bypass attempts as security regressions.
