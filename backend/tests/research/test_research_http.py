"""Unit tests for Search Providers and Fast HTTP Fetch Engine."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.app.mcp.vault import McpVaultService
from backend.app.research.engines.http import HttpFetchEngine, extract_clean_text_from_html
from backend.app.research.policy import DomainPolicy, SsrfSecurityError
from backend.app.research.search.duckduckgo import DuckDuckGoSearchProvider, _unwrap_ddg_url
from backend.app.research.search.factory import BraveSearchProvider, SearchProviderFactory


SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Nexora Architecture Overview</title>
    <script>console.log("malicious script");</script>
    <style>body { color: red; }</style>
</head>
<body>
    <header><nav><a href="/home">Home</a></nav></header>
    <main>
        <h1>Nexora System</h1>
        <p>Nexora is a multi-agent Windows automation and desktop orchestration framework.</p>
        <p>It provides structured tools, governance tiers, and isolated environments.</p>
        <a href="https://github.com/nexora/core">Project Repository</a>
    </main>
    <footer><p>&copy; 2026 Nexora Team</p></footer>
</body>
</html>
"""

SAMPLE_DDG_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div class="result">
        <h2 class="result__title">
            <a class="result__a" href="/l/?uddg=https%3A%2F%2Fpython.org%2Fdoc&rut=...">Python Documentation</a>
        </h2>
        <a class="result__snippet" href="...">Official Python documentation and tutorials.</a>
    </div>
    <div class="result">
        <h2 class="result__title">
            <a class="result__a" href="https://docs.python.org/3/">Python 3 Documentation</a>
        </h2>
        <a class="result__snippet" href="...">Standard library reference and tutorials.</a>
    </div>
</body>
</html>
"""


def test_extract_clean_text_from_html():
    """Verify HTML cleaning strips noise and preserves main content."""
    title, text, links = extract_clean_text_from_html(SAMPLE_HTML)
    assert title == "Nexora Architecture Overview"
    assert "console.log" not in text
    assert "color: red" not in text
    assert "Home" not in text
    assert "&copy; 2026" not in text
    assert "Nexora is a multi-agent Windows automation" in text
    assert "https://github.com/nexora/core" in links


def test_unwrap_ddg_url():
    """Verify DuckDuckGo redirect link unwrapping."""
    raw = "/l/?uddg=https%3A%2F%2Fexample.com%2Ftarget%3Fid%3D1&rut=xyz"
    assert _unwrap_ddg_url(raw) == "https://example.com/target?id=1"
    assert _unwrap_ddg_url("https://direct.com/page") == "https://direct.com/page"


@pytest.mark.asyncio
async def test_duckduckgo_search_provider_parsing():
    """Verify DuckDuckGo search parses results from HTML."""
    provider = DuckDuckGoSearchProvider()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = SAMPLE_DDG_HTML

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        results = await provider.search("python docs", max_results=2)

    assert len(results) == 2
    assert results[0].title == "Python Documentation"
    assert results[0].url == "https://python.org/doc"
    assert "Official Python documentation" in results[0].snippet
    assert results[0].rank == 1

    assert results[1].title == "Python 3 Documentation"
    assert results[1].url == "https://docs.python.org/3/"
    assert results[1].rank == 2


def test_search_factory_vault_integration(tmp_path):
    """Verify SearchProviderFactory uses BraveSearchProvider when key exists in vault."""
    vault = McpVaultService(base_dir=tmp_path)

    # Empty vault -> DuckDuckGo
    provider = SearchProviderFactory.create(vault)
    assert isinstance(provider, DuckDuckGoSearchProvider)

    # With Brave key -> BraveSearchProvider
    vault.set_secret("BRAVE_API_KEY", "BSA_mock_token_123")
    provider_brave = SearchProviderFactory.create(vault)
    assert isinstance(provider_brave, BraveSearchProvider)


@pytest.mark.asyncio
async def test_http_fetch_engine_success():
    """Verify HttpFetchEngine fetches, extracts content, and computes SHA-256."""
    engine = HttpFetchEngine()

    mock_stream = MagicMock()
    mock_stream.status_code = 200
    mock_stream.is_redirect = False

    async def mock_aiter():
        yield SAMPLE_HTML.encode("utf-8")

    mock_stream.aiter_bytes = mock_aiter

    class MockAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def stream(self, method, url):
            class StreamCtx:
                async def __aenter__(ctx):
                    return mock_stream
                async def __aexit__(ctx, *args):
                    pass
            return StreamCtx()

    with patch("backend.app.research.engines.http.validate_url_against_ssrf", return_value="https://example.com/doc"):
        with patch("httpx.AsyncClient", return_value=MockAsyncClient()):
            result = await engine.fetch("https://example.com/doc")

    assert result.title == "Nexora Architecture Overview"
    assert "multi-agent Windows automation" in result.content
    assert result.engine == "http"
    assert result.http_status == 200
    assert len(result.content_hash) == 64  # SHA-256


@pytest.mark.asyncio
async def test_http_fetch_engine_oversized_response():
    """Verify HttpFetchEngine aborts stream when response exceeds max_response_bytes."""
    engine = HttpFetchEngine()
    policy = DomainPolicy(max_response_bytes=100)

    mock_stream = MagicMock()
    mock_stream.status_code = 200
    mock_stream.is_redirect = False

    async def mock_aiter():
        yield b"X" * 150  # Exceeds 100 bytes limit

    mock_stream.aiter_bytes = mock_aiter

    class MockAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def stream(self, method, url):
            class StreamCtx:
                async def __aenter__(ctx):
                    return mock_stream
                async def __aexit__(ctx, *args):
                    pass
            return StreamCtx()

    with patch("backend.app.research.engines.http.validate_url_against_ssrf", return_value="https://example.com/big"):
        with patch("httpx.AsyncClient", return_value=MockAsyncClient()):
            with pytest.raises(SsrfSecurityError) as exc_info:
                await engine.fetch("https://example.com/big", policy=policy)
            assert "exceeded max limit" in str(exc_info.value)
