"""DuckDuckGo Search Provider (Zero-config, free web search)."""

import logging
from urllib.parse import parse_qs, unquote, urlparse
from bs4 import BeautifulSoup
import httpx

from backend.app.research.models import SearchResult
from backend.app.research.search.base import SearchProvider

logger = logging.getLogger(__name__)

DDG_HTML_URL = "https://html.duckduckgo.com/html/"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _unwrap_ddg_url(raw_href: str) -> str:
    """Extract actual destination URL from DuckDuckGo redirect link."""
    if not raw_href:
        return ""
    if "/l/?uddg=" in raw_href or "uddg=" in raw_href:
        parsed = urlparse(raw_href)
        qs = parse_qs(parsed.query)
        if "uddg" in qs and qs["uddg"]:
            return unquote(qs["uddg"][0])
    return raw_href


class DuckDuckGoSearchProvider(SearchProvider):
    """Fetches and parses public search results from DuckDuckGo HTML."""

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        if not query or not query.strip():
            return []

        clean_query = query.strip()
        results: list[SearchResult] = []

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.post(
                    DDG_HTML_URL,
                    data={"q": clean_query},
                    headers=DEFAULT_HEADERS,
                )

                if resp.status_code != 200:
                    logger.warning("DuckDuckGo HTML search returned HTTP %d", resp.status_code)
                    return []

                soup = BeautifulSoup(resp.text, "html.parser")
                result_elements = soup.select(".result")

                rank = 1
                for el in result_elements:
                    a_elem = el.select_one(".result__a")
                    if not a_elem:
                        continue

                    raw_href = a_elem.get("href", "")
                    clean_url = _unwrap_ddg_url(raw_href)
                    if not clean_url or not clean_url.startswith(("http://", "https://")):
                        continue

                    title = a_elem.get_text(strip=True)
                    snippet_elem = el.select_one(".result__snippet")
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

                    results.append(
                        SearchResult(
                            title=title or clean_url,
                            url=clean_url,
                            snippet=snippet,
                            rank=rank,
                        )
                    )
                    rank += 1
                    if len(results) >= max_results:
                        break

        except Exception as e:
            logger.warning("DuckDuckGo search error for query '%s': %s", clean_query, e)
            return []

        return results
