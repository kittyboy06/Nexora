"""End-to-End Verification Test for Phase 8: Universal MCP Platform.

Validates:
1. Encrypted vault secret creation (ref:vault/<key>)
2. Server configuration registration
3. Operator approval gating
4. Handshake and capability discovery via stdio subprocess (using Python sys.executable MCP server)
5. Dynamic tool bridging into central ToolRegistry
6. PermissionManager risk level checks and execution
7. Runtime ping telemetry
8. Disconnect and tool registry cleanup
9. Security tampering: modifying command/args automatically revokes operator approval
"""

import sys
from pathlib import Path
import pytest

from backend.app.core.config import get_settings
from backend.app.mcp.bridge import McpCapabilityBridge
from backend.app.mcp.models import (
    McpServerConfig,
    McpServerStatus,
    McpServerUpdateRequest,
)
from backend.app.mcp.registry import McpServerRegistry
from backend.app.mcp.session import McpSecurityError, McpSessionPool
from backend.app.mcp.vault import McpVaultService
from backend.app.models.agent import ActionApproval, AgentTask, PlanStep, RiskLevel, ToolCall
from backend.app.permissions.manager import PermissionManager
from backend.app.tools.registry import ToolRegistry


# Lightweight self-contained Python stdio MCP server script
MCP_SERVER_CODE = """
import sys
import json
import os

secret = os.environ.get("MOCK_API_KEY", "")

while True:
    line = sys.stdin.readline()
    if not line:
        break
    try:
        msg = json.loads(line)
    except Exception:
        continue

    method = msg.get("method")
    msg_id = msg.get("id")

    if method == "initialize":
        resp = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "e2e-server", "version": "1.0.0"}
            }
        }
        sys.stdout.write(json.dumps(resp) + "\\n")
        sys.stdout.flush()
    elif method == "notifications/initialized":
        # Notification: no response
        continue
    elif method == "tools/list":
        resp = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": [
                    {
                        "name": "echo_vault_key",
                        "description": "Echoes the resolved vault secret securely",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "prefix": {"type": "string"}
                            }
                        }
                    }
                ]
            }
        }
        sys.stdout.write(json.dumps(resp) + "\\n")
        sys.stdout.flush()
    elif method == "tools/call":
        params = msg.get("params", {})
        args = params.get("arguments", {})
        prefix = args.get("prefix", "")
        resp = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": f"{prefix}:{secret}"
                    }
                ]
            }
        }
        sys.stdout.write(json.dumps(resp) + "\\n")
        sys.stdout.flush()
    elif method == "ping":
        resp = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {}
        }
        sys.stdout.write(json.dumps(resp) + "\\n")
        sys.stdout.flush()
"""


@pytest.mark.asyncio
async def test_full_mcp_platform_e2e_lifecycle(tmp_path: Path):
    """End-to-end integration test with real subprocess stdio transport and encrypted vault."""
    mcp_dir = tmp_path / "mcp"
    mcp_dir.mkdir(parents=True, exist_ok=True)

    # 1. Initialize core services
    vault = McpVaultService(base_dir=mcp_dir)
    registry = McpServerRegistry(base_dir=mcp_dir)
    pool = McpSessionPool(registry=registry, vault=vault, idle_timeout_seconds=60.0)
    tool_registry = ToolRegistry()
    perm_mgr = PermissionManager(get_settings())

    # 2. Store sensitive API token in encrypted vault
    vault.set_secret("E2E_KEY", "super_secret_token_xyz987", description="E2E Mock Token")
    assert vault.get_secret("E2E_KEY") == "super_secret_token_xyz987"

    # Write mini server script to disk
    server_script = tmp_path / "mini_mcp_server.py"
    server_script.write_text(MCP_SERVER_CODE, encoding="utf-8")

    # 3. Register server with ref:vault/E2E_KEY
    cfg = McpServerConfig(
        id="e2e-srv",
        name="E2E Server",
        description="End-to-end verification server",
        command=sys.executable,
        args=[str(server_script)],
        env={"MOCK_API_KEY": "ref:vault/E2E_KEY"},
        is_approved=False,
    )
    reg_record = registry.register_server(cfg)
    assert reg_record.status == McpServerStatus.DISCOVERED
    assert reg_record.config.is_approved is False

    # 4. Attempt connect BEFORE approval -> MUST FAIL
    session = pool.get_or_create_session("e2e-srv")
    with pytest.raises(McpSecurityError) as exc_info:
        await session.connect()
    assert "not approved" in str(exc_info.value).lower()

    # 5. Approve server
    approved_record = registry.approve_server("e2e-srv")
    assert approved_record is not None
    assert approved_record.config.is_approved is True
    assert approved_record.status == McpServerStatus.APPROVED

    # Refresh session with approved record
    session.record = approved_record

    # 6. Connect with real stdio transport -> handshake + capability discovery
    await session.connect()
    assert session.is_connected is True
    assert session.record.status == McpServerStatus.CONNECTED
    assert session.record.protocol_version == "2024-11-05"
    assert len(session.record.advertised_tools) == 1
    assert session.record.advertised_tools[0].name == "echo_vault_key"

    # 7. Bridge capabilities into central ToolRegistry
    registered_names = McpCapabilityBridge.register_server_tools(
        server_id="e2e-srv",
        tools=session.record.advertised_tools,
        session=session,
        registry=tool_registry,
    )
    assert registered_names == ["mcp__e2e-srv__echo_vault_key"]
    assert "mcp__e2e-srv__echo_vault_key" in tool_registry.get_tool_names()

    # 8. Check PermissionManager governance
    tool_def = tool_registry.get("mcp__e2e-srv__echo_vault_key")
    assert tool_def is not None
    assert tool_def.risk_level == RiskLevel.CONTROLLED

    task = AgentTask(task_id="task_e2e", prompt="Test MCP tool")
    step = PlanStep(
        step_id=1,
        description="Invoke MCP tool",
        tool_call=ToolCall(tool_name="mcp__e2e-srv__echo_vault_key", arguments={"prefix": "VAL"}),
        risk_level=tool_def.risk_level,
    )
    authorized, approval = perm_mgr.evaluate_permission(step, task)
    assert isinstance(authorized, bool)

    # 9. Execute tool invocation via bridged McpToolWrapper
    result = await tool_def.execute(prefix="VAL")
    assert result == "VAL:super_secret_token_xyz987"

    # 10. Ping server
    latency = await session.ping()
    assert latency >= 0.0

    # 11. Security tampering: modifying args revokes approval
    updated_rec = registry.update_server(
        "e2e-srv",
        McpServerUpdateRequest(args=[str(server_script), "--extra-arg"]),
    )
    assert updated_rec.config.is_approved is False
    assert updated_rec.status == McpServerStatus.DISCOVERED

    # 12. Disconnect and unregister tools
    await pool.disconnect_server("e2e-srv")
    assert session.is_connected is False
    McpCapabilityBridge.unregister_server_tools("e2e-srv", tool_registry)
    assert "mcp__e2e-srv__echo_vault_key" not in tool_registry.get_tool_names()
