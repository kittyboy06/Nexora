"""End-to-End Integration Verification for Phase 10 Generated Tools and Sandbox Platform."""

import hashlib
import json
import pytest
from pathlib import Path

from backend.app.models.agent import RiskLevel
from backend.app.sandbox.bridge import GeneratedToolBridgeManager
from backend.app.sandbox.evidence import SandboxEvidenceStore
from backend.app.sandbox.models import (
    GeneratedToolProposal,
    SandboxRunStatus,
    TestCase,
    ToolPromotionRequest,
    TrialRunRequest,
)
from backend.app.sandbox.registry import GeneratedToolRegistry
from backend.app.sandbox.runners.job_object import Win32JobObjectRunner
from backend.app.sandbox.service import SandboxOrchestrationService
from backend.app.sandbox.validator import AstSecurityValidator
from backend.app.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_sandbox_platform_e2e_lifecycle(tmp_path: Path):
    """Verify complete end-to-end lifecycle:

    Proposal -> AST Gate -> Job Object Sandbox Trial -> Evidence Telemetry ->
    Operator Promotion -> ToolRegistry Bridge (gen__*) -> Agent Execution ->
    Disable/Enable Governance -> Rollback -> Deletion.
    """
    sb_dir = tmp_path / "sandbox"
    runs_dir = tmp_path / "runs"
    catalog_dir = tmp_path / "catalog"

    validator = AstSecurityValidator()
    runner = Win32JobObjectRunner(base_sandbox_dir=sb_dir)
    evidence_store = SandboxEvidenceStore(runs_dir=runs_dir)
    service = SandboxOrchestrationService(
        validator=validator,
        runner=runner,
        evidence_store=evidence_store,
    )
    gen_registry = GeneratedToolRegistry(catalog_dir=catalog_dir)
    tool_registry = ToolRegistry()
    bridge_mgr = GeneratedToolBridgeManager(
        generated_registry=gen_registry,
        tool_registry=tool_registry,
        runner=runner,
    )

    # 1. Capability Gap: Agent proposes a new custom tool
    tool_code = """
import csv

def parse_csv_rows(raw_csv: str) -> list:
    if not isinstance(raw_csv, str):
        raise TypeError("raw_csv must be a string")
    reader = csv.DictReader(raw_csv.strip().splitlines())
    return [row for row in reader]
"""
    proposal = GeneratedToolProposal(
        name="parse_csv_rows",
        description="Parses raw CSV string into a list of row dictionaries",
        code=tool_code,
        input_schema={
            "type": "object",
            "properties": {"raw_csv": {"type": "string"}},
            "required": ["raw_csv"],
        },
        output_schema={"type": "array"},
        test_cases=[
            TestCase(
                name="pos_valid_csv",
                inputs={"raw_csv": "name,score\nAlice,95\nBob,88"},
                expected_output=[{"name": "Alice", "score": "95"}, {"name": "Bob", "score": "88"}],
                is_negative=False,
            ),
            TestCase(
                name="neg_invalid_type",
                inputs={"raw_csv": 12345},
                expected_output=None,
                is_negative=True,
            ),
        ],
        task_id="task_e2e_001",
    )

    # 2. Step 1: AST Static Security Gate
    validation_report = service.validate_proposal(proposal)
    assert validation_report.is_valid is True
    assert len(validation_report.errors) == 0
    assert len(validation_report.source_sha256) == 64

    # 3. Step 2: One-off Sandboxed Trial Execution (under Win32 Job Object isolation)
    trial_result = await service.run_trial(proposal, mode="test", task_id="task_e2e_001")
    assert trial_result.status == SandboxRunStatus.TESTS_PASSED
    assert trial_result.exit_code == 0
    assert len(trial_result.test_results) == 2
    assert trial_result.test_results[0]["passed"] is True
    assert trial_result.test_results[1]["passed"] is True
    assert trial_result.peak_memory_bytes > 0
    assert trial_result.execution_time_ms > 0

    # 4. Step 3: Verify Evidence Telemetry was persisted immutably
    stored_evidence = service.get_evidence(trial_result.run_id)
    assert stored_evidence is not None
    assert stored_evidence.run_id == trial_result.run_id
    assert stored_evidence.source_sha256 == validation_report.source_sha256

    # 5. Step 4: Operator Reviews and Promotes to Versioned Catalog
    record = gen_registry.promote(
        proposal=proposal,
        evidence=stored_evidence,
        reviewer="senior_operator",
        version="1.0.0",
    )
    assert record.manifest.name == "parse_csv_rows"
    assert record.manifest.version == "1.0.0"
    assert record.is_enabled is True
    assert record.audit_history[0]["reviewer"] == "senior_operator"

    # 6. Step 5: Mount into Central ToolRegistry via Capability Bridge
    bridge_mgr.register_tool(record)
    registered_tool = tool_registry.get("gen__parse_csv_rows")
    assert registered_tool is not None
    assert registered_tool.name == "gen__parse_csv_rows"
    assert registered_tool.risk_level == RiskLevel.CONTROLLED

    # Check specs exposed to LLM planner
    tool_spec = registered_tool.get_spec()
    assert tool_spec["name"] == "gen__parse_csv_rows"
    assert tool_spec["risk_level"] == "CONTROLLED"

    # 7. Step 6: Agent Execution of Promoted Tool
    # Note: Promoted execution routes directly through the isolated Job Object sandbox
    output = await registered_tool.execute(raw_csv="fruit,qty\nApple,10\nOrange,5")
    assert output == [{"fruit": "Apple", "qty": "10"}, {"fruit": "Orange", "qty": "5"}]

    # 8. Step 7: Operator Governance - Disable and Remount
    gen_registry.set_enabled("parse_csv_rows", False)
    bridge_mgr.sync_all()
    assert tool_registry.get("gen__parse_csv_rows") is None

    gen_registry.set_enabled("parse_csv_rows", True)
    bridge_mgr.sync_all()
    assert tool_registry.get("gen__parse_csv_rows") is not None

    # 9. Step 8: Version Rollback
    # Promote a v1.0.1 update
    v2_code = tool_code + "\n# minor update"
    v2_sha = hashlib.sha256(v2_code.encode("utf-8")).hexdigest()
    v2_proposal = GeneratedToolProposal(
        name="parse_csv_rows",
        description="Parses raw CSV string into a list of row dictionaries v2",
        code=v2_code,
        input_schema=proposal.input_schema,
        output_schema=proposal.output_schema,
        test_cases=proposal.test_cases,
    )
    v2_evidence = stored_evidence.model_copy(update={"run_id": "run_v2", "source_sha256": v2_sha})
    v2_record = gen_registry.promote(v2_proposal, v2_evidence, reviewer="admin", version="1.0.1")
    assert gen_registry.get_tool("parse_csv_rows").manifest.version == "1.0.1"

    # Roll back to 1.0.0
    rollback_ok = gen_registry.rollback("parse_csv_rows", "1.0.0")
    assert rollback_ok is True
    assert gen_registry.get_tool("parse_csv_rows").manifest.version == "1.0.0"

    # 10. Step 9: Complete Deletion
    bridge_mgr.unregister_tool("parse_csv_rows")
    assert tool_registry.get("gen__parse_csv_rows") is None
    delete_ok = gen_registry.delete_tool("parse_csv_rows")
    assert delete_ok is True
    assert gen_registry.get_tool("parse_csv_rows") is None
