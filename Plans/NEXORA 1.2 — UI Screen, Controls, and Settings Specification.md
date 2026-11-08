# NEXORA 1.2 — UI Screen, Controls, and Settings Specification

## Purpose

This document is the UI handoff for NEXORA 1.2. It defines the screens, controls, information hierarchy, interaction rules, and settings required for a native WinUI 3 desktop application. The landing screen is a general local-AI chat, while the existing operational modules remain available as detailed workspaces.

## Design direction

**Signal Console** — a focused, dark Windows-native command center. It should feel calm when idle and precise when active. The distinctive visual anchor is a thin vertical **signal spine**: a live color-coded activity line that links the chat, work cards, approvals, and automation state.

Use a near-black blue surface, warm ivory text, muted blue-gray panels, electric teal for healthy/active work, amber for attention, red for blocked/stop states, and a single indigo highlight for selected navigation. Avoid generic glowing “AI” gradients, oversized cards, and rainbow status colors.

## Global application shell

### Persistent regions

| Region | Contents | Behavior |
|---|---|---|
| Left navigation rail | NEXORA mark, page icons/labels, compact status dot, Settings | Collapsible. Selected item has indigo rail and high-contrast text. |
| Top command bar | Current workspace name, global search, model/profile selector, local-backend health, notifications, account/device menu | Always visible except in compact companion mode. |
| Signal spine | Vertical live event timeline between navigation and content | Teal=running, amber=awaiting decision, red=failed/stopped, gray=historical. Selecting an event opens its source. |
| Main content | Current page | Scrolls independently. |
| Context drawer | Task/chat details, approvals, source preview, inspector | Opens from the right; never blocks the emergency stop. |
| Companion overlay | Compact status, pause/stop, current task, indicator that screen capture is active | Optional; controlled by settings. |

### Global buttons

| Button/control | Location | Action |
|---|---|---|
| **New chat** | Navigation rail | Creates a blank conversation and focuses composer. |
| **Quick task** | Command bar | Opens a small task prompt with mode/profile selector. |
| **Stop all** | Command bar and companion | Immediately stops active autonomous sessions and cancels queued work; confirmation only if no active work exists. |
| **Search** | Command bar | Searches conversations, tasks, skills, MCP servers, schedules, and audit records. |
| **Notifications** | Command bar | Opens approval, completion, failure, and health events. |
| **Settings** | Navigation rail | Opens application settings. |

## Screen inventory

### 1. Chat — default landing screen

**Purpose:** general local AI conversation and the starting point for all work.

#### Layout

- Conversation list: recent, pinned, and archived chats.
- Main transcript: user/assistant messages, citations, task cards, approval cards, and completion summaries.
- Right contextual panel: current task/work item, selected model, sources, or conversation metadata.
- Composer: multi-line prompt, mode picker, optional model override, attachment/import button when supported, send and stop controls.

#### Buttons and controls

| Control | Action |
|---|---|
| **New chat** | Starts a new conversation. |
| Conversation menu `…` | Rename, pin, export, archive, delete. |
| **Mode: Auto** | Opens choices: Auto route, Answer only, Create task, Research, Import skill, Connect MCP, Desktop Vision, Schedule. |
| **Model: Auto** | Opens profile list; manual choice shows “manual override” in the transcript. |
| `+` | Opens supported add actions: paste URL, import skill folder, attach approved input, start desktop session. |
| **Send** | Sends the current draft. Disabled for empty input. |
| **Stop response** | Cancels current local inference only. |
| Message `…` | Copy, retry, branch conversation, report issue, view raw metadata. |
| Citation | Opens source preview in right drawer. |
| Work card | Opens linked Task/Skills/MCP/Desktop Vision/Scheduler record. |
| Approval card | View proposed action, approve, reject, or open detailed record. |

#### States

- Empty: three starter chips — “Plan a task”, “Research a topic”, “Connect a tool”.
- Thinking: compact elapsed timer and **Stop response**.
- Offline: clear local-model/backend issue with **Retry connection** and **Open health**.
- Awaiting approval: amber work card remains in transcript until resolved/expired.

### 2. Tasks

**Purpose:** inspect, approve, monitor, and recover agent work created from chat or manually.

#### Subscreens

1. **Task list**: status filters, text search, source conversation, model, date, risk, and owner filters.
2. **Task detail**: goal, originating chat, route/model, plan DAG, timeline, current action, evidence, approvals, artifacts, logs, retry/cancel controls.
3. **Task creation**: direct task creation for users who do not start in chat.

