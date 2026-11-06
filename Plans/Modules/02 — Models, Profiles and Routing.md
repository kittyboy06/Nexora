# Module 02 — Models, Profiles and Routing

## Responsibility

Separate local model provider mechanics from specialist profiles and from route choice. The first provider is Ollama, but application code should depend on provider/model contracts rather than Ollama-specific behavior outside the adapter.

## Contracts

`ModelProvider` lists models, resolves model identifiers/tags, performs bounded chat/structured generation and returns normalized errors/usage data. `InstalledModel` stores provider ID, name/tag, availability, metadata and last seen time. `ModelProfile` stores profile ID, model target, role, specialties, instructions, skill/capability policy, context/resource constraints and enabled state. `RouteDecision` stores selected profile/model, task kind, confidence, escalation, alternatives/rejection reasons and audit fields.

## Routing policy

Use the configured lightweight model to classify bounded task metadata. Validate its structured response. Escalate when confidence is below threshold, structured output is invalid, capability is uncertain, or a higher-risk route requires stronger analysis. Filter candidates by enabled/installed state, modality, allowed capability, context, resource budget and manual override. A manual override is accepted only when profile/model is available and policy permits it. Routing does not authorize capabilities.

## Resource policy

Default to one inference and one active task on the reference system. Inventory can include many downloaded models; runtime selection decides what to load. Collect measured metadata separately from claimed model names. Do not concurrently load large models or change concurrency without benchmarked VRAM/RAM behavior and failure tests.

## Profile lifecycle

Profiles are versioned configuration, not free-form prompt blobs. Validate unique IDs, valid model references, allowed roles/specialties, instruction size, selected skills and capability policy. Changes are auditable and must be visible in task history. Disabled/unavailable profiles cannot be selected. Preserve a configured primary-model fallback so an inventory/profile mismatch fails clearly rather than breaks existing chat/planning.

## Tests

Mock provider inventory and generation. Test model tag matching, missing/offline provider, shared-model multi-profile routing, confidence escalation, deterministic fallback, override, disabled profile, profile schema failure, guard use and audit data.
