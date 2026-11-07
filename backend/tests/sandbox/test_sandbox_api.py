"""Integration tests for Sandbox API Endpoints."""

import hashlib
import pytest
import pytest_asyncio
import httpx
from pathlib import Path

from backend.app.main import create_app
from backend.app.sandbox.bridge import GeneratedToolBridgeManager
from backend.app.sandbox.evidence import SandboxEvidenceStore
from backend.app.sandbox.models import GeneratedToolProposal, TestCase
from backend.app.sandbox.registry import GeneratedToolRegistry
from backend.app.sandbox.runners.job_object import Win32JobObjectRunner
from backend.app.sandbox.service import SandboxOrchestrationService
from backend.app.sandbox.validator import AstSecurityValidator
from backend.app.tools.registry import ToolRegistry


@pytest_asyncio.fixture
async def sandbox_api_client(tmp_path: Path):
    """Set up test client with isolated Sandbox components."""
    sb_dir = tmp_path / "sandbox"
    catalog_dir = tmp_path / "catalog"
    runs_dir = tmp_path / "runs"

    validator = AstSecurityValidator()
    runner = Win32JobObjectRunner(base_sandbox_dir=sb_dir)
    store = SandboxEvidenceStore(runs_dir=runs_dir)
    service = SandboxOrchestrationService(validator=validator, runner=runner, evidence_store=store)
    gen_reg = GeneratedToolRegistry(catalog_dir=catalog_dir)
    tool_reg = ToolRegistry()
    bridge_mgr = GeneratedToolBridgeManager(
        generated_registry=gen_reg,
        tool_registry=tool_reg,
        runner=runner,
    )

    app = create_app()
    app.state.sandbox_service = service
    app.state.generated_tool_registry = gen_reg
    app.state.generated_tool_bridge = bridge_mgr
    app.state.tool_registry = tool_reg

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client, service, gen_reg, bridge_mgr, tool_reg


def sample_proposal_dict(name: str = "sum_evens", is_malicious: bool = False) -> dict:
    if is_malicious:
        code = f"import os\ndef {name}(): return os.getcwd()"
    else:
        code = f"""
def {name}(items: list) -> int:
    if not isinstance(items, list):
        raise TypeError("Input must be a list")
    return sum(x for x in items if isinstance(x, int) and x % 2 == 0)
"""
    return {
        "name": name,
        "description": "Calculates sum of even integers in list",
        "code": code,
        "input_schema": {"type": "object", "properties": {"items": {"type": "array"}}, "required": ["items"]},
        "output_schema": {"type": "integer"},
        "test_cases": [
            {"name": "pos", "inputs": {"items": [1, 2, 3, 4, 5, 6]}, "expected_output": 12, "is_negative": False},
            {"name": "neg", "inputs": {"items": "not_list"}, "expected_output": None, "is_negative": True},
        ],
    }


@pytest.mark.asyncio
async def test_api_validate_proposal(sandbox_api_client):
    client, _, _, _, _ = sandbox_api_client

    # Test valid proposal
    resp = await client.post("/api/sandbox/validate", json=sample_proposal_dict())
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is True
    assert len(data["errors"]) == 0
    assert len(data["source_sha256"]) == 64

    # Test malicious proposal
    resp_bad = await client.post("/api/sandbox/validate", json=sample_proposal_dict(is_malicious=True))
    assert resp_bad.status_code == 200
    data_bad = resp_bad.json()
    assert data_bad["is_valid"] is False
    assert len(data_bad["errors"]) > 0


@pytest.mark.asyncio
async def test_api_trial_and_evidence(sandbox_api_client):
    client, service, _, _, _ = sandbox_api_client
    proposal = sample_proposal_dict()

    # Run trial in test mode
    resp = await client.post("/api/sandbox/trial", json={"proposal": proposal, "mode": "test"})
    assert resp.status_code == 200
    trial_data = resp.json()
    assert trial_data["status"] == "TESTS_PASSED"
    assert len(trial_data["test_results"]) == 2
    run_id = trial_data["run_id"]

    # Verify evidence can be listed
    ev_list_resp = await client.get("/api/sandbox/evidence")
    assert ev_list_resp.status_code == 200
    ev_list = ev_list_resp.json()
    assert any(e["run_id"] == run_id for e in ev_list)

    # Verify single evidence fetch
    ev_resp = await client.get(f"/api/sandbox/evidence/{run_id}")
    assert ev_resp.status_code == 200
    assert ev_resp.json()["run_id"] == run_id


@pytest.mark.asyncio
async def test_api_promote_lifecycle(sandbox_api_client):
    client, _, gen_reg, bridge_mgr, tool_reg = sandbox_api_client
    proposal = sample_proposal_dict(name="calc_evens")

    # 1. Run trial to get valid evidence
    trial_resp = await client.post("/api/sandbox/trial", json={"proposal": proposal, "mode": "test"})
    run_id = trial_resp.json()["run_id"]

    # 2. Promote tool
    promote_resp = await client.post(
        "/api/sandbox/tools/promote",
        json={"proposal": proposal, "evidence_run_id": run_id, "reviewer": "admin"},
    )
    assert promote_resp.status_code == 200
    record = promote_resp.json()
    assert record["manifest"]["name"] == "calc_evens"
    assert record["manifest"]["version"] == "1.0.0"

    # 3. Verify mounted in ToolRegistry
    assert tool_reg.get("gen__calc_evens") is not None

    # 4. List tools
    list_resp = await client.get("/api/sandbox/tools")
    assert list_resp.status_code == 200
    tools = list_resp.json()
    assert any(t["manifest"]["name"] == "calc_evens" for t in tools)

    # 5. Get tool details
    get_resp = await client.get("/api/sandbox/tools/calc_evens")
    assert get_resp.status_code == 200
    assert get_resp.json()["manifest"]["name"] == "calc_evens"

    # 6. Disable tool
    update_resp = await client.post("/api/sandbox/tools/calc_evens/update", json={"is_enabled": False})
    assert update_resp.status_code == 200
    assert update_resp.json()["is_enabled"] is False
    assert tool_reg.get("gen__calc_evens") is None

    # 7. Delete tool
    del_resp = await client.delete("/api/sandbox/tools/calc_evens")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True
