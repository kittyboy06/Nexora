"""Headless Playwright Browser Engine with Ephemeral Task Contexts and Route Filtering."""

import hashlib
import logging
import re
from pathlib import Path
from typing import Optional

from backend.app.research.engines.base import FetchEngine
from backend.app.research.engines.http import DEFAULT_HEADERS, extract_clean_text_from_html
from backend.app.research.models import CitationItem, FetchResult
from backend.app.research.policy import DomainPolicy, SsrfSecurityError, validate_url_against_ssrf

logger = logging.getLogger(__name__)

# Check Playwright availability
try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Route
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class PlaywrightBrowserEngine(FetchEngine):
    """Executes dynamic JavaScript-rendered webpage navigation and screenshots via headless Chromium."""

    def __init__(self, screenshot_dir: Optional[Path] = None):
        self.screenshot_dir = screenshot_dir
        if self.screenshot_dir:
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def is_available(cls) -> bool:
        """Returns True if playwright package is installed in runtime environment."""
        return PLAYWRIGHT_AVAILABLE

    async def fetch(
        self,
        url: str,
        policy: Optional[DomainPolicy] = None,
        take_screenshot: bool = False,
    ) -> FetchResult:
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "Playwright is not installed in runtime environment. Install via 'pip install playwright'."
            )

        pol = policy or DomainPolicy()
        validated_url = validate_url_against_ssrf(url, pol)

        browser: Optional[Browser] = None
        context: Optional[BrowserContext] = None
        page: Optional[Page] = None

        screenshot_path: Optional[str] = None

        async with async_playwright() as p:
            try:
                # Launch Chromium headless with security sandboxing
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-gpu",
                        "--disable-dev-shm-usage",
                        "--no-first-run",
                        "--no-default-browser-check",
                    ],
                )
            except Exception as e:
                logger.error("Failed to launch Playwright Chromium: %s", e)
                raise RuntimeError(
                    f"Playwright Chromium browser binary failed to launch: {e}. "
                    "Run 'playwright install chromium' to install browser binaries."
                ) from e

            try:
                # Ephemeral isolated context (no ambient cookies or session sharing)
                context = await browser.new_context(
                    user_agent=DEFAULT_HEADERS["User-Agent"],
                    java_script_enabled=True,
                    viewport={"width": 1280, "height": 800},
                )

                page = await context.new_page()

                # Intercept and validate every subresource request against Anti-SSRF
                async def handle_route(route: Route) -> None:
                    req_url = route.request.url
                    # Block images/fonts if screenshot not required to optimize speed
                    resource_type = route.request.resource_type
                    if not take_screenshot and resource_type in ("image", "media", "font"):
                        await route.abort("blockedbyclient")
                        return

                    try:
                        validate_url_against_ssrf(req_url, pol)
                        await route.continue_()
                    except Exception as err:
                        logger.warning("Playwright route blocked by Anti-SSRF policy: %s (%s)", req_url, err)
                        await route.abort("blockedbyclient")

                await page.route("**/*", handle_route)

                # Navigate with strict timeout
                timeout_ms = int(pol.timeout_seconds * 1000)
                resp = await page.goto(
                    validated_url,
                    timeout=timeout_ms,
                    wait_until="domcontentloaded",
                )

                http_status = resp.status if resp else 200
                html_text = await page.content()
                page_title = await page.title()

                title_clean, content, _ = extract_clean_text_from_html(html_text)
                title = page_title or title_clean or validated_url

                # Optional screenshot capture
                if take_screenshot and self.screenshot_dir:
                    shot_name = f"shot_{hashlib.md5(validated_url.encode()).hexdigest()[:10]}.png"
                    dest = self.screenshot_dir / shot_name
                    await page.screenshot(path=str(dest), full_page=False)
                    screenshot_path = str(dest)

                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

                # Build citations
                sentences = [s.strip() for s in re.split(r"[.!?]\s+", content) if len(s.strip()) > 30]
                citations = [
                    CitationItem(quote=s, source_url=validated_url, char_offset=content.find(s))
                    for s in sentences[:3]
                ]

                return FetchResult(
                    url=page.url or validated_url,
                    title=title,
                    content=content,
                    citations=citations,
                    content_hash=content_hash,
                    http_status=http_status,
                    engine="playwright",
                    screenshot_path=screenshot_path,
                )

            finally:
                # Guaranteed deterministic disposal of task browser context
                if page:
                    await page.close()
                if context:
                    await context.close()
                if browser:
                    await browser.close()
