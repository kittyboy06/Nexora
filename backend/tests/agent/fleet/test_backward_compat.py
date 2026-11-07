"""Regression & Backward-Compatibility Tests for AgentTask and StateManager with Fleet."""

import pytest
from backend.app.agent.fleet.coordinator import FleetCoordinator
from backend.app.agent.fleet.models import Artifact, FleetNode, FleetPlan
from backend.app.agent.orchestrator import AgentOrchestrator
from backend.app.agent.state_manager import StateManager
from backend.app.models.agent import AgentTask, TaskStatus


@pytest.mark.asyncio
async def test_legacy_agent_task_deserialization():
    legacy_json = {
        "task_id": "legacy_task_1",
        "prompt": "List files",
        "status": "SUBMITTED",
        "execution_trace": [],
        "iterations_used": 0,
    }
    task = AgentTask.model_validate(legacy_json)
    assert task.task_id == "legacy_task_1"
    assert task.fleet_plan is None
    assert task.artifacts == []


@pytest.mark.asyncio
async def test_state_manager_fleet_plan_and_artifacts(test_settings, tmp_path):
    state_mgr = StateManager(settings=test_settings)
    state_mgr.data_dir = tmp_path / "data"
    state_mgr.data_dir.mkdir(parents=True, exist_ok=True)
    task = await state_mgr.create_task(prompt="Complex workflow")

    assert task.fleet_plan is None
    assert task.artifacts == []

    # Update fleet plan
    n1 = FleetNode(node_id="n1", role="planner", objective="Step 1")
    plan = FleetPlan(parent_task_id=task.task_id, goal="Complex workflow", nodes={"n1": n1})
    updated_task = await state_mgr.update_fleet_plan(task.task_id, plan)
    assert updated_task.fleet_plan is not None
    assert updated_task.fleet_plan.get_node("n1") is not None

    # Record artifact
    art = Artifact.create(node_id="n1", producer_role="planner", content={"summary": "Plan done"})
    task_with_art = await state_mgr.record_artifact(task.task_id, art)
    assert len(task_with_art.artifacts) == 1
    assert task_with_art.artifacts[0].content_hash == art.content_hash

    # Verify atomic disk persistence
    reloaded = await state_mgr.get_task(task.task_id)
    assert reloaded.fleet_plan is not None
    assert len(reloaded.artifacts) == 1


@pytest.mark.asyncio
async def test_orchestrator_fleet_task_execution(test_settings, tmp_path):
    state_mgr = StateManager(settings=test_settings)
    state_mgr.data_dir = tmp_path / "data"
    state_mgr.data_dir.mkdir(parents=True, exist_ok=True)
    task = await state_mgr.create_task(prompt="Run fleet")

    async def mock_runner(runtime, node):
        return {"step_output": f"done by {node.role}"}

    coordinator = FleetCoordinator(node_runner=mock_runner)

    orchestrator = AgentOrchestrator(
        state_manager=state_mgr,
        planner=None,  # type: ignore
        executor=None,  # type: ignore
        evaluator=None,  # type: ignore
        settings=test_settings,
        fleet_coordinator=coordinator,
    )

    n1 = FleetNode(node_id="n1", role="researcher", objective="gather")
    n2 = FleetNode(node_id="n2", role="coder", objective="write", dependencies=["n1"])
    plan = FleetPlan(parent_task_id=task.task_id, goal="Run fleet", nodes={"n1": n1, "n2": n2})

    result = await orchestrator.run_fleet_task(task.task_id, plan)
    assert result.is_verified is True
    assert len(result.artifacts) == 2

    # Check updated task status
    final_task = await state_mgr.get_task(task.task_id)
    assert final_task.status == TaskStatus.COMPLETED
    assert len(final_task.artifacts) == 2
