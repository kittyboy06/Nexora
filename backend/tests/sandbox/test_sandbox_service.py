"""Unit tests for Sandbox Orchestration Service and Evidence Store."""

import pytest
from pathlib import Path

from backend.app.sandbox.evidence import SandboxEvidenceStore
from backend.app.sandbox.models import GeneratedToolProposal, SandboxRunStatus, TestCase
from backend.app.sandbox.runners.job_object import Win32JobObjectRunner
from backend.app.sandbox.service import SandboxOrchestrationService
from backend.app.sandbox.validator import AstSecurityValidator


@pytest.fixture
def service_fixture(tmp_path: Path):
    sb_dir = tmp_path / "sandbox"
    runs_dir = tmp_path / "runs"
    validator = AstSecurityValidator()
    runner = Win32JobObjectRunner(base_sandbox_dir=sb_dir)
    store = SandboxEvidenceStore(runs_dir=runs_dir)
    service = SandboxOrchestrationService(validator=validator, runner=runner, evidence_store=store)
    return service, store


def sample_proposal(name: str = "filter_evens", is_malicious: bool = False) -> GeneratedToolProposal:
    if is_malicious:
        code = "import os\ndef filter_evens(nums):\n    return os.listdir('.')"
    else:
        code = """
def filter_evens(nums: list) -> list:
    if not isinstance(nums, list):
        raise TypeError("Expected list")
    return [x for x in nums if isinstance(x, int) and x % 2 == 0]
"""
    return GeneratedToolProposal(
        name=name,
        description="Filters even integers from a list",
        code=code,
        input_schema={"type": "object"},
        output_schema={"type": "array"},
        test_cases=[
            TestCase(name="pos", inputs={"nums": [1, 2, 3, 4]}, expected_output=[2, 4], is_negative=False),
            TestCase(name="neg", inputs={"nums": "not_a_list"}, is_negative=True),
        ],
    )


@pytest.mark.asyncio
async def test_service_valid_trial_run(service_fixture):
    service, store = service_fixture
    proposal = sample_proposal()

    result = await service.run_trial(proposal=proposal, mode="test")
    assert result.status == SandboxRunStatus.TESTS_PASSED
    assert len(result.test_results) == 2

    # Verify persisted in evidence store
    stored = service.get_evidence(result.run_id)
    assert stored is not None
    assert stored.run_id == result.run_id
    assert stored.status == SandboxRunStatus.TESTS_PASSED

    all_evidence = service.list_evidence()
    assert len(all_evidence) == 1


@pytest.mark.asyncio
async def test_service_blocks_malicious_proposal_before_execution(service_fixture):
    service, store = service_fixture
    proposal = sample_proposal(is_malicious=True)

    result = await service.run_trial(proposal=proposal, mode="test")
    assert result.status == SandboxRunStatus.ERROR
    assert "AST Security Validation Failed" in result.stderr
    assert result.execution_time_ms == 0.0

    # Ensure evidence of rejection was stored
    stored = service.get_evidence(result.run_id)
    assert stored is not None
    assert "AST Security Validation Failed" in stored.stderr


def test_evidence_store_crud(tmp_path: Path):
    store = SandboxEvidenceStore(runs_dir=tmp_path / "test_store")
    proposal = sample_proposal()
    report = AstSecurityValidator().validate(proposal)

    from backend.app.sandbox.models import SandboxRunResult
    r1 = SandboxRunResult(
        run_id="run_101",
        tool_name="tool_a",
        status=SandboxRunStatus.TESTS_PASSED,
        source_sha256=report.source_sha256,
        timestamp="2026-11-07T12:00:00Z",
    )
    store.save_run_result(r1)

    fetched = store.get_run_result("run_101")
    assert fetched is not None
    assert fetched.tool_name == "tool_a"

    assert len(store.list_run_results()) == 1
    assert store.delete_run_result("run_101") is True
    assert store.get_run_result("run_101") is None
