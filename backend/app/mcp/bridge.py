"""Dynamic MCP Capability Bridge Mapping Advertised Tools into NEXORA BaseTool Instances."""

import logging
import re
from typing import Any, Optional, Type
from pydantic import BaseModel, ConfigDict, create_model

from backend.app.mcp.models import McpToolDefinition
from backend.app.mcp.session import McpClientSession
from backend.app.models.agent import RiskLevel
from backend.app.tools.base import BaseTool
from backend.app.tools.registry import ToolRegistry

logger = logging.getLogger("nexora.mcp.bridge")

# Redaction pattern for common secret tokens
SECRET_REDACTION_REGEX = re.compile(
    r"(ghp_[a-zA-Z0-9]{30,}|Bearer\s+[a-zA-Z0-9_\-\.]{20,}|(?:password|token|secret)\s*[:=]\s*['\"]?[^\s'\",]+)",
    re.IGNORECASE,
)


def _schema_type_to_python_type(type_name: Optional[str]) -> Type:
    """Map JSON Schema primitive type strings to Python types."""
    if type_name == "string":
        return str
    elif type_name == "integer":
        return int
    elif type_name == "number":
        return float
    elif type_name == "boolean":
        return bool
    elif type_name == "array":
        return list
    elif type_name == "object":
        return dict
    return Any


def create_dynamic_args_model(tool_name: str, input_schema: dict[str, Any]) -> Type[BaseModel]:
    """Dynamically construct a Pydantic model from JSON Schema input properties."""
    properties = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))

    field_definitions: dict[str, Any] = {}
    for prop_name, prop_spec in properties.items():
        type_str = prop_spec.get("type", "string")
        py_type = _schema_type_to_python_type(type_str)

        if prop_name in required:
            field_definitions[prop_name] = (py_type, ...)
        else:
            field_definitions[prop_name] = (Optional[py_type], None)

    model_name = f"McpArgs_{tool_name.replace('-', '_')}"
    if not field_definitions:
        # Permissive empty args schema
        return create_model(model_name, __config__=ConfigDict(extra="allow"))

    return create_model(model_name, __config__=ConfigDict(extra="ignore"), **field_definitions)


class McpToolWrapper(BaseTool):
    """Dynamic BaseTool implementation backed by an active McpClientSession."""

    def __init__(
        self,
        server_id: str,
        tool_def: McpToolDefinition,
        session: McpClientSession,
    ):
        self.server_id = server_id
        self.raw_tool_name = tool_def.name
        self.session = session

        self.name = f"mcp__{server_id}__{tool_def.name}"
        self.description = (
            f"[MCP Server: {server_id}] {tool_def.description or 'No documentation provided by server.'}"
        )
        self.risk_level = tool_def.risk_level
        self.args_schema = create_dynamic_args_model(self.name, tool_def.input_schema)

    @staticmethod
    def _sanitize_output(output: Any) -> Any:
        """Scan and redact any accidental secret exposure from untrusted tool output."""
        if isinstance(output, str):
            return SECRET_REDACTION_REGEX.sub("[REDACTED_SECRET]", output)
        elif isinstance(output, dict):
            return {k: McpToolWrapper._sanitize_output(v) for k, v in output.items()}
        elif isinstance(output, list):
            return [McpToolWrapper._sanitize_output(item) for item in output]
        return output

    async def execute(self, **kwargs: Any) -> Any:
        """Execute tool call over the active MCP session."""
        logger.info("Executing MCP tool '%s' on server '%s' with args %s", self.name, self.server_id, kwargs)
        raw_result = await self.session.call_tool(self.raw_tool_name, kwargs)

        # Normalize standard MCP response: {"content": [{"type": "text", "text": "..."}]}
        if isinstance(raw_result, dict) and "content" in raw_result:
            content_items = raw_result["content"]
            if isinstance(content_items, list):
                text_parts = [
                    item.get("text", "") for item in content_items if isinstance(item, dict) and "text" in item
                ]
                if text_parts:
                    return self._sanitize_output("\n".join(text_parts))

        return self._sanitize_output(raw_result)


class McpCapabilityBridge:
    """Bridges discovered MCP capabilities into the central ToolRegistry."""

    @staticmethod
    def register_server_tools(
        server_id: str,
        tools: list[McpToolDefinition],
        session: McpClientSession,
        registry: ToolRegistry,
    ) -> list[str]:
        """Wrap and register all advertised tools into the central ToolRegistry."""
        registered_names: list[str] = []
        for tdef in tools:
            wrapper = McpToolWrapper(server_id=server_id, tool_def=tdef, session=session)
            registry.register(wrapper)
            registered_names.append(wrapper.name)
            logger.info("Registered MCP tool '%s' into ToolRegistry.", wrapper.name)
        return registered_names

    @staticmethod
    def unregister_server_tools(server_id: str, registry: ToolRegistry) -> list[str]:
        """Unregister all tools associated with a server from ToolRegistry."""
        prefix = f"mcp__{server_id}__"
        removed_names: list[str] = []
        for name in list(registry.get_tool_names()):
            if name.startswith(prefix):
                if registry.unregister(name):
                    removed_names.append(name)
                    logger.info("Unregistered MCP tool '%s' from ToolRegistry.", name)
        return removed_names
