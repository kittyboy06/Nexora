"""FastAPI Router for Phase 9: Browser and Internet Research Platform."""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.app.research.models import (
    FetchResult,
    QuarantineItem,
    ResearchEvidence,
    ResearchFetchRequest,
    ResearchSearchRequest,
    SearchResult,
)
from backend.app.research.policy import DomainPolicyError, SsrfSecurityError
from backend.app.research.service import BrowserResearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["Research & Web"])


def get_research_service(request: Request) -> BrowserResearchService:
    """Dependency provider for BrowserResearchService from application state."""
    service = getattr(request.app.state, "research_service", None)
    if not service:
        evidence_store = getattr(request.app.state, "research_evidence_store", None)
        quarantine_mgr = getattr(request.app.state, "quarantine_manager", None)
        vault = getattr(request.app.state, "mcp_vault", None)
        service = BrowserResearchService(
            evidence_store=evidence_store,
            quarantine_mgr=quarantine_mgr,
            vault=vault,
        )
        request.app.state.research_service = service
    return service


@router.post("/search", response_model=list[SearchResult])
async def search_web(
    request: ResearchSearchRequest,
    service: BrowserResearchService = Depends(get_research_service),
) -> list[SearchResult]:
    """Execute a public web search query via configured search provider."""
    try:
        return await service.search(query=request.query, max_results=request.max_results)
    except Exception as e:
        logger.error("Web search failed for query '%s': %s", request.query, e)
        raise HTTPException(status_code=500, detail=f"Web search failed: {e}")


@router.post("/fetch", response_model=FetchResult)
async def fetch_webpage(
    request: ResearchFetchRequest,
    service: BrowserResearchService = Depends(get_research_service),
) -> FetchResult:
    """Fetch and extract readable text from a target webpage with Anti-SSRF protection."""
    try:
        return await service.fetch_page(
            url=request.url,
            render_js=request.render_js,
            take_screenshot=request.take_screenshot,
        )
    except (SsrfSecurityError, DomainPolicyError) as e:
        logger.warning("SSRF / Domain policy blocked fetch for '%s': %s", request.url, e)
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error("Web fetch failed for '%s': %s", request.url, e)
        raise HTTPException(status_code=502, detail=f"Failed to fetch webpage: {e}")


@router.get("/evidence/{task_id}", response_model=list[ResearchEvidence])
async def list_task_evidence(
    task_id: str,
    service: BrowserResearchService = Depends(get_research_service),
) -> list[ResearchEvidence]:
    """Retrieve all immutable research evidence records collected during task execution."""
    return service.evidence_store.list_evidence(task_id)


@router.get("/evidence/{task_id}/{evidence_id}", response_model=ResearchEvidence)
async def get_evidence_detail(
    task_id: str,
    evidence_id: str,
    service: BrowserResearchService = Depends(get_research_service),
) -> ResearchEvidence:
    """Retrieve details for a specific research evidence artifact."""
    evidence = service.evidence_store.get_evidence(task_id, evidence_id)
    if not evidence:
        raise HTTPException(status_code=404, detail=f"Evidence artifact '{evidence_id}' not found.")
    return evidence


@router.get("/quarantine/{task_id}", response_model=list[QuarantineItem])
async def list_quarantined_downloads(
    task_id: str,
    service: BrowserResearchService = Depends(get_research_service),
) -> list[QuarantineItem]:
    """List all external files downloaded into task quarantine with verification metadata."""
    return service.quarantine_mgr.list_quarantined_files(task_id)


@router.delete("/quarantine/{task_id}/{filename}")
async def delete_quarantined_download(
    task_id: str,
    filename: str,
    service: BrowserResearchService = Depends(get_research_service),
) -> dict:
    """Delete a quarantined file and purge its entry from the task manifest."""
    deleted = service.quarantine_mgr.delete_quarantined_file(task_id, filename)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Quarantined file '{filename}' not found.")
    return {"status": "deleted", "task_id": task_id, "filename": filename}
