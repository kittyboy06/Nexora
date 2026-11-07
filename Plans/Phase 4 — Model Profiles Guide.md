# NEXORA — Phase 4 Model Profiles & Hybrid Routing Guide

**Document Type:** Configuration & Operations Guide  
**Project:** NEXORA — Local Autonomous Intelligence  
**Target:** Phase 4 (Agent Fleet Foundation)  
**Status:** Implemented & Verified  

---

## 1. Overview

NEXORA's Phase 4 introduces the **Model Profile Registry** and **Hybrid Model Router**. This allows tasks to be classified and dispatched to specialized profiles (coding, research, reasoning, general) with automated escalation, fallback, and full diagnostic visibility.

Routing decisions only choose the model and system instructions for task planning. They do **not** bypass deterministic validation, tool permission gates, or execution limits.

---

## 2. Configuration & Catalogue (`data/model_profiles.json`)

Specialist profiles are defined in `data/model_profiles.json`. Multiple profiles can reference the same locally installed model, or point to different models.

### Example Configuration:

```json
{
  "profiles": [
    {
      "profile_id": "router",
      "model": "qwen2.5:1.5b",
      "specialties": ["general"],
      "system_instruction": "Classify task intent and return the requested routing JSON only.",
      "role": "router",
      "enabled": true
    },
    {
      "profile_id": "general-planner",
      "model": "qwen3.5:9b",
      "specialties": ["general"],
      "system_instruction": "Create concise, tool-grounded plans and do not assume tools that are not listed.",
      "role": "planner",
      "enabled": true
    },
    {
      "profile_id": "coding-planner",
      "model": "qwen3.5:9b",
      "specialties": ["code"],
      "system_instruction": "For coding goals, plan small, verifiable steps and use only registered tools.",
      "role": "planner",
      "enabled": true
    },
    {
      "profile_id": "research-planner",
      "model": "qwen3.5:9b",
      "specialties": ["research"],
      "system_instruction": "For research goals, identify evidence needs and use only registered tools.",
      "role": "planner",
      "enabled": true
    },
    {
      "profile_id": "reasoning-planner",
      "model": "qwen3.5:9b",
      "specialties": ["reasoning"],
      "system_instruction": "For analytical goals, decompose dependencies and validate each conclusion.",
      "role": "planner",
      "enabled": true
    }
  ]
}
```

### Profile Fields:
* `profile_id`: Unique identifier (e.g. `coding-planner`).
* `model`: The Ollama model name (e.g. `qwen3.5:9b` or `qwen2.5:1.5b`).
* `specialties`: Supported task kinds (`code`, `research`, `reasoning`, `general`).
* `system_instruction`: Specialist guidance injected into the planner's system prompt.
* `role`: `planner`, `router`, or `worker`.
* `enabled`: Set to `false` to disable a profile without deleting it.

---

## 3. Environment Variables

Configure these settings in your `.env` or environment:

* `OLLAMA_MODEL`: Primary reasoning model (default: `qwen3.5:9b`).
* `MODEL_ROUTER_MODEL`: Lightweight router model (default: `qwen3.5:9b`). If pointed to a smaller model (e.g. `qwen2.5:1.5b`), NEXORA will route with the smaller model first.
* `MODEL_ROUTER_CONFIDENCE_THRESHOLD`: Confidence score (default: `0.65`) below which the router escalates to the primary model.
* `MODEL_PROFILES_FILE`: Path to profiles JSON (default: `data/model_profiles.json`).

---

## 4. Hybrid Routing Flow

1. **Inventory Check:** Router queries local Ollama tags. Only enabled profiles whose models are currently installed are eligible for selection.
2. **Manual Override:** If `model_profile_id` is supplied in `POST /api/agent/tasks`, classification is skipped and the requested profile is used directly.
3. **Small Model Classification:** Router prompts `MODEL_ROUTER_MODEL` to return `{"task_kind": "...", "confidence": float}`.
4. **Escalation:** If confidence < threshold and `MODEL_ROUTER_MODEL != OLLAMA_MODEL`, escalates to `OLLAMA_MODEL`.
5. **Deterministic Heuristic Fallback:** If output is unparseable or confidence remains low, keyword scoring selects the best category.
6. **Task Diagnostics:** Selected `profile_id`, `model`, `task_kind`, `reason`, and `escalated` are durably recorded in `task.routing`.

---

## 5. Dynamic Profile Reloading

Changes to `data/model_profiles.json` can be loaded dynamically without restarting the server:

* **Trigger via API:**
  * `POST /api/ollama/profiles/reload`: forces immediate reload from disk and returns the updated catalogue.
  * `GET /api/ollama/profiles?refresh=true`: reloads and returns profile availability.
* **Internal Programmatic Reload:**
  * `ModelProfileRegistry.reload()` re-reads the JSON, validates schemas, ensures default primary fallback, and updates the in-memory catalogue atomically.

---

## 6. Resilience & Offline Ollama Behavior

* If Ollama is offline when a task begins, the task cleanly transitions to `TaskStatus.FAILED` with a diagnostic error message:
  `"Local Ollama service is unreachable at configured URL."`
* The task record and its failure state are persisted to disk at `data/tasks/<task_id>.json`.
* Tasks never hang indefinitely in `PLANNING` or `PARSING` state.
