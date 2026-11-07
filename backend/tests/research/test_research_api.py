"""Integration tests for Research API Endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import pytest_asyncio
import httpx

from backend.app.main import create_app
from backend.app.research.evidence import ResearchEvidenceStore
from backend.app.research.models import FetchResult, QuarantineItem, SearchResult
from backend.app.research.quarantine import QuarantineManager
from backend.app.research.service import BrowserResearchService


@pytest_asyncio.fixture
async def research_api_client(tmp_path):
    """Set up test client with isolated Research services."""
    evidence_store = ResearchEvidenceStore(base_dir=tmp_path / "evidence")
    quarantine_mgr = QuarantineManager(base_dir=tmp_path / "quarantine")

    mock_service = MagicMock(spec=BrowserResearchService)
    mock_service.evidence_store = evidence_store
    mock_service.quarantine_mgr = quarantine_mgr

    mock_service.search = AsyncMock(
        return_value=[
            SearchResult(title="Pytest Docs", url="https://docs.pytest.org", snippet="Testing framework", rank=1)
        ]
    )
    mock_service.fetch_page = AsyncMock(
        return_value=FetchResult(
            url="https://example.com/info",
            title="Info Page",
            content="Informational content regarding system capabilities.",
            content_hash="hash987654321",
            engine="http",
        )
    )

    app = create_app()
    app.state.research_service = mock_service
    app.state.research_evidence_store = evidence_store
    app.state.quarantine_manager = quarantine_mgr

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client, mock_service, evidence_store, quarantine_mgr


@pytest.mark.asyncio
async def test_api_search_endpoint(research_api_client):
    """Verify POST /api/research/search returns search results."""
    client, mock_service, _, _ = research_api_client

    resp = await client.post("/api/research/search", json={"query": "pytest", "max_results": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Pytest Docs"
    assert data[0]["url"] == "https://docs.pytest.org"


@pytest.mark.asyncio
async def test_api_fetch_endpoint_success(research_api_client):
    """Verify POST /api/research/fetch returns extracted webpage content."""
    client, mock_service, _, _ = research_api_client

    resp = await client.post("/api/research/fetch", json={"url": "https://example.com/info"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Info Page"
    assert "Informational content" in data["content"]
    assert data["content_hash"] == "hash987654321"


@pytest.mark.asyncio
async def test_api_fetch_endpoint_ssrf_blocked(tmp_path):
    """Verify POST /api/research/fetch returns 403 when Anti-SSRF triggers."""
    app = create_app()
    # Real service to trigger real policy check
    real_service = BrowserResearchService(
        evidence_store=ResearchEvidenceStore(tmp_path / "ev"),
        quarantine_mgr=QuarantineManager(tmp_path / "quar"),
    )
    app.state.research_service = real_service

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        resp = await client.post("/api/research/fetch", json={"url": "http://127.0.0.1:8000/secret"})
        assert resp.status_code == 403
        data = resp.json()
        error_msg = data.get("detail") or data.get("error", {}).get("message", "")
        assert "Anti-SSRF" in error_msg or "loopback" in error_msg


@pytest.mark.asyncio
async def test_api_evidence_and_quarantine_crud(research_api_client):
    """Verify listing and detail retrieval of evidence and quarantine files."""
    client, _, evidence_store, quarantine_mgr = research_api_client

    # Seed an evidence item directly in store
    ev = evidence_store.record_evidence(
        "task_int_1",
        FetchResult(
            url="https://example.com/api-doc",
            title="API Doc",
            content="Full API specifications.",
            content_hash="h12345",
        ),
    )

    # 1. List evidence
    list_resp = await client.get("/api/research/evidence/task_int_1")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1
    assert list_resp.json()[0]["evidence_id"] == ev.evidence_id

    # 2. Get evidence detail
    detail_resp = await client.get(f"/api/research/evidence/task_int_1/{ev.evidence_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["title"] == "API Doc"

    # 404 for unknown evidence
    notFound_resp = await client.get("/api/research/evidence/task_int_1/ev_unknown")
    assert notFound_resp.status_code == 404

    # 3. Seed quarantine item directly
    quarantine_mgr._save_manifest(
        "task_int_1",
        [
            QuarantineItem(
                task_id="task_int_1",
                filename="archive.zip",
                original_url="https://example.com/archive.zip",
                file_size=1024,
                content_type="application/zip",
                sha256_hash="hash_zip",
                quarantine_path="data/quarantine/task_int_1/archive.zip",
                downloaded_at="2026-11-07T12:00:00Z",
            ).model_dump()
        ],
    )

    # 4. List quarantine
    quar_list = await client.get("/api/research/quarantine/task_int_1")
    assert quar_list.status_code == 200
    assert len(quar_list.json()) == 1
    assert quar_list.json()[0]["filename"] == "archive.zip"

    # 5. Delete quarantine
    del_resp = await client.delete("/api/research/quarantine/task_int_1/archive.zip")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"

    # List again -> empty
    quar_list_after = await client.get("/api/research/quarantine/task_int_1")
    assert len(quar_list_after.json()) == 0
