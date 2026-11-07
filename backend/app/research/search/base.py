"""Abstract Base Class for Search Providers."""

from abc import ABC, abstractmethod
from backend.app.research.models import SearchResult


class SearchProvider(ABC):
    """Abstract interface for web search providers."""

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        """Execute a search query and return normalized results ranked by relevance."""
        raise NotImplementedError
