import logging
from typing import Any
from backend.app.tools.base import BaseTool

logger = logging.getLogger("nexora.tools")


class ToolRegistry:
    """Registry maintaining available tools and their specifications."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a new tool instance."""
        if tool.name in self._tools:
            logger.warning("Overwriting existing tool registration: %s", tool.name)
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s (risk=%s)", tool.name, tool.risk_level.value)

    def unregister(self, name: str) -> bool:
        """Unregister a tool by name."""
        if name in self._tools:
            del self._tools[name]
            logger.debug("Unregistered tool: %s", name)
            return True
        return False

    def get(self, name: str) -> BaseTool | None:
        """Lookup a registered tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        """Return list of all registered tools."""
        return list(self._tools.values())

    def get_tool_names(self) -> list[str]:
        """Return list of registered tool names."""
        return list(self._tools.keys())

    def get_specs(self) -> list[dict[str, Any]]:
        """Return tool specifications formatted for LLM planning prompts."""
        return [tool.get_spec() for tool in self._tools.values()]
