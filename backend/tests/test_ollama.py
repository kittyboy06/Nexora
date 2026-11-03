import json
import pytest
import httpx
from httpx import ASGITransport


@pytest.mark.asyncio
async def test_ollama_status_online_model_available(app_with_mock_ollama):
    def handler(request: httpx.Request):
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": "qwen3.5:9b", "size": 5200000000, "digest": "abc123"},
                        {"name": "llama3:8b", "size": 4700000000, "digest": "def456"},
                    ]
                },
            )
        return httpx.Response(404)

    app, mock_client = app_with_mock_ollama(handler)
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/ollama/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["reachable"] is True
        assert data["model_available"] is True
        assert "qwen3.5:9b" in data["installed_models"]
    await mock_client.aclose()


@pytest.mark.asyncio
async def test_ollama_status_online_model_missing(app_with_mock_ollama):
    def handler(request: httpx.Request):
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={"models": [{"name": "mistral:7b", "size": 4100000000}]},
            )
        return httpx.Response(404)

    app, mock_client = app_with_mock_ollama(handler)
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/ollama/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["reachable"] is True
        assert data["model_available"] is False
    await mock_client.aclose()


@pytest.mark.asyncio
async def test_ollama_status_offline_graceful(app_with_mock_ollama):
    def offline_handler(request: httpx.Request):
        raise httpx.ConnectError("Connection refused", request=request)

    app, mock_client = app_with_mock_ollama(offline_handler)
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/ollama/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["reachable"] is False
        assert data["model_available"] is False
        assert data["installed_models"] == []
    await mock_client.aclose()


@pytest.mark.asyncio
async def test_list_models_success(app_with_mock_ollama):
    def handler(request: httpx.Request):
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={"models": [{"name": "qwen3.5:9b", "size": 5200000000}]},
            )
        return httpx.Response(404)

    app, mock_client = app_with_mock_ollama(handler)
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/ollama/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["models"][0]["name"] == "qwen3.5:9b"
    await mock_client.aclose()


@pytest.mark.asyncio
async def test_list_models_offline_raises_503(app_with_mock_ollama):
    def offline_handler(request: httpx.Request):
        raise httpx.ConnectError("Connection refused", request=request)

    app, mock_client = app_with_mock_ollama(offline_handler)
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/ollama/models")
        assert resp.status_code == 503
        data = resp.json()
        assert data["error"]["code"] == "OLLAMA_UNAVAILABLE"
    await mock_client.aclose()
