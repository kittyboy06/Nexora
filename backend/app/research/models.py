"""Domain Models for Phase 9: Browser and Internet Research Platform."""

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class SearchResult(BaseModel):
    """Normalized search result returned by any search provider."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(..., description="Webpage or article title")
    url: str = Field(..., description="Canonical target URL")
    snippet: str = Field(default="", description="Snippet or summary text")
    rank: int = Field(default=1, description="Result rank starting at 1")


class CitationItem(BaseModel):
    """Specific verbatim quote or extracted claim linked to its source."""

    model_config = ConfigDict(extra="ignore")

    quote: str = Field(..., description="Verbatim text extracted from document")
    source_url: str = Field(..., description="Source URL where quote appears")
    char_offset: int = Field(default=0, description="Character offset in source document")


class FetchResult(BaseModel):
    """Extracted text and metadata from a retrieved webpage."""

    model_config = ConfigDict(extra="ignore")

    url: str = Field(..., description="Original or final canonical URL")
    title: str = Field(default="", description="Document title")
    content: str = Field(default="", description="Cleaned readable text content")
    citations: list[CitationItem] = Field(default_factory=list, description="Extracted citations or key quotes")
    content_hash: str = Field(..., description="Deterministic SHA-256 hash of extracted content")
    http_status: int = Field(default=200, description="HTTP response status code")
    engine: str = Field(default="http", description="Engine used: 'http' or 'playwright'")
    screenshot_path: Optional[str] = Field(default=None, description="Relative path to screenshot if captured")


class ResearchEvidence(BaseModel):
    """Immutable audit evidence artifact persisted per task for research provenance."""

    model_config = ConfigDict(extra="ignore")

    evidence_id: str = Field(..., description="Unique ID for this evidence record")
    task_id: str = Field(..., description="Associated agent task ID")
    url: str = Field(..., description="Source webpage URL")
    title: str = Field(default="", description="Source page title")
    timestamp: str = Field(..., description="ISO 8601 access timestamp")
    content_snippet: str = Field(..., description="Bounded preview snippet of the fetched content")
    content_hash: str = Field(..., description="SHA-256 hash of full extracted text")
    citations: list[CitationItem] = Field(default_factory=list, description="Extracted citations")
    engine: str = Field(default="http", description="Engine used ('http' or 'playwright')")
    screenshot_path: Optional[str] = Field(default=None, description="Path to screenshot evidence if captured")


class QuarantineItem(BaseModel):
    """Metadata for an external file downloaded into task-specific quarantine."""

    model_config = ConfigDict(extra="ignore")

    task_id: str = Field(..., description="Task that requested the download")
    filename: str = Field(..., description="Sanitized filename stored in quarantine")
    original_url: str = Field(..., description="Remote source URL")
    file_size: int = Field(..., description="Size in bytes")
    content_type: str = Field(..., description="MIME content type reported by server")
    sha256_hash: str = Field(..., description="SHA-256 checksum of downloaded payload")
    quarantine_path: str = Field(..., description="Local path to file within data/quarantine/<task_id>/")
    downloaded_at: str = Field(..., description="ISO 8601 download timestamp")


class ResearchSearchRequest(BaseModel):
    """Request payload for manual search endpoint."""

    query: str = Field(..., min_length=1, max_length=500, description="Search query string")
    max_results: int = Field(default=5, ge=1, le=20, description="Maximum number of results to return")


class ResearchFetchRequest(BaseModel):
    """Request payload for manual webpage fetch endpoint."""

    url: str = Field(..., min_length=1, description="Target webpage URL")
    render_js: bool = Field(default=False, description="Whether to execute JavaScript with headless Playwright")
    take_screenshot: bool = Field(default=False, description="Whether to capture a visual screenshot")


class ResearchCitationsRequest(BaseModel):
    """Request payload for extracting targeted citations from a webpage."""

    url: str = Field(..., min_length=1, description="Target webpage URL")
    focus_query: str = Field(..., min_length=1, description="Topic or query to find relevant citations for")


class ResearchDownloadRequest(BaseModel):
    """Request payload for downloading a remote file to quarantine."""

    url: str = Field(..., min_length=1, description="Target file URL to download")
    filename: Optional[str] = Field(default=None, description="Optional custom filename override")
