"""Integration tests for MCP API routes (/api/mcp/*)."""

from pathlib import Path
from typing import Any, Optional
import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport

from backend.app.main import create_app
from backend.app.mcp.models import McpServerConfig
from backend.app.mcp.registry import McpServerRegistry
from backend.app.mcp.session import McpSessionPool
from backend.app.mcp.transport import McpTransport
from backend.app.mcp.vault import McpVaultService
from backend.app.tools.registry import ToolRegistry


class ApiMockMcpTransport(McpTransport):
    """In-memory mock transport for API integration testing."""

    def __init__(self):
        self._connected = False
        self.sent_messages: list[dict[str, Any]] = []

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        self._connected = True

    async def send_message(self, message: dict[str, Any]) -> None:
        self.sent_messages.append(message)

    async def receive_message(self) -> Optional[dict[str, Any]]:
        if not self.sent_messages:
            return None
        last = self.sent_messages[-1]
        method = last.get("method")
        msg_id = last.get("id")

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"protocolVersion": "2024-11-05"},
            }
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": [
                        {
                            "name": "echo",
                            "description": "Echoes input text",
                            "inputSchema": {"type": "object", "properties": {"message": {"type": "string"}}},
                        }
                    ]
                },
            }
        elif method == "ping":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
        return None

    async def close(self) -> None:
        self._connected = False


@pytest_asyncio.fixture
async def mcp_api_client(tmp_path: Path):
    """Create test client with isolated MCP services and pre-configured mock transport."""
    mcp_dir = tmp_path / "mcp"
    vault = McpVaultService(base_dir=mcp_dir)
    registry = McpServerRegistry(base_dir=mcp_dir)
    pool = McpSessionPool(registry=registry, vault=vault)
    tool_registry = ToolRegistry()

    # Pre-register an unapproved server
    cfg = McpServerConfig(
        id="test-server",
        name="Test Server",
        command="python",
        is_approved=False,
    )
    registry.register_server(cfg)

    app = create_app()
    app.state.mcp_vault = vault
    app.state.mcp_registry = registry
    app.state.mcp_session_pool = pool
    app.state.tool_registry = tool_registry

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, registry, vault, pool, tool_registry


@pytest.mark.asyncio
async def test_vault_api_lifecycle(mcp_api_client):
    """Verify storing, listing, and deleting secrets via /api/mcp/vault."""
    client, _, _, _, _ = mcp_api_client

    # Write secret
    write_resp = await client.post(
        "/api/mcp/vault",
        json={"key": "gh_token", "secret_value": "ghp_12345", "description": "GitHub Token"},
    )
    assert write_resp.status_code == 200
    assert write_resp.json()["key"] == "gh_token"

    # List secrets
    list_resp = await client.get("/api/mcp/vault")
    assert list_resp.status_code == 200
    secrets = list_resp.json()
    assert len(secrets) == 1
    assert secrets[0]["key"] == "gh_token"
    assert secrets[0]["description"] == "GitHub Token"
    assert "secret_value" not in secrets[0]  # Secret must not be exposed

    # Delete secret
    del_resp = await client.delete("/api/mcp/vault/gh_token")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"

    # Confirm deletion
    list_after = await client.get("/api/mcp/vault")
    assert len(list_after.json()) == 0


@pytest.mark.asyncio
async def test_server_registration_and_approval_gate(mcp_api_client):
    """Verify register, approval gate blocking, and approving an MCP server."""
    client, _, _, _, _ = mcp_api_client

    # List servers
    resp = await client.get("/api/mcp/servers")
    assert resp.status_code == 200
    servers = resp.json()
    assert len(servers) == 1
    assert servers[0]["config"]["id"] == "test-server"
    assert servers[0]["config"]["is_approved"] is False

    # Attempting to connect unapproved server must fail with 403
    connect_resp = await client.post("/api/mcp/servers/test-server/connect")
    assert connect_resp.status_code == 403

    # Approve server
    approve_resp = await client.post("/api/mcp/servers/test-server/approve")
    assert approve_resp.status_code == 200
    assert approve_resp.json()["config"]["is_approved"] is True
    assert approve_resp.json()["status"] == "APPROVED"


@pytest.mark.asyncio
async def test_server_connect_ping_disconnect_lifecycle(mcp_api_client):
    """Verify connect with tool registration, ping, and disconnect."""
    client, registry, _, pool, tool_registry = mcp_api_client

    # Approve server
    await client.post("/api/mcp/servers/test-server/approve")

    # Inject mock transport into session pool
    mock_transport = ApiMockMcpTransport()
    pool.get_or_create_session("test-server", transport=mock_transport)

    # Connect
    conn_resp = await client.post("/api/mcp/servers/test-server/connect")
    assert conn_resp.status_code == 200
    assert conn_resp.json()["status"] == "CONNECTED"
    assert len(conn_resp.json()["advertised_tools"]) == 1

    # Verify tool registered in ToolRegistry
    assert "mcp__test-server__echo" in tool_registry.get_tool_names()

    # Ping
    ping_resp = await client.post("/api/mcp/servers/test-server/ping")
    assert ping_resp.status_code == 200
    assert ping_resp.json()["status"] == "ok"
    assert "latency_ms" in ping_resp.json()

    # Disconnect
    disc_resp = await client.post("/api/mcp/servers/test-server/disconnect")
    assert disc_resp.status_code == 200
    assert disc_resp.json()["status"] == "disconnected"

    # Verify tool removed from ToolRegistry
    assert "mcp__test-server__echo" not in tool_registry.get_tool_names()
