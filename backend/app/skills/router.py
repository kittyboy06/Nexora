"""FastAPI Endpoints for Skills Management and GitHub Discovery."""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from backend.app.skills.discovery import (
    GitHubDiscoveryError,
    GitHubDiscoveryService,
    GitHubResourceNotFoundError,
    RateLimitExceededError,
)
from backend.app.skills.manager import SkillManager
from backend.app.skills.models import (
    GitHubRateLimitStatus,
    InstallSkillRequest,
    SkillBundle,
    SkillDiscoveryCandidate,
    SkillPatchRequest,
    SkillProvenance,
    SkillSummary,
)

logger = logging.getLogger("nexora.skills.router")

router = APIRouter(prefix="/skills", tags=["skills"])


def get_skill_manager(request: Request) -> SkillManager:
    """Dependency retrieving the singleton SkillManager from app state."""
    manager = getattr(request.app.state, "skill_manager", None)
    if manager is None:
        manager = SkillManager()
        request.app.state.skill_manager = manager
    return manager


def get_github_discovery(request: Request) -> GitHubDiscoveryService:
    """Dependency retrieving the singleton GitHubDiscoveryService from app state."""
    service = getattr(request.app.state, "github_discovery", None)
    if service is None:
        service = GitHubDiscoveryService()
        request.app.state.github_discovery = service
    return service


@router.get("", response_model=list[SkillSummary])
async def list_skills(
    enabled_only: bool = Query(False, description="Filter for enabled skills only"),
    role: Optional[str] = Query(None, description="Filter for compatible target role"),
    manager: SkillManager = Depends(get_skill_manager),
) -> list[SkillSummary]:
    """List all installed skill bundles (active versions)."""
    return manager.list_skills(enabled_only=enabled_only, role=role)


@router.get("/discover/rate-limit", response_model=GitHubRateLimitStatus)
async def get_github_rate_limit(
    discovery: GitHubDiscoveryService = Depends(get_github_discovery),
) -> GitHubRateLimitStatus:
    """Check remaining GitHub REST API quota."""
    return await discovery.get_rate_limit()


@router.get("/discover/search", response_model=list[SkillDiscoveryCandidate])
async def search_github_skills(
    q: str = Query("", description="Search keywords"),
    page: int = Query(1, ge=1, description="Results page"),
    per_page: int = Query(10, ge=1, le=30, description="Items per page"),
    discovery: GitHubDiscoveryService = Depends(get_github_discovery),
) -> list[SkillDiscoveryCandidate]:
    """Search GitHub for repositories tagged or containing agent skill manifests."""
    try:
        return await discovery.search_repositories(query=q, page=page, per_page=per_page)
    except RateLimitExceededError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except GitHubDiscoveryError as e:
        raise HTTPException(status_code=502, detail=f"GitHub API gateway error: {e}")


@router.get("/discover/preview", response_model=SkillDiscoveryCandidate)
async def preview_github_skill(
    owner: str = Query(..., description="Repository owner"),
    repo: str = Query(..., description="Repository name"),
    branch: str = Query("main", description="Branch ref"),
    path: Optional[str] = Query(None, description="Subdirectory containing manifest and SKILL.md"),
    discovery: GitHubDiscoveryService = Depends(get_github_discovery),
) -> SkillDiscoveryCandidate:
    """Read-only preview of manifest and markdown from a candidate repository."""
    try:
        return await discovery.fetch_skill_preview(
            owner=owner, repo=repo, branch=branch, path=path
        )
    except RateLimitExceededError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except GitHubResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except GitHubDiscoveryError as e:
        raise HTTPException(status_code=502, detail=f"GitHub API gateway error: {e}")


@router.post("/install", response_model=SkillBundle)
async def install_skill(
    req: InstallSkillRequest,
    manager: SkillManager = Depends(get_skill_manager),
    discovery: GitHubDiscoveryService = Depends(get_github_discovery),
) -> SkillBundle:
    """Install a skill from a GitHub repository or direct manifest/markdown definition."""
    manifest = req.manifest
    instructions = req.instructions
    source_url = req.source_url or "local"

    # If GitHub repository specified, fetch candidate files
    if req.owner and req.repo:
        source_url = f"https://github.com/{req.owner}/{req.repo}"
        preview = await discovery.fetch_skill_preview(
            owner=req.owner,
            repo=req.repo,
            branch=req.branch or "main",
            path=req.path,
        )

        if not preview.has_manifest or not preview.manifest_preview:
            raise HTTPException(
                status_code=400,
                detail=f"Repository {req.owner}/{req.repo} does not contain a valid manifest.json",
            )
        if not preview.has_skill_md or not preview.skill_md_preview:
            raise HTTPException(
                status_code=400,
                detail=f"Repository {req.owner}/{req.repo} does not contain a SKILL.md file",
            )

        manifest = preview.manifest_preview
        instructions = preview.skill_md_preview

    if not manifest or not instructions:
        raise HTTPException(
            status_code=400,
            detail="Must provide either valid (owner, repo) or (manifest, instructions)",
        )

    try:
        provenance = SkillProvenance(
            source_url=source_url,
            skill_sha256="",
        )
        return manager.install_bundle(
            manifest=manifest,
            instructions=instructions,
            provenance=provenance,
            set_active=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to install skill bundle: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to install skill: {e}")


@router.get("/{skill_id}", response_model=SkillBundle)
async def get_skill(
    skill_id: str,
    version: Optional[str] = Query(None, description="Specific SemVer or active if omitted"),
    manager: SkillManager = Depends(get_skill_manager),
) -> SkillBundle:
    """Retrieve full skill bundle including instructions markdown and provenance."""
    bundle = manager.get_skill(skill_id=skill_id, version=version)
    if not bundle:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found.")
    return bundle


@router.patch("/{skill_id}", response_model=SkillBundle)
async def patch_skill(
    skill_id: str,
    patch: SkillPatchRequest,
    manager: SkillManager = Depends(get_skill_manager),
) -> SkillBundle:
    """Toggle skill enabled status or switch active version."""
    try:
        bundle = manager.patch_skill(skill_id=skill_id, patch=patch)
        if not bundle:
            raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found.")
        return bundle
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{skill_id}")
async def delete_skill(
    skill_id: str,
    version: Optional[str] = Query(None, description="Specific version to delete or entire skill"),
    manager: SkillManager = Depends(get_skill_manager),
) -> dict:
    """Delete a specific version bundle or the entire skill."""
    deleted = manager.delete_skill(skill_id=skill_id, version=version)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found.")
    return {"status": "deleted", "id": skill_id, "version": version}
