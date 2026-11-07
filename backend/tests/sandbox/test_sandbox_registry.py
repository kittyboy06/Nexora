"""Unit tests for Generated Tool Registry and ToolRegistry Bridge."""

import hashlib
import pytest
from pathlib import Path

from backend.app.models.agent import RiskLevel
from backend.app.sandbox.bridge import GeneratedSandboxTool, GeneratedToolBridgeManager
from backend.app.sandbox.models import (
    GeneratedToolProposal,
    SandboxRunResult,
    SandboxRunStatus,
    TestCase,
)
from backend.app.sandbox.registry import GeneratedToolRegistry
from backend.app.sandbox.runners.job_object import Win32JobObjectRunner
from backend.app.tools.registry import ToolRegistry


@pytest.fixture
def test_setup(tmp_path: Path):
    catalog_dir = tmp_path / "catalog"
    sb_dir = tmp_path / "sandbox"
    gen_registry = GeneratedToolRegistry(catalog_dir=catalog_dir)
    tool_registry = ToolRegistry()
    runner = Win32JobObjectRunner(base_sandbox_dir=sb_dir)
    bridge_mgr = GeneratedToolBridgeManager(
        generated_registry=gen_registry,
        tool_registry=tool_registry,
        runner=runner,
    )
    return gen_registry, tool_registry, runner, bridge_mgr


def sample_proposal_and_evidence(name: str = "json_sorter"):
    code = """
def json_sorter(keys: list) -> list:
    return sorted(keys)
"""
    sha = hashlib.sha256(code.encode("utf-8")).hexdigest()
    proposal = GeneratedToolProposal(
        name=name,
        description="Sorts a list of keys alphabetically",
        code=code,
        input_schema={
            "type": "object",
            "properties": {"keys": {"type": "array"}},
            "required": ["keys"],
        },
        output_schema={"type": "array"},
        test_cases=[
            TestCase(name="pos", inputs={"keys": ["z", "a"]}, expected_output=["a", "z"], is_negative=False),
            TestCase(name="neg", inputs={"keys": []}, expected_output=[], is_negative=True),
        ],
    )
    evidence = SandboxRunResult(
        run_id="run_verify_001",
        tool_name=name,
        status=SandboxRunStatus.TESTS_PASSED,
        source_sha256=sha,
        timestamp="2026-11-07T12:00:00Z",
    )
    return proposal, evidence


def test_registry_promote_success(test_setup):
    gen_reg, _, _, _ = test_setup
    proposal, evidence = sample_proposal_and_evidence()

    record = gen_reg.promote(proposal, evidence, reviewer="alice")
    assert record.manifest.name == "json_sorter"
    assert record.manifest.version == "1.0.0"
    assert record.is_enabled is True
    assert len(record.audit_history) == 1
    assert record.audit_history[0]["reviewer"] == "alice"

    # Verify retrieval
    retrieved = gen_reg.get_tool("json_sorter")
    assert retrieved is not None
    assert retrieved.manifest.version == "1.0.0"
    assert retrieved.code == proposal.code


def test_registry_rejects_failed_evidence(test_setup):
    gen_reg, _, _, _ = test_setup
    proposal, evidence = sample_proposal_and_evidence()
    evidence.status = SandboxRunStatus.TESTS_FAILED

    with pytest.raises(ValueError, match="status was 'TESTS_FAILED'"):
        gen_reg.promote(proposal, evidence)


def test_registry_rejects_hash_mismatch(test_setup):
    gen_reg, _, _, _ = test_setup
    proposal, evidence = sample_proposal_and_evidence()
    evidence.source_sha256 = "invalid_hash_value"

    with pytest.raises(ValueError, match="Source code hash mismatch"):
        gen_reg.promote(proposal, evidence)


def test_registry_version_increment_and_rollback(test_setup):
    gen_reg, _, _, _ = test_setup
    proposal, evidence = sample_proposal_and_evidence()

    # Promote v1.0.0
    rec1 = gen_reg.promote(proposal, evidence, version="1.0.0")
    assert rec1.manifest.version == "1.0.0"

    # Promote v1.0.1
    rec2 = gen_reg.promote(proposal, evidence, version="1.0.1")
    assert rec2.manifest.version == "1.0.1"

    # Check active version
    active = gen_reg.get_tool("json_sorter")
    assert active.manifest.version == "1.0.1"

    versions = gen_reg.list_versions("json_sorter")
    assert versions == ["1.0.0", "1.0.1"]

    # Roll back to 1.0.0
    assert gen_reg.rollback("json_sorter", "1.0.0") is True
    rolled_back = gen_reg.get_tool("json_sorter")
    assert rolled_back.manifest.version == "1.0.0"


def test_registry_enable_disable(test_setup):
    gen_reg, _, _, _ = test_setup
    proposal, evidence = sample_proposal_and_evidence()
    gen_reg.promote(proposal, evidence)

    assert gen_reg.get_tool("json_sorter").is_enabled is True
    assert gen_reg.set_enabled("json_sorter", False) is True
    assert gen_reg.get_tool("json_sorter").is_enabled is False


@pytest.mark.asyncio
async def test_tool_registry_bridge(test_setup):
    gen_reg, tool_reg, runner, bridge_mgr = test_setup
    proposal, evidence = sample_proposal_and_evidence()
    record = gen_reg.promote(proposal, evidence)

    # Sync into ToolRegistry
    count = bridge_mgr.sync_all()
    assert count == 1

    registered_tool = tool_reg.get("gen__json_sorter")
    assert registered_tool is not None
    assert registered_tool.name == "gen__json_sorter"
    assert registered_tool.risk_level == RiskLevel.CONTROLLED

    # Check specs
    spec = registered_tool.get_spec()
    assert spec["name"] == "gen__json_sorter"
    assert spec["risk_level"] == "CONTROLLED"

    # Test execution through bridge delegating to sandbox
    output = await registered_tool.execute(keys=["delta", "bravo", "charlie"])
    assert output == ["bravo", "charlie", "delta"]

    # Test disabling unmounts from tool registry
    gen_reg.set_enabled("json_sorter", False)
    bridge_mgr.sync_all()
    assert tool_reg.get("gen__json_sorter") is None
