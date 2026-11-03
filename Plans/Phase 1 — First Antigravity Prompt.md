# NEXORA — PHASE 1: CORE BACKEND FOUNDATION

You are working on NEXORA, a new independent local autonomous AI agent project.

Read and follow the NEXORA Technical Specification before implementing anything.

Your current responsibility is Phase 1 only.

## Objective

Build the initial Python backend and establish reliable communication with the locally installed Ollama instance.

The target environment is Windows 11.

The currently installed Ollama model is:

qwen3.5:9b

## Tasks

### 1. Initialize the backend

Create the backend structure according to the technical specification.

Use:
- Python
- FastAPI
- Uvicorn
- Pydantic
- HTTPX

Create a suitable requirements.txt.

### 2. Configuration Management

Implement centralized configuration.

Support:
- Ollama base URL.
- Model name.
- Backend host and port.
- Application environment.
- Logging configuration.

Use environment variables and provide a .env.example file.

Never hardcode sensitive configuration values.

Default Ollama URL:

http://localhost:11434

Default model:

qwen3.5:9b

### 3. Ollama Integration

Create a dedicated Ollama service.

It must support:

- Checking whether Ollama is reachable.
- Retrieving installed models.
- Checking whether the configured model is available.
- Sending a user message to the model.
- Receiving and parsing the response.
- Handling connection errors.
- Handling model-not-found errors.
- Handling timeout errors.
- Handling malformed responses.

Use asynchronous HTTP requests where appropriate.

Do not assume that every Ollama model supports identical tool-calling or structured-output behaviour. Test the actual installed model before designing future tool execution around it.

### 4. FastAPI Endpoints

Implement:

GET /api/health

Returns backend health information.

GET /api/ollama/status

Returns Ollama connectivity and model availability.

GET /api/ollama/models

Returns locally installed models.

POST /api/chat

Accepts a user message and returns the model response.

Use Pydantic request and response schemas.

### 5. Logging

Implement structured application logging.

Record:
- Application startup and shutdown.
- API requests.
- Ollama connection status.
- Model response errors.
- Unexpected exceptions.

Never log passwords, credentials or private secrets.

### 6. Testing

Create backend tests using Pytest.

Test:
- FastAPI startup.
- Health endpoint.
- Request validation.
- Ollama unavailable handling.
- Model unavailable handling.
- Chat response handling using mocked Ollama responses.

Tests must not require the real model to be running.

### 7. Documentation

Create a backend README explaining:

- Python environment setup.
- Dependency installation.
- Environment configuration.
- Starting the backend.
- Running tests.
- Available API endpoints.

Include exact Windows PowerShell commands.

## Restrictions

- Do not build the frontend yet.
- Do not implement desktop automation.
- Do not implement mouse or keyboard control.
- Do not implement browser automation.
- Do not implement unrestricted terminal execution.
- Do not implement autonomous background execution.
- Do not implement long-term memory.
- Do not introduce unnecessary dependencies.
- Do not modify files outside the NEXORA project directory.

## Completion Requirements

Before declaring Phase 1 complete:

1. Run the backend tests.
2. Resolve implementation-related test failures.
3. Start the FastAPI server.
4. Verify the health endpoint.
5. Verify Ollama connectivity.
6. Verify communication with qwen3.5:9b if Ollama is available.
7. Document any remaining limitations.

At the end, provide:

- Implemented components.
- Project structure.
- Dependencies added.
- Commands to run the application.
- Test results.
- Any unresolved issues.
- Confirmation that no Phase 2 features were implemented prematurely.

Do not proceed to Phase 2 without my instruction.