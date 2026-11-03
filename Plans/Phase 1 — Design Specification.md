# NEXORA — Phase 1: Core Backend Foundation
## Technical Design Specification — Version 1.0

---

## 1. Executive Summary

This document specifies the architectural and technical design for **Phase 1: Core Backend Foundation** of the NEXORA local autonomous AI agent. 

The primary objective of Phase 1 is to build a robust, production-grade Python FastAPI backend that interfaces reliably with a locally running Ollama instance (`qwen3.5:9b`), complete with diagnostics, concurrency controls for local GPU protection, and an automated offline test suite.

---

## 2. Understanding Summary

* **Objective**: Establish the core backend and verified local LLM communication bridge.
* **Target Environment**: Windows 11 on AMD Ryzen 7 5700X, 16 GB RAM, NVIDIA RTX 5050 (8 GB VRAM).
* **Technology Stack**: Python 3.10+, FastAPI, Uvicorn, Pydantic v2, `pydantic-settings`, HTTPX, Pytest.
* **LLM Engine**: Locally hosted Ollama (`http://localhost:11434`), default model: `qwen3.5:9b`.
* **State Management**: Stateless backend. `POST /api/chat` receives client-managed message history (`messages: list[ChatMessage]`).
* **Delivery Model**: Standard JSON response contracts for Phase 1 (streaming and WebSockets deferred to subsequent UI phases).
* **GPU Protection**: Centralized concurrency guard (`asyncio.Semaphore(1)`) preventing concurrent model inference and VRAM thrashing on the 8 GB RTX 5050.
* **Resilience**: Non-blocking startup with decoupled health probes (backend health is independent of Ollama availability).
* **Explicit Non-Goals (Scope Restrictions)**:
  * No frontend interface (React/Vite).
  * No desktop automation, mouse/keyboard control, or screenshot capture.
  * No browser automation (Playwright).
  * No unrestricted terminal/shell execution.
  * No autonomous background scheduler or task execution loops.
  * No long-term persistent memory or database storage.

---

## 3. Assumptions

1. **Local Ollama**: Ollama is installed on the host machine and listens on `http://localhost:11434` by default.
2. **Environment**: Standard Python virtual environment (`.venv`) managed via PowerShell on Windows 11.
3. **Network Isolation**: The backend server binds strictly to `127.0.0.1:8000` by default.
4. **Testing Offline**: All backend unit tests must run and pass without requiring an active Ollama process or GPU execution.

---

## 4. Decision Log

| # | Topic | Decision | Alternatives Considered | Rationale |
|---|---|---|---|---|
| **D1** | Scope for Phase 1 | Focus exclusively on Core Backend Foundation (FastAPI + Ollama) | Macro specification review; Agent planner deep-dive | Builds a verified local LLM foundation first before introducing complex agentic tooling. |
| **D2** | Chat State Management | Stateless backend; client passes `messages: list[ChatMessage]` | Backend in-memory session store; Single-turn prompt string | Keeps backend simple, prevents memory leaks, and matches standard chat completion patterns. |
| **D3** | Response Delivery | Standard JSON response for `POST /api/chat` in Phase 1 | SSE streaming; WebSockets | Prioritizes simple testing and verifiable contracts; streaming deferred to UI integration. |
| **D4** | Startup & Resilience | Non-blocking startup; independent health endpoints; 60–120s timeout | Fail-fast startup; Background warmup poll | Allows offline testing, diagnostic clarity, and tolerates cold VRAM loading. |
| **D5** | GPU VRAM Protection | Centralized `asyncio.Semaphore` (default 1) with acquisition timeout returning HTTP 503 `INFERENCE_BUSY` | Unbounded requests; Process-wide thread lock | Protects the 8 GB RTX 5050 from VRAM thrashing with clear backpressure signaling. |
| **D6** | Logging Architecture | Dual sink (formatted console + rotating file at `data/logs/nexora_backend.log`) | Console-only; Pure JSON files | Provides real-time developer terminal visibility and persistent troubleshooting logs. |
| **D7** | Error Status Separation | `/api/health` reports FastAPI status; `/api/ollama/status` reports Ollama & model status | Single blended health status endpoint; Generic 500 errors | Isolates faults cleanly between web server, local runtime, and model loading. |
| **D8** | Lifespan & HTTP Client | Single shared `httpx.AsyncClient` instantiated and closed via FastAPI `lifespan` | Per-request client creation; Global singleton import | Prevents socket exhaustion, connection leaks, and ensures graceful teardown. |
| **D9** | Dependency Injection | Native FastAPI `Depends(...)` for services, clients, and guards | Injector/Dependency-injector packages; Manual module globals | Zero third-party DI bloat; idiomatic, easily overridden in unit tests. |
| **D10** | Error Response Schema | Unified Pydantic `ErrorResponse` schema across all endpoints | Default FastAPI validation errors; Inconsistent ad-hoc dictionaries | Consistent machine-readable contract for frontend and test assertions. |

