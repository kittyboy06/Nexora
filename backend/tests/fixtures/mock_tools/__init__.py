"""NEXORA Test Fixture Mock Tools."""

from backend.tests.fixtures.mock_tools.search import MockSearchTool
from backend.tests.fixtures.mock_tools.summarize import MockSummarizeTool
from backend.tests.fixtures.mock_tools.calculate import MockCalculateTool
from backend.tests.fixtures.mock_tools.file_read import MockFileReadTool
from backend.app.tools.registry import ToolRegistry


def register_mock_tools(registry: ToolRegistry) -> None:
    """Register test fixture mock tools into a test registry."""
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
