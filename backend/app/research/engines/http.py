"""Fast Asynchronous HTTP Fetch Engine with Pre-Flight Anti-SSRF."""

import hashlib
import logging
import re
from typing import Optional
from bs4 import BeautifulSoup
import httpx

from backend.app.research.engines.base import FetchEngine
from backend.app.research.models import CitationItem, FetchResult
from backend.app.research.policy import DomainPolicy, SsrfSecurityError, validate_url_against_ssrf

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

DISCARD_TAGS = {"script", "style", "noscript", "svg", "header", "footer", "nav", "aside", "form"}


def extract_clean_text_from_html(html: str) -> tuple[str, str, list[str]]:
    """
    Parse HTML and extract page title, cleaned article/body text, and outbound links.
    Returns: (title, cleaned_text, links)
    """
    if not html:
        return "", "", []

    soup = BeautifulSoup(html, "html.parser")

    # Extract title
    title_elem = soup.find("title")
    title = title_elem.get_text(strip=True) if title_elem else ""

    # Discard non-content elements
    for tag in soup.find_all(DISCARD_TAGS):
        tag.decompose()

    # Collect outbound links
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("http://", "https://")) and href not in links:
            links.append(href)
        if len(links) >= 20:
            break

    # Extract main text
    raw_text = soup.get_text(separator="\n", strip=True)
    # Compress repetitive blank lines
    cleaned_text = re.sub(r"\n{3,}", "\n\n", raw_text)

    return title, cleaned_text, links


class HttpFetchEngine(FetchEngine):
    """Retrieves web pages over HTTP with Anti-SSRF validation and clean text extraction."""

    async def fetch(
        self,
        url: str,
        policy: Optional[DomainPolicy] = None,
        take_screenshot: bool = False,
    ) -> FetchResult:
        pol = policy or DomainPolicy()

        # Step 1: Pre-flight Anti-SSRF check on initial URL
        validated_url = validate_url_against_ssrf(url, pol)

        current_url = validated_url
        redirect_count = 0
        response_bytes = bytearray()
        status_code = 200

        # Custom redirect loop ensuring every hop is re-validated against Anti-SSRF
        async with httpx.AsyncClient(
            timeout=pol.timeout_seconds,
            follow_redirects=False,
            headers=DEFAULT_HEADERS,
        ) as client:
            while True:
                # Validate current hop against SSRF before connecting
                validate_url_against_ssrf(current_url, pol)

                async with client.stream("GET", current_url) as resp:
                    status_code = resp.status_code

                    # Check for redirect
                    if resp.is_redirect:
                        redirect_count += 1
                        if redirect_count > pol.max_redirects:
                            raise SsrfSecurityError(
                                f"Too many redirects ({redirect_count} > {pol.max_redirects}) for URL '{url}'."
                            )

                        location = resp.headers.get("location")
                        if not location:
                            raise SsrfSecurityError("Redirect encountered without Location header.")

                        # Resolve relative redirect URLs
                        current_url = str(httpx.URL(current_url).join(location))
                        continue

                    # Read streamed chunks up to max_response_bytes
                    async for chunk in resp.aiter_bytes():
                        response_bytes.extend(chunk)
                        if len(response_bytes) > pol.max_response_bytes:
                            raise SsrfSecurityError(
                                f"Response size exceeded max limit ({len(response_bytes)} > {pol.max_response_bytes} bytes)."
                            )
                    break

        encoding = "utf-8"
        try:
            html_text = response_bytes.decode(encoding, errors="replace")
        except Exception:
            html_text = response_bytes.decode("latin-1", errors="replace")

        title, content, _ = extract_clean_text_from_html(html_text)
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        # Build initial citation summary from top sentences
        sentences = [s.strip() for s in re.split(r"[.!?]\s+", content) if len(s.strip()) > 30]
        citations = [
            CitationItem(quote=s, source_url=current_url, char_offset=content.find(s))
            for s in sentences[:3]
        ]

        return FetchResult(
            url=current_url,
            title=title or current_url,
            content=content,
            citations=citations,
            content_hash=content_hash,
            http_status=status_code,
            engine="http",
            screenshot_path=None,
        )
