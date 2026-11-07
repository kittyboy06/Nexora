"""Unit tests for Research Service and ToolRegistry Integration."""

from unittest.mock import AsyncMock, MagicMock
import pytest

from backend.app.core.config import get_settings
from backend.app.models.agent import AgentTask, PlanStep, RiskLevel, ToolCall
from backend.app.permissions.manager import PermissionManager
from backend.app.research.models import CitationItem, FetchResult, QuarantineItem, SearchResult
from backend.app.research.service import BrowserResearchService
from backend.app.research.tools import (
    WebDownloadQuarantineTool,
    WebExtractCitationsTool,
    WebFetchTool,
    WebSearchTool,
    register_research_tools,
)
from backend.app.tools.registry import ToolRegistry


@pytest.fixture
def mock_research_service():
    service = MagicMock(spec=BrowserResearchService)
    service.search = AsyncMock(
        return_value=[
            SearchResult(title="Python Official", url="https://python.org", snippet="Python language home", rank=1),
            SearchResult(title="Python Tutorial", url="https://python.org/tutorial", snippet="Learn Python basics", rank=2),
        ]
    )
    service.fetch_page = AsyncMock(
        return_value=FetchResult(
            url="https://example.com/guide",
            title="Nexora Guide",
            content="Nexora is an autonomous Windows orchestrator designed for multi-agent workflows.",
            citations=[
                CitationItem(quote="Nexora is an autonomous Windows orchestrator", source_url="https://example.com/guide", char_offset=0)
            ],
            content_hash="abc1234567890",
            engine="http",
        )
    )
    service.extract_citations = AsyncMock(
        return_value=[
            CitationItem(quote="Nexora provides multi-agent workflows.", source_url="https://example.com/guide", char_offset=10)
        ]
    )
    service.download_file = AsyncMock(
        return_value=QuarantineItem(
            task_id="task_001",
            filename="data_sheet.pdf",
            original_url="https://example.com/data_sheet.pdf",
            file_size=24500,
            content_type="application/pdf",
            sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            quarantine_path="data/quarantine/task_001/data_sheet.pdf",
            downloaded_at="2026-11-07T12:00:00Z",
        )
    )
    return service


def test_research_tools_registration(mock_research_service):
    """Verify all 4 research tools are registered with correct risk tiers in ToolRegistry."""
    registry = ToolRegistry()
    registered = register_research_tools(registry, mock_research_service)

    assert registered == [
        "web_search",
        "web_fetch",
        "web_extract_citations",
        "web_download_quarantine",
    ]

    search_tool = registry.get("web_search")
    assert search_tool is not None
    assert search_tool.risk_level == RiskLevel.CONTROLLED

    fetch_tool = registry.get("web_fetch")
    assert fetch_tool is not None
    assert fetch_tool.risk_level == RiskLevel.CONTROLLED

    citation_tool = registry.get("web_extract_citations")
    assert citation_tool is not None
    assert citation_tool.risk_level == RiskLevel.CONTROLLED

    download_tool = registry.get("web_download_quarantine")
    assert download_tool is not None
    assert download_tool.risk_level == RiskLevel.SENSITIVE


@pytest.mark.asyncio
async def test_web_search_tool_execute(mock_research_service):
    """Verify WebSearchTool formats search results."""
    tool = WebSearchTool(mock_research_service)
    result = await tool.execute(query="python", max_results=2)

    assert "1. Python Official" in result
    assert "https://python.org" in result
    assert "2. Python Tutorial" in result


@pytest.mark.asyncio
async def test_web_fetch_tool_execute(mock_research_service):
    """Verify WebFetchTool wraps text in <untrusted_web_evidence>."""
    tool = WebFetchTool(mock_research_service)
    result = await tool.execute(url="https://example.com/guide")

    assert result.startswith('<untrusted_web_evidence source="https://example.com/guide" title="Nexora Guide" hash="abc1234567890">')
    assert "autonomous Windows orchestrator" in result
    assert result.endswith("</untrusted_web_evidence>")


@pytest.mark.asyncio
async def test_web_extract_citations_tool_execute(mock_research_service):
    """Verify WebExtractCitationsTool formats citation matches."""
    tool = WebExtractCitationsTool(mock_research_service)
    result = await tool.execute(url="https://example.com/guide", focus_query="multi-agent")

    assert "Citations extracted from https://example.com/guide" in result
    assert '[1] "Nexora provides multi-agent workflows."' in result


@pytest.mark.asyncio
async def test_web_download_quarantine_tool_execute(mock_research_service):
    """Verify WebDownloadQuarantineTool reports quarantine metadata."""
    tool = WebDownloadQuarantineTool(mock_research_service)
    result = await tool.execute(url="https://example.com/data_sheet.pdf", task_id="task_001")

    assert "File successfully quarantined." in result
    assert "Filename: data_sheet.pdf" in result
    assert "SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" in result
    assert "Status: Quarantined safely (not executed)." in result


def test_permission_manager_governance_tiers(mock_research_service):
    """Verify PermissionManager enforces appropriate governance over research tools."""
    perm_mgr = PermissionManager(get_settings())
    task = AgentTask(task_id="t1", prompt="Research task")

    # CONTROLLED web_fetch
    step_fetch = PlanStep(
        step_id=1,
        description="Fetch docs",
        tool_call=ToolCall(tool_name="web_fetch", arguments={"url": "https://example.com"}),
        risk_level=RiskLevel.CONTROLLED,
    )
    authorized_fetch, approval_fetch = perm_mgr.evaluate_permission(step_fetch, task)
    assert isinstance(authorized_fetch, bool)

    # SENSITIVE web_download_quarantine -> ALWAYS requires human approval
    step_download = PlanStep(
        step_id=2,
        description="Download file",
        tool_call=ToolCall(tool_name="web_download_quarantine", arguments={"url": "https://example.com/f.bin"}),
        risk_level=RiskLevel.SENSITIVE,
    )
    authorized_dl, approval_dl = perm_mgr.evaluate_permission(step_download, task)
    assert authorized_dl is False
    assert approval_dl is not None
    assert approval_dl.tool_name == "web_download_quarantine"
    assert step_download.risk_level == RiskLevel.SENSITIVE
