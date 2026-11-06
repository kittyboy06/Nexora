# Module 06 — Browser and Research Service

## Responsibility

Own browser contexts, external web requests, research evidence, downloads and cleanup. Agents ask for narrow, typed research operations. They do not receive raw browser-profile control, ambient cookies or permission to act on page instructions.

## Operations

Initial operations are search, navigate/fetch, extract bounded content, cite source, capture permitted page-state evidence and download to quarantine. Each has typed inputs, origin policy, size/time limits, cancellation and normalized output. Login, authenticated context attachment, upload, form submit, messaging, purchase and account change are separate sensitive operations.

## Context isolation

Create an isolated browser context per task by default, with no user session/cookies. Attach an existing signed-in context only with explicit task/site scope, visible status, expiry and revocation. Never share existing session credentials across unrelated agents/tasks. Dispose contexts, temporary profiles, downloads and processes deterministically.

## Page content and evidence

All page text is untrusted external data and is quoted/labeled as such in prompts. Research artifacts store URL, title, timestamp, relevant extract, status, hash and request policy, subject to retention/redaction. They support provenance but do not prove claims are true. Browser page instructions cannot cause tool calls or permission changes.

## Downloads

Place files in task-specific quarantine. Enforce allowed origin, redirect, type, name, size and hash policy. Do not auto-open/run downloads. Move inspected safe data into existing workspace boundaries only through registered filesystem tools.

## Tests

Fixture pages for injection, redirects, oversized content, invalid markup, download hazards and failures; context cleanup; domain policy; session authorization; external side-effect approval; cancellation and evidence traces.
