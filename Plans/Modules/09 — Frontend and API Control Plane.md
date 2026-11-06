# Module 09 — Native Control Plane and API Client

## Responsibility

Provide the native Windows human control surface and typed local API client for NEXORA. It visualizes backend-authoritative state; it does not contain independent permission/execution logic.

## UI responsibilities

Show backend/Ollama/model state; submit task/constraints/profile override; display tasks, plan/fleet nodes, actions, evidence and errors; surface exact pending approvals and expiry; support cancel/reject; manage user-visible configuration and approved assets. Make uncertainty and blocked state explicit. Render model/tool/page output as text, never trusted HTML.

## API client rules

One typed client normalizes transport/domain errors and reads base URL from configuration. Backend Pydantic contracts are source of truth. Poll initially with bounded interval and terminal cleanup; introduce events only with a defined reconnect/replay contract. API writes must be idempotency-aware where actions can be double-clicked/retried.

## Privacy/security

Localhost default, no third-party analytics, no secret storage in shell settings, no approval caching. Redaction comes from backend; UI must not accidentally reveal raw sensitive arguments. Show shell/backend/model source/version/status rather than inferring availability.

## Accessibility and tests

Keyboard navigation, semantic controls, focus handling for approval dialogs, readable error/expiry states, screen-reader labels and reduced-motion compatibility. Test API errors, polling lifecycle, double submit, output escaping, approval expiry and task terminal states.