---

## 5. Architectural Design

### 5.1 Project Directory Structure

```text
NEXORA/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── dependencies.py      # FastAPI Depends() providers
│   │   │   └── routes/
│   │   │       ├── health.py        # GET /api/health
│   │   │       ├── ollama.py        # GET /api/ollama/status, GET /api/ollama/models
│   │   │       └── chat.py          # POST /api/chat
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic Settings (.env loader)
│   │   │   ├── logging.py           # Dual-sink logging configuration
│   │   │   └── guard.py             # InferenceSemaphore with acquisition timeout
│   │   ├── models/
│   │   │   ├── common.py            # ErrorResponse, ErrorDetail schemas
│   │   │   ├── health.py            # HealthCheckResponse schema
│   │   │   ├── ollama.py            # OllamaStatusResponse, ModelInfo schemas
│   │   │   └── chat.py              # ChatMessage, ChatRequest, ChatResponse
│   │   ├── services/
│   │   │   └── ollama_service.py    # Async Ollama communication & translation
│   │   └── main.py                  # FastAPI app factory & lifespan
│   ├── tests/
│   │   ├── conftest.py              # TestClient, mock fixtures, settings overrides
│   │   ├── test_health.py
│   │   ├── test_ollama.py
│   │   └── test_chat.py
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
├── data/
│   └── logs/
│       └── nexora_backend.log       # Application logs (rotating)
└── Plans/
```

### 5.2 Application Lifespan & Dependency Injection

`backend/app/main.py` uses FastAPI's `@asynccontextmanager` to bind resources cleanly:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup:
    setup_logging()
    settings = get_settings()
    app.state.http_client = httpx.AsyncClient(
        base_url=settings.OLLAMA_BASE_URL,
        timeout=httpx.Timeout(settings.OLLAMA_INFERENCE_TIMEOUT_SECONDS, connect=5.0)
    )
    app.state.inference_guard = InferenceGuard(
        limit=settings.INFERENCE_CONCURRENCY_LIMIT,
        timeout=settings.INFERENCE_SEMAPHORE_TIMEOUT_SECONDS
    )
    yield
    # Shutdown:
    await app.state.http_client.aclose()
```

Dependencies (`backend/app/api/dependencies.py`):
* `get_settings() -> Settings`
* `get_http_client(request: Request) -> httpx.AsyncClient`
* `get_inference_guard(request: Request) -> InferenceGuard`
* `get_ollama_service(...) -> OllamaService`

---

## 6. Data Contracts & Unified Error Handling

### 6.1 Common Error Schema (`models/common.py`)

```python
class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict | list | None = None

class ErrorResponse(BaseModel):
    error: ErrorDetail
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

Standard error codes:
* `INFERENCE_BUSY` (HTTP 503): Concurrency limit reached and semaphore acquisition timed out.
* `OLLAMA_UNAVAILABLE` (HTTP 503): Network connection to local Ollama service refused or failed.
* `MODEL_NOT_FOUND` (HTTP 404): Configured or requested model is not installed in Ollama.
* `INFERENCE_TIMEOUT` (HTTP 504): Model generation exceeded the configured timeout threshold.
* `OLLAMA_MALFORMED_RESPONSE` (HTTP 502): Ollama returned an unparsable response.
* `VALIDATION_ERROR` (HTTP 422): Request schema validation failure.

### 6.2 Health & Status Schemas

* `GET /api/health` $\rightarrow$ `HealthCheckResponse`:
  * `status`: `"ok"`
  * `app_name`: `"NEXORA"`
  * `version`: `"0.1.0"`
  * `environment`: `"development"`
  * `timestamp`: ISO-8601 string
* `GET /api/ollama/status` $\rightarrow$ `OllamaStatusResponse`:
  * `reachable`: `bool`
  * `model_available`: `bool`
  * `configured_model`: `"qwen3.5:9b"`
  * `installed_models`: `list[str]`
  * `checked_at`: ISO-8601 string
