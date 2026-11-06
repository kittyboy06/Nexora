# Module 08 — Memory and Persistence

## Responsibility

Store only the minimum local information needed for task continuity and user-approved recall. It controls lifetime, provenance, sensitivity, retrieval and deletion; it never acts as an unrestricted transcript archive.

## Tiers and records

Request context is ephemeral. Task working memory is bounded to execution/review. Durable memory stores explicit preferences/facts with provenance and lifecycle. Optional archive/retrieval needs a later privacy/indexing decision. Every record has ID, category, owner/scope, source task/artifact, sensitivity, consent/reason, created/updated/expires/deleted timestamps, content/version hash and audit references.

## Retrieval policy

Agents request a narrow category/reason. Policy filters records by task/agent scope, consent, expiry, sensitivity and size. Returned material is marked recalled data and cannot override policy. Audit which record IDs were read. Models cannot promote observations to durable records independently.

## Storage and migration

Current task JSON snapshots remain valid until a versioned tested migration exists. A SQLite move requires transactional migration, backups, integrity checks, idempotency, rollback and documented recovery. Sensitive data should be minimized/redacted before storage. Secrets/cookies/passwords are prohibited by default.

## User controls and tests

Dashboard must permit inspect, edit, delete, export and retention visibility. Test expired/deleted filtering, sensitive exclusion, provenance, consent, storage migration failure/rollback, backup/restore, retrieval budget and audit completeness.
