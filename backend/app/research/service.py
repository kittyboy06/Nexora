"""Central Orchestrator for Phase 9: Browser and Internet Research Service."""

import logging
import re
from pathlib import Path
from typing import Optional

from backend.app.mcp.vault import McpVaultService
from backend.app.research.engines.base import FetchEngine
from backend.app.research.engines.browser import PlaywrightBrowserEngine
from backend.app.research.engines.http import HttpFetchEngine
from backend.app.research.evidence import ResearchEvidenceStore
from backend.app.research.models import CitationItem, FetchResult, QuarantineItem, SearchResult
from backend.app.research.policy import DomainPolicy
from backend.app.research.quarantine import QuarantineManager
from backend.app.research.search.base import SearchProvider
from backend.app.research.search.factory import SearchProviderFactory

logger = logging.getLogger(__name__)


class BrowserResearchService:
    """Coordinates search providers, dual fetch engines, evidence storage, and quarantine downloads."""

    def __init__(
        self,
        evidence_store: Optional[ResearchEvidenceStore] = None,
        quarantine_mgr: Optional[QuarantineManager] = None,
        vault: Optional[McpVaultService] = None,
        http_engine: Optional[FetchEngine] = None,
        browser_engine: Optional[FetchEngine] = None,
        search_provider: Optional[SearchProvider] = None,
    ):
        self.evidence_store = evidence_store or ResearchEvidenceStore()
        self.quarantine_mgr = quarantine_mgr or QuarantineManager()
        self.vault = vault
        self.http_engine = http_engine or HttpFetchEngine()

        # Initialize browser engine with screenshots directory under data/research/screenshots/
        screenshot_dir = self.evidence_store.base_dir / "screenshots"
        self.browser_engine = browser_engine or (
            PlaywrightBrowserEngine(screenshot_dir=screenshot_dir)
            if PlaywrightBrowserEngine.is_available()
            else None
        )

        self.search_provider = search_provider or SearchProviderFactory.create(self.vault)

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        """Execute a web search query via the configured search provider."""
        return await self.search_provider.search(query, max_results=max_results)

    async def fetch_page(
        self,
        url: str,
        task_id: Optional[str] = None,
        render_js: bool = False,
        take_screenshot: bool = False,
        policy: Optional[DomainPolicy] = None,
    ) -> FetchResult:
        """
        Fetch a webpage, extract text, compute content hash, and record evidence.
        Uses Playwright if render_js or take_screenshot is True; otherwise uses fast HttpFetchEngine.
        """
        engine: FetchEngine
        if (render_js or take_screenshot) and self.browser_engine is not None:
            engine = self.browser_engine
        else:
            engine = self.http_engine

        result = await engine.fetch(url, policy=policy, take_screenshot=take_screenshot)

        # If associated with an active task, record immutable evidence artifact
        if task_id:
            self.evidence_store.record_evidence(task_id, result)

        return result

    async def extract_citations(
        self,
        url: str,
        focus_query: str,
        task_id: Optional[str] = None,
        policy: Optional[DomainPolicy] = None,
    ) -> list[CitationItem]:
        """Fetch page and extract targeted verbatim sentences relevant to the focus query."""
        fetch_res = await self.fetch_page(url, task_id=task_id, render_js=False, policy=policy)
        content = fetch_res.content

        if not focus_query or not focus_query.strip():
            return fetch_res.citations

        # Split into sentences and find those matching words in focus_query
        keywords = set(re.findall(r"\w+", focus_query.lower()))
        sentences = [s.strip() for s in re.split(r"[.!?]\n*|\n+", content) if len(s.strip()) > 20]

        scored_citations: list[tuple[int, CitationItem]] = []
        for s in sentences:
            sentence_words = set(re.findall(r"\w+", s.lower()))
            common = len(keywords.intersection(sentence_words))
            if common > 0:
                offset = content.find(s)
                item = CitationItem(quote=s, source_url=fetch_res.url, char_offset=max(0, offset))
                scored_citations.append((common, item))

        scored_citations.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored_citations[:5]]

    async def download_file(
        self,
        url: str,
        task_id: str,
        filename: Optional[str] = None,
        policy: Optional[DomainPolicy] = None,
    ) -> QuarantineItem:
        """Download remote asset into isolated task quarantine directory."""
        return await self.quarantine_mgr.download_file(
            task_id=task_id,
            url=url,
            filename=filename,
            policy=policy,
        )
