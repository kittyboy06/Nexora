# Module 07 — Generated Tool Sandbox

## Responsibility

Evaluate and run model-generated code only in a real disposable isolation environment, then make reviewed versions available as normal governed capabilities. The sandbox is a security boundary, not merely a testing helper.

## Required controls

The implementation must explicitly enforce a disposable runtime, dedicated unprivileged execution identity, minimal mounted working/input/output directories, denied-by-default network, no user-home/backend/secret access, CPU/RAM/time/PID/output limits, restricted runtime/dependency set, process-tree cleanup and evidence capture. Record the selected technology and its limits.

## Proposal contract

Generated code requires manifest: purpose, input/output schemas, allowed runtime, dependencies, requested permissions, tests, postcondition and source hash. Static validation happens before sandbox launch. Reject no-manifest, invalid schema, forbidden imports, shell commands, path escape, unmanaged dependencies or network requests outside declared policy.

## Lifecycle

Gap assessment → proposal → static validation → user/policy approval → disposable sandbox test/trial → verification → review → disabled draft or approved versioned registry entry. The only route from an approved version to real work is ToolRegistry and PermissionManager. Passing a sandbox trial does not retain it automatically.

## Failure policy

Timeout/crash/escape signal/unknown outcome ends the run and destroys environment. Do not rerun an uncertain side-effect. If sandbox infrastructure is unavailable, refuse generated execution and report why.

## Tests

Static negative tests; file/network/process/resource containment; cleanup; output limits; version hash/approval binding; registry disable/rollback; adversarial breakout fixtures appropriate to chosen technology.
