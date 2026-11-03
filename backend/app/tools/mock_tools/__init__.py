"""NEXORA Mock Tools for Phase 2."""

from backend.app.tools.mock_tools.search import MockSearchTool
from backend.app.tools.mock_tools.summarize import MockSummarizeTool
from backend.app.tools.mock_tools.calculate import MockCalculateTool
from backend.app.tools.mock_tools.file_read import MockFileReadTool
from backend.app.tools.registry import ToolRegistry


def register_mock_tools(registry: ToolRegistry) -> None:
    """Register all default Phase 2 mock tools."""
    registry.register(MockSearchTool())
    registry.register(MockSummarizeTool())
    registry.register(MockCalculateTool())
    registry.register(MockFileReadTool())


__all__ = [
    "MockSearchTool",
    "MockSummarizeTool",
    "MockCalculateTool",
    "MockFileReadTool",
    "register_mock_tools",
]
