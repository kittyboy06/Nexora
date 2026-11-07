"""JSON-RPC 2.0 Protocol Framing, Handshake Negotiation, and Message Dispatch."""

import logging
from typing import Any, Optional

logger = logging.getLogger("nexora.mcp.protocol")

LATEST_PROTOCOL_VERSION = "2024-11-05"
SUPPORTED_PROTOCOL_VERSIONS = ["2024-11-05", "2024-10-07"]


class McpProtocolError(Exception):
    """Raised when an MCP server returns a JSON-RPC error response."""

    def __init__(self, code: int, message: str, data: Optional[Any] = None):
        super().__init__(f"MCP Error [{code}]: {message}")
        self.code = code
        self.message = message
        self.data = data


class McpProtocolHandler:
    """Encapsulates JSON-RPC 2.0 framing and standard MCP specification workflows."""

    def __init__(self):
        self._id_counter = 0

    def next_id(self) -> int:
        """Generate monotonically increasing request ID."""
        self._id_counter += 1
        return self._id_counter

    def build_request(
        self, method: str, params: Optional[dict[str, Any]] = None, req_id: Optional[int] = None
    ) -> tuple[int, dict[str, Any]]:
        """Construct a JSON-RPC 2.0 request frame."""
        msg_id = req_id if req_id is not None else self.next_id()
        msg: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": method,
        }
        if params is not None:
            msg["params"] = params
        return msg_id, msg

    def build_notification(
        self, method: str, params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Construct a JSON-RPC 2.0 notification frame without an ID."""
        msg: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            msg["params"] = params
        return msg

    def build_initialize(
        self, client_name: str = "Nexora", client_version: str = "0.1.0"
    ) -> tuple[int, dict[str, Any]]:
        """Build standard MCP 'initialize' handshake request."""
        params = {
            "protocolVersion": LATEST_PROTOCOL_VERSION,
            "capabilities": {
                "tools": {},
            },
            "clientInfo": {
                "name": client_name,
                "version": client_version,
            },
        }
        return self.build_request("initialize", params)

    def build_initialized(self) -> dict[str, Any]:
        """Build standard MCP 'notifications/initialized' notification."""
        return self.build_notification("notifications/initialized")

    def build_tools_list(self) -> tuple[int, dict[str, Any]]:
        """Build 'tools/list' request to discover advertised server tools."""
        return self.build_request("tools/list", {})

    def build_tools_call(self, tool_name: str, arguments: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        """Build 'tools/call' request to execute an advertised tool."""
        params = {
            "name": tool_name,
            "arguments": arguments,
        }
        return self.build_request("tools/call", params)

    def build_ping(self) -> tuple[int, dict[str, Any]]:
        """Build 'ping' request for latency measurement and health check."""
        return self.build_request("ping", {})

    def parse_response(self, response: dict[str, Any], expected_id: Optional[int] = None) -> Any:
        """Validate JSON-RPC framing and extract result or raise McpProtocolError."""
        if not isinstance(response, dict):
            raise McpProtocolError(-32600, "Invalid Response: payload is not a JSON object")

        if response.get("jsonrpc") != "2.0":
            logger.warning("MCP response missing or invalid jsonrpc version: %s", response)

        resp_id = response.get("id")
        if expected_id is not None and resp_id != expected_id:
            logger.warning("Mismatched response ID: expected %s, got %s", expected_id, resp_id)

        if "error" in response:
            err = response["error"]
            if isinstance(err, dict):
                raise McpProtocolError(
                    code=err.get("code", -32000),
                    message=err.get("message", "Unknown server error"),
                    data=err.get("data"),
                )
            raise McpProtocolError(-32000, str(err))

        return response.get("result")
