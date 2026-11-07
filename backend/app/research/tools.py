"""Typed Research Tools for ToolRegistry Integration."""

from typing import Any, Optional
from pydantic import BaseModel, Field

from backend.app.models.agent import RiskLevel
from backend.app.research.sanitizer import wrap_untrusted_evidence
from backend.app.research.service import BrowserResearchService
from backend.app.tools.base import BaseTool
from backend.app.tools.registry import ToolRegistry


class WebSearchArgs(BaseModel):
    query: str = Field(..., description="The search query keywords")
    max_results: int = Field(default=5, ge=1, le=20, description="Max search results to retrieve (1-20)")


class WebSearchTool(BaseTool):
    """Searches the public web using the configured search provider."""

    name = "web_search"
    description = (
        "Search the public web for documentation, articles, and references. "
        "Returns ranked search results containing title, URL, and summary snippet."
    )
    risk_level = RiskLevel.CONTROLLED
    args_schema = WebSearchArgs

    def __init__(self, service: BrowserResearchService):
        self.service = service

    async def execute(self, **kwargs: Any) -> Any:
        args = self.validate_args(kwargs)
        results = await self.service.search(args.query, max_results=args.max_results)
        if not results:
            return f"No search results found for query: '{args.query}'."

        lines = [f"Search results for '{args.query}':\n"]
        for r in results:
            lines.append(f"{r.rank}. {r.title}\n   URL: {r.url}\n   Snippet: {r.snippet}\n")
        return "\n".join(lines).strip()


class WebFetchArgs(BaseModel):
    url: str = Field(..., description="Target webpage URL to retrieve")
    render_js: bool = Field(default=False, description="Enable headless browser for JavaScript-heavy dynamic apps")
    take_screenshot: bool = Field(default=False, description="Capture a visual screenshot evidence artifact")


class WebFetchTool(BaseTool):
    """Fetches a webpage and returns cleaned body text enclosed in <untrusted_web_evidence>."""

    name = "web_fetch"
    description = (
        "Fetch and read webpage text with Anti-SSRF protection. "
        "Returns cleaned content safely encapsulated in <untrusted_web_evidence>."
    )
    risk_level = RiskLevel.CONTROLLED
    args_schema = WebFetchArgs

    def __init__(self, service: BrowserResearchService):
        self.service = service

    async def execute(self, **kwargs: Any) -> Any:
        args = self.validate_args(kwargs)
        fetch_res = await self.service.fetch_page(
            url=args.url,
            render_js=args.render_js,
            take_screenshot=args.take_screenshot,
        )

        wrapped = wrap_untrusted_evidence(
            content=fetch_res.content,
            url=fetch_res.url,
            title=fetch_res.title,
            content_hash=fetch_res.content_hash,
        )
        return wrapped


class WebExtractCitationsArgs(BaseModel):
    url: str = Field(..., description="Webpage URL to extract citations from")
    focus_query: str = Field(..., description="The claim or topic query to find citations for")


class WebExtractCitationsTool(BaseTool):
    """Extracts targeted verbatim quotes from a webpage for factual citations."""

    name = "web_extract_citations"
    description = (
        "Extract verbatim sentence-level quotes from a webpage relevant to a specific topic or claim. "
        "Returns citations with character offsets and source provenance."
    )
    risk_level = RiskLevel.CONTROLLED
    args_schema = WebExtractCitationsArgs

    def __init__(self, service: BrowserResearchService):
        self.service = service

    async def execute(self, **kwargs: Any) -> Any:
        args = self.validate_args(kwargs)
        citations = await self.service.extract_citations(url=args.url, focus_query=args.focus_query)
        if not citations:
            return f"No matching citations found on '{args.url}' for query '{args.focus_query}'."

        lines = [f"Citations extracted from {args.url} (focus: '{args.focus_query}'):\n"]
        for i, c in enumerate(citations, start=1):
            lines.append(f"[{i}] \"{c.quote}\" (char offset: {c.char_offset})")
        return "\n".join(lines).strip()


class WebDownloadQuarantineArgs(BaseModel):
    url: str = Field(..., description="Remote asset URL to download")
    filename: Optional[str] = Field(default=None, description="Optional safe filename to save as in quarantine")
    task_id: Optional[str] = Field(default="default", description="Associated task identifier for quarantine folder")


class WebDownloadQuarantineTool(BaseTool):
    """Downloads a remote file into the isolated task quarantine directory."""

    name = "web_download_quarantine"
    description = (
        "Download an external remote asset into an isolated quarantine folder with SHA-256 and MIME verification. "
        "Does NOT execute or open the downloaded file. Sensitive operation requiring operator approval."
    )
    risk_level = RiskLevel.SENSITIVE
    args_schema = WebDownloadQuarantineArgs

    def __init__(self, service: BrowserResearchService):
        self.service = service

    async def execute(self, **kwargs: Any) -> Any:
        args = self.validate_args(kwargs)
        item = await self.service.download_file(
            url=args.url,
            task_id=args.task_id or "default",
            filename=args.filename,
        )

        return (
            f"File successfully quarantined.\n"
            f"Filename: {item.filename}\n"
            f"Task Quarantine: data/quarantine/{item.task_id}/{item.filename}\n"
            f"Size: {item.file_size:,} bytes\n"
            f"MIME: {item.content_type}\n"
            f"SHA-256: {item.sha256_hash}\n"
            f"Status: Quarantined safely (not executed)."
        )


def register_research_tools(registry: ToolRegistry, service: BrowserResearchService) -> list[str]:
    """Register all 4 Phase 9 research tools into central ToolRegistry."""
    tools = [
        WebSearchTool(service),
        WebFetchTool(service),
        WebExtractCitationsTool(service),
        WebDownloadQuarantineTool(service),
    ]

    names: list[str] = []
    for tool in tools:
        registry.register(tool)
        names.append(tool.name)

    return names
