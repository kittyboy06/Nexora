# NEXORA — Phase 9: Browser and Internet Research

## Purpose

Add a centralized research service so agents can search and inspect public web information with shared governance. The service gives agents structured research results and evidence, while keeping browser sessions, permissions and external side effects under deterministic control.

## Prerequisites

- Read `Modules/06 — Browser and Research Service.md` and `Modules/01 — Governance, Permissions, Audit and Verification.md`.
- Select browser automation engine and record Windows installation, profile isolation and versioning decisions.
- Dashboard approval/status design from Phase 5 is available.

## Scope

### Included

- Browser/research service with a controlled request queue, isolated context by default, navigation/search/extraction APIs, page-state evidence and explicit lifecycle cleanup.
- Typed tools for search, fetch/inspect, extract cited text, download-to-quarantine and optionally read a local downloaded file after validation.
- Per-task domain allow/deny policy, request/response size limits, timeout, redirect limit, download directory, content-type checks and safe filename handling.
- Structured research artifact: query, URLs, timestamps, source title, extracted content/citations, tool settings, fetch status and content hash.
- User authorization to attach an existing signed-in browser session for one task/scope only, if the chosen engine supports this safely.
- Dashboard research evidence view and pending approval action display.

### Excluded

- Automatic form submission, posting, messaging, account changes, purchases, uploads, payments or login without explicit task-scoped approval.
- Sharing browser cookies or authenticated sessions among agents by default.
- Always-on browsing/background monitoring.
- Treating search-result text as trusted instructions.

## Default permission policy

Public search, page navigation and extraction are normally `CONTROLLED` because they contact external services and expose query data. Domain policy may narrow them. Downloads, uploads, logins, form submission, clipboard interaction, browser extension use and authenticated session attachment require stronger policy; sensitive external side effects require action-scoped user approval.

The service must make query/data exposure visible before executing a task that sends private context to a search engine or site. It should submit the smallest query necessary.

## Browser context lifecycle

1. Task requests an allowed research operation.
2. Permission manager approves according to policy; no raw URL/model instruction can bypass domain policy.
3. Browser service creates/reuses an isolated task context with no ambient user profile/cookies.
4. It applies navigation controls, timeout and allowed origins.
5. It extracts only required content, stores a bounded evidence artifact, and closes/disposes the context after task completion.
6. Existing-session use follows explicit authorization, selected profile/site scope, visible indicator, expiration and cleanup/revocation. It must never silently attach a user profile.

## Prompt-injection defenses

Web content can contain attempts to alter agent instructions. Browser service must label every extracted page/result as untrusted external content. Agent prompts separate system/task instructions from quoted material. Page text cannot create tools, change permission policy, ask the agent to reveal data, or cause navigation/action beyond the original bounded request. The planner must confirm any new action against policy rather than following text in a page.

## Download handling

Downloads enter a task-specific quarantine directory, not the project or user Downloads folder. Validate redirect chain, HTTP status, size, type/extension, filename and hash. Do not automatically open executable/archive documents. Future file processing routes through the existing workspace security boundary and appropriate scanners/validators. Downloading a file does not authorize executing it.

## Verification

For a research task, verification means evidence supports the report: source URL, access time, relevant extract and fetch status exist. It does not prove a page is true. For a browser side effect, verification must inspect the resulting page/application state and may still be `UNCERTAIN` if a request could have been submitted but confirmation is unavailable.

## Test plan

- Local fixture pages for normal extraction, redirect loop, oversized body, hostile instructions, malformed HTML, unexpected download and navigation error.
- Domain policy, origin change, timeout, cancellation and context cleanup tests.
- Existing-session authorization/expiry/revocation tests with a mocked profile adapter.
- Download quarantine and dangerous content rejection tests.
- Assert browser actions are not possible through direct model/tool bypass.
- Opt-in live tests only on harmless public pages and disposable accounts; never submit a real form in automated tests.

## Acceptance criteria

- Agents receive bounded, cited research artifacts rather than unrestricted browser access.
- Isolated contexts are the default and cleanup is confirmed.
- Page instructions cannot affect permissions or policy.
- Authenticated sessions, downloads and external side effects use explicit policy/approval paths.
- Browser failures/cancellations do not leak sessions or leave hidden processes.

## Implementation sequence

1. Publish engine/profile/isolation decision record.
2. Build a local fixture-backed research service and typed schemas.
3. Add safe public navigation/extraction tools with evidence artifacts.
4. Add dashboard evidence/status display and policy errors.
5. Add quarantine downloads and session authorization architecture.
6. Add opt-in live smoke checks and record only actual results.
