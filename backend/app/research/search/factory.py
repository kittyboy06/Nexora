"""Search Provider Factory with Vault Integration."""

import logging
from typing import Optional
import httpx

from backend.app.mcp.vault import McpVaultService
from backend.app.research.models import SearchResult
from backend.app.research.search.base import SearchProvider
from backend.app.research.search.duckduckgo import DuckDuckGoSearchProvider

logger = logging.getLogger(__name__)


class BraveSearchProvider(SearchProvider):
    """Executes search queries via the Brave Search REST API."""

    def __init__(self, api_key: str, timeout: float = 15.0):
        self.api_key = api_key
        self.timeout = timeout

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }
        params = {"q": query, "count": max_results}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=headers, params=params)
                if resp.status_code != 200:
                    logger.warning("Brave search API returned status %d", resp.status_code)
                    return []

                data = resp.json()
                web_results = data.get("web", {}).get("results", [])
                results: list[SearchResult] = []
                for i, item in enumerate(web_results[:max_results], start=1):
                    results.append(
                        SearchResult(
                            title=item.get("title", ""),
                            url=item.get("url", ""),
                            snippet=item.get("description", ""),
                            rank=i,
                        )
                    )
                return results
        except Exception as e:
            logger.warning("Brave search API failed: %s", e)
            return []


class SearchProviderFactory:
    """Factory creating appropriate SearchProvider based on encrypted vault configuration."""

    @staticmethod
    def create(vault: Optional[McpVaultService] = None) -> SearchProvider:
        if vault is not None:
            brave_key = vault.get_secret("BRAVE_API_KEY") or vault.get_secret("SEARCH_API_KEY")
            if brave_key:
                logger.info("Using Brave Search API from encrypted vault.")
                return BraveSearchProvider(api_key=brave_key)

        logger.info("Using default DuckDuckGo Search Provider (zero-key).")
        return DuckDuckGoSearchProvider()
