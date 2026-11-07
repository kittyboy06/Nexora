"""Integration Tests for Phase 4: Model Registry, Hybrid Routing, and Diagnostics."""

import asyncio
import json
import pytest
import httpx
from httpx import ASGITransport

from backend.app.api.dependencies import get_ollama_service, get_settings
from backend.app.main import create_app
from backend.app.models.agent import TaskStatus
from backend.app.services.ollama_service import OllamaService


@pytest.mark.asyncio
async def test_phase4_end_to_end_routing_diagnostics(tmp_path):
    """Test full task lifecycle records RouteSelection diagnostics on AgentTask."""
    app = create_app()
    settings = get_settings()

    simple_plan = {
        "plan_id": "plan_phase4_route",
        "goal": "List files",
        "steps": [
            {
                "step_id": 1,
                "description": "List workspace files",
                "tool_call": {
                    "tool_name": "file_list",
                    "arguments": {
                        "path": ".",
                    },
                },
                "risk_level": "SAFE",
                "dependencies": [],
            }
        ],
    }

    chat_calls = []

    def mock_ollama_handler(request: httpx.Request):
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={"models": [{"name": "qwen3.5:9b"}]},
            )
        if request.url.path == "/api/chat":
            body = json.loads(request.content.decode("utf-8"))
            chat_calls.append(body)
            # First call is routing classifier
            if len(chat_calls) == 1:
                return httpx.Response(
                    200,
                    json={
                        "model": "qwen3.5:9b",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({"task_kind": "code", "confidence": 0.95}),
                        },
                        "done": True,
                    },
                )
            # Second call is planner
            return httpx.Response(
                200,
                json={
                    "model": "qwen3.5:9b",
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(simple_plan),
                    },
                    "done": True,
                },
            )
        return httpx.Response(200, json={})

    mock_transport = httpx.MockTransport(mock_ollama_handler)
    mock_client = httpx.AsyncClient(transport=mock_transport, base_url="http://mock-ollama:11434")
    mock_service = OllamaService(client=mock_client, settings=settings)

    app.dependency_overrides[get_ollama_service] = lambda: mock_service

    async with app.router.lifespan_context(app):
        app.state.http_client = mock_client
        app.state.task_manager.orchestrator.planner.ollama = mock_service
        app.state.task_manager.orchestrator.evaluator.ollama = mock_service

        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post("/api/agent/tasks", json={"prompt": "Implement a data parser in Python"})
            assert res.status_code == 201
            task_id = res.json()["task"]["task_id"]

            # Poll for execution completion
            final_task = None
            for _ in range(40):
                await asyncio.sleep(0.1)
                get_res = await client.get(f"/api/agent/tasks/{task_id}")
                task_data = get_res.json()["task"]
                if task_data["status"] in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                    final_task = task_data
                    break

            assert final_task is not None
            assert final_task["status"] == TaskStatus.COMPLETED
            assert final_task["routing"] is not None
            assert final_task["routing"]["profile_id"] == "coding-planner"
            assert final_task["routing"]["task_kind"] == "code"
            assert final_task["routing"]["model"] == "qwen3.5:9b"
            assert final_task["routing"]["escalated"] is False
            assert "classification" in final_task["routing"]["reason"]


