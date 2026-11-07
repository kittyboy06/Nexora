"""Abstract Base Class for Web Fetch Engines."""

from abc import ABC, abstractmethod
from typing import Optional
from backend.app.research.models import FetchResult
from backend.app.research.policy import DomainPolicy


class FetchEngine(ABC):
    """Abstract interface for retrieving and extracting webpage content."""

    @abstractmethod
    async def fetch(
        self,
        url: str,
        policy: Optional[DomainPolicy] = None,
        take_screenshot: bool = False,
    ) -> FetchResult:
        """Fetch the given URL, extract structured text and metadata, and enforce security policies."""
        raise NotImplementedError
