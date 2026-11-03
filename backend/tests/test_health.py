import pytest
import httpx
from httpx import ASGITransport
from backend.app.main import create_app


@pytest.mark.asyncio
async def test_health_check_returns_ok():
    app = create_app()
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["app_name"] == "NEXORA"
        assert "version" in data
        assert "timestamp" in data


@pytest.mark.asyncio
async def test_health_check_independent_of_ollama(app_with_mock_ollama):
    def offline_handler(request: httpx.Request):
        raise httpx.ConnectError("Connection refused to Ollama", request=request)

    app, mock_client = app_with_mock_ollama(offline_handler)
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
    await mock_client.aclose()