#### Buttons

- **Create task**, **Open in chat**, **Pause**, **Resume**, **Cancel**, **Retry failed step**, **Approve**, **Reject**, **Export evidence**, **Copy task link**.

### 3. Fleet coordination

**Purpose:** show dynamic task-specific agents and DAG progress without hiding the parent task.

#### Controls

- Fleet selector, graph/list toggle, filter by node state, inspect node, retry node, cancel fleet, export artifacts.
- Every agent node shows role, model/profile, dependencies, allowed capabilities, token budget, output artifact, and state.

### 4. Skills

**Purpose:** discover, inspect, import, enable, version, and selectively inject Markdown skills.

#### Subscreens

1. **Installed skills**: status, version, provenance, target roles, enable toggle, recent use.
2. **Import skill**: folder import, open local skills folder, paste definition, conflict handling.
3. **GitHub discovery**: search candidates and preview repository content.
4. **Skill review**: manifest, `SKILL.md`, provenance/hash, permissions, compatibility, enable decision.

#### Buttons

| Button | Action |
|---|---|
| **Import folder** | Opens native folder picker; creates review candidate. |
| **Open skills folder** | Opens configured local skills directory in Explorer. |
| **Paste skill** | Opens manifest + Markdown paste editor. |
| **Refresh folder** | Re-scans the local skills folder. |
| **Discover on GitHub** | Opens discovery search. |
| **Preview** | Opens README, manifest, and skill tabs without installing. |
| **Install disabled** | Stores candidate but keeps it excluded from prompts. |
| **Enable skill** / **Disable** | Changes selective injection eligibility. |
| **Version history** | Shows versions, hashes, and rollback choice. |

### 5. GitHub repository preview

**Purpose:** review external skill or MCP repositories safely before adoption.

#### Required tabs

- **README**: sanitized rendered Markdown.
- **Files**: discovered files with selected path, size, hash, and retrieval status.
- **Skill**: manifest and `SKILL.md` preview.
- **MCP setup**: proposed launch configuration, if a repository is being used for MCP onboarding.
- **Provenance**: owner, repository, branch/commit SHA, URL, fetched time, and warnings.

#### Buttons

- **Back to results**, **Copy source URL**, **Use for skill import**, **Use for MCP draft**, **Refresh preview**, **Open externally**.
- No button should install packages, execute scripts, or launch a server from repository content.

### 6. MCP hub

**Purpose:** manually configure, review, connect, test, classify, and manage MCP servers.

#### Subscreens

1. **Servers**: cards/table for discovered, approved, connected, stopped, disabled, and error servers.
2. **Manual setup**: executable, tokenized arguments, working directory, environment-key references.
3. **Repository-assisted setup**: URL/ref/path → inspected proposal → review.
4. **Review and approval**: immutable launch fingerprint and diff from prior approval.
5. **Test connection**: handshake, tools/list, ping, logs, clean shutdown.
6. **Capabilities**: advertised tools, risk classification, enablement, last use.
7. **Vault**: secret key names/descriptions only; never plaintext values.

#### Buttons

- **Add manually**, **From repository**, **From chat draft**, **Inspect**, **Approve launch config**, **Connect**, **Test connection**, **Disconnect**, **Disable**, **Delete**, **Classify tool**, **Add vault secret**, **Rotate secret**.

#### Guardrails visible in UI

- A server remains “Review required” until its exact command/arguments/directory/env-key fingerprint is approved.
- Test connection never calls a discovered tool automatically.
- New/unclassified capabilities display **Sensitive — approval required**.

### 7. Research lab

**Purpose:** search, fetch, inspect citations, manage domain policy, and quarantine downloads.

#### Controls

- Search box, source type filter, result list, fetch/read button, render-JavaScript toggle, citation picker, domain policy editor, download quarantine list.
- Buttons: **Search**, **Fetch**, **Send to chat**, **Create research task**, **Add allowed domain**, **Block domain**, **Delete quarantined file**, **Export citations**.

### 8. Desktop Vision

**Purpose:** start and supervise bounded autonomous screen/UI work.

#### Subscreens

1. **Session list**: active, paused, completed, blocked, stopped.
2. **Start session**: originating task/chat, target app/window, goal, session duration, action budget, capture policy, allowed categories.
3. **Live session**: target identity, capture indicator, last screenshot reference, UI-tree summary, current action, verification, timeline, budget, pause/stop.
4. **Evidence review**: quarantined screenshots/UI snapshots and redaction indicators.

