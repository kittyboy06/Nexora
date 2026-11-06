# NEXORA Architecture Documentation Index

This folder is the source of truth for Antigravity before it changes NEXORA. Read the master guide first, then the relevant phase file and module files before implementing a feature.

## Existing foundation

| Document | Scope | Status |
|---|---|---|
| `Phase 0 — Technical Specification.md` | Initial product and local-first security direction | Documented |
| `Phase 1 — Design Specification.md` and implementation plan | FastAPI, Ollama, chat, logging and inference guard | Implemented; verify |
| `Phase 2 — Design Specification.md` and implementation plan | Deterministic agent engine, state, validation, approvals | Implemented; preserve |
| `Phase 3 — Design Specification.md` and implementation plan | Filesystem, Windows application and terminal tools | Implemented; preserve |
| `Phase 4 — Agent Fleet Foundation.md` | Model profiles and hybrid routing foundation | Started; verify and complete |
| `NEXORA — Master Architecture and Antigravity Build Guide.md` | Complete product direction and roadmap | Architecture reference |

## Future phase specifications

| Phase | Document | Module specifications to read |
|---|---|---|
| 5 | `Phase 5 — Dashboard and Control Plane.md` | Native Windows Shell module, Control Plane module, Governance module |
| 6 | `Phase 6 — Dynamic Agent Fleet and DAG.md` | Fleet module, Model module, Governance module |
| 7 | `Phase 7 — Skills and GitHub Discovery.md` | Skills module, Governance module |
| 8 | `Phase 8 — Universal MCP Platform.md` | MCP module, Governance module |
| 9 | `Phase 9 — Browser and Internet Research.md` | Browser module, Governance module |
| 10 | `Phase 10 — Generated Tools and Sandbox.md` | Sandbox module, Governance module |
| 11 | `Phase 11 — Memory and Persistence.md` | Memory module, Governance module |
| 12 | `Phase 12 — Desktop Vision and Interaction.md` | Desktop module, Governance module |
| 13 | `Phase 13 — Scheduler and Background Work.md` | Scheduler module, Governance module |
| 14 | `Phase 14 — Hardening and Release.md` | All relevant modules |

## Module specifications

The `Modules/` documents define subsystem contracts shared by more than one phase. Do not duplicate these contracts in feature implementations.

1. `Modules/01 — Governance, Permissions, Audit and Verification.md`
2. `Modules/02 — Models, Profiles and Routing.md`
3. `Modules/03 — Dynamic Agent Fleet and DAG Runtime.md`
4. `Modules/04 — Skills and GitHub Discovery.md`
5. `Modules/05 — Universal MCP Manager.md`
6. `Modules/06 — Browser and Research Service.md`
7. `Modules/07 — Generated Tool Sandbox.md`
8. `Modules/08 — Memory and Persistence.md`
9. `Modules/09 — Frontend and API Control Plane.md` (native control plane and API client)
10. `Modules/10 — Desktop Interaction and Scheduler.md`
11. `Modules/11 — Native Windows Shell.md`

## Required implementation workflow

For every milestone: inspect current code and tests; read the phase/module documents; write or update the detailed implementation checklist; implement a small vertical slice; add focused tests; run only tests appropriate to the environment; record what actually passed; update the phase status. Do not move past a stated gate merely because code has been written.
