# NEXORA — Phase 1: Implementation Plan
## Core Backend Foundation

---

### Task List & Execution Sequence

- [ ] **Step 1: Environment & Dependency Setup**
  - Create `backend/requirements.txt` with pinned/compatible versions: `fastapi`, `uvicorn[standard]`, `pydantic>=2.0`, `pydantic-settings`, `httpx>=0.27`, `pytest`, `pytest-asyncio`, `respx`.
  - Create `backend/.env.example` with default configuration values.
  - Create `data/logs/` directory.

- [ ] **Step 2: Core Infrastructure (Config, Logging, Guard)**
  - Implement `backend/app/core/config.py`: `pydantic-settings` loader with defaults for Windows host, Ollama URL, model, and timeout thresholds.
  - Implement `backend/app/core/logging.py`: Structured console logging and rotating file handler writing to `data/logs/nexora_backend.log`.
  - Implement `backend/app/core/guard.py`: `InferenceGuard` managing `asyncio.Semaphore` with acquisition timeout and `InferenceBusyException`.

- [ ] **Step 3: Domain Models & Exception Contracts**
  - Implement `backend/app/models/common.py`: Unified `ErrorResponse`, `ErrorDetail`, and custom domain exceptions.
  - Implement `backend/app/models/health.py`: `HealthCheckResponse` (backend operational status).
  - Implement `backend/app/models/ollama.py`: `OllamaStatusResponse` (separate reachability & model availability flags) and `ModelListResponse`.
  - Implement `backend/app/models/chat.py`: `ChatMessage`, `ChatRequest` (stateless client-managed history), and `ChatResponse`.

- [ ] **Step 4: Ollama Service Layer**
  - Implement `backend/app/services/ollama_service.py`:
    - Reachability check (`GET /api/tags`).
    - Model listing and availability verification for `qwen3.5:9b`.
    - Chat invocation (`POST /api/chat`) with timeout enforcement.
    - Translation of `httpx` exceptions to domain exceptions.

- [ ] **Step 5: API Routes, Lifespan & Application Wiring**
  - Implement `backend/app/api/dependencies.py`: Dependency injection providers for `Settings`, `httpx.AsyncClient`, `InferenceGuard`, and `OllamaService`.
  - Implement `backend/app/api/routes/health.py`: `GET /api/health`.
  - Implement `backend/app/api/routes/ollama.py`: `GET /api/ollama/status`, `GET /api/ollama/models`.
  - Implement `backend/app/api/routes/chat.py`: `POST /api/chat` guarded by `InferenceGuard`.
  - Implement `backend/app/main.py`: FastAPI app factory, lifespan manager for shared client & guard teardown, global exception handlers mapping domain exceptions to `ErrorResponse`.

- [ ] **Step 6: Comprehensive Offline Test Suite**
  - Implement `backend/tests/conftest.py`: Async test client and fixtures using `respx` to mock Ollama HTTP responses.
  - Implement `backend/tests/test_health.py`: Test backend health independent of Ollama.
  - Implement `backend/tests/test_ollama.py`: Test online, offline, and model-not-found scenarios.
  - Implement `backend/tests/test_chat.py`: Test valid generation, Ollama offline (503), model missing (404), timeout (504), and concurrency saturation (503 `INFERENCE_BUSY`).
  - Run and verify all tests pass via `pytest`.

- [ ] **Step 7: Documentation & Verification**
  - Create `backend/README.md` with exact Windows PowerShell commands for venv creation, setup, running, and testing.
  - Verify live Ollama reachability if Ollama is running on the local host.
  - Provide Phase 1 completion summary.
