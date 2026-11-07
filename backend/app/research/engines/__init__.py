"""Webpage fetch engines for Phase 9."""

from backend.app.research.engines.base import FetchEngine
from backend.app.research.engines.browser import PlaywrightBrowserEngine
from backend.app.research.engines.http import HttpFetchEngine, extract_clean_text_from_html

__all__ = [
    "FetchEngine",
    "HttpFetchEngine",
    "PlaywrightBrowserEngine",
    "extract_clean_text_from_html",
]