#### Buttons

- **Start desktop session**, **Select target window**, **Capture now**, **Inspect UI**, **Pause**, **Resume**, **Stop now**, **Approve sensitive action**, **Open evidence**, **Report target mismatch**.

#### Mandatory status indicators

- “Screen capture active”, target window/app, remaining time, actions used/budget, focus status, protected-content status, and emergency-stop hint.

### 9. Scheduler

**Purpose:** create, review, activate, pause, and inspect recurring/background work.

#### Controls

- Schedule list, cron/interval builder, linked task template, dry-run preview, next-run calendar, execution history, approval policy.
- Buttons: **Create schedule**, **Run once**, **Pause**, **Resume**, **Edit**, **Delete**, **View run**, **Open source chat**.

### 10. Memory and knowledge

**Purpose:** transparently inspect long-term memory and its use in planning.

#### Controls

- Search memories, source/task filter, confidence/freshness filter, propose memory, approve/reject proposal, edit/remove, backup/restore.
- Buttons: **Search**, **Propose**, **Approve**, **Reject**, **Open source**, **Export**, **Backup**, **Restore**.

### 11. Approvals and audit

**Purpose:** one authoritative inbox for human decisions and proof of what happened.

#### Controls

- Tabs: Awaiting approval, Recent decisions, All audit events, Security events.
- Filters: module, task, risk, date, outcome.
- Buttons: **Approve**, **Reject**, **Open origin**, **Compare change**, **Export audit trail**, **Acknowledge event**.

### 12. System health and settings

**Purpose:** configure NEXORA without exposing raw configuration files.

#### Settings groups

| Group | Settings |
|---|---|
| General | launch on startup, start minimized, theme, language, notification style, default landing page. |
| Models and routing | installed local models, profile editor, default model, router model, confidence threshold, manual override behavior, inference concurrency. |
| Chat | default mode, conversation retention, export/delete behavior, streaming display, Markdown rendering. |
| Permissions | controlled-action policy, sensitive-action approval timeout, schedule approval policy, emergency-stop behavior. |
| Skills | local folder path, discovery settings, imported skills default disabled, allowed role injection. |
| MCP | data path, idle timeout, approved launch manifests, vault metadata, default tool risk = Sensitive. |
| Research | search provider, allow/block domains, response/download size limit, browser isolation, retention. |
| Desktop Vision | enablement, companion visibility, session duration, action budget, capture mode, cross-window policy, protected app list, emergency-stop shortcut. |
| Storage and privacy | workspace path, encryption/vault status, evidence retention, quarantine pruning, backups, diagnostic redaction. |
| Advanced | API port/loopback state, logs, diagnostics, reset/recovery. |

## Reusable component inventory

- `SignalSpine`, `StatusChip`, `RiskBadge`, `WorkCard`, `ApprovalCard`, `EvidenceLink`, `ModelBadge`, `SourcePill`, `EmptyState`, `InlineError`, `ConnectionHealth`, `DangerConfirmDialog`, `SearchCommand`, `SegmentedModePicker`, `RightContextDrawer`, `CompanionStatusStrip`.

## Accessibility and interaction rules

- Keyboard navigation, visible focus ring, 4.5:1 minimum text contrast, and non-color status labels are required.
- Red/amber/teal status indicators always include text and an icon.
- Destructive or sensitive actions show exact target/action summary before confirmation.
- Every loading action has a cancellable state where technically possible.
- Tooltips explain unfamiliar status terms; avoid forcing users to learn internal model names.
- Prefer native WinUI controls and system dialogs for file/folder selection, notifications, and accessibility behavior.

## Responsive Windows behavior

- Wide desktop: full navigation rail, signal spine, main content, optional context drawer.
- Narrow desktop: rail collapses to icons; context drawer becomes overlay.
- Companion: only current task/status, capture indicator, pause, stop, and open-dashboard controls.

## UI acceptance checklist

- [ ] Chat is the landing screen.
- [ ] Every task/MCP/skill/desktop action created from chat links back to its source message.
- [ ] No imported repository content can execute from preview.
- [ ] Every sensitive state is understandable without opening raw logs.
- [ ] Desktop capture/autonomy is visibly active, bounded, pausable, and stoppable.
- [ ] All settings have safe defaults and a clear description.
