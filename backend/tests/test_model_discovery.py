import pytest
import httpx
from httpx import ASGITransport
from unittest.mock import MagicMock
from backend.app.core.config import Settings
from backend.app.core.guard import InferenceGuard
from backend.app.models.chat import ChatMessage, ChatRequest
from backend.app.models.model_profile import TaskKind
from backend.app.services.model_registry import HybridModelRouter, ModelProfileRegistry
from backend.app.services.ollama_service import OllamaService


@pytest.mark.asyncio
async def test_model_matches_dynamic_keywords():
    service = OllamaService(client=MagicMock(), settings=Settings())

    # "auto", "*", "any" match whenever models exist
    assert service.model_matches("auto", ["llama3.2:3b", "mistral:latest"]) is True
    assert service.model_matches("*", ["mistral:latest"]) is True
    assert service.model_matches("any", ["phi3:mini"]) is True
    assert service.model_matches("", ["llama3.2:3b"]) is True

    # "auto" doesn't match if no models exist
    assert service.model_matches("auto", []) is False
    assert service.model_matches("", []) is False

    # Exact and tag matching
    assert service.model_matches("llama3.2:3b", ["llama3.2:3b"]) is True
    assert service.model_matches("llama3.2", ["llama3.2:latest"]) is True
    assert service.model_matches("llama3.2", ["llama3.2:3b"]) is True
    assert service.model_matches("unknown_model", ["llama3.2:3b"]) is False


@pytest.mark.asyncio
async def test_resolve_active_model_auto_discovery():
    settings = Settings(OLLAMA_MODEL="")
    mock_tags = {
        "models": [
            {"name": "deepseek-coder:6.7b", "size": 3800000000},
            {"name": "llama3.2:3b", "size": 2000000000},
        ]
    }

    def handler(request: httpx.Request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json=mock_tags)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://mock-ollama:11434") as client:
        service = OllamaService(client=client, settings=settings)

        # 1. First resolution should pick the first installed model dynamically
        active = await service.resolve_active_model()
        assert active == "deepseek-coder:6.7b"

        # 2. Status check reports the dynamic model
        status = await service.get_status()
        assert status.reachable is True
        assert status.model_available is True
        assert status.configured_model == "deepseek-coder:6.7b"
        assert "deepseek-coder:6.7b" in status.installed_models

        # 3. Explicitly setting active model switches it
        service.set_active_model("llama3.2:3b")
        active_updated = await service.resolve_active_model()
        assert active_updated == "llama3.2:3b"

        status_updated = await service.get_status()
        assert status_updated.configured_model == "llama3.2:3b"


@pytest.mark.asyncio
async def test_active_model_api_endpoints(app_with_mock_ollama):
    mock_tags = {
        "models": [
            {"name": "mistral:7b", "size": 4100000000},
            {"name": "phi3:mini", "size": 2200000000},
        ]
    }

    def handler(request: httpx.Request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json=mock_tags)
        return httpx.Response(404)

    app, mock_client = app_with_mock_ollama(handler)
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # GET /api/ollama/active-model should return current active or configured model
        resp = await ac.get("/api/ollama/active-model")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "active_model" in data

        # POST /api/ollama/active-model should switch to phi3:mini
        resp_post = await ac.post("/api/ollama/active-model", json={"model": "phi3:mini"})
        assert resp_post.status_code == 200
        assert resp_post.json()["active_model"] == "phi3:mini"

        # Verify GET now returns phi3:mini
        resp_after = await ac.get("/api/ollama/active-model")
        assert resp_after.json()["active_model"] == "phi3:mini"

    await mock_client.aclose()


@pytest.mark.asyncio
async def test_hybrid_router_resolves_auto_profile():
    settings = Settings(OLLAMA_MODEL="", MODEL_ROUTER_MODEL="")
    mock_tags = {
        "models": [
            {"name": "llama3.2:latest", "size": 2000000000},
        ]
    }

    def handler(request: httpx.Request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json=mock_tags)
        if request.url.path == "/api/chat":
            return httpx.Response(
                200,
                json={
                    "model": "llama3.2:latest",
                    "message": {"role": "assistant", "content": '{"task_kind":"code","confidence":0.95}'},
                    "done": True,
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://mock-ollama:11434") as client:
        service = OllamaService(client=client, settings=settings)
        registry = ModelProfileRegistry(settings=settings)
        guard = InferenceGuard(limit=1, timeout=1.0)
        router = HybridModelRouter(profiles=registry, settings=settings, ollama=service, guard=guard)

        selection = await router.route("Implement quicksort in Python")
        assert selection.profile_id == "coding-planner"
        # The auto model must be resolved to the installed llama3.2:latest
        assert selection.model == "llama3.2:latest"
        assert selection.task_kind == TaskKind.CODE


@pytest.mark.asyncio
async def test_chat_generation_auto_model_dispatch():
    settings = Settings(OLLAMA_MODEL="")
    dispatched_models = []

    def handler(request: httpx.Request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "mistral-small"}]})
        if request.url.path == "/api/chat":
            import json
            body = json.loads(request.content.decode("utf-8"))
            dispatched_models.append(body.get("model"))
            return httpx.Response(
                200,
                json={
                    "model": body.get("model"),
                    "message": {"role": "assistant", "content": "Hello from model"},
                    "done": True,
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://mock-ollama:11434") as client:
        service = OllamaService(client=client, settings=settings)

        # 1. Calling generate_chat with model="auto" dispatches to mistral-small
        resp = await service.generate_chat(ChatRequest(model="auto", messages=[ChatMessage(role="user", content="Hi")]))
        assert resp.model == "mistral-small"

        # 2. Calling generate_chat with model="" also dispatches to mistral-small
        resp2 = await service.generate_chat(ChatRequest(model="", messages=[ChatMessage(role="user", content="Hi 2")]))
        assert resp2.model == "mistral-small"

        assert dispatched_models == ["mistral-small", "mistral-small"]
