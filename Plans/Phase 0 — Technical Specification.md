# NEXORA
## Local Autonomous Intelligence
### Technical Specification — Version 1.0

## 1. Project Overview

NEXORA is a local-first autonomous AI computer agent designed for Windows 11.

Its primary objective is to understand natural-language instructions, plan multi-step tasks, interact with the computer through controlled tools, and complete tasks with minimal human intervention.

NEXORA will use a locally hosted language model through Ollama as its reasoning engine.

It will operate through a local web dashboard connected to a Python backend.

NEXORA is an independent project. Do not integrate it with any existing personal assistant, chatbot, or previous project.

## 2. Primary Objectives

NEXORA must eventually support:

- Natural-language interaction.
- Multi-step task planning.
- Autonomous task execution.
- Browser automation.
- Desktop interaction.
- Mouse and keyboard control.
- Screenshot capture and visual understanding.
- File creation, reading, editing and organization.
- Controlled terminal execution.
- Persistent memory.
- Background task execution.
- Scheduled tasks.
- Error detection and recovery.
- Execution verification.
- Human approval for sensitive actions.
- Real-time task and activity monitoring.

## 3. Target Environment

Operating System: Windows 11

Hardware:
- CPU: AMD Ryzen 7 5700X
- RAM: 16 GB
- GPU: NVIDIA RTX 5050 8 GB VRAM

AI Runtime:
- Ollama

Initial Model:
- qwen3.5:9b

The implementation must consider the available VRAM and system memory. Avoid loading multiple large language models simultaneously.

## 4. Technology Stack

Backend:
- Python
- FastAPI
- Pydantic
- WebSockets

AI:
- Ollama API
- Qwen 3.5 9B

Frontend:
- React
- Vite
- TypeScript

Automation:
- Playwright for browser automation.
- Windows-compatible UI automation for desktop interaction.
- Screenshot capture and mouse/keyboard interaction.

Database:
- SQLite for initial persistent storage.

Scheduling:
- APScheduler or an equivalent Python scheduling solution.

Testing:
- Pytest for backend testing.
- Frontend tests where appropriate.

## 5. High-Level Architecture

The application must use a modular architecture.

The main components are:

1. Frontend Dashboard
2. FastAPI Backend
3. Agent Orchestrator
4. Planning Engine
5. LLM Provider
6. Tool Registry
7. Permission Manager
8. Execution Engine
9. Memory Manager
10. Task Scheduler
11. Logging and Monitoring

The frontend communicates with the backend through HTTP APIs and WebSockets.

The Agent Orchestrator communicates with the local LLM through Ollama.

The Execution Engine invokes registered tools only after checking their permissions.

## 6. Proposed Project Structure

NEXORA/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── tools/
│   │   ├── permissions/
│   │   ├── memory/
│   │   ├── scheduler/
│   │   ├── services/
│   │   └── main.py
│   │
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│
├── data/
│   ├── memory/
│   ├── tasks/
│   └── logs/
│
├── docs/
│
├── .gitignore
└── README.md

The structure may evolve when justified, but maintain clear separation between components.

## 7. Agent Execution Principles

NEXORA must eventually support the following execution cycle:

USER REQUEST
    ↓
REQUEST UNDERSTANDING
    ↓
TASK PLANNING
    ↓
PLAN VALIDATION
    ↓
PERMISSION CHECK
    ↓
TOOL EXECUTION
    ↓
RESULT OBSERVATION
    ↓
SUCCESS VERIFICATION
    ↓
NEXT STEP OR RECOVERY
    ↓
FINAL RESPONSE

The agent must not assume that a tool succeeded simply because it returned without an exception.

Where possible, it must independently verify the result.

## 8. Permission and Security Model

Implement a centralized permission manager.

Safe operations:
- Read permitted files.
- Search within permitted directories.
- Summarize information.
- Create temporary files inside the designated workspace.

Controlled operations:
- Modify existing files.
- Execute scripts.
- Install software.
- Interact with external websites.

Sensitive operations:
- Delete important data.
- Send emails or messages.
- Make purchases or payments.
- Access credentials.
- Change system settings.
- Execute administrative commands.

Sensitive actions must require explicit user approval.

Never expose API keys, credentials, passwords or private configuration values in logs or model prompts unnecessarily.

Do not provide unrestricted administrator or shell access to the agent.

## 9. Local-First Requirements

- Ollama is the default LLM provider.
- Do not require an external AI API.
- Store application data locally.
- Keep configuration separate from source code.
- Provide clear error messages if Ollama is unavailable.
- Make the model configurable rather than hardcoding it throughout the application.

## 10. Development Rules

Follow these rules throughout development:

1. Build one phase at a time.
2. Do not implement future phases prematurely.
3. Keep modules independent and maintainable.
4. Use type hints and structured validation.
5. Handle errors explicitly.
6. Write tests for important functionality.
7. Do not silently replace working architecture.
8. Avoid unnecessary dependencies.
9. Document important design decisions.
10. Do not claim a feature is complete without testing it.
11. Preserve existing working functionality when modifying code.
12. Ask before making major architectural changes.

## 11. Initial Development Scope

The first implementation phase must focus exclusively on:

- Backend project initialization.
- FastAPI application setup.
- Ollama connectivity.
- Model availability checks.
- Basic chat communication.
- Configuration management.
- Logging.
- Health-check endpoints.
- Initial backend tests.

Do not implement desktop automation, unrestricted terminal execution, browser control, autonomous scheduling or persistent long-term memory in the first phase.

These capabilities will be added incrementally.

## 12. Definition of Success

NEXORA should eventually become a reliable local autonomous computer agent capable of completing real-world multi-step tasks while maintaining user control, transparency and security.

The project must prioritize reliability and verifiable execution over simply maximizing autonomy.