"""Autonomous Integration Tests for Phase 3 Real-World Tool Operations."""

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
async def test_phase3_autonomous_multi_tool_workflow():
    """Test autonomous plan execution: file_create -> terminal_run_script -> file_read."""
    app = create_app()
    settings = get_settings()

    # Ensure clean workspace file state
    workspace = settings.get_workspace_dir()
    test_script = workspace / "calc_pi_workflow.py"
    if test_script.exists():
        test_script.unlink()

    plan_response = {
        "plan_id": "plan_phase3_multi",
        "goal": "Compute pi and verify code",
        "steps": [
            {
                "step_id": 1,
                "description": "Create python script",
                "tool_call": {
                    "tool_name": "file_create",
                    "arguments": {
                        "path": "calc_pi_workflow.py",
                        "content": "import math\nprint(f'RESULT={round(math.pi, 4)}')\n",
                        "overwrite": False,
                    },
                },
                "risk_level": "CONTROLLED",
                "dependencies": [],
            },
            {
                "step_id": 2,
                "description": "Execute python script",
                "tool_call": {
                    "tool_name": "terminal_run_script",
                    "arguments": {
                        "script_path": "calc_pi_workflow.py",
                    },
                },
                "risk_level": "CONTROLLED",
                "dependencies": [1],
            },
            {
                "step_id": 3,
                "description": "Read back python script",
                "tool_call": {
                    "tool_name": "file_read",
                    "arguments": {
                        "path": "calc_pi_workflow.py",
                    },
                },
                "risk_level": "SAFE",
                "dependencies": [2],
            },
        ],
    }

    def mock_ollama_handler(request: httpx.Request):
        if request.url.path == "/api/chat":
            return httpx.Response(
                200,
                json={
                    "model": "qwen3.5:9b",
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(plan_response),
                    },
                    "done": True,
                },
            )
        return httpx.Response(200, json={"models": [{"name": "qwen3.5:9b"}]})

    mock_transport = httpx.MockTransport(mock_ollama_handler)
    mock_client = httpx.AsyncClient(transport=mock_transport, base_url="http://mock-ollama:11434")

    app.dependency_overrides[get_ollama_service] = lambda: OllamaService(client=mock_client, settings=settings)

    async with app.router.lifespan_context(app):
        app.state.http_client = mock_client
        app.state.task_manager.orchestrator.planner.ollama = OllamaService(client=mock_client, settings=settings)
        app.state.task_manager.orchestrator.evaluator.ollama = OllamaService(client=mock_client, settings=settings)

        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post("/api/agent/tasks", json={"prompt": "Compute pi and verify code"})
            assert res.status_code == 201
            task_id = res.json()["task"]["task_id"]

            # Poll for completion
            final_task = None
            for _ in range(50):
                await asyncio.sleep(0.1)
                get_res = await client.get(f"/api/agent/tasks/{task_id}")
                task_data = get_res.json()["task"]
                if task_data["status"] in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                    final_task = task_data
                    break

            assert final_task is not None
            assert final_task["status"] == TaskStatus.COMPLETED
            assert len(final_task["execution_trace"]) == 3

            step2_out = final_task["execution_trace"][1]["output"]
            assert "RESULT=3.1416" in step2_out["stdout"]

            step3_out = final_task["execution_trace"][2]["output"]
            assert "calc_pi_workflow.py" in step3_out["path"]
            assert "import math" in step3_out["content"]


@pytest.mark.asyncio
async def test_phase3_sensitive_tool_approval_and_resumption():
    """Test task execution pausing for SENSITIVE file_delete tool, approving, and completing."""
    app = create_app()
    settings = get_settings()

    # Ensure clean workspace file state
    workspace = settings.get_workspace_dir()
    deleted_file = workspace / "temp_to_delete.txt"
    if deleted_file.exists():
        deleted_file.unlink()

    plan_response = {
        "plan_id": "plan_phase3_sensitive",
        "goal": "Create and delete temporary file",
        "steps": [
            {
                "step_id": 1,
                "description": "Create temp file",
                "tool_call": {
                    "tool_name": "file_create",
                    "arguments": {
                        "path": "temp_to_delete.txt",
                        "content": "temporary content",
                        "overwrite": False,
                    },
                },
                "risk_level": "CONTROLLED",
                "dependencies": [],
            },
            {
                "step_id": 2,
                "description": "Delete temp file",
                "tool_call": {
                    "tool_name": "file_delete",
                    "arguments": {
                        "path": "temp_to_delete.txt",
                    },
                },
                "risk_level": "SENSITIVE",
                "dependencies": [1],
            },
        ],
    }

    def mock_ollama_handler(request: httpx.Request):
        if request.url.path == "/api/chat":
            return httpx.Response(
                200,
                json={
                    "model": "qwen3.5:9b",
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(plan_response),
                    },
                    "done": True,
                },
            )
        return httpx.Response(200, json={"models": [{"name": "qwen3.5:9b"}]})

    mock_transport = httpx.MockTransport(mock_ollama_handler)
    mock_client = httpx.AsyncClient(transport=mock_transport, base_url="http://mock-ollama:11434")

    app.dependency_overrides[get_ollama_service] = lambda: OllamaService(client=mock_client, settings=settings)

    async with app.router.lifespan_context(app):
        app.state.http_client = mock_client
        app.state.task_manager.orchestrator.planner.ollama = OllamaService(client=mock_client, settings=settings)
        app.state.task_manager.orchestrator.evaluator.ollama = OllamaService(client=mock_client, settings=settings)

        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post("/api/agent/tasks", json={"prompt": "Create and delete temporary file"})
            assert res.status_code == 201
            task_id = res.json()["task"]["task_id"]

            # 1. Wait for task to pause in WAITING_APPROVAL
            waiting_task = None
            for _ in range(30):
                await asyncio.sleep(0.1)
                get_res = await client.get(f"/api/agent/tasks/{task_id}")
                task_data = get_res.json()["task"]
                if task_data["status"] == TaskStatus.WAITING_APPROVAL:
                    waiting_task = task_data
                    break

            assert waiting_task is not None
            assert waiting_task["pending_approval"] is not None
            approval_id = waiting_task["pending_approval"]["approval_id"]
            assert waiting_task["pending_approval"]["tool_name"] == "file_delete"

            # 2. Issue Approval Decision
            approve_res = await client.post(
                f"/api/agent/tasks/{task_id}/approve",
                json={
                    "approval_id": approval_id,
                    "approved": True,
                },
            )
            assert approve_res.status_code == 200

            # 3. Wait for Task Completion
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
            assert len(final_task["execution_trace"]) == 2

            # Verify file was actually deleted from workspace
            assert not deleted_file.exists()
