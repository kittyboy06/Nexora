"""Unit tests for Playwright Headless Browser Engine."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.app.research.engines.browser import PlaywrightBrowserEngine
from backend.app.research.policy import SsrfSecurityError


def test_playwright_availability():
    """Verify Playwright availability detection."""
    assert PlaywrightBrowserEngine.is_available() is True


@pytest.mark.asyncio
async def test_playwright_engine_mock_fetch(tmp_path):
    """Verify PlaywrightBrowserEngine lifecycle: launch, page load, text extract, cleanup."""
    engine = PlaywrightBrowserEngine(screenshot_dir=tmp_path)

    mock_page = MagicMock()
    mock_page.url = "https://example.com/spa"
    mock_page.title = AsyncMock(return_value="SPA Dashboard")
    mock_page.content = AsyncMock(return_value="<html><head><title>SPA Dashboard</title></head><body><div id='app'>Dynamic React app content loaded here.</div></body></html>")
    mock_page.goto = AsyncMock(return_value=MagicMock(status=200))
    mock_page.route = AsyncMock()
    mock_page.screenshot = AsyncMock()
    mock_page.close = AsyncMock()

    mock_context = MagicMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.close = AsyncMock()

    mock_browser = MagicMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_browser.close = AsyncMock()

    mock_playwright = MagicMock()
    mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

    class MockAsyncPlaywrightCtx:
        async def __aenter__(self):
            return mock_playwright
        async def __aexit__(self, *args):
            pass

    with patch("backend.app.research.engines.browser.async_playwright", return_value=MockAsyncPlaywrightCtx()):
        with patch("backend.app.research.engines.browser.validate_url_against_ssrf", return_value="https://example.com/spa"):
            result = await engine.fetch("https://example.com/spa", take_screenshot=True)

    assert result.title == "SPA Dashboard"
    assert "Dynamic React app content" in result.content
    assert result.engine == "playwright"
    assert result.http_status == 200

    # Verify context and browser were deterministically closed
    mock_page.close.assert_awaited_once()
    mock_context.close.assert_awaited_once()
    mock_browser.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_playwright_engine_ssrf_pre_flight():
    """Verify Playwright engine aborts on private IP before launching browser."""
    engine = PlaywrightBrowserEngine()

    with pytest.raises(SsrfSecurityError):
        await engine.fetch("http://127.0.0.1:8080/admin")


@pytest.mark.asyncio
async def test_playwright_engine_missing_binary_error():
    """Verify descriptive error when Playwright Chromium binary is not installed."""
    engine = PlaywrightBrowserEngine()

    mock_playwright = MagicMock()
    mock_playwright.chromium.launch = AsyncMock(side_effect=Exception("Executable doesn't exist at C:\\..."))

    class MockAsyncPlaywrightCtx:
        async def __aenter__(self):
            return mock_playwright
        async def __aexit__(self, *args):
            pass

    with patch("backend.app.research.engines.browser.async_playwright", return_value=MockAsyncPlaywrightCtx()):
        with patch("backend.app.research.engines.browser.validate_url_against_ssrf", return_value="https://example.com"):
            with pytest.raises(RuntimeError) as exc_info:
                await engine.fetch("https://example.com")
            assert "Playwright Chromium browser binary failed to launch" in str(exc_info.value)
            assert "playwright install chromium" in str(exc_info.value)