@pytest.mark.asyncio
async def test_phase4_end_to_end_router_escalation():
    """Uncertain small router model escalates to distinct primary model before planning."""
    app = create_app()
    settings = get_settings()
    # Configure router model to a distinct model
    settings.MODEL_ROUTER_MODEL = "qwen2.5:1.5b"
    settings.OLLAMA_MODEL = "qwen3.5:9b"

    simple_plan = {
        "plan_id": "plan_escalate",
        "goal": "List files",
        "steps": [
            {
                "step_id": 1,
                "description": "List files",
                "tool_call": {"tool_name": "file_list", "arguments": {"path": "."}},
                "risk_level": "SAFE",
                "dependencies": [],
            }
        ],
    }

    chat_models_called = []

    def mock_ollama_handler(request: httpx.Request):
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={"models": [{"name": "qwen2.5:1.5b"}, {"name": "qwen3.5:9b"}]},
            )
        if request.url.path == "/api/chat":
            body = json.loads(request.content.decode("utf-8"))
            chat_models_called.append(body["model"])
            # Call 1: Router model (low confidence 0.40)
            if len(chat_models_called) == 1:
                return httpx.Response(
                    200,
                    json={
                        "model": "qwen2.5:1.5b",
                        "message": {"role": "assistant", "content": json.dumps({"task_kind": "general", "confidence": 0.40})},
                        "done": True,
                    },
                )
            # Call 2: Escalated primary model (high confidence 0.92)
            if len(chat_models_called) == 2:
                return httpx.Response(
                    200,
                    json={
                        "model": "qwen3.5:9b",
                        "message": {"role": "assistant", "content": json.dumps({"task_kind": "research", "confidence": 0.92})},
                        "done": True,
                    },
                )
            # Call 3: Planner execution
            return httpx.Response(
                200,
                json={
                    "model": "qwen3.5:9b",
                    "message": {"role": "assistant", "content": json.dumps(simple_plan)},
                    "done": True,
                },
            )
        return httpx.Response(200, json={})

    mock_transport = httpx.MockTransport(mock_ollama_handler)
    mock_client = httpx.AsyncClient(transport=mock_transport, base_url="http://mock-ollama:11434")
    mock_service = OllamaService(client=mock_client, settings=settings)

    app.dependency_overrides[get_ollama_service] = lambda: mock_service

    async with app.router.lifespan_context(app):
        app.state.http_client = mock_client
        app.state.task_manager.orchestrator.planner.ollama = mock_service
        app.state.task_manager.orchestrator.evaluator.ollama = mock_service

        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post("/api/agent/tasks", json={"prompt": "Compare technical architectures"})
            assert res.status_code == 201
            task_id = res.json()["task"]["task_id"]

            final_task = None
            for _ in range(40):
                await asyncio.sleep(0.1)
                get_res = await client.get(f"/api/agent/tasks/{task_id}")
                task_data = get_res.json()["task"]
                if task_data["status"] in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                    final_task = task_data
                    break

            assert final_task is not None
            assert final_task["status"] == TaskStatus.COMPLETED
            assert final_task["routing"] is not None
            assert final_task["routing"]["profile_id"] == "research-planner"
            assert final_task["routing"]["task_kind"] == "research"
            assert final_task["routing"]["escalated"] is True
            assert chat_models_called == ["qwen2.5:1.5b", "qwen3.5:9b", "qwen3.5:9b"]



