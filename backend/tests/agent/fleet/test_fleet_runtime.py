"""Unit tests for ScopedToolProxy, AgentRuntime, and AgentRuntimeFactory."""

import pytest
from backend.app.agent.fleet.catalog import SpecialistCatalog
from backend.app.agent.fleet.models import Artifact, FleetNode
from backend.app.agent.fleet.runtime import (
    AgentRuntimeFactory,
    CapabilityNotPermittedError,
    ScopedToolProxy,
)
from pydantic import BaseModel
from backend.app.models.agent import RiskLevel
from backend.app.tools.base import BaseTool
from backend.app.tools.registry import ToolRegistry


class DummyArgs(BaseModel):
    path: str = ""


class DummyTool(BaseTool):
    def __init__(self, name: str):
        self.name = name
        self.description = f"Dummy tool {name}"
        self.risk_level = RiskLevel.SAFE
        self.args_schema = DummyArgs

    async def execute(self, args: BaseModel):
        return f"Executed {self.name}"


def test_scoped_tool_proxy_filters_tools():
    base_registry = ToolRegistry()
    tool_a = DummyTool("read_file")
    tool_b = DummyTool("write_file")
    tool_c = DummyTool("execute_command")
    base_registry.register(tool_a)
    base_registry.register(tool_b)
    base_registry.register(tool_c)

    # Scoped proxy allowing ONLY read_file
    proxy = ScopedToolProxy(base_registry, allowlist=["read_file"])

    assert proxy.get("read_file") == tool_a
    assert proxy.get("write_file") is None
    assert proxy.get("execute_command") is None

    assert proxy.has_tool("read_file") is True
    assert proxy.has_tool("write_file") is False

    assert proxy.get_tool_names() == ["read_file"]
    assert len(proxy.list_tools()) == 1
    assert len(proxy.get_specs()) == 1
    assert proxy.get_specs()[0]["name"] == "read_file"


def test_agent_runtime_prompt_construction():
    catalog = SpecialistCatalog()
    base_registry = ToolRegistry()
    node = FleetNode(
        node_id="research_node",
        role="researcher",
        objective="Inspect project files",
        capability_allowlist=["read_file"],
        token_budget=1024,
    )
    art1 = Artifact.create(
        node_id="plan_node",
        producer_role="planner",
        content={"action": "Find config"},
    )

    runtime = AgentRuntimeFactory.create_runtime(
        node=node,
        catalog=catalog,
        input_artifacts=[art1],
        tool_registry=base_registry,
    )

    prompt = runtime.build_system_prompt()
    assert "=== ROLE: SYSTEM & CODEBASE RESEARCHER ===" in prompt
    assert "=== SUBTASK OBJECTIVE ===" in prompt
    assert "Inspect project files" in prompt
    assert "=== INPUT ARTIFACTS FROM UPSTREAM SPECIALISTS ===" in prompt
    assert art1.artifact_id in prompt
    assert "Find config" in prompt
    assert "Token budget: 1024" in prompt


def test_agent_runtime_verify_tool_access():
    catalog = SpecialistCatalog()
    base_registry = ToolRegistry()
    node = FleetNode(
        node_id="node_1",
        role="researcher",
        objective="Read file only",
        capability_allowlist=["read_file"],
    )
    runtime = AgentRuntimeFactory.create_runtime(
        node=node,
        catalog=catalog,
        input_artifacts=[],
        tool_registry=base_registry,
    )

    # Allowed
    runtime.verify_tool_access("read_file")

    # Disallowed raises CapabilityNotPermittedError
    with pytest.raises(CapabilityNotPermittedError, match="attempted to access unauthorized tool"):
        runtime.verify_tool_access("write_file")


def test_factory_rejects_unknown_role():
    catalog = SpecialistCatalog()
    base_registry = ToolRegistry()
    node = FleetNode(
        node_id="n1",
        role="unknown_role",
        objective="Step",
    )
    with pytest.raises(ValueError, match="Unknown specialist role"):
        AgentRuntimeFactory.create_runtime(
            node=node,
            catalog=catalog,
            input_artifacts=[],
            tool_registry=base_registry,
        )
