"""Unit tests for McpCapabilityBridge, dynamic BaseTool wrappers, and ToolRegistry integration."""

from typing import Any, Optional
import pytest
from pydantic import ValidationError

from backend.app.mcp.bridge import McpCapabilityBridge, create_dynamic_args_model
from backend.app.mcp.models import (
    McpServerConfig,
    McpServerRecord,
    McpToolDefinition,
)
from backend.app.mcp.session import McpClientSession
from backend.app.mcp.transport import McpTransport
from backend.app.mcp.vault import McpVaultService
from backend.app.models.agent import RiskLevel
from backend.app.tools.registry import ToolRegistry


class DummyMcpTransport(McpTransport):
    """Minimal mock transport for tool call testing."""

    def __init__(self, return_payload: Any = None):
        self._connected = True
        self.return_payload = return_payload or {
            "content": [{"type": "text", "text": "Sample MCP output"}]
        }

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        pass

    async def send_message(self, message: dict[str, Any]) -> None:
        pass

    async def receive_message(self) -> Optional[dict[str, Any]]:
        return {"jsonrpc": "2.0", "id": 1, "result": self.return_payload}

    async def close(self) -> None:
        self._connected = False


def test_create_dynamic_args_model():
    """Verify dynamic Pydantic args model creation from JSON Schema."""
    schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["query"],
    }
    model_cls = create_dynamic_args_model("test_tool", schema)

    # Valid instance
    instance = model_cls(query="SELECT *", limit=10)
    assert instance.query == "SELECT *"
    assert instance.limit == 10

    # Optional field omitted is fine
    instance_opt = model_cls(query="SELECT 1")
    assert instance_opt.query == "SELECT 1"
    assert instance_opt.limit is None

    # Missing required field raises ValidationError
    with pytest.raises(ValidationError):
        model_cls(limit=5)


def test_unclassified_mcp_tools_require_explicit_approval():
    """An advertised capability is untrusted until an operator classifies it."""
    tool = McpToolDefinition(name="unclassified_remote_action")

    assert tool.risk_level == RiskLevel.SENSITIVE


@pytest.mark.asyncio
async def test_register_and_execute_mcp_tool(tmp_path):
    """Verify registering an MCP tool in ToolRegistry and executing it."""
    registry = ToolRegistry()
    vault = McpVaultService(base_dir=tmp_path / "mcp")
    record = McpServerRecord(
        config=McpServerConfig(
            id="sqlite",
            name="SQLite",
            command="python",
            is_approved=True,
        )
    )

    mock_transport = DummyMcpTransport(
        return_payload={"content": [{"type": "text", "text": "Found 42 rows"}]}
    )
    session = McpClientSession(record=record, vault=vault, transport=mock_transport)

    tools = [
        McpToolDefinition(
            name="query",
            description="Execute SQL",
            input_schema={"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]},
            risk_level=RiskLevel.SAFE,
        )
    ]

    registered = McpCapabilityBridge.register_server_tools("sqlite", tools, session, registry)
    assert registered == ["mcp__sqlite__query"]
    assert "mcp__sqlite__query" in registry.get_tool_names()

    # Retrieve and execute via ToolRegistry
    tool = registry.get("mcp__sqlite__query")
    assert tool is not None
    assert tool.name == "mcp__sqlite__query"
    assert tool.risk_level == RiskLevel.SAFE

    result = await tool.execute(sql="SELECT * FROM users")
    assert result == "Found 42 rows"


@pytest.mark.asyncio
async def test_mcp_output_secret_redaction(tmp_path):
    """Verify raw secret tokens in tool output are automatically redacted."""
    registry = ToolRegistry()
    vault = McpVaultService(base_dir=tmp_path / "mcp")
    record = McpServerRecord(
        config=McpServerConfig(id="github", name="GitHub", command="npx", is_approved=True)
    )

    leaked_token = "ghp_1234567890abcdef1234567890abcdef1234"
    mock_transport = DummyMcpTransport(
        return_payload={"content": [{"type": "text", "text": f"Error with token: {leaked_token}"}]}
    )
    session = McpClientSession(record=record, vault=vault, transport=mock_transport)

    tools = [McpToolDefinition(name="get_repo", description="Get repository")]
    McpCapabilityBridge.register_server_tools("github", tools, session, registry)

    tool = registry.get("mcp__github__get_repo")
    result = await tool.execute()
    assert leaked_token not in result
    assert "[REDACTED_SECRET]" in result


def test_unregister_server_tools():
    """Verify unregistering a server removes only its specific tools."""
    registry = ToolRegistry()

    # Pre-populate registry with two servers
    t1 = McpToolDefinition(name="t1")
    t2 = McpToolDefinition(name="t2")
    t3 = McpToolDefinition(name="t3")

    McpCapabilityBridge.register_server_tools("server_a", [t1, t2], session=None, registry=registry)
    McpCapabilityBridge.register_server_tools("server_b", [t3], session=None, registry=registry)

    assert "mcp__server_a__t1" in registry.get_tool_names()
    assert "mcp__server_a__t2" in registry.get_tool_names()
    assert "mcp__server_b__t3" in registry.get_tool_names()

    # Unregister server_a
    removed = McpCapabilityBridge.unregister_server_tools("server_a", registry)
    assert len(removed) == 2
    assert "mcp__server_a__t1" not in registry.get_tool_names()
    assert "mcp__server_a__t2" not in registry.get_tool_names()
    assert "mcp__server_b__t3" in registry.get_tool_names()
