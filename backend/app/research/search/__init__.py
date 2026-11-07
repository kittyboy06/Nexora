"""Pluggable search providers for Phase 9."""

from backend.app.research.search.base import SearchProvider
from backend.app.research.search.duckduckgo import DuckDuckGoSearchProvider
from backend.app.research.search.factory import BraveSearchProvider, SearchProviderFactory

__all__ = [
    "SearchProvider",
    "DuckDuckGoSearchProvider",
    "BraveSearchProvider",
    "SearchProviderFactory",
]
