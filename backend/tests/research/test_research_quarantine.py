"""Unit tests for Research Evidence Store and Quarantine Manager."""

from unittest.mock import MagicMock, patch
import pytest

from backend.app.research.evidence import ResearchEvidenceStore
from backend.app.research.models import FetchResult
from backend.app.research.policy import DomainPolicy, SsrfSecurityError
from backend.app.research.quarantine import QuarantineManager


def test_evidence_store_lifecycle(tmp_path):
    """Verify recording, listing, and retrieving research evidence artifacts."""
    store = ResearchEvidenceStore(base_dir=tmp_path / "evidence")

    fetch_res1 = FetchResult(
        url="https://example.com/doc1",
        title="Doc 1",
        content="First document content for task analysis.",
        content_hash="hash_1111",
        engine="http",
    )
    fetch_res2 = FetchResult(
        url="https://example.com/doc2",
        title="Doc 2",
        content="Second document content with dynamic results.",
        content_hash="hash_2222",
        engine="playwright",
    )

    ev1 = store.record_evidence("task_abc", fetch_res1)
    ev2 = store.record_evidence("task_abc", fetch_res2)

    assert ev1.task_id == "task_abc"
    assert ev1.url == "https://example.com/doc1"
    assert ev2.engine == "playwright"

    # List evidence
    all_ev = store.list_evidence("task_abc")
    assert len(all_ev) == 2
    assert {e.evidence_id for e in all_ev} == {ev1.evidence_id, ev2.evidence_id}

    # Retrieve specific item
    retrieved = store.get_evidence("task_abc", ev1.evidence_id)
    assert retrieved is not None
    assert retrieved.title == "Doc 1"
    assert retrieved.content_hash == "hash_1111"


@pytest.mark.asyncio
async def test_quarantine_download_success(tmp_path):
    """Verify QuarantineManager streams download, computes SHA-256, and updates manifest."""
    qm = QuarantineManager(base_dir=tmp_path / "quarantine")
    mock_payload = b"Hello, this is a simulated downloaded PDF document."

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_redirect = False
    mock_resp.headers = {"content-type": "application/pdf"}

    async def mock_aiter():
        yield mock_payload

    mock_resp.aiter_bytes = mock_aiter

    class MockAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def stream(self, method, url):
            class StreamCtx:
                async def __aenter__(ctx):
                    return mock_resp
                async def __aexit__(ctx, *args):
                    pass
            return StreamCtx()

    with patch("backend.app.research.quarantine.validate_url_against_ssrf", return_value="https://example.com/report.pdf"):
        with patch("httpx.AsyncClient", return_value=MockAsyncClient()):
            item = await qm.download_file("task_999", "https://example.com/report.pdf", filename="../traversal/report.pdf")

    assert item.task_id == "task_999"
    assert item.filename == "report.pdf"  # Traversal sanitized
    assert item.file_size == len(mock_payload)
    assert item.content_type == "application/pdf"
    assert len(item.sha256_hash) == 64

    # Verify manifest tracking
    listed = qm.list_quarantined_files("task_999")
    assert len(listed) == 1
    assert listed[0].filename == "report.pdf"

    # Verify delete
    assert qm.delete_quarantined_file("task_999", "report.pdf") is True
    assert len(qm.list_quarantined_files("task_999")) == 0


@pytest.mark.asyncio
async def test_quarantine_download_ssrf_blocking(tmp_path):
    """Verify QuarantineManager blocks private IP targets before downloading."""
    qm = QuarantineManager(base_dir=tmp_path / "quarantine")

    with pytest.raises(SsrfSecurityError):
        await qm.download_file("task_999", "http://127.0.0.1:5000/firmware.bin")


@pytest.mark.asyncio
async def test_quarantine_revalidates_each_redirect(tmp_path):
    """A public URL must not be able to redirect a download into a private network."""
    qm = QuarantineManager(base_dir=tmp_path / "quarantine")

    redirect = MagicMock()
    redirect.status_code = 302
    redirect.is_redirect = True
    redirect.headers = {"location": "http://127.0.0.1/private-file"}

    class MockAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def stream(self, method, url):
            class StreamCtx:
                async def __aenter__(ctx):
                    return redirect

                async def __aexit__(ctx, *args):
                    pass
            return StreamCtx()

    def validate(url, policy):
        if "127.0.0.1" in url:
            raise SsrfSecurityError("private redirect blocked")
        return url

    with patch("backend.app.research.quarantine.validate_url_against_ssrf", side_effect=validate):
        with patch("httpx.AsyncClient", return_value=MockAsyncClient()):
            with pytest.raises(SsrfSecurityError, match="private redirect blocked"):
                await qm.download_file("task_999", "https://example.com/file.bin")


@pytest.mark.asyncio
async def test_quarantine_download_oversized_cleanup(tmp_path):
    """Verify partial file is deleted if download exceeds max size."""
    qm = QuarantineManager(base_dir=tmp_path / "quarantine")
    policy = DomainPolicy(max_response_bytes=50)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_redirect = False
    mock_resp.headers = {"content-type": "application/octet-stream"}

    async def mock_aiter():
        yield b"A" * 100

    mock_resp.aiter_bytes = mock_aiter

    class MockAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def stream(self, method, url):
            class StreamCtx:
                async def __aenter__(ctx):
                    return mock_resp
                async def __aexit__(ctx, *args):
                    pass
            return StreamCtx()

    with patch("backend.app.research.quarantine.validate_url_against_ssrf", return_value="https://example.com/large.iso"):
        with patch("httpx.AsyncClient", return_value=MockAsyncClient()):
            with pytest.raises(SsrfSecurityError) as exc_info:
                await qm.download_file("task_999", "https://example.com/large.iso", policy=policy)
            assert "exceeded maximum size" in str(exc_info.value)

    # Check partial file was removed
    files = list((tmp_path / "quarantine" / "task_999").glob("*"))
    # manifest.json might exist or empty directory, but no large.iso
    assert not any(f.name == "large.iso" for f in files)
