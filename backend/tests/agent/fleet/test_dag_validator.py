"""Unit tests for DAGValidator (topological sort, cycle detection, bounds)."""

import pytest
from backend.app.agent.fleet.models import FleetNode, FleetPlan
from backend.app.agent.fleet.validator import DAGCycleDetectedError, DAGValidationError, DAGValidator
from backend.app.tools.registry import ToolRegistry


def test_valid_sequential_dag():
    n1 = FleetNode(node_id="n1", role="planner", objective="plan")
    n2 = FleetNode(node_id="n2", role="researcher", objective="research", dependencies=["n1"])
    n3 = FleetNode(node_id="n3", role="coder", objective="code", dependencies=["n2"])

    plan = FleetPlan(parent_task_id="t1", goal="Goal", nodes={"n1": n1, "n2": n2, "n3": n3})
    order = DAGValidator.validate(plan)
    assert order == ["n1", "n2", "n3"]


def test_valid_branching_dag():
    # n1 -> n2, n1 -> n3; n2 & n3 -> n4
    n1 = FleetNode(node_id="n1", role="planner", objective="plan")
    n2 = FleetNode(node_id="n2", role="researcher", objective="research 1", dependencies=["n1"])
    n3 = FleetNode(node_id="n3", role="researcher", objective="research 2", dependencies=["n1"])
    n4 = FleetNode(node_id="n4", role="coder", objective="merge", dependencies=["n2", "n3"])

    plan = FleetPlan(parent_task_id="t1", goal="Goal", nodes={"n1": n1, "n2": n2, "n3": n3, "n4": n4})
    order = DAGValidator.validate(plan)
    assert order[0] == "n1"
    assert set(order[1:3]) == {"n2", "n3"}
    assert order[3] == "n4"


def test_empty_fleet_rejected():
    plan = FleetPlan(parent_task_id="t1", goal="Goal", nodes={})
    with pytest.raises(DAGValidationError, match="at least 1 node"):
        DAGValidator.validate(plan)


def test_over_limit_nodes_rejected():
    nodes = {
        f"n{i}": FleetNode(node_id=f"n{i}", role="coder", objective="step")
        for i in range(6)
    }
    plan = FleetPlan(parent_task_id="t1", goal="Goal", nodes=nodes, max_nodes=5)
    with pytest.raises(DAGValidationError, match="exceeds maximum"):
        DAGValidator.validate(plan)


def test_key_mismatch_rejected():
    n1 = FleetNode(node_id="n1", role="coder", objective="step")
    plan = FleetPlan(parent_task_id="t1", goal="Goal", nodes={"wrong_key": n1})
    with pytest.raises(DAGValidationError, match="does not match"):
        DAGValidator.validate(plan)


def test_missing_dependency_rejected():
    n1 = FleetNode(node_id="n1", role="coder", objective="step", dependencies=["nonexistent"])
    plan = FleetPlan(parent_task_id="t1", goal="Goal", nodes={"n1": n1})
    with pytest.raises(DAGValidationError, match="nonexistent node"):
        DAGValidator.validate(plan)


def test_self_dependency_cycle_rejected():
    n1 = FleetNode(node_id="n1", role="coder", objective="step", dependencies=["n1"])
    plan = FleetPlan(parent_task_id="t1", goal="Goal", nodes={"n1": n1})
    with pytest.raises(DAGCycleDetectedError, match="Self-dependency"):
        DAGValidator.validate(plan)


def test_two_node_cycle_rejected():
    n1 = FleetNode(node_id="n1", role="coder", objective="step", dependencies=["n2"])
    n2 = FleetNode(node_id="n2", role="researcher", objective="step", dependencies=["n1"])
    plan = FleetPlan(parent_task_id="t1", goal="Goal", nodes={"n1": n1, "n2": n2})
    with pytest.raises(DAGCycleDetectedError, match="Circular dependency"):
        DAGValidator.validate(plan)


def test_three_node_cycle_rejected():
    n1 = FleetNode(node_id="n1", role="coder", objective="step", dependencies=["n3"])
    n2 = FleetNode(node_id="n2", role="researcher", objective="step", dependencies=["n1"])
    n3 = FleetNode(node_id="n3", role="verifier", objective="step", dependencies=["n2"])
    plan = FleetPlan(parent_task_id="t1", goal="Goal", nodes={"n1": n1, "n2": n2, "n3": n3})
    with pytest.raises(DAGCycleDetectedError, match="Circular dependency"):
        DAGValidator.validate(plan)


def test_capability_containment_catalog():
    catalog = {
        "researcher": {"capability_allowlist": ["read_file", "list_directory"]}
    }
    n1 = FleetNode(
        node_id="n1",
        role="researcher",
        objective="step",
        capability_allowlist=["write_file"],  # Not allowed for researcher
    )
    plan = FleetPlan(parent_task_id="t1", goal="Goal", nodes={"n1": n1})
    with pytest.raises(DAGValidationError, match="not permitted for role"):
        DAGValidator.validate(plan, specialist_catalog=catalog)


def test_capability_containment_tool_registry():
    registry = ToolRegistry()
    # registry has no tools registered
    n1 = FleetNode(
        node_id="n1",
        role="coder",
        objective="step",
        capability_allowlist=["unregistered_tool"],
    )
    plan = FleetPlan(parent_task_id="t1", goal="Goal", nodes={"n1": n1})
    with pytest.raises(DAGValidationError, match="unregistered capability"):
        DAGValidator.validate(plan, tool_registry=registry)
