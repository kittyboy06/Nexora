"""Integration tests for Skills API routes (/api/skills/*)."""

from pathlib import Path
import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport

from backend.app.main import create_app
from backend.app.skills.discovery import GitHubDiscoveryService
from backend.app.skills.manager import SkillManager
from backend.app.skills.models import SkillManifest


@pytest_asyncio.fixture
async def skills_api_client(tmp_path: Path):
    """Create test client with isolated SkillManager and mocked GitHubDiscoveryService."""
    skills_dir = tmp_path / "skills"
    manager = SkillManager(base_dir=skills_dir)

    # Seed one test skill
    manager.install_bundle(
        manifest=SkillManifest(
            id="pytest-pro",
            name="Pytest Pro",
            version="1.0.0",
            description="Best practices for pytest test suites",
            tags=["python", "testing"],
            target_roles=["coder"],
        ),
        instructions="# Pytest Rules\nAlways write isolated tests.",
    )

    # Mock handler for GitHub discovery
    def gh_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        headers = {
            "x-ratelimit-limit": "60",
            "x-ratelimit-remaining": "55",
            "x-ratelimit-reset": "1770000000",
        }
        if "/search/repositories" in url_str:
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "name": "mock-skill-repo",
                            "owner": {"login": "nexora-community"},
                            "stargazers_count": 99,
                            "description": "Mocked community skill",
                            "html_url": "https://github.com/nexora-community/mock-skill-repo",
                            "default_branch": "main",
                        }
                    ]
                },
                headers=headers,
            )
        elif "manifest.json" in url_str:
            return httpx.Response(
                200,
                json={
                    "id": "mock-skill",
                    "name": "Mock Skill",
                    "version": "1.0.0",
                    "description": "Remote mock skill guidance",
                    "tags": ["remote"],
                },
                headers=headers,
            )
        elif "SKILL.md" in url_str:
            return httpx.Response(200, text="# Mock Skill Guidance\nRemote instructions.", headers=headers)
        elif "/rate_limit" in url_str:
            return httpx.Response(200, json={"resources": {"core": {"limit": 60, "remaining": 55}}}, headers=headers)

        return httpx.Response(404, text="Not Found", headers=headers)

    mock_transport = httpx.MockTransport(gh_handler)
    mock_gh_client = httpx.AsyncClient(transport=mock_transport)
    discovery = GitHubDiscoveryService(client=mock_gh_client)

    app = create_app()
    app.state.skill_manager = manager
    app.state.github_discovery = discovery

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, manager, discovery


@pytest.mark.asyncio
async def test_api_list_skills(skills_api_client):
    """Verify GET /api/skills lists installed skills."""
    client, _, _ = skills_api_client
    resp = await client.get("/api/skills")
    assert resp.status_code == 200
    skills = resp.json()
    assert len(skills) == 1
    assert skills[0]["id"] == "pytest-pro"
    assert skills[0]["name"] == "Pytest Pro"


@pytest.mark.asyncio
async def test_api_get_skill_detail(skills_api_client):
    """Verify GET /api/skills/{id} returns bundle details."""
    client, _, _ = skills_api_client
    resp = await client.get("/api/skills/pytest-pro")
    assert resp.status_code == 200
    bundle = resp.json()
    assert bundle["manifest"]["id"] == "pytest-pro"
    assert "Always write isolated tests" in bundle["instructions"]

    # 404 for unknown skill
    not_found = await client.get("/api/skills/non-existent")
    assert not_found.status_code == 404


@pytest.mark.asyncio
async def test_api_patch_skill(skills_api_client):
    """Verify PATCH /api/skills/{id} toggles enabled status."""
    client, _, _ = skills_api_client

    # Disable skill
    patch_resp = await client.patch("/api/skills/pytest-pro", json={"is_enabled": False})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["is_enabled"] is False

    # Filter enabled only
    list_resp = await client.get("/api/skills?enabled_only=true")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 0


@pytest.mark.asyncio
async def test_api_delete_skill(skills_api_client):
    """Verify DELETE /api/skills/{id} removes the skill."""
    client, _, _ = skills_api_client
    del_resp = await client.delete("/api/skills/pytest-pro")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"

    # Confirm deletion
    get_resp = await client.get("/api/skills/pytest-pro")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_api_github_rate_limit(skills_api_client):
    """Verify GET /api/skills/discover/rate-limit returns quota info."""
    client, _, _ = skills_api_client
    resp = await client.get("/api/skills/discover/rate-limit")
    assert resp.status_code == 200
    data = resp.json()
    assert data["limit"] == 60
    assert data["remaining"] == 55


@pytest.mark.asyncio
async def test_api_github_search(skills_api_client):
    """Verify GET /api/skills/discover/search returns candidates."""
    client, _, _ = skills_api_client
    resp = await client.get("/api/skills/discover/search?q=test")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["repo"] == "mock-skill-repo"
    assert items[0]["stars"] == 99


@pytest.mark.asyncio
async def test_api_github_preview(skills_api_client):
    """Verify GET /api/skills/discover/preview returns manifest and markdown preview."""
    client, _, _ = skills_api_client
    resp = await client.get("/api/skills/discover/preview?owner=nexora-community&repo=mock-skill-repo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_manifest"] is True
    assert data["has_skill_md"] is True
    assert data["manifest_preview"]["id"] == "mock-skill"
    assert "Remote instructions" in data["skill_md_preview"]


@pytest.mark.asyncio
async def test_api_install_from_github(skills_api_client):
    """Verify POST /api/skills/install with GitHub repo imports and activates skill."""
    client, manager, _ = skills_api_client
    payload = {
        "owner": "nexora-community",
        "repo": "mock-skill-repo",
    }
    install_resp = await client.post("/api/skills/install", json=payload)
    assert install_resp.status_code == 200
    bundle = install_resp.json()
    assert bundle["manifest"]["id"] == "mock-skill"
    assert bundle["is_enabled"] is True
    assert bundle["is_valid"] is True

    # Check that it's now listed in local skills
    list_resp = await client.get("/api/skills")
    ids = [s["id"] for s in list_resp.json()]
    assert "mock-skill" in ids
