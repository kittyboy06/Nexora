import asyncio
import pytest
import httpx
from httpx import ASGITransport


@pytest.mark.asyncio
async def test_chat_success(app_with_mock_ollama):
    def handler(request: httpx.Request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3.5:9b"}]})
        if request.url.path == "/api/chat":
            return httpx.Response(
                200,
                json={
                    "model": "qwen3.5:9b",
                    "message": {"role": "assistant", "content": "Hello! I am NEXORA."},
                    "done": True,
                    "total_duration": 1500000000,
                    "eval_count": 24,
                },
            )
        return httpx.Response(404)

    app, mock_client = app_with_mock_ollama(handler)
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "messages": [
                {"role": "user", "content": "Hello NEXORA"}
            ]
        }
        resp = await client.post("/api/chat", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"]["role"] == "assistant"
        assert data["message"]["content"] == "Hello! I am NEXORA."
        assert data["model"] == "qwen3.5:9b"
        assert data["done"] is True
        assert data["eval_count"] == 24
        assert data["duration_ms"] == 1500.0
    await mock_client.aclose()


@pytest.mark.asyncio
async def test_chat_validation_error_empty_messages(app_with_mock_ollama):
    def handler(request: httpx.Request):
        return httpx.Response(200)

    app, mock_client = app_with_mock_ollama(handler)
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/chat", json={"messages": []})
        assert resp.status_code == 422
        data = resp.json()
        assert data["error"]["code"] == "VALIDATION_ERROR"
    await mock_client.aclose()


@pytest.mark.asyncio
async def test_chat_ollama_offline_returns_503(app_with_mock_ollama):
    def offline_handler(request: httpx.Request):
        raise httpx.ConnectError("Ollama is not running", request=request)

    app, mock_client = app_with_mock_ollama(offline_handler)
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"messages": [{"role": "user", "content": "Ping"}]}
        resp = await client.post("/api/chat", json=payload)
        assert resp.status_code == 503
        data = resp.json()
        assert data["error"]["code"] == "OLLAMA_UNAVAILABLE"
    await mock_client.aclose()


@pytest.mark.asyncio
async def test_chat_model_not_found_returns_404(app_with_mock_ollama):
    def handler(request: httpx.Request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "different-model:latest"}]})
        return httpx.Response(404)

    app, mock_client = app_with_mock_ollama(handler)
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"messages": [{"role": "user", "content": "Ping"}]}
        resp = await client.post("/api/chat", json=payload)
        assert resp.status_code == 404
        data = resp.json()
        assert data["error"]["code"] == "MODEL_NOT_FOUND"
    await mock_client.aclose()


@pytest.mark.asyncio
async def test_chat_inference_timeout_returns_504(app_with_mock_ollama):
    def timeout_handler(request: httpx.Request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3.5:9b"}]})
        if request.url.path == "/api/chat":
            raise httpx.TimeoutException("Inference timed out", request=request)
        return httpx.Response(404)

    app, mock_client = app_with_mock_ollama(timeout_handler)
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"messages": [{"role": "user", "content": "Long task"}]}
        resp = await client.post("/api/chat", json=payload)
        assert resp.status_code == 504
        data = resp.json()
        assert data["error"]["code"] == "INFERENCE_TIMEOUT"
    await mock_client.aclose()


@pytest.mark.asyncio
async def test_chat_concurrency_busy_returns_503(app_with_mock_ollama):
    # Simulate a slow inference (0.3s) where semaphore acquisition timeout is 0.1s
    async def slow_handler(request: httpx.Request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3.5:9b"}]})
        if request.url.path == "/api/chat":
            await asyncio.sleep(0.3)
            return httpx.Response(
                200,
                json={
                    "model": "qwen3.5:9b",
                    "message": {"role": "assistant", "content": "Finished"},
                    "done": True,
                },
            )
        return httpx.Response(404)

    app, mock_client = app_with_mock_ollama(slow_handler)
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"messages": [{"role": "user", "content": "Concurrent 1"}]}

        # Fire two concurrent requests
        res1, res2 = await asyncio.gather(
            client.post("/api/chat", json=payload),
            client.post("/api/chat", json=payload),
        )

        statuses = [res1.status_code, res2.status_code]
        # One request should succeed with 200, the other should be rejected with 503 INFERENCE_BUSY
        assert 200 in statuses
        assert 503 in statuses

        busy_res = res1 if res1.status_code == 503 else res2
        assert busy_res.json()["error"]["code"] == "INFERENCE_BUSY"

    await mock_client.aclose()
