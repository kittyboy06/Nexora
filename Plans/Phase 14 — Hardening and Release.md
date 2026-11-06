# NEXORA — Phase 14: Hardening and Release

## Purpose

Integrate and validate the supported NEXORA product for a real Windows laptop. This phase does not add broad new capabilities. It makes the accumulated product reproducible, observable, recoverable and honest about its limits.

## Prerequisites

- Each previous phase has a signed-off design, passing focused tests and documented known limitations.
- Read all module documents and preserve their boundaries.
- Establish a release checklist, supported hardware/model matrix and rollback/backup approach.

## Scope

- Full test matrix: unit, service, API, integration, Windows fixture, sandbox containment, browser/MCP mock, security regression and opt-in live smoke tests.
- Reproducible local installation/onboarding, environment validation, dependency locking/version reporting and model setup guide.
- Configuration validation, safe defaults, migrations, backups/restores, log rotation, audit retention and diagnostics export without secrets.
- Performance/resource profiling on supported laptop(s): model load, route latency, task throughput, memory/VRAM, browser/sandbox overhead and cleanup.
- Security review: trust boundaries, dependency inventory, secrets handling, localhost exposure, filesystem/process/network controls, prompt injection tests, audit completeness and recovery behavior.
- User documentation: setup, dashboard, model profiles, approvals, skills, MCP, browser, generated tools, memory, scheduling, limitations, emergency stop, backup, upgrade and uninstall.
- Release versioning, migration notes, known issues, changelog and rollback procedure.

## Excluded

- Adding unreviewed features to meet a release date.
- Calling mock tests live validation.
- Releasing with broad permissions or weakened sandbox/approval behavior as a workaround.

## Validation matrix

For each capability, distinguish: mocked/offline test passed; Windows fixture test passed; live local test passed; external-account test passed; unsupported/not tested. Record exact version, OS, model/provider, dependencies and date. Failures and skipped tests belong in release notes.

Run destructive or external-side-effect scenarios only in dedicated workspaces/test accounts, with approval and cleanup. Test crash/restart behavior at task, browser, MCP and sandbox boundaries. Test downgrade/rollback from any data migration.

## Release acceptance criteria

- Clean setup can start backend/dashboard and diagnose missing Ollama/model configuration.
- Full offline suite passes from documented commands.
- Required Windows and security tests pass on a supported environment.
- Live results are recorded separately and accurately.
- User can review/cancel tasks, reject approvals, disable/revoke capabilities, view audits, remove retained data and recover from interruption.
- Backup/restore and update/rollback are documented and tested.
- No known critical bypass of central authorization, audit or verification remains.

## Implementation sequence

1. Build test matrix and mark existing evidence/status.
2. Close reproducibility/configuration/migration gaps.
3. Profile resource use and tune only from measurement.
4. Perform security and failure-mode review.
5. Write user/operator documentation and dry-run clean installation.
6. Produce release notes with tested, untested and known-limit statements.
