"""Unit tests for Fleet domain models and Artifact hashing."""

import hashlib
import json
import pytest
from pydantic import ValidationError
from backend.app.agent.fleet.models import (
    Artifact,
    FleetNode,
    FleetNodeState,
    FleetPlan,
    FleetResult,
)


def test_artifact_creation_and_hashing():
    content = {"key": "val", "count": 42}
    artifact = Artifact.create(
        node_id="node_1",
        producer_role="researcher",
        content=content,
        evidence_refs=["file:test.txt"],
    )

    assert artifact.node_id == "node_1"
    assert artifact.producer_role == "researcher"
    assert artifact.content == content
    assert len(artifact.evidence_refs) == 1

    # Verify SHA-256 hash match
    expected_serialized = json.dumps(content, sort_keys=True, separators=(",", ":"))
    expected_hash = hashlib.sha256(expected_serialized.encode("utf-8")).hexdigest()
    assert artifact.content_hash == expected_hash


def test_artifact_immutability():
    artifact = Artifact.create(
        node_id="node_1",
        producer_role="researcher",
        content={"data": "original"},
    )
    with pytest.raises(ValidationError):
        artifact.content = {"data": "tampered"}


def test_fleet_node_defaults():
    node = FleetNode(
        node_id="n1",
        role="coder",
        objective="Write hello world",
    )
    assert node.state == FleetNodeState.QUEUED
    assert node.dependencies == []
    assert node.capability_allowlist == []
    assert node.token_budget == 2048


def test_fleet_plan_retrieval():
    node1 = FleetNode(node_id="n1", role="planner", objective="plan")
    node2 = FleetNode(node_id="n2", role="coder", objective="code", dependencies=["n1"])
    plan = FleetPlan(
        parent_task_id="task_123",
        goal="Build feature",
        nodes={"n1": node1, "n2": node2},
    )

    assert plan.get_node("n1") == node1
    assert plan.get_node("n2") == node2
    assert plan.get_node("nonexistent") is None
    assert plan.max_nodes == 5


def test_fleet_result_synthesis():
    art = Artifact.create(node_id="n1", producer_role="coder", content="ok")
    result = FleetResult(
        fleet_id="f1",
        parent_task_id="t1",
        node_outcomes={"n1": FleetNodeState.COMPLETED},
        artifacts=[art],
        summary="Done successfully",
        is_verified=True,
    )
    assert result.is_verified is True
    assert len(result.artifacts) == 1
    assert result.node_outcomes["n1"] == FleetNodeState.COMPLETED
