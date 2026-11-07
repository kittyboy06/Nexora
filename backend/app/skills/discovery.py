"""Asynchronous Read-Only GitHub Discovery Service with Rate-Limit Tracking."""

from datetime import datetime, timezone
import json
import logging
from typing import Optional
import httpx

from backend.app.core.config import get_settings
from backend.app.skills.models import (
    GitHubRateLimitStatus,
    SkillDiscoveryCandidate,
    SkillManifest,
)

logger = logging.getLogger("nexora.skills.discovery")


class GitHubDiscoveryError(Exception):
    """Base exception for GitHub discovery failures."""
    pass


class RateLimitExceededError(GitHubDiscoveryError):
    """Raised when GitHub API rate quota is exhausted."""
    def __init__(self, reset_at: Optional[str] = None):
        super().__init__(f"GitHub API rate limit exceeded. Resets at {reset_at or 'unknown'}.")
        self.reset_at = reset_at


class GitHubResourceNotFoundError(GitHubDiscoveryError):
    """Raised when repository or file is not found."""
    pass


class GitHubDiscoveryService:
    """Read-only client for discovering community skills and manifests via GitHub REST API."""

    BASE_URL = "https://api.github.com"
    RAW_BASE_URL = "https://raw.githubusercontent.com"

    def __init__(
        self,
        token: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        settings = get_settings()
        self.token = token if token is not None else settings.GITHUB_TOKEN
        self._external_client = client
        self.rate_limit_status = GitHubRateLimitStatus(
            is_authenticated=bool(self.token),
        )

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Nexora-Agent-Discovery/1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _update_rate_limits(self, headers: httpx.Headers) -> None:
        """Parse GitHub rate-limit headers to keep local status updated."""
        limit_hdr = headers.get("x-ratelimit-limit")
        rem_hdr = headers.get("x-ratelimit-remaining")
        reset_hdr = headers.get("x-ratelimit-reset")

        if limit_hdr and limit_hdr.isdigit():
            self.rate_limit_status.limit = int(limit_hdr)
        if rem_hdr and rem_hdr.isdigit():
            self.rate_limit_status.remaining = int(rem_hdr)
        if reset_hdr and reset_hdr.isdigit():
            try:
                dt = datetime.fromtimestamp(int(reset_hdr), tz=timezone.utc)
                self.rate_limit_status.reset_at = dt.isoformat()
            except Exception:
                pass

    async def _request(
        self,
        method: str,
        url: str,
        params: Optional[dict] = None,
    ) -> httpx.Response:
        """Execute HTTP request with rate-limit tracking and error classification."""
        headers = self._get_headers()

        if self._external_client:
            resp = await self._external_client.request(
                method, url, headers=headers, params=params, timeout=10.0
            )
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.request(
                    method, url, headers=headers, params=params
                )

        self._update_rate_limits(resp.headers)

        if resp.status_code in (403, 429) and self.rate_limit_status.remaining == 0:
            raise RateLimitExceededError(self.rate_limit_status.reset_at)

        if resp.status_code == 404:
            raise GitHubResourceNotFoundError(f"Resource not found at {url}")

        if resp.is_error:
            raise GitHubDiscoveryError(
                f"GitHub API error {resp.status_code}: {resp.text[:200]}"
            )

        return resp

    async def get_rate_limit(self) -> GitHubRateLimitStatus:
        """Fetch current rate limit status from GitHub."""
        try:
            resp = await self._request("GET", f"{self.BASE_URL}/rate_limit")
            data = resp.json()
            core = data.get("resources", {}).get("core", {})
            self.rate_limit_status.limit = core.get("limit", self.rate_limit_status.limit)
            self.rate_limit_status.remaining = core.get("remaining", self.rate_limit_status.remaining)
            if "reset" in core:
                dt = datetime.fromtimestamp(core["reset"], tz=timezone.utc)
                self.rate_limit_status.reset_at = dt.isoformat()
        except Exception as e:
            logger.warning("Could not refresh GitHub rate limits: %s", e)

        return self.rate_limit_status

    async def search_repositories(
        self,
        query: str,
        page: int = 1,
        per_page: int = 10,
    ) -> list[SkillDiscoveryCandidate]:
        """Search GitHub for repositories tagged or describing agent skills."""
        clean_q = query.strip()
        if clean_q:
            q = f"{clean_q} skill"
        else:
            q = "topic:nexora-skill"

        url = f"{self.BASE_URL}/search/repositories"
        params = {
            "q": q,
            "sort": "stars",
            "order": "desc",
            "page": page,
            "per_page": min(per_page, 30),
        }

        resp = await self._request("GET", url, params=params)
        data = resp.json()
        items = data.get("items", [])

        candidates: list[SkillDiscoveryCandidate] = []
        for item in items:
            owner = item.get("owner", {}).get("login", "")
            repo = item.get("name", "")
            candidates.append(
                SkillDiscoveryCandidate(
                    owner=owner,
                    repo=repo,
                    description=item.get("description"),
                    stars=item.get("stargazers_count", 0),
                    html_url=item.get("html_url", ""),
                    default_branch=item.get("default_branch", "main"),
                )
            )

        return candidates

    async def fetch_skill_preview(
        self,
        owner: str,
        repo: str,
        branch: str = "main",
        path: Optional[str] = None,
    ) -> SkillDiscoveryCandidate:
        """Read-only preview fetcher for manifest.json and SKILL.md in a repository."""
        # Clean relative path
        prefix = f"{path.strip('/')}/" if path and path.strip("/") else ""

        manifest_url = f"{self.RAW_BASE_URL}/{owner}/{repo}/{branch}/{prefix}manifest.json"
        skill_md_url = f"{self.RAW_BASE_URL}/{owner}/{repo}/{branch}/{prefix}SKILL.md"

        has_manifest = False
        has_skill_md = False
        manifest_preview: Optional[SkillManifest] = None
        skill_md_preview: Optional[str] = None

        # Fetch manifest.json
        try:
            m_resp = await self._request("GET", manifest_url)
            if m_resp.status_code == 200:
                raw_json = json.loads(m_resp.text)
                manifest_preview = SkillManifest(**raw_json)
                has_manifest = True
        except Exception as e:
            logger.info("Could not fetch manifest at %s: %s", manifest_url, e)

        # Fetch SKILL.md
        try:
            s_resp = await self._request("GET", skill_md_url)
            if s_resp.status_code == 200:
                skill_md_preview = s_resp.text
                has_skill_md = True
        except Exception as e:
            logger.info("Could not fetch SKILL.md at %s: %s", skill_md_url, e)

        return SkillDiscoveryCandidate(
            owner=owner,
            repo=repo,
            html_url=f"https://github.com/{owner}/{repo}",
            default_branch=branch,
            has_manifest=has_manifest,
            has_skill_md=has_skill_md,
            manifest_preview=manifest_preview,
            skill_md_preview=skill_md_preview,
        )
