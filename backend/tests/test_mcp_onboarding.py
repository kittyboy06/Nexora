"""Unit tests for Phase 15 MCP Safe Onboarding, Fingerprinting, and Handshake Verification."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.mcp.models import (
    McpServerConfig,
    McpServerStatus,
    compute_manifest_fingerprint,
)
from backend.app.mcp.onboarding import McpOnboardingService
from backend.app.mcp.registry import McpServerRegistry
from backend.app.mcp.session import McpClientSession, McpSecurityError
from backend.app.mcp.vault import McpVaultService
from backend.app.models.agent import RiskLevel


@pytest.fixture
def temp_mcp_dir(tmp_path: Path):
    d = tmp_path / "mcp"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def mcp_registry(temp_mcp_dir: Path):
    return McpServerRegistry(base_dir=temp_mcp_dir)


@pytest.fixture
def mcp_vault(temp_mcp_dir: Path):
    return McpVaultService(base_dir=temp_mcp_dir)


@pytest.fixture
def onboarding_service(mcp_registry: McpServerRegistry, mcp_vault: McpVaultService):
    return McpOnboardingService(registry=mcp_registry, vault=mcp_vault)


def test_compute_manifest_fingerprint_deterministic_and_sensitive():
    fp1 = compute_manifest_fingerprint(
        command="python",
        args=["-m", "mcp_server"],
        env={"API_KEY": "secret123", "PORT": "8080"},
        working_dir="C:\\app",
    )
    fp2 = compute_manifest_fingerprint(
        command="python",
        args=["-m", "mcp_server"],
        env={"API_KEY": "secret_DIFFERENT", "PORT": "8080"},  # Value changed, keys same
        working_dir="C:\\app",
    )
    # Changing secret values does NOT change fingerprint (only keys)
    assert fp1 == fp2

    # Changing args changes fingerprint
    fp_args = compute_manifest_fingerprint(
        command="python",
        args=["-m", "mcp_server", "--extra"],
        env={"API_KEY": "secret123", "PORT": "8080"},
        working_dir="C:\\app",
    )
    assert fp1 != fp_args

    # Changing command changes fingerprint
    fp_cmd = compute_manifest_fingerprint(
        command="node",
        args=["-m", "mcp_server"],
        env={"API_KEY": "secret123", "PORT": "8080"},
        working_dir="C:\\app",
    )
    assert fp1 != fp_cmd


def test_inspect_manifest_detects_risks_and_missing_secrets(
    onboarding_service: McpOnboardingService,
    mcp_vault: McpVaultService,
):
    # Missing secret test
    config = McpServerConfig(
        id="github-mcp",
        name="GitHub MCP",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={"GITHUB_TOKEN": "ref:vault/github_pat"},
    )
    report = onboarding_service.inspect_manifest(config)
    assert "github_pat" in report.missing_secrets
    assert report.is_valid is False

    # After saving secret
    mcp_vault.set_secret("github_pat", "ghp_1234567890", "Test token")
    report_valid = onboarding_service.inspect_manifest(config)
    assert "github_pat" not in report_valid.missing_secrets
    assert report_valid.is_valid is True

    # High-risk detection test
    risky_config = McpServerConfig(
        id="suspicious-mcp",
        name="Suspicious MCP",
        command="powershell",
        args=["-enc", "SGVsbG8gV29ybGQ="],
        env={},
    )
    risky_report = onboarding_service.inspect_manifest(risky_config)
    assert risky_report.risk_level == RiskLevel.SENSITIVE
    assert len(risky_report.warnings) > 0
    assert risky_report.is_valid is False


def test_approve_manifest_and_fingerprint_tampering_guard(
    mcp_registry: McpServerRegistry,
    onboarding_service: McpOnboardingService,
    mcp_vault: McpVaultService,
):
    config = McpServerConfig(
        id="local-fs",
        name="Filesystem MCP",
        command="python",
        args=["server.py"],
        env={},
    )
    mcp_registry.register_server(config)

    # Approve
    record = onboarding_service.approve_manifest("local-fs", operator="admin")
    assert record is not None
    assert record.config.is_approved is True
    assert record.status == McpServerStatus.APPROVED
    assert record.approved_fingerprint == record.fingerprint

    # Tampering: modify args directly in record config to simulate rogue config change
    record.config.args.append("--dangerous-flag")

    session = McpClientSession(record=record, vault=mcp_vault)
    with pytest.raises(McpSecurityError, match="fingerprint mismatch"):
        # connect should catch fingerprint tampering and revoke approval
        import asyncio
        asyncio.run(session.connect())


def test_api_mcp_onboarding_endpoints():
    import uuid
    srv_id = f"srv-{uuid.uuid4().hex[:8]}"

    app = create_app()
    client = TestClient(app)

    # Test inspect endpoint
    inspect_resp = client.post(
        "/api/mcp/onboard/inspect",
        json={
            "id": srv_id,
            "name": "Test Server",
            "command": "python",
            "args": ["-c", "print(1)"],
            "env": {},
        },
    )
    assert inspect_resp.status_code == 200
    inspect_data = inspect_resp.json()
    assert inspect_data["server_id"] == srv_id
    assert len(inspect_data["fingerprint"]) == 64

    # Register server then approve via endpoint
    reg_resp = client.post(
        "/api/mcp/servers",
        json={
            "id": srv_id,
            "name": "Approve Test Server",
            "command": "python",
            "args": ["-V"],
            "env": {},
        },
    )
    assert reg_resp.status_code == 200

    approve_resp = client.post(
        "/api/mcp/onboard/approve",
        json={
            "server_id": srv_id,
            "fingerprint": inspect_data["fingerprint"],
            "operator": "test_operator",
        },
    )
    assert approve_resp.status_code == 200
    approved_record = approve_resp.json()
    assert approved_record["config"]["is_approved"] is True
    assert approved_record["approved_by"] == "test_operator"
