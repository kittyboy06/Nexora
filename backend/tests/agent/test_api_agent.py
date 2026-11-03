import asyncio
import json
import pytest
import httpx
from httpx import ASGITransport
from backend.app.api.dependencies import get_ollama_service
from backend.app.core.config import get_settings
from backend.app.main import create_app
from backend.app.models.agent import TaskStatus
from backend.app.services.ollama_service import OllamaService


@pytest.mark.asyncio
async def test_agent_api_endpoints():
    app = create_app()

    def mock_ollama_handler(request: httpx.Request):
        if request.url.path == "/api/chat":
            return httpx.Response(
                200,
                json={
                    "model": "qwen3.5:9b",
                    "message": {
                        "role": "assistant",
                        "content": json.dumps({
                            "plan_id": "plan_test_api",
                            "goal": "Read simulated configuration file",
                            "steps": [
                                {
                                    "step_id": 1,
                                    "description": "Read file contents",
                                    "tool_call": {
                                        "tool_name": "mock_file_read",
                                        "arguments": {"filepath": "config.json"}
                                    },
                                    "dependencies": []
                                }
                            ]
                        })
                    },
                    "done": True,
                }
            )
        return httpx.Response(200, json={"models": [{"name": "qwen3.5:9b"}]})

    mock_transport = httpx.MockTransport(mock_ollama_handler)
    mock_client = httpx.AsyncClient(transport=mock_transport, base_url="http://mock-ollama:11434")

    # Override dependencies
    app.dependency_overrides[get_ollama_service] = lambda: OllamaService(client=mock_client, settings=get_settings())

    async with app.router.lifespan_context(app):
        # Override http client in state
        app.state.http_client = mock_client
        # Recreate planner/evaluator with mock client
        app.state.task_manager.orchestrator.planner.ollama = OllamaService(client=mock_client, settings=get_settings())
        app.state.task_manager.orchestrator.evaluator.ollama = OllamaService(client=mock_client, settings=get_settings())

        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Create Task (mock_file_read is SENSITIVE, so it will pause in WAITING_APPROVAL)
            res = await client.post("/api/agent/tasks", json={"prompt": "Read the config file"})
            assert res.status_code == 201
            data = res.json()
            task_id = data["task"]["task_id"]

            # Wait briefly for planning and step 1 pause
            for _ in range(10):
                await asyncio.sleep(0.05)
                get_res = await client.get(f"/api/agent/tasks/{task_id}")
                if get_res.json()["task"]["status"] == TaskStatus.WAITING_APPROVAL:
                    break

            task_data = get_res.json()["task"]
            assert task_data["status"] == TaskStatus.WAITING_APPROVAL
            approval = task_data["pending_approval"]
            assert approval is not None

            # 2. Approve Task
            appr_res = await client.post(
                f"/api/agent/tasks/{task_id}/approve",
                json={"approval_id": approval["approval_id"], "approved": True},
            )
            assert appr_res.status_code == 200

            # Wait for execution completion
            for _ in range(10):
                await asyncio.sleep(0.05)
                get_res = await client.get(f"/api/agent/tasks/{task_id}")
                if get_res.json()["task"]["status"] == TaskStatus.COMPLETED:
                    break

            assert get_res.json()["task"]["status"] == TaskStatus.COMPLETED

            # 3. Create another task and test Cancel while waiting for approval
            res2 = await client.post("/api/agent/tasks", json={"prompt": "Read another file"})
            task_id2 = res2.json()["task"]["task_id"]

            for _ in range(10):
                await asyncio.sleep(0.05)
                get_res2 = await client.get(f"/api/agent/tasks/{task_id2}")
                if get_res2.json()["task"]["status"] == TaskStatus.WAITING_APPROVAL:
                    break

            cancel_res = await client.post(f"/api/agent/tasks/{task_id2}/cancel")
            assert cancel_res.status_code == 200
            assert cancel_res.json()["task"]["status"] == TaskStatus.CANCELLED

    await mock_client.aclose()
