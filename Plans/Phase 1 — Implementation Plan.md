# NEXORA — Phase 1: Implementation Plan
## Core Backend Foundation

---

### Task List & Execution Status

- [x] **Step 1: Environment & Dependency Setup**
  - Created `backend/requirements.txt` with pinned/compatible versions (`fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `httpx`, `pytest`, `pytest-asyncio`).
  - Created `backend/.env.example` and `backend/.env` with default configuration values.
  - Initialized `data/logs/` with `.gitkeep` and configured `.gitignore`.

- [x] **Step 2: Core Infrastructure (Config, Logging, Guard)**
  - Implemented `backend/app/core/config.py`: `pydantic-settings` loader with defaults for Windows host, Ollama URL, model, and timeout thresholds.
  - Implemented `backend/app/core/logging.py`: Structured console logging and rotating file handler writing to `data/logs/nexora_backend.log`.
  - Implemented `backend/app/core/guard.py`: `InferenceGuard` managing `asyncio.Semaphore` with acquisition timeout and `InferenceBusyException`.
  - Implemented `backend/app/core/exceptions.py`: Centralized domain exceptions.

- [x] **Step 3: Domain Models & Exception Contracts**
  - Implemented `backend/app/models/common.py`: Unified `ErrorResponse`, `ErrorDetail`, and custom domain exception bindings.
  - Implemented `backend/app/models/health.py`: `HealthCheckResponse` (backend operational status).
  - Implemented `backend/app/models/ollama.py`: `OllamaStatusResponse` (separate reachability & model availability flags) and `ModelListResponse`.
  - Implemented `backend/app/models/chat.py`: `ChatMessage`, `ChatRequest` (stateless client-managed history), and `ChatResponse`.

- [x] **Step 4: Ollama Service Layer**
  - Implemented `backend/app/services/ollama_service.py`:
    - Reachability check (`GET /api/tags`).
    - Model listing and availability verification for `qwen3.5:9b`.
    - Chat invocation (`POST /api/chat`) with timeout enforcement.
    - Exception translation for connection errors, missing models, malformed payloads, and timeouts.

- [x] **Step 5: API Routes, Lifespan & Application Wiring**
  - Implemented `backend/app/api/dependencies.py`: Dependency injection providers for `Settings`, `httpx.AsyncClient`, `InferenceGuard`, and `OllamaService`.
  - Implemented `backend/app/api/routes/health.py`: `GET /api/health`.
  - Implemented `backend/app/api/routes/ollama.py`: `GET /api/ollama/status`, `GET /api/ollama/models`.
  - Implemented `backend/app/api/routes/chat.py`: `POST /api/chat` guarded by `InferenceGuard`.
  - Implemented `backend/app/main.py`: FastAPI app factory, lifespan manager for shared client & guard teardown, global exception handlers mapping domain exceptions to `ErrorResponse`.

- [x] **Step 6: Comprehensive Offline Test Suite**
  - Implemented `backend/tests/conftest.py`: Async test fixtures with mock HTTP transports.
  - Implemented `backend/tests/test_health.py`: Tests backend health independent of Ollama.
  - Implemented `backend/tests/test_ollama.py`: Tests online, offline, and model-not-found scenarios.
  - Implemented `backend/tests/test_chat.py`: Tests valid generation, Ollama offline (503), model missing (404), timeout (504), and concurrency saturation (503 `INFERENCE_BUSY`).
  - **Result**: 13/13 tests passed in 0.46s.

- [x] **Step 7: Documentation & Live Verification**
  - Created `backend/README.md` with exact Windows PowerShell instructions for setup, running, and testing.
  - Verified live Ollama connectivity on `localhost:11434` with `qwen3.5:9b` returning 200 OK.
  - Confirmed zero Phase 2 scope leaks.