@pytest.mark.asyncio
async def test_phase4_manual_profile_override_integration():
    """Manual model_profile_id override skips classification and uses specified profile."""
    app = create_app()
    settings = get_settings()

    simple_plan = {
        "plan_id": "plan_override",
        "goal": "Read file",
        "steps": [
            {
                "step_id": 1,
                "description": "Read file",
                "tool_call": {
                    "tool_name": "file_read",
                    "arguments": {"path": "phase4_output.txt"},
                },
                "risk_level": "SAFE",
                "dependencies": [],
            }
        ],
    }

    chat_calls = []

    def mock_ollama_handler(request: httpx.Request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3.5:9b"}]})
        if request.url.path == "/api/chat":
            body = json.loads(request.content.decode("utf-8"))
            chat_calls.append(body)
            return httpx.Response(
                200,
                json={
                    "model": "qwen3.5:9b",
                    "message": {"role": "assistant", "content": json.dumps(simple_plan)},
                    "done": True,
                },
            )
        return httpx.Response(200, json={})

    mock_transport = httpx.MockTransport(mock_ollama_handler)
    mock_client = httpx.AsyncClient(transport=mock_transport, base_url="http://mock-ollama:11434")
    mock_service = OllamaService(client=mock_client, settings=settings)

    app.dependency_overrides[get_ollama_service] = lambda: mock_service

    async with app.router.lifespan_context(app):
        app.state.http_client = mock_client
        app.state.task_manager.orchestrator.planner.ollama = mock_service
        app.state.task_manager.orchestrator.evaluator.ollama = mock_service

        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post(
                "/api/agent/tasks",
                json={
                    "prompt": "Analyze dataset",
                    "model_profile_id": "reasoning-planner",
                },
            )
            assert res.status_code == 201
            task_id = res.json()["task"]["task_id"]

            final_task = None
            for _ in range(40):
                await asyncio.sleep(0.1)
                get_res = await client.get(f"/api/agent/tasks/{task_id}")
                task_data = get_res.json()["task"]
                if task_data["status"] in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                    final_task = task_data
                    break

            assert final_task is not None
            assert final_task["routing"] is not None
            assert final_task["routing"]["profile_id"] == "reasoning-planner"
            assert final_task["routing"]["reason"] == "manual profile override"
            # Classifier call was skipped, so only 1 chat call (for planning) occurred
            assert len(chat_calls) == 1


@pytest.mark.asyncio
async def test_phase4_offline_ollama_transitions_to_failed_gracefully():
    """Unreachable Ollama during planning transitions task to FAILED with descriptive error and preserves snapshot."""
    app = create_app()
    settings = get_settings()

    def offline_handler(request: httpx.Request):
        raise httpx.ConnectError("Connection refused to 127.0.0.1:11434")

    mock_transport = httpx.MockTransport(offline_handler)
    mock_client = httpx.AsyncClient(transport=mock_transport, base_url="http://mock-ollama:11434")
    mock_service = OllamaService(client=mock_client, settings=settings)

    app.dependency_overrides[get_ollama_service] = lambda: mock_service

    async with app.router.lifespan_context(app):
        app.state.http_client = mock_client
        app.state.task_manager.orchestrator.planner.ollama = mock_service
        app.state.task_manager.orchestrator.evaluator.ollama = mock_service

        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post("/api/agent/tasks", json={"prompt": "Do work while Ollama is offline"})
            assert res.status_code == 201
            task_id = res.json()["task"]["task_id"]

            final_task = None
            for _ in range(30):
                await asyncio.sleep(0.1)
                get_res = await client.get(f"/api/agent/tasks/{task_id}")
                task_data = get_res.json()["task"]
                if task_data["status"] in (TaskStatus.FAILED, TaskStatus.COMPLETED):
                    final_task = task_data
                    break

            assert final_task is not None
            assert final_task["status"] == TaskStatus.FAILED
            assert final_task["error_message"] is not None
            assert "Ollama" in final_task["error_message"] or "unreachable" in final_task["error_message"].lower()

            # Verify persistent snapshot on disk
            task_file = settings.get_task_data_dir() / f"{task_id}.json"
            assert task_file.exists()
            persisted = json.loads(task_file.read_text(encoding="utf-8"))
            assert persisted["status"] == TaskStatus.FAILED


@pytest.mark.asyncio
async def test_phase4_profiles_api_list_and_reload():
    """Test GET /api/ollama/profiles and POST /api/ollama/profiles/reload."""
    app = create_app()
    settings = get_settings()

    def mock_ollama_handler(request: httpx.Request):
        return httpx.Response(200, json={"models": [{"name": "qwen3.5:9b"}]})

    mock_transport = httpx.MockTransport(mock_ollama_handler)
    mock_client = httpx.AsyncClient(transport=mock_transport, base_url="http://mock-ollama:11434")
    mock_service = OllamaService(client=mock_client, settings=settings)

    app.dependency_overrides[get_ollama_service] = lambda: mock_service

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # GET /api/ollama/profiles
        res = await client.get("/api/ollama/profiles")
        assert res.status_code == 200
        data = res.json()
        assert data["count"] >= 4
        profile_ids = [p["profile_id"] for p in data["profiles"]]
        assert "coding-planner" in profile_ids
        assert "general-planner" in profile_ids

        # POST /api/ollama/profiles/reload
        reload_res = await client.post("/api/ollama/profiles/reload")
        assert reload_res.status_code == 200
        reload_data = reload_res.json()
        assert reload_data["count"] == data["count"]
