"""Unit tests for GitHubDiscoveryService with mocked HTTP transports."""

import json
import pytest
import httpx

from backend.app.skills.discovery import (
    GitHubDiscoveryService,
    RateLimitExceededError,
)


@pytest.mark.asyncio
async def test_rate_limit_header_tracking():
    """Verify rate-limit headers update internal state."""
    def handler(request: httpx.Request) -> httpx.Response:
        headers = {
            "x-ratelimit-limit": "60",
            "x-ratelimit-remaining": "42",
            "x-ratelimit-reset": "1770000000",
        }
        return httpx.Response(200, json={"resources": {"core": {"limit": 60, "remaining": 42}}}, headers=headers)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        service = GitHubDiscoveryService(client=client)
        status = await service.get_rate_limit()
        assert status.limit == 60
        assert status.remaining == 42
        assert status.reset_at is not None


@pytest.mark.asyncio
async def test_rate_limit_exhausted_raises():
    """Verify 403/429 with 0 remaining raises RateLimitExceededError."""
    def handler(request: httpx.Request) -> httpx.Response:
        headers = {
            "x-ratelimit-limit": "60",
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": "1770000000",
        }
        return httpx.Response(403, text="API rate limit exceeded", headers=headers)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        service = GitHubDiscoveryService(client=client)
        with pytest.raises(RateLimitExceededError):
            await service.search_repositories("test")


@pytest.mark.asyncio
async def test_search_repositories():
    """Verify search repository returns parsed candidate models."""
    sample_items = [
        {
            "name": "docker-workflow",
            "owner": {"login": "nexora-community"},
            "stargazers_count": 150,
            "description": "Production Docker workflows for agents.",
            "html_url": "https://github.com/nexora-community/docker-workflow",
            "default_branch": "main",
        },
        {
            "name": "k8s-operator",
            "owner": {"login": "cloud-devs"},
            "stargazers_count": 85,
            "description": "Kubernetes manifest guidance.",
            "html_url": "https://github.com/cloud-devs/k8s-operator",
            "default_branch": "master",
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": sample_items})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        service = GitHubDiscoveryService(client=client)
        candidates = await service.search_repositories("docker")
        assert len(candidates) == 2
        assert candidates[0].owner == "nexora-community"
        assert candidates[0].repo == "docker-workflow"
        assert candidates[0].stars == 150
        assert candidates[1].repo == "k8s-operator"


@pytest.mark.asyncio
async def test_fetch_skill_preview_success():
    """Verify reading raw manifest.json and SKILL.md populates candidate preview."""
    manifest_data = {
        "id": "flutter-pro",
        "name": "Flutter Pro",
        "version": "1.0.0",
        "description": "Flutter mobile architecture guidance",
        "tags": ["flutter", "dart", "mobile"],
    }
    skill_md = "# Flutter Best Practices\nUse Riverpod for state management."

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "manifest.json" in url_str:
            return httpx.Response(200, json=manifest_data)
        elif "SKILL.md" in url_str:
            return httpx.Response(200, text=skill_md)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        service = GitHubDiscoveryService(client=client)
        preview = await service.fetch_skill_preview("flutter-dev", "skills")
        assert preview.has_manifest is True
        assert preview.has_skill_md is True
        assert preview.manifest_preview is not None
        assert preview.manifest_preview.id == "flutter-pro"
        assert preview.skill_md_preview == skill_md


@pytest.mark.asyncio
async def test_fetch_skill_preview_missing_files():
    """Verify candidate preview handles 404s gracefully without raising."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Not Found")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        service = GitHubDiscoveryService(client=client)
        preview = await service.fetch_skill_preview("empty-repo", "no-skills")
        assert preview.has_manifest is False
        assert preview.has_skill_md is False
        assert preview.manifest_preview is None
        assert preview.skill_md_preview is None
