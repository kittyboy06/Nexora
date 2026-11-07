"""Unit tests for FleetCoordinator (sequential scheduling, artifact flow, fail-fast)."""

import pytest
from backend.app.agent.fleet.coordinator import FleetCoordinator
from backend.app.agent.fleet.models import FleetNode, FleetNodeState, FleetPlan
from backend.app.core.guard import InferenceGuard


@pytest.mark.asyncio
async def test_coordinator_sequential_success():
    executed_order = []

    async def mock_runner(runtime, node):
        executed_order.append(node.node_id)
        return {"output_from": node.node_id, "role": node.role}

    coordinator = FleetCoordinator(node_runner=mock_runner)

    n1 = FleetNode(node_id="n1", role="planner", objective="step 1")
    n2 = FleetNode(node_id="n2", role="researcher", objective="step 2", dependencies=["n1"])
    n3 = FleetNode(node_id="n3", role="coder", objective="step 3", dependencies=["n2"])

    plan = FleetPlan(parent_task_id="task_1", goal="Goal", nodes={"n1": n1, "n2": n2, "n3": n3})
    result = await coordinator.execute_fleet(plan)

    assert executed_order == ["n1", "n2", "n3"]
    assert result.is_verified is True
    assert len(result.artifacts) == 3
    assert result.node_outcomes["n1"] == FleetNodeState.COMPLETED
    assert result.node_outcomes["n2"] == FleetNodeState.COMPLETED
    assert result.node_outcomes["n3"] == FleetNodeState.COMPLETED


@pytest.mark.asyncio
async def test_coordinator_artifact_passing_between_nodes():
    received_artifacts = {}

    async def mock_runner(runtime, node):
        received_artifacts[node.node_id] = [a.artifact_id for a in runtime.input_artifacts]
        return {"result": f"processed_{node.node_id}"}

    coordinator = FleetCoordinator(node_runner=mock_runner)

    n1 = FleetNode(node_id="n1", role="researcher", objective="gather facts")
    n2 = FleetNode(node_id="n2", role="coder", objective="write code", dependencies=["n1"])

    plan = FleetPlan(parent_task_id="task_2", goal="Goal", nodes={"n1": n1, "n2": n2})
    result = await coordinator.execute_fleet(plan)

    assert result.is_verified is True
    assert received_artifacts["n1"] == []  # No upstream dependencies
    assert len(received_artifacts["n2"]) == 1  # Received n1's artifact
    n1_art_id = result.artifacts[0].artifact_id
    assert received_artifacts["n2"][0] == n1_art_id


@pytest.mark.asyncio
async def test_coordinator_fail_fast_and_downstream_blocking():
    async def failing_runner(runtime, node):
        if node.node_id == "n2":
            raise RuntimeError("Database connection timed out permanently.")
        return {"status": "ok"}

    coordinator = FleetCoordinator(node_runner=failing_runner)

    # Graph: n1 -> n2 -> n3; and n2 -> n4
    n1 = FleetNode(node_id="n1", role="planner", objective="plan")
    n2 = FleetNode(node_id="n2", role="researcher", objective="fail step", dependencies=["n1"])
    n3 = FleetNode(node_id="n3", role="coder", objective="code", dependencies=["n2"])
    n4 = FleetNode(node_id="n4", role="auditor_verifier", objective="audit", dependencies=["n2"])

    plan = FleetPlan(parent_task_id="task_3", goal="Goal", nodes={"n1": n1, "n2": n2, "n3": n3, "n4": n4})
    result = await coordinator.execute_fleet(plan)

    assert result.is_verified is False
    assert result.node_outcomes["n1"] == FleetNodeState.COMPLETED
    assert result.node_outcomes["n2"] == FleetNodeState.FAILED
    assert result.node_outcomes["n3"] == FleetNodeState.BLOCKED
    assert result.node_outcomes["n4"] == FleetNodeState.BLOCKED
    assert "Blocked due to upstream failure in 'n2'" in plan.nodes["n3"].error
    assert "Blocked due to upstream failure in 'n2'" in plan.nodes["n4"].error
    assert len(result.artifacts) == 1  # Only n1's artifact was preserved


@pytest.mark.asyncio
async def test_coordinator_enforces_inference_guard():
    guard = InferenceGuard(limit=1, timeout=2.0)
    guard_acquired = []

    async def mock_runner(runtime, node):
        # Verify semaphore is currently held (available == 0)
        guard_acquired.append(guard._semaphore.locked())
        return "done"

    coordinator = FleetCoordinator(guard=guard, node_runner=mock_runner)

    n1 = FleetNode(node_id="n1", role="planner", objective="step")
    plan = FleetPlan(parent_task_id="task_4", goal="Goal", nodes={"n1": n1})
    await coordinator.execute_fleet(plan)

    assert guard_acquired == [True]
    assert not guard._semaphore.locked()  # Released afterwards
