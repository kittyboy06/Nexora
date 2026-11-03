import pytest
from backend.app.models.agent import RiskLevel
from backend.app.tools.mock_tools.calculate import MockCalculateTool
from backend.app.tools.mock_tools.file_read import MockFileReadTool
from backend.app.tools.mock_tools.search import MockSearchTool
from backend.app.tools.mock_tools.summarize import MockSummarizeTool
from backend.app.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_mock_search_tool():
    tool = MockSearchTool()
    assert tool.risk_level == RiskLevel.SAFE
    res = await tool.execute(query="AI agents", max_results=2)
    assert res["query"] == "AI agents"
    assert len(res["results"]) == 2


@pytest.mark.asyncio
async def test_mock_summarize_tool():
    tool = MockSummarizeTool()
    res = await tool.execute(text="One two three four five six seven", max_words=5)
    assert res["original_word_count"] == 7
    assert res["summary"] == "One two three four five..."


@pytest.mark.asyncio
async def test_mock_calculate_tool():
    tool = MockCalculateTool()
    res = await tool.execute(expression="10 * 5 + 4")
    assert res["result"] == 54

    with pytest.raises(ValueError):
        await tool.execute(expression="import os; os.system('bad')")


@pytest.mark.asyncio
async def test_mock_file_read_tool():
    tool = MockFileReadTool()
    assert tool.risk_level == RiskLevel.SENSITIVE
    res = await tool.execute(filepath="config.json")
    assert res["simulated"] is True
    assert "config.json" in res["content"]


def test_tool_registry():
    registry = ToolRegistry()
    search = MockSearchTool()
    registry.register(search)

    assert registry.get("mock_search") is search
    assert registry.get("nonexistent") is None
    assert "mock_search" in registry.get_tool_names()
    specs = registry.get_specs()
    assert len(specs) == 1
    assert specs[0]["name"] == "mock_search"
