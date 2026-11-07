"""Unit tests for McpServerRegistry, McpClientSession, and McpSessionPool."""

from pathlib import Path
from typing import Any, Optional
import pytest

from backend.app.mcp.models import (
    McpServerConfig,
    McpServerStatus,
    McpServerUpdateRequest,
)
from backend.app.mcp.registry import McpServerRegistry
from backend.app.mcp.session import (
    McpClientSession,
    McpSecurityError,
    McpSessionPool,
)
from backend.app.mcp.transport import McpTransport
from backend.app.mcp.vault import McpVaultService


class MockMcpTransport(McpTransport):
    """In-memory mock transport simulating a compliant MCP server."""

    def __init__(self):
        self._connected = False
        self.sent_messages: list[dict[str, Any]] = []
        self.mock_tools = [
            {
                "name": "sqlite_query",
                "description": "Run read-only query",
                "inputSchema": {"type": "object", "properties": {"sql": {"type": "string"}}},
            }
        ]

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
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "MockServer", "version": "1.0"},
                },
            }
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": self.mock_tools},
            }
        elif method == "tools/call":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"content": [{"type": "text", "text": "Query success: 3 rows"}]},
            }
        elif method == "ping":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {},
            }
        return None

    async def close(self) -> None:
        self._connected = False


@pytest.fixture
def base_dir(tmp_path: Path) -> Path:
    return tmp_path / "mcp"


@pytest.fixture
def registry(base_dir: Path) -> McpServerRegistry:
    return McpServerRegistry(base_dir=base_dir)


@pytest.fixture
def vault(base_dir: Path) -> McpVaultService:
    return McpVaultService(base_dir=base_dir)


def test_registry_crud_and_approval_invalidation(registry: McpServerRegistry):
    """Verify registering a server, operator approval, and invalidation upon command edit."""
    cfg = McpServerConfig(
        id="postgres-mcp",
        name="Postgres MCP",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-postgres"],
        env={"DB_URL": "ref:vault/db_url"},
    )

    record = registry.register_server(cfg)
    assert record.config.id == "postgres-mcp"
    assert record.config.is_approved is False
    assert record.status == McpServerStatus.DISCOVERED

    # Approve server
    approved = registry.approve_server("postgres-mcp")
    assert approved.config.is_approved is True
    assert approved.status == McpServerStatus.APPROVED

    # Modifying command must invalidate approval
    updated = registry.update_server("postgres-mcp", McpServerUpdateRequest(command="node"))
    assert updated.config.command == "node"
    assert updated.config.is_approved is False
    assert updated.status == McpServerStatus.DISCOVERED


@pytest.mark.asyncio
async def test_session_unapproved_server_fails(registry: McpServerRegistry, vault: McpVaultService):
    """Verify that attempting to connect to an unapproved server raises McpSecurityError."""
    cfg = McpServerConfig(
        id="unapproved-server",
        name="Unapproved",
        command="python",
        is_approved=False,
    )
    record = registry.register_server(cfg)
    session = McpClientSession(record=record, vault=vault)

    with pytest.raises(McpSecurityError) as exc_info:
        await session.connect()

    assert "not approved by operator" in str(exc_info.value)


@pytest.mark.asyncio
async def test_session_handshake_and_tool_call(registry: McpServerRegistry, vault: McpVaultService):
    """Verify complete MCP lifecycle: approved handshake, tools discovery, and tool call."""
    cfg = McpServerConfig(
        id="sqlite-mcp",
        name="SQLite",
        command="python",
        is_approved=True,
    )
    record = registry.register_server(cfg)
    mock_transport = MockMcpTransport()

    session = McpClientSession(
        record=record,
        vault=vault,
        transport=mock_transport,
    )

    await session.connect()
    assert session.is_connected is True
    assert record.status == McpServerStatus.CONNECTED
    assert record.protocol_version == "2024-11-05"
    assert len(record.advertised_tools) == 1
    assert record.advertised_tools[0].name == "sqlite_query"

    # Call tool
    result = await session.call_tool("sqlite_query", {"sql": "SELECT 1;"})
    assert result["content"][0]["text"] == "Query success: 3 rows"

    # Ping
    latency = await session.ping()
    assert latency >= 0.0
    assert record.ping_latency_ms is not None

    # Disconnect
    await session.disconnect()
    assert session.is_connected is False
    assert record.status == McpServerStatus.STOPPED


@pytest.mark.asyncio
async def test_session_pool_lifecycle(registry: McpServerRegistry, vault: McpVaultService):
    """Verify McpSessionPool instantiates and cleanly disconnects all sessions."""
    cfg = McpServerConfig(
        id="pool-test",
        name="Pool Test",
        command="python",
        is_approved=True,
    )
    registry.register_server(cfg)
    pool = McpSessionPool(registry=registry, vault=vault)
    mock_transport = MockMcpTransport()

    session = pool.get_or_create_session("pool-test", transport=mock_transport)
    await session.connect()
    assert session.is_connected is True

    await pool.disconnect_all()
    assert session.is_connected is False