* `GET /api/ollama/models` $\rightarrow$ `ModelListResponse`:
  * `models`: `list[ModelItem]`

### 6.3 Chat Schemas

* `POST /api/chat` $\rightarrow$ Input: `ChatRequest`:
  * `messages`: `list[ChatMessage]` where `ChatMessage(role: "system"|"user"|"assistant", content: str)`
  * `model`: `Optional[str] = None` (defaults to configured model)
  * `temperature`: `Optional[float] = None`
* `POST /api/chat` $\rightarrow$ Output: `ChatResponse`:
  * `message`: `ChatMessage`
  * `model`: `str`
  * `done`: `bool`
  * `eval_count`: `Optional[int]`
  * `total_duration_ms`: `Optional[float]`

---

## 7. Service Layer & Concurrency Control

### 7.1 Inference Guard (`core/guard.py`)

Protects 8 GB GPU VRAM from multi-request thrashing:

```python
class InferenceGuard:
    def __init__(self, limit: int = 1, timeout: float = 5.0):
        self._semaphore = asyncio.Semaphore(limit)
        self._timeout = timeout

    @asynccontextmanager
    async def acquire(self):
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=self._timeout)
        except asyncio.TimeoutError:
            raise InferenceBusyException("Inference capacity busy. Try again shortly.")
        try:
            yield
        finally:
            self._semaphore.release()
```

### 7.2 Ollama Service (`services/ollama_service.py`)

* Encapsulates all communication with Ollama endpoints (`/api/tags`, `/api/chat`).
* Translates low-level `httpx` exceptions into domain exceptions handled by global FastAPI exception handlers.
* Enforces inference timeouts (default 120s) to support cold-loading model weights.

---

## 8. Configuration Specification (`core/config.py`)

| Variable | Type | Default | Description |
|---|---|---|---|
| `APP_NAME` | `str` | `"NEXORA"` | Application display name |
| `APP_ENV` | `str` | `"development"` | Application environment |
| `HOST` | `str` | `"127.0.0.1"` | Bind host |
| `PORT` | `int` | `8000` | Bind port |
| `OLLAMA_BASE_URL` | `str` | `"http://localhost:11434"` | Local Ollama endpoint |
| `OLLAMA_MODEL` | `str` | `"qwen3.5:9b"` | Default reasoning model |
| `INFERENCE_CONCURRENCY_LIMIT` | `int` | `1` | Max concurrent model generations |
| `INFERENCE_SEMAPHORE_TIMEOUT_SECONDS` | `float` | `5.0` | Max wait time for inference semaphore |
| `OLLAMA_INFERENCE_TIMEOUT_SECONDS` | `float` | `120.0` | Max wait time for model generation |
| `LOG_LEVEL` | `str` | `"INFO"` | Console & file log level |
| `LOG_FILE_PATH` | `str` | `"data/logs/nexora_backend.log"` | Path to rotating log file |

---

## 9. Testing Strategy

All tests execute in `backend/tests/` via `pytest`:
* **Zero Real GPU/Ollama Dependency**: `pytest-asyncio` + mock fixtures (`pytest-httpx` / mock transports).
* **Test Matrix**:
  1. `test_health.py`: Confirms `/api/health` returns 200 even when Ollama is offline.
  2. `test_ollama.py`: Validates `/api/ollama/status` and `/api/ollama/models` under online, offline, and missing-model conditions.
  3. `test_chat.py`:
     * Successful chat completion with mocked token payload.
     * Ollama offline triggers HTTP 503 `OLLAMA_UNAVAILABLE`.
     * Missing model triggers HTTP 404 `MODEL_NOT_FOUND`.
     * Inference timeout triggers HTTP 504 `INFERENCE_TIMEOUT`.
     * Two concurrent requests verify that the second request times out on semaphore and receives HTTP 503 `INFERENCE_BUSY`.

---

## 10. Risk Assessment & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **VRAM Exhaustion (OOM)** | GPU crash / system freeze | Enforce `INFERENCE_CONCURRENCY_LIMIT=1` via `InferenceGuard` semaphore. |
| **Model Cold-Start Timeout** | Chat requests fail on first run | Configure generous 120s timeout for model weight loading. |
| **Ollama Offline at Boot** | Backend fails to start | Non-blocking startup; independent health endpoints return structured diagnostics. |
| **Connection Leak** | Socket exhaustion over time | Single shared `httpx.AsyncClient` managed via FastAPI application `lifespan`. |
