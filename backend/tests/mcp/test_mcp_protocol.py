"""Unit tests for JSON-RPC 2.0 framing, handshake negotiation, and StdioTransport."""

import sys
import pytest

from backend.app.mcp.protocol import (
    LATEST_PROTOCOL_VERSION,
    McpProtocolError,
    McpProtocolHandler,
)
from backend.app.mcp.transport import StdioTransport


@pytest.fixture
def protocol() -> McpProtocolHandler:
    return McpProtocolHandler()


def test_build_request_increments_id(protocol: McpProtocolHandler):
    """Verify request generation increments IDs and builds valid JSON-RPC 2.0 frames."""
    id1, msg1 = protocol.build_request("test_method", {"param": 1})
    id2, msg2 = protocol.build_request("test_method_2")

    assert id1 == 1
    assert id2 == 2
    assert msg1["jsonrpc"] == "2.0"
    assert msg1["id"] == 1
    assert msg1["method"] == "test_method"
    assert msg1["params"] == {"param": 1}

    assert msg2["jsonrpc"] == "2.0"
    assert msg2["id"] == 2
    assert "params" not in msg2


def test_build_notification(protocol: McpProtocolHandler):
    """Verify notifications omit the ID field."""
    notif = protocol.build_notification("notify_something", {"status": "ok"})
    assert notif["jsonrpc"] == "2.0"
    assert "id" not in notif
    assert notif["method"] == "notify_something"


def test_build_handshake(protocol: McpProtocolHandler):
    """Verify MCP standard handshake requests comply with 2024-11-05 specification."""
    req_id, init_req = protocol.build_initialize(client_name="NexoraTest", client_version="1.0.0")
    assert init_req["method"] == "initialize"
    assert init_req["params"]["protocolVersion"] == LATEST_PROTOCOL_VERSION
    assert init_req["params"]["clientInfo"]["name"] == "NexoraTest"

    init_notif = protocol.build_initialized()
    assert init_notif["method"] == "notifications/initialized"
    assert "id" not in init_notif


def test_parse_response_success_and_error(protocol: McpProtocolHandler):
    """Verify response parsing returns result or raises McpProtocolError."""
    # Successful response
    success_frame = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"tools": [{"name": "test_tool"}]},
    }
    result = protocol.parse_response(success_frame, expected_id=1)
    assert result == {"tools": [{"name": "test_tool"}]}

    # Error response
    error_frame = {
        "jsonrpc": "2.0",
        "id": 2,
        "error": {
            "code": -32601,
            "message": "Method not found",
        },
    }
    with pytest.raises(McpProtocolError) as exc_info:
        protocol.parse_response(error_frame, expected_id=2)

    assert exc_info.value.code == -32601
    assert "Method not found" in exc_info.value.message


@pytest.mark.asyncio
async def test_stdio_transport_real_subprocess_roundtrip():
    """Verify StdioTransport spawns a real Python child process, writes to stdin, and reads from stdout."""
    # Echo script: reads one line from stdin, prepends prefix, writes to stdout
    echo_code = "import sys; line = sys.stdin.readline(); sys.stdout.write(line); sys.stdout.flush()"
    transport = StdioTransport(
        command=sys.executable,
        args=["-c", echo_code],
    )

    await transport.connect()
    assert transport.is_connected is True

    test_msg = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    await transport.send_message(test_msg)

    received = await transport.receive_message()
    assert received == test_msg

    await transport.close()
    assert transport.is_connected is False
